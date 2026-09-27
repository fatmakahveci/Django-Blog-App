from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from blog.models import Comment, Post


class EditorialAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = get_user_model().objects.create_superuser(username='editor', password=None)
        cls.staff = get_user_model().objects.create_user(username='staff-reader', password=None, is_staff=True)

    def test_editor_can_create_update_and_delete_a_post(self):
        self.client.force_login(self.editor)
        data = {'title': 'Editorial draft', 'body': 'An article managed through the editor panel.', 'author': self.editor.pk, 'status': 'draft', 'cover_style': 'sage', 'published_at_0': '2026-09-25', 'published_at_1': '12:00:00'}
        response = self.client.post(reverse('admin:blog_app_post_add'), data)
        self.assertEqual(response.status_code, 302)
        post = Post.objects.get()
        self.assertEqual(post.status, 'draft')
        response = self.client.post(reverse('admin:blog_app_post_change', args=[post.pk]), data | {'title': 'Updated draft'})
        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.assertEqual(post.title, 'Updated draft')
        self.assertEqual(self.client.post(reverse('admin:blog_app_post_delete', args=[post.pk]), {'post': 'yes'}).status_code, 302)
        self.assertFalse(Post.objects.exists())

    def test_staff_without_editor_permissions_cannot_create_posts(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('admin:blog_app_post_add')).status_code, 403)

    def test_moderator_can_approve_and_hide_comments(self):
        self.client.force_login(self.editor)
        post = Post.objects.create(title='Moderated post', body='A useful public article.', author=self.editor)
        comment = Comment.objects.create(post=post, name='Reader', body='A pending comment for moderation.')
        url = reverse('admin:blog_app_comment_changelist')
        for action, expected in [('approve', True), ('hide', False)]:
            self.assertEqual(self.client.post(url, {'action': action, '_selected_action': [comment.pk]}).status_code, 302)
            comment.refresh_from_db()
            self.assertEqual(comment.approved, expected)
