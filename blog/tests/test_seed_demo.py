from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from blog.models import Post


class DemoContentTests(TestCase):
    def test_seeding_is_repeatable_and_preserves_edited_content(self):
        call_command('seed_demo', stdout=StringIO())
        self.assertEqual(Post.objects.published().count(), 8)
        post = Post.objects.first()
        post.title = 'An editor changed this title'
        post.save()
        call_command('seed_demo', stdout=StringIO())
        self.assertEqual(Post.objects.count(), 8)
        post.refresh_from_db()
        self.assertEqual(post.title, 'An editor changed this title')
        author = get_user_model().objects.get(username='folio-demo')
        self.assertFalse(author.is_active)
        self.assertFalse(author.is_staff)
        self.assertFalse(author.has_usable_password())
