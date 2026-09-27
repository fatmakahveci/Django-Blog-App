from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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

    def test_drafts_and_scheduled_posts_have_private_previews(self):
        self.client.force_login(self.editor)
        for status in (Post.Status.DRAFT, Post.Status.PUBLISHED):
            with self.subTest(status=status):
                post = Post.objects.create(title=f'Private {status} article', author=self.editor,
                                           body='Private article text for editorial review.', status=status,
                                           published_at=timezone.now() + timedelta(days=1))
                response = self.client.get(reverse('admin:blog_app_post_preview', args=[post.pk]))
                self.assertContains(response, post.body)
                self.assertContains(response, 'Back to editing')
                self.assertNotContains(response, 'Copy link')
                self.assertNotContains(response, 'Post comment')
                self.assertNotContains(response, 'rel="canonical"')
                self.assertNotContains(response, 'property="og:title"')
                self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
                self.assertIn('no-store', response['Cache-Control'])
                self.assertIn('private', response['Cache-Control'])
                self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 404)

    def test_preview_requires_login_and_article_permission(self):
        post = Post.objects.create(title='Confidential draft', body='Private unpublished draft content.', author=self.editor)
        url = reverse('admin:blog_app_post_preview', args=[post.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.staff.user_permissions.add(Permission.objects.get(codename='view_post', content_type__app_label='blog_app'))
        response = self.client.get(url)
        self.assertContains(response, post.body)
        self.assertContains(response, 'Back to articles')
        self.assertNotContains(response, 'Back to editing')

    def test_preview_missing_post_is_404_and_post_requests_are_rejected(self):
        self.client.force_login(self.editor)
        url = reverse('admin:blog_app_post_preview', args=[123456])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_editor_can_save_preview_and_publish_an_article(self):
        self.client.force_login(self.editor)
        data = {'title': 'My first story', 'body': 'A complete first article written and reviewed by its editor.',
                'author': self.editor.pk, 'status': 'draft', 'cover_style': 'ink',
                'published_at_0': '2020-01-01', 'published_at_1': '12:00:00', '_continue': '1'}
        self.assertEqual(self.client.post(reverse('admin:blog_app_post_add'), data).status_code, 302)
        post = Post.objects.get()
        edit_url = reverse('admin:blog_app_post_change', args=[post.pk])
        editor_page = self.client.get(edit_url)
        self.assertContains(editor_page, 'Preview saved article')
        self.assertNotContains(editor_page, 'View on site')
        self.assertContains(self.client.get(reverse('admin:blog_app_post_preview', args=[post.pk])), data['body'])
        self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.post(edit_url, data | {'status': 'published'}).status_code, 302)
        self.assertContains(self.client.get(edit_url), 'View on site')
        self.client.logout()
        self.assertContains(self.client.get(post.get_absolute_url()), data['body'])
        self.assertContains(self.client.get(reverse('home')), data['title'])

    def test_dashboard_shortcuts_follow_model_permissions(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Write an article')
        self.assertContains(response, 'Review pending comments')
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin:index'))
        self.assertNotContains(response, 'Write an article')
        self.assertNotContains(response, 'Review pending comments')

    def test_public_footer_leads_to_editor_login(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Editor sign in')
        self.assertContains(response, f'href="{reverse("admin:index")}"')

    def test_moderator_can_approve_and_hide_comments(self):
        self.client.force_login(self.editor)
        post = Post.objects.create(title='Moderated post', body='A useful public article.', author=self.editor)
        comment = Comment.objects.create(post=post, name='Reader', body='A pending comment for moderation.')
        url = reverse('admin:blog_app_comment_changelist')
        for action, expected in [('approve', True), ('hide', False)]:
            self.assertEqual(self.client.post(url, {'action': action, '_selected_action': [comment.pk]}).status_code, 302)
            comment.refresh_from_db()
            self.assertEqual(comment.approved, expected)
