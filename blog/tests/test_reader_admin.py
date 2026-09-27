from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from blog.models import Collection, Poll, PollChoice, PollVote, Post


class ReaderEditorialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = get_user_model().objects.create_superuser(username='editor', password=None)
        cls.post = Post.objects.create(title='A story for a collection', body='An article ready for a reading collection.', author=cls.editor)

    def setUp(self):
        self.client.force_login(self.editor)

    def poll_data(self, labels):
        data = {'post': self.post.pk, 'question': 'Which idea would you explore?', 'is_open': 'on',
                'choices-TOTAL_FORMS': len(labels), 'choices-INITIAL_FORMS': 0,
                'choices-MIN_NUM_FORMS': 2, 'choices-MAX_NUM_FORMS': 4}
        for index, label in enumerate(labels):
            data[f'choices-{index}-label'] = label
            data[f'choices-{index}-position'] = index + 1
        return data

    def test_editor_can_create_a_poll_with_two_to_four_distinct_answers(self):
        response = self.client.post(reverse('admin:blog_app_poll_add'), self.poll_data(['Design', 'Technology']))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Poll.objects.get().choices.count(), 2)

    def test_incomplete_duplicate_and_excess_poll_answers_are_rejected(self):
        for labels in (['Design'], ['Design', 'design'], ['A', 'B', 'C', 'D', 'E']):
            with self.subTest(labels=labels):
                response = self.client.post(reverse('admin:blog_app_poll_add'), self.poll_data(labels))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['inline_admin_formsets'][0].formset.non_form_errors())
                self.assertFalse(Poll.objects.exists())

    def test_voted_poll_cannot_have_its_question_or_answers_rewritten(self):
        poll = Poll.objects.create(post=self.post, question='An original question?')
        first = PollChoice.objects.create(poll=poll, label='First original choice')
        second = PollChoice.objects.create(poll=poll, label='Second original choice')
        PollVote.objects.create(poll=poll, choice=first, reader_digest='test-reader')
        data = self.poll_data(['Replacement one', 'Replacement two'])
        data.update({'choices-INITIAL_FORMS': 2, 'choices-0-id': first.pk, 'choices-1-id': second.pk,
                     'choices-0-poll': poll.pk, 'choices-1-poll': poll.pk})
        data.pop('is_open')
        response = self.client.post(reverse('admin:blog_app_poll_change', args=[poll.pk]), data)
        self.assertEqual(response.status_code, 302)
        poll.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual(poll.question, 'An original question?')
        self.assertEqual(first.label, 'First original choice')
        self.assertFalse(poll.is_open)

    def test_editor_can_create_a_collection_and_choose_its_order(self):
        response = self.client.post(reverse('admin:blog_app_collection_add'), {
            'name': 'A new reading path', 'description': 'A thoughtful sequence of articles.', 'is_public': 'on',
            'entries-TOTAL_FORMS': 1, 'entries-INITIAL_FORMS': 0,
            'entries-MIN_NUM_FORMS': 0, 'entries-MAX_NUM_FORMS': 1000,
            'entries-0-post': self.post.pk, 'entries-0-position': 3,
        })
        self.assertEqual(response.status_code, 302)
        collection = Collection.objects.get()
        self.assertTrue(collection.is_public)
        self.assertEqual(collection.entries.get().position, 3)
        # Marking the collection public must not publish its draft article.
        self.assertEqual(self.client.get(collection.get_absolute_url()).status_code, 404)
