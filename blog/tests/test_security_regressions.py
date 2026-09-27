from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from blog.models import Category, Poll, PollChoice, PollVote, Post, Reaction, SubmissionQuota, Tag


class PublicSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        author = get_user_model().objects.create_user(username='security-writer')
        cls.post = Post.objects.create(title='Public story', body='A story for security regression tests.',
                                       author=author, status='published')
        poll = Poll.objects.create(post=cls.post, question='What should come next?')
        cls.choice = PollChoice.objects.create(poll=poll, label='Design')
        PollChoice.objects.create(poll=poll, label='Technology')

    def test_cookie_rotation_and_forged_forwarding_headers_cannot_flood_feedback(self):
        react = reverse('react', args=[self.post.slug])
        vote = reverse('vote', args=[self.post.slug])
        for index in range(30):
            url, data = (react, {'kind': 'useful'}) if index % 2 else (vote, {'choice': self.choice.pk})
            response = Client().post(url, data, HTTP_X_FORWARDED_FOR=f'192.0.2.{index}')
            self.assertEqual(response.status_code, 302)
        for url, data in ((react, {'kind': 'inspiring'}), (vote, {'choice': self.choice.pk})):
            response = Client().post(url, data, HTTP_X_FORWARDED_FOR='203.0.113.1')
            self.assertEqual(response.status_code, 429)
            self.assertGreater(int(response['Retry-After']), 0)
            self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(Reaction.objects.count() + PollVote.objects.count(), 30)
        self.assertEqual(Client().post(react, {'kind': 'useful'}, REMOTE_ADDR='192.0.2.2').status_code, 302)

    def test_foreign_origin_feedback_is_rejected_even_with_a_valid_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.get(self.post.get_absolute_url())
        for name, data in (('react', {'kind': 'useful'}), ('vote', {'choice': self.choice.pk})):
            response = client.post(reverse(name, args=[self.post.slug]),
                                   data | {'csrfmiddlewaretoken': client.cookies['csrftoken'].value},
                                   HTTP_ORIGIN='https://attacker.example')
            self.assertEqual(response.status_code, 403)
        self.assertFalse(Reaction.objects.exists())
        self.assertFalse(PollVote.objects.exists())
        self.assertFalse(SubmissionQuota.objects.exists())

    def test_unpublished_taxonomy_does_not_disclose_editorial_metadata(self):
        category = Category.objects.create(name='Confidential launch', description='Unannounced editorial plans.')
        tag = Tag.objects.create(name='Unannounced product')
        draft = Post.objects.create(title='Private story', body='A private story for future readers.',
                                    author=self.post.author, category=category)
        draft.tags.add(tag)
        for url in (category.get_absolute_url(), tag.get_absolute_url()):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)
            self.assertNotContains(response, category.description, status_code=404)
        draft.status = 'published'
        draft.save()
        for url in (category.get_absolute_url(), tag.get_absolute_url()):
            self.assertEqual(self.client.get(url).status_code, 200)
        draft.published_at = timezone.now() + timedelta(days=1)
        draft.save()
        for url in (category.get_absolute_url(), tag.get_absolute_url()):
            self.assertEqual(self.client.get(url).status_code, 404)
