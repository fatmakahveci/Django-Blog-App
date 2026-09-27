from datetime import timedelta
from xml.etree import ElementTree

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.views.defaults import server_error

from blog.models import Category, Comment, Post, Tag


class BlogViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.writer = get_user_model().objects.create_user(username='writer', first_name='Ada', password=None, email='private@example.com')
        cls.category = Category.objects.create(name='Technology')
        cls.tag = Tag.objects.create(name='Python')
        cls.post = cls.make_post('Public article', body='Unique searchable notebook text. ' * 20, category=cls.category)
        cls.post.tags.add(cls.tag)
        cls.draft = cls.make_post('Secret draft', status=Post.Status.DRAFT)
        cls.future = cls.make_post('Scheduled secret', published_at=timezone.now() + timedelta(days=1))

    @classmethod
    def make_post(cls, title, **kwargs):
        defaults = {'author': cls.writer, 'body': 'A useful article for curious readers. ' * 10, 'status': Post.Status.PUBLISHED, 'published_at': timezone.now() - timedelta(days=2)}
        return Post.objects.create(title=title, **(defaults | kwargs))

    def test_home_is_public_and_hides_unpublished_posts(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, self.post.title)
        self.assertNotContains(response, self.draft.title)
        self.assertNotContains(response, self.future.title)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        self.assertContains(response, '<html lang="en">')

    def test_home_supports_head_requests(self):
        response = self.client.head(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

    def test_unknown_path_returns_not_found(self):
        response = self.client.get("/this-page-does-not-exist/")

        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False)
    def test_missing_page_offers_a_way_back_to_articles(self):
        response = self.client.get('/this-page-does-not-exist/')
        self.assertContains(response, 'Explore articles', status_code=404)
        self.assertTemplateUsed(response, '404.html')

    def test_server_error_page_can_render_without_database_access(self):
        with self.assertNumQueries(0):
            response = server_error(RequestFactory().get('/'))
        self.assertContains(response, 'Please try again in a moment.', status_code=500)

    def test_empty_home_has_useful_message(self):
        Post.objects.all().delete()
        self.assertContains(self.client.get('/'), 'The first page is still being written.')

    def test_drafts_and_scheduled_posts_are_not_directly_accessible(self):
        for post in (self.draft, self.future):
            with self.subTest(post=post.title):
                self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 404)

    def test_scheduled_post_appears_when_publication_time_passes(self):
        Post.objects.filter(pk=self.future.pk).update(published_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(self.future.get_absolute_url()).status_code, 200)

    def test_search_covers_body_and_excludes_drafts(self):
        response = self.client.get('/', {'q': 'searchable notebook'})
        self.assertEqual(list(response.context['page_obj']), [self.post])
        response = self.client.get('/', {'q': 'Secret'})
        self.assertEqual(response.context['page_obj'].paginator.count, 0)

    def test_categories_and_tags_filter_posts(self):
        self.make_post('Other article')
        for url in (self.category.get_absolute_url(), self.tag.get_absolute_url()):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(list(response.context['page_obj']), [self.post])

    def test_nonexistent_category_and_tag_return_404(self):
        for name in ('category', 'tag'):
            self.assertEqual(self.client.get(reverse(name, args=['missing'])).status_code, 404)

    def test_author_page_does_not_expose_email_or_drafts(self):
        response = self.client.get(reverse('author', args=[self.writer.pk]))
        self.assertContains(response, 'Ada')
        self.assertNotContains(response, self.writer.email)
        self.assertEqual(list(response.context['page_obj']), [self.post])

    def test_author_without_public_posts_has_no_public_profile(self):
        user = get_user_model().objects.create_user(username='private-writer', password=None)
        self.assertEqual(self.client.get(reverse('author', args=[user.pk])).status_code, 404)

    def test_featured_article_is_not_duplicated_in_grid(self):
        self.post.featured = True
        self.post.save()
        response = self.client.get('/')
        self.assertEqual(response.context['featured'], self.post)
        self.assertNotIn(self.post, response.context['page_obj'])

    def test_pagination_preserves_search_and_sort(self):
        for index in range(8):
            self.make_post(f'Archive {index}')
        response = self.client.get('/', {'q': 'Archive', 'sort': 'oldest'})
        self.assertEqual(len(response.context['page_obj']), 6)
        self.assertContains(response, 'q=Archive&amp;sort=oldest&amp;page=2')
        second = self.client.get('/', {'q': 'Archive', 'sort': 'oldest', 'page': 2})
        self.assertEqual(len(second.context['page_obj']), 2)
        self.assertFalse(set(response.context['page_obj']) & set(second.context['page_obj']))

    def test_invalid_page_and_sort_do_not_error(self):
        response = self.client.get('/', {'page': 'bad', 'sort': 'invalid'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['sort'], 'newest')

    def test_sorting_by_date_and_approved_comment_count(self):
        newer = self.make_post('Newer post', published_at=timezone.now() - timedelta(hours=1))
        Comment.objects.create(post=self.post, name='Reader', body='A useful approved thought.', approved=True)
        Comment.objects.create(post=newer, name='Pending', body='Hidden discussion must not count.', approved=False)
        for sort, expected in [('newest', [newer, self.post]), ('oldest', [self.post, newer]), ('discussed', [self.post, newer])]:
            with self.subTest(sort=sort):
                self.assertEqual(list(self.client.get('/', {'sort': sort}).context['page_obj']), expected)

    def test_reading_list_returns_only_selected_public_posts(self):
        response = self.client.get(reverse('reading_list'), {'ids': f'{self.post.pk},{self.draft.pk},{self.future.pk},bad,99999999999999999999999'})
        self.assertEqual(list(response.context['page_obj']), [self.post])
        self.assertContains(response, 'noindex,follow')
        self.assertIn('private', response['Cache-Control'])

    def test_article_sharing_metadata_escapes_untrusted_text(self):
        self.post.title = 'A "quoted" title <script>alert(1)</script>'
        self.post.save()
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, '<meta property="og:type" content="article">')
        self.assertContains(response, 'A &quot;quoted&quot; title &lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_related_posts_share_a_topic_and_are_public(self):
        related = self.make_post('Related article', category=self.category)
        self.make_post('Unrelated article')
        self.draft.category = self.category
        self.draft.save()
        response = self.client.get(self.post.get_absolute_url())
        self.assertEqual(list(response.context['related_posts']), [related])

    def test_post_text_and_summary_are_escaped(self):
        self.post.body = '<script>alert("body")</script> This is plain article text.'
        self.post.excerpt = '<img src=x onerror=alert(1)>'
        self.post.save()
        response = self.client.get(self.post.get_absolute_url())
        self.assertNotContains(response, '<script>alert')
        self.assertNotContains(response, '<img src=x')
        self.assertContains(response, '&lt;script&gt;')

    def test_feed_contains_public_posts_only(self):
        response = self.client.get(reverse('rss'))
        self.assertEqual(response.status_code, 200)
        items = ElementTree.fromstring(response.content).findall('./channel/item/title')
        self.assertEqual([item.text for item in items], [self.post.title])

    def test_sitemap_contains_only_public_urls(self):
        response = self.client.get(reverse('sitemap'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.post.get_absolute_url())
        self.assertNotContains(response, self.draft.get_absolute_url())
        self.assertNotContains(response, self.future.get_absolute_url())

    def test_feed_descriptions_cannot_inject_html_into_feed_readers(self):
        self.post.excerpt = '<script>alert(1)</script>'
        self.post.save()
        response = self.client.get(reverse('rss'))
        description = ElementTree.fromstring(response.content).find('./channel/item/description').text
        self.assertEqual(description, '&lt;script&gt;alert(1)&lt;/script&gt;')

    def test_robots_links_to_sitemap_and_excludes_admin(self):
        response = self.client.get(reverse('robots'))
        self.assertContains(response, 'Disallow: /admin/')
        self.assertContains(response, 'Sitemap: http://testserver/sitemap.xml')

    def test_listing_query_count_does_not_grow_per_card(self):
        with CaptureQueriesContext(connection) as single:
            self.client.get('/')
        for index in range(5):
            post = self.make_post(f'Extra {index}', category=self.category)
            post.tags.add(self.tag)
        with CaptureQueriesContext(connection) as multiple:
            self.client.get('/')
        self.assertEqual(len(multiple), len(single))
