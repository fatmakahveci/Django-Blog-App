from django.contrib.auth import get_user_model
from django.test import TestCase

from blog.models import Post


class PostModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user(username='author', password=None)

    def test_slug_collisions_are_resolved_and_title_edits_keep_links(self):
        first = Post.objects.create(title='Same title', body='A plain text article.', author=self.author)
        second = Post.objects.create(title='Same title', body='A plain text article.', author=self.author)
        self.assertNotEqual(first.slug, second.slug)
        original = first.get_absolute_url()
        first.title = 'New title'
        first.save()
        self.assertEqual(first.get_absolute_url(), original)

    def test_reading_time_rounds_up_and_has_a_one_minute_minimum(self):
        for words, minutes in [(0, 1), (200, 1), (201, 2), (600, 3)]:
            with self.subTest(words=words):
                post = Post(body='word ' * words)
                self.assertEqual(post.reading_minutes, minutes)

    def test_excerpt_falls_back_to_a_short_body_summary(self):
        post = Post(body='word ' * 100)
        self.assertLess(len(post.summary), len(post.body))
        post.excerpt = 'Custom introduction.'
        self.assertEqual(post.summary, post.excerpt)
