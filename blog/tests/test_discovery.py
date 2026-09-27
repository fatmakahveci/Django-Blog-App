from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from blog.discovery import bounded_ids
from blog.models import Category, Collection, CollectionEntry, Comment, Post, Reaction


class DiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user(username='writer', password=None)
        cls.topic = Category.objects.create(name='Design')
        cls.other_topic = Category.objects.create(name='Technology')
        cls.short = cls.post('A short discovery', words=600, category=cls.topic)
        cls.medium = cls.post('A medium discovery', words=601, category=cls.other_topic)
        cls.long = cls.post('A long discovery', words=1401, category=cls.topic)
        cls.draft = cls.post('Secret unpublished story', status=Post.Status.DRAFT, category=cls.topic)
        cls.future = cls.post('Secret scheduled story', published_at=timezone.now() + timedelta(days=2), category=cls.topic)

    @classmethod
    def post(cls, title, words=50, **kwargs):
        return Post.objects.create(title=title, body='word ' * words, author=cls.author,
                                   **({'status': Post.Status.PUBLISHED} | kwargs))

    def test_discovery_filters_exact_reading_length_boundaries(self):
        for length, expected in [('short', self.short), ('medium', self.medium), ('long', self.long)]:
            with self.subTest(length=length):
                response = self.client.get(reverse('discover'), {'length': length})
                self.assertEqual(list(response.context['page_obj']), [expected])
                self.assertNotContains(response, self.draft.title)
                self.assertNotContains(response, self.future.title)
        self.assertEqual(self.client.get(reverse('discover'), {'length': 'invalid'}).context['page_obj'].paginator.count, 3)

    def test_search_and_reading_length_work_together(self):
        response = self.client.get(reverse('discover'), {'q': 'medium', 'length': 'medium'})
        self.assertEqual(list(response.context['page_obj']), [self.medium])
        self.assertContains(response, 'value="medium" selected')

    def test_word_count_stays_correct_when_body_is_saved_with_update_fields(self):
        self.short.body = 'one\ntwo\tthree  four'
        self.short.save(update_fields=['body'])
        self.short.refresh_from_db()
        self.assertEqual(self.short.word_count, 4)

    def test_followed_feed_only_includes_public_posts_in_selected_topics(self):
        response = self.client.get(reverse('for_you'), {'topics': str(self.topic.pk)})
        self.assertEqual(set(response.context['page_obj']), {self.short, self.long})
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, 'noindex,follow')
        self.assertContains(self.client.get(reverse('for_you')), 'Make this space yours.')

    def test_browser_id_input_is_bounded_and_deduplicated(self):
        self.assertEqual(bounded_ids('1,1,2,-3,wrong,999999999999999'), [1, 2])
        self.assertEqual(len(bounded_ids(','.join(str(i) for i in range(50)))), 20)

    def test_history_preserves_reader_order_but_excludes_private_posts(self):
        ids = [self.short.pk, self.draft.pk, self.long.pk, self.future.pk, self.medium.pk]
        response = self.client.get(reverse('reading_history'), {'ids': ','.join(map(str, ids)), 'sort': 'oldest'})
        self.assertEqual(list(response.context['page_obj']), [self.short, self.long, self.medium])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, 'noindex,follow')

    def test_trending_counts_only_recent_reactions_and_approved_comments(self):
        for number in range(2):
            Reaction.objects.create(post=self.short, reader_digest=f'reader-{number}', kind='useful')
        for number in range(3):
            Comment.objects.create(post=self.short, name='Reader', body='An approved response.', approved=True)
        for number in range(4):
            Reaction.objects.create(post=self.medium, reader_digest=f'reader-{number}', kind='useful')
        stale = Reaction.objects.create(post=self.long, reader_digest='old', kind='useful')
        Reaction.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(days=8))
        Comment.objects.create(post=self.long, name='Reader', body='A pending response.', approved=False)
        Reaction.objects.create(post=self.draft, reader_digest='secret', kind='useful')
        response = self.client.get(reverse('trending'))
        posts = list(response.context['page_obj'])
        self.assertEqual(posts, [self.short, self.medium])
        self.assertEqual(posts[0].weekly_score, 5)
        self.assertEqual(posts[1].weekly_score, 4)

    def test_trending_empty_state_does_not_invent_popularity(self):
        response = self.client.get(reverse('trending'))
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        self.assertContains(response, 'Start the conversation.')

    def test_surprise_selects_only_public_posts_and_disables_caching(self):
        with patch('blog.discovery.secrets.randbelow', return_value=1):
            response = self.client.get(reverse('surprise'))
        self.assertRedirects(response, self.medium.get_absolute_url())
        self.assertIn('no-store', response['Cache-Control'])
        Post.objects.all().delete()
        self.assertRedirects(self.client.get(reverse('surprise')), reverse('discover'))

    def test_collection_uses_editorial_order_and_hides_unpublished_entries(self):
        collection = Collection.objects.create(name='A reading path', description='A curated introduction.', is_public=True)
        for position, post in enumerate([self.long, self.draft, self.short, self.future, self.medium]):
            CollectionEntry.objects.create(collection=collection, post=post, position=position)
        other = Collection.objects.create(name='Another reading path', description='Different order.', is_public=True)
        CollectionEntry.objects.create(collection=other, post=self.short, position=0)
        CollectionEntry.objects.create(collection=other, post=self.long, position=5)
        response = self.client.get(collection.get_absolute_url())
        self.assertEqual(list(response.context['page_obj']), [self.long, self.short, self.medium])
        self.assertEqual(response.context['collection'].article_count, 3)
        self.assertNotContains(response, self.draft.title)
        self.assertNotContains(response, self.future.title)
        article = self.client.get(self.long.get_absolute_url(), {'collection': collection.slug})
        self.assertEqual(article.context['next_entry'].post, self.short)
        self.assertIsNone(article.context['previous_entry'])
        self.assertNotContains(article, self.draft.title)
        self.assertNotContains(article, self.future.title)

    def test_private_and_empty_collections_are_absent_from_discovery_and_sitemap(self):
        for name, is_public, post in [('Private collection', False, self.short), ('Draft collection', True, self.draft)]:
            collection = Collection.objects.create(name=name, description='Not yet ready.', is_public=is_public)
            CollectionEntry.objects.create(collection=collection, post=post)
            self.assertEqual(self.client.get(collection.get_absolute_url()).status_code, 404)
            for url in (reverse('collections'), reverse('discover'), reverse('sitemap')):
                self.assertNotContains(self.client.get(url), collection.slug)

    def test_collection_paginates_without_changing_order(self):
        collection = Collection.objects.create(name='A longer path', description='A complete reading path.', is_public=True)
        posts = [self.post(f'Chapter {index}') for index in range(13)]
        for index, post in enumerate(posts):
            CollectionEntry.objects.create(collection=collection, post=post, position=index)
        self.assertEqual(list(self.client.get(collection.get_absolute_url()).context['page_obj']), posts[:12])
        self.assertEqual(list(self.client.get(collection.get_absolute_url(), {'page': 2}).context['page_obj']), posts[12:])
