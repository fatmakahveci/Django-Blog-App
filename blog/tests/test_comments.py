from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from blog.models import Comment, Post


class CommentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        writer = get_user_model().objects.create_user(username='writer', password=None)
        cls.post = Post.objects.create(title='Public article', body='A useful public article.', author=writer, status=Post.Status.PUBLISHED)

    def setUp(self):
        self.url = reverse('add_comment', args=[self.post.slug])
        self.data = {'name': 'Reader', 'body': 'This is a thoughtful comment.'}

    def test_comment_is_pending_and_cannot_self_approve(self):
        response = self.client.post(self.url, self.data | {'approved': 'on'})
        self.assertRedirects(response, self.post.get_absolute_url() + '#comments')
        comment = Comment.objects.get()
        self.assertFalse(comment.approved)
        self.assertEqual(len(comment.client_digest), 64)
        self.assertNotEqual(comment.client_digest, '127.0.0.1')
        self.assertNotContains(self.client.get(self.post.get_absolute_url()), self.data['body'])

    def test_only_approved_comments_are_visible_and_html_is_escaped(self):
        Comment.objects.create(post=self.post, name='Approved', body='<script>alert(1)</script>', approved=True)
        Comment.objects.create(post=self.post, name='Hidden', body='Unmoderated secret comment.')
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, 'Unmoderated secret comment.')

    def test_large_discussions_are_paginated_without_exposing_pending_comments(self):
        Comment.objects.bulk_create([
            Comment(post=self.post, name=f'Reader {index}', body=f'Approved thought number {index}.', approved=True)
            for index in range(21)
        ])
        Comment.objects.create(post=self.post, name='Pending', body='This must stay private.')
        first = self.client.get(self.post.get_absolute_url())
        self.assertEqual(len(first.context['comments']), 20)
        self.assertEqual(first.context['comment_page'].paginator.count, 21)
        self.assertContains(first, '?comments_page=2#comments')
        second = self.client.get(self.post.get_absolute_url(), {'comments_page': 2})
        self.assertEqual(len(second.context['comments']), 1)
        self.assertFalse(set(first.context['comments']) & set(second.context['comments']))
        self.assertNotContains(second, 'This must stay private.')
        invalid = self.client.get(self.post.get_absolute_url(), {'comments_page': 'invalid'})
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(invalid.context['comment_page'].number, 1)

    def test_invalid_and_honeypot_submissions_are_rejected(self):
        for data in (self.data | {'website': 'https://spam.example'}, self.data | {'body': 'x'}, self.data | {'body': 'x' * 2001}, self.data | {'name': ' '}):
            with self.subTest(data_keys=list(data)):
                self.assertEqual(self.client.post(self.url, data).status_code, 400)
        self.assertEqual(Comment.objects.count(), 0)

    def test_invalid_submission_is_not_cached_and_keeps_form_values(self):
        response = self.client.post(self.url, self.data | {'body': 'Short'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, 'value="Reader"', status_code=400)
        self.assertContains(response, 'Short</textarea>', status_code=400)

    def test_comment_requires_post_and_csrf(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url, self.data).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.get(self.post.get_absolute_url())
        response = client.post(self.url, self.data | {'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)

    def test_comments_on_drafts_are_rejected(self):
        self.post.status = Post.Status.DRAFT
        self.post.save()
        self.assertEqual(self.client.post(self.url, self.data).status_code, 404)
        self.assertFalse(Comment.objects.exists())

    def test_spam_limit_survives_cookie_and_forwarded_ip_changes_and_expires(self):
        for _ in range(3):
            self.assertEqual(Client().post(self.url, self.data).status_code, 302)
        blocked = Client().post(self.url, self.data, HTTP_X_FORWARDED_FOR='192.0.2.9')
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked['Retry-After'], '600')
        self.assertEqual(Comment.objects.count(), 3)
        Comment.objects.update(created_at=timezone.now() - timedelta(minutes=11))
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
