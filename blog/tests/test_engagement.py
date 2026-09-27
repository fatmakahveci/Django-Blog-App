from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from blog.engagement import READER_COOKIE
from blog.models import Poll, PollChoice, PollVote, Post, Reaction


class EngagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user(username='author', password=None)
        cls.post = Post.objects.create(title='A public idea', body='A story worth discussing with other readers.', author=cls.author, status='published')
        cls.poll = Poll.objects.create(post=cls.post, question='What would you like to read next?')
        cls.first = PollChoice.objects.create(poll=cls.poll, label='Design', position=1)
        cls.second = PollChoice.objects.create(poll=cls.poll, label='Technology', position=2)
        cls.react_url = reverse('react', args=[cls.post.slug])
        cls.vote_url = reverse('vote', args=[cls.post.slug])

    def test_reactions_are_idempotent_can_change_and_can_be_removed(self):
        for kind in ('useful', 'useful', 'insightful'):
            response = self.client.post(self.react_url, {'kind': kind})
            self.assertRedirects(response, self.post.get_absolute_url() + '#reactions')
            self.assertEqual(Reaction.objects.count(), 1)
            self.assertEqual(Reaction.objects.get().kind, kind)
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, 'Remove reaction')
        self.assertIn('no-store', response['Cache-Control'])
        self.client.post(self.react_url, {'kind': 'remove'})
        self.assertFalse(Reaction.objects.exists())

    @override_settings(DEBUG=False)
    def test_reader_cookie_is_signed_private_and_secure_for_deployment(self):
        response = self.client.post(self.react_url, {'kind': 'useful'}, secure=True)
        cookie = response.cookies[READER_COOKIE]
        self.assertTrue(cookie['httponly'])
        self.assertTrue(cookie['secure'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertGreater(int(cookie['max-age']), 0)
        digest = Reaction.objects.get().reader_digest
        self.assertNotEqual(digest, cookie.value)
        self.assertNotContains(self.client.get(self.post.get_absolute_url()), digest)

    def test_get_requests_do_not_create_an_identity_or_write_feedback(self):
        response = self.client.get(self.post.get_absolute_url())
        self.assertNotIn(READER_COOKIE, response.cookies)
        self.assertEqual(self.client.get(self.react_url).status_code, 405)
        self.assertEqual(self.client.get(self.vote_url).status_code, 405)
        self.assertFalse(Reaction.objects.exists())
        self.assertFalse(PollVote.objects.exists())

    def test_feedback_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for url, data in ((self.react_url, {'kind': 'useful'}), (self.vote_url, {'choice': self.first.pk})):
            self.assertEqual(client.post(url, data).status_code, 403)
        self.assertFalse(Reaction.objects.exists())
        self.assertFalse(PollVote.objects.exists())

    def test_invalid_reaction_does_not_create_data_or_a_cookie(self):
        response = self.client.post(self.react_url, {'kind': '<script>alert(1)</script>'})
        self.assertContains(response, 'Choose a reaction', status_code=400)
        self.assertNotIn(READER_COOKIE, response.cookies)
        self.assertFalse(Reaction.objects.exists())

    def test_separate_browsers_have_independent_reactions(self):
        self.client.post(self.react_url, {'kind': 'useful'})
        Client().post(self.react_url, {'kind': 'useful'})
        self.assertEqual(Reaction.objects.count(), 2)

    def test_tampered_reader_cookie_cannot_impersonate_an_existing_reader(self):
        self.client.post(self.react_url, {'kind': 'useful'})
        other = Client()
        other.cookies[READER_COOKIE] = self.client.cookies[READER_COOKIE].value + 'invalid'
        other.post(self.react_url, {'kind': 'inspiring'})
        self.assertEqual(Reaction.objects.count(), 2)
        self.assertEqual(Reaction.objects.filter(kind='useful').count(), 1)

    def test_drafts_and_scheduled_posts_reject_feedback(self):
        for values in ({'status': 'draft'}, {'status': 'published', 'published_at': timezone.now() + timedelta(days=2)}):
            Post.objects.filter(pk=self.post.pk).update(**values)
            for url, data in ((self.react_url, {'kind': 'useful'}), (self.vote_url, {'choice': self.first.pk})):
                self.assertEqual(self.client.post(url, data).status_code, 404)
        self.assertFalse(Reaction.objects.exists())
        self.assertFalse(PollVote.objects.exists())

    def test_vote_is_final_and_repeated_submissions_count_once(self):
        self.client.post(self.vote_url, {'choice': self.first.pk})
        response = self.client.post(self.vote_url, {'choice': self.second.pk}, follow=True)
        self.assertContains(response, 'You have already voted')
        self.assertEqual(PollVote.objects.count(), 1)
        self.assertEqual(PollVote.objects.get().choice, self.first)
        self.assertContains(response, 'Your vote')
        self.assertNotContains(response, 'Cast my vote')
        Client().post(self.vote_url, {'choice': self.second.pk})
        response = self.client.get(self.post.get_absolute_url())
        self.assertEqual(response.context['poll_total'], 2)
        self.assertEqual([choice.percent for choice in response.context['poll_options']], [50, 50])

    def test_cross_poll_and_invalid_choice_ids_are_rejected(self):
        post = Post.objects.create(title='Another story', body='Another public story for the reader.', author=self.author, status='published')
        other_poll = Poll.objects.create(post=post, question='Another question?')
        choice = PollChoice.objects.create(poll=other_poll, label='Another answer')
        for value in (choice.pk, 'not-an-id', '9' * 1000, '', '-1'):
            with self.subTest(value=str(value)[:20]):
                self.assertEqual(self.client.post(self.vote_url, {'choice': value}).status_code, 400)
        self.assertFalse(PollVote.objects.exists())

    def test_closed_poll_keeps_results_and_rejects_new_votes(self):
        self.client.post(self.vote_url, {'choice': self.first.pk})
        self.poll.is_open = False
        self.poll.save()
        other = Client()
        response = other.post(self.vote_url, {'choice': self.second.pk})
        self.assertContains(response, 'This poll is closed', status_code=409)
        self.assertEqual(PollVote.objects.count(), 1)
        self.assertContains(other.get(self.post.get_absolute_url()), 'Results · 1 vote')

    def test_incomplete_poll_is_hidden_and_cannot_receive_votes(self):
        self.second.delete()
        self.assertNotContains(self.client.get(self.post.get_absolute_url()), self.poll.question)
        self.assertEqual(self.client.post(self.vote_url, {'choice': self.first.pk}).status_code, 400)
        self.assertFalse(PollVote.objects.exists())
