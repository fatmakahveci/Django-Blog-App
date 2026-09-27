from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import tempfile
from unittest import TestCase as IsolatedTestCase
from unittest.mock import patch

from django.db import connections
from django.test import RequestFactory, TestCase
from django.utils import timezone

from blog.models import SubmissionQuota
from blog.rate_limits import client_digest, submission_retry_after


class SubmissionQuotaTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().post('/')

    def test_quota_expires_and_scopes_are_independent(self):
        now = timezone.now()
        with patch('blog.rate_limits.timezone.now', return_value=now):
            for _ in range(3):
                self.assertEqual(submission_retry_after(self.request, 'comment', 3), 0)
            self.assertEqual(submission_retry_after(self.request, 'comment', 3), 600)
            self.assertEqual(submission_retry_after(self.request, 'feedback', 30), 0)
        with patch('blog.rate_limits.timezone.now', return_value=now + timedelta(seconds=600)):
            self.assertEqual(submission_retry_after(self.request, 'comment', 3), 0)

    def test_ipv6_spellings_and_mapped_ipv4_cannot_reset_a_quota(self):
        factory = RequestFactory()
        for first, second in (('2001:db8::1', '2001:0db8:0:0:0:0:0:1'), ('192.0.2.1', '::ffff:192.0.2.1')):
            self.assertEqual(client_digest(factory.post('/', REMOTE_ADDR=first), 'feedback'),
                             client_digest(factory.post('/', REMOTE_ADDR=second), 'feedback'))
        self.assertEqual(len(client_digest(self.request, 'feedback')), 64)

    def test_cleanup_is_bounded_and_does_not_remove_active_quotas(self):
        now = timezone.now()
        SubmissionQuota.objects.bulk_create([
            SubmissionQuota(key=f'expired-{index}', expires_at=now - timedelta(seconds=1))
            for index in range(105)
        ])
        SubmissionQuota.objects.create(key='active', expires_at=now + timedelta(minutes=5), used=30)
        submission_retry_after(self.request, 'feedback', 30)
        self.assertEqual(SubmissionQuota.objects.filter(expires_at__lte=now).count(), 5)
        self.assertTrue(SubmissionQuota.objects.filter(key='active', used=30).exists())


class ConcurrentQuotaTests(IsolatedTestCase):
    def test_simultaneous_clients_cannot_exceed_new_or_expired_quota(self):
        # A disposable file database exercises independent worker connections;
        # Django's shared in-memory SQLite test database has different locking.
        alias = 'security_quota_threads'
        with tempfile.TemporaryDirectory() as directory:
            config = deepcopy(connections['default'].settings_dict)
            config.update(ENGINE='django.db.backends.sqlite3', NAME=str(Path(directory) / 'quota.sqlite3'),
                          OPTIONS={'timeout': 20}, ATOMIC_REQUESTS=False)
            connections.databases[alias] = config
            try:
                with connections[alias].schema_editor() as schema:
                    schema.create_model(SubmissionQuota)

                def reserve(_):
                    try:
                        return submission_retry_after(RequestFactory().post('/'), 'comment', 3, using=alias)
                    finally:
                        connections[alias].close()

                for _ in range(2):
                    with ThreadPoolExecutor(max_workers=6) as workers:
                        results = list(workers.map(reserve, range(24)))
                    self.assertEqual(results.count(0), 3)
                    self.assertEqual(SubmissionQuota.objects.using(alias).get().used, 3)
                    SubmissionQuota.objects.using(alias).update(expires_at=timezone.now() - timedelta(seconds=1))
            finally:
                connections[alias].close()
                del connections[alias]
                del connections.databases[alias]
