import os
import runpy
import secrets
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse


TEST_SECRET = secrets.token_urlsafe(64)
SETTINGS_FILE = Path(__file__).resolve().parents[1] / 'config' / 'settings.py'


def load_settings(**environment):
    # Evaluate startup validation independently of the developer's environment.
    values = {
        'DJANGO_SECRET_KEY': TEST_SECRET,
        'DJANGO_ALLOWED_HOSTS': 'testserver',
        **environment,
    }
    with patch.dict(os.environ, values, clear=True):
        return runpy.run_path(str(SETTINGS_FILE))


def production_transport_settings():
    return {
        key: value
        for key, value in load_settings().items()
        if key.startswith(('SECURE_', 'SESSION_COOKIE_', 'CSRF_COOKIE_'))
        or key in {'DEBUG', 'ALLOWED_HOSTS', 'X_FRAME_OPTIONS'}
    }


class ConfigurationSecurityTests(SimpleTestCase):
    def test_missing_or_unsafe_secret_prevents_startup(self):
        for secret in ('', 'short', 'x' * 64, 'django-insecure-' + TEST_SECRET):
            with self.subTest(secret_type=secret[:15]):
                with self.assertRaisesMessage(ImproperlyConfigured, 'DJANGO_SECRET_KEY'):
                    load_settings(DJANGO_SECRET_KEY=secret)

    def test_production_requires_explicit_hosts(self):
        for hosts in ('', '  , ', '*', 'example.com,*', '*.example.com'):
            with self.subTest(hosts=hosts):
                with self.assertRaisesMessage(ImproperlyConfigured, 'DJANGO_ALLOWED_HOSTS'):
                    load_settings(DJANGO_ALLOWED_HOSTS=hosts)

    def test_invalid_debug_value_prevents_startup(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'DJANGO_DEBUG'):
            load_settings(DJANGO_DEBUG='tru')

    def test_default_configuration_disables_debug_and_requires_https(self):
        config = load_settings()

        self.assertFalse(config['DEBUG'])
        self.assertTrue(config['SECURE_SSL_REDIRECT'])
        self.assertTrue(config['SESSION_COOKIE_SECURE'])
        self.assertTrue(config['CSRF_COOKIE_SECURE'])
        self.assertGreater(config['SECURE_HSTS_SECONDS'], 0)
        self.assertEqual(
            config['SILENCED_SYSTEM_CHECKS'], ['security.W005', 'security.W021'],
        )

    def test_local_http_requires_explicit_debug_opt_in(self):
        config = load_settings(DJANGO_DEBUG='true', DJANGO_ALLOWED_HOSTS='')

        self.assertEqual(config['ALLOWED_HOSTS'], ['localhost', '127.0.0.1', '[::1]'])
        self.assertFalse(config['SECURE_SSL_REDIRECT'])
        self.assertFalse(config['SESSION_COOKIE_SECURE'])
        self.assertEqual(config['SECURE_HSTS_SECONDS'], 0)


@override_settings(**production_transport_settings())
class RequestSecurityTests(TestCase):
    def test_http_redirects_to_https(self):
        response = self.client.get(reverse('home'))

        self.assertRedirects(
            response, 'https://testserver/', status_code=301,
            fetch_redirect_response=False,
        )

    def test_forged_forwarding_header_cannot_bypass_https(self):
        response = self.client.get('/', HTTP_X_FORWARDED_PROTO='https')

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://testserver/')

    def test_untrusted_host_is_rejected(self):
        response = self.client.get('/', secure=True, HTTP_HOST='attacker.example')

        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, 'Traceback', status_code=400)

    def test_https_response_has_protective_headers(self):
        response = self.client.get('/', secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        self.assertEqual(response['Strict-Transport-Security'], 'max-age=3600')

    def test_cross_origin_login_is_rejected_even_with_a_valid_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        login_url = reverse('admin:login')
        page = client.get(login_url, secure=True)
        self.assertTrue(page.cookies['csrftoken']['secure'])

        response = client.post(
            login_url,
            {'username': 'staff', 'password': 'test-only-password',
             'csrfmiddlewaretoken': client.cookies['csrftoken'].value},
            secure=True,
            HTTP_ORIGIN='https://attacker.example',
        )

        self.assertEqual(response.status_code, 403)
