from urllib.parse import urlencode

from axes.models import AccessAttempt
from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .test_security import production_transport_settings


def admin_login_url(next_url):
    return f"{reverse('admin:login')}?{urlencode({'next': next_url})}"


class AdminAccessTests(SimpleTestCase):
    def test_anonymous_visitors_are_redirected_to_login(self):
        for name in ("admin:index", "admin:auth_user_changelist"):
            with self.subTest(url_name=name):
                url = reverse(name)
                response = self.client.get(url)

                self.assertRedirects(response, admin_login_url(url))

    def test_login_page_renders_form_with_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)

        response = client.get(reverse("admin:login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/login.html")
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_login_without_csrf_token_is_rejected(self):
        # Reject before authentication or any database lookup. The test client
        # skips CSRF checks unless explicitly enabled.
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            reverse("admin:login"),
            {"username": "staff", "password": "test-only-password"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn(SESSION_KEY, response.wsgi_request.session)


# These tests exercise authentication behavior, not password-hashing strength.
# Scope the fast hasher to this class; the application keeps its default hashers.
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AdminAuthenticationTests(TestCase):
    # These credentials exist only in Django's isolated test database.
    password = "test-only-admin-password"

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        # Staff status alone should grant access to the admin index; using a
        # superuser here would hide accidental superuser-only restrictions.
        cls.staff = user_model.objects.create_user(
            username="staff", password=cls.password, is_staff=True
        )
        cls.member = user_model.objects.create_user(
            username="member", password=cls.password, is_staff=False
        )
        cls.inactive_staff = user_model.objects.create_user(
            username="inactive", password=cls.password,
            is_staff=True, is_active=False,
        )

    def test_active_staff_can_log_in_and_open_admin(self):
        response = self.client.post(
            reverse("admin:login"),
            {"username": self.staff.username, "password": self.password,
             "next": reverse("admin:index")},
            follow=True,
        )

        self.assertRedirects(response, reverse("admin:index"))
        self.assertTemplateUsed(response, "admin/index.html")
        self.assertEqual(response.wsgi_request.user.pk, self.staff.pk)

    def test_invalid_or_ineligible_credentials_do_not_create_a_session(self):
        cases = (
            ("wrong password", self.staff.username, "incorrect-password"),
            ("non-staff user", self.member.username, self.password),
            ("inactive staff", self.inactive_staff.username, self.password),
        )
        for scenario, username, password in cases:
            with self.subTest(scenario=scenario):
                # Subtests share the test method's state, so give each scenario
                # a fresh cookie jar and session.
                client = Client()
                response = client.post(
                    reverse("admin:login"),
                    {"username": username, "password": password},
                )

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "admin/login.html")
                self.assertTrue(response.context["form"].non_field_errors())
                # client.session creates a database session if no cookie exists;
                # inspect the request's existing session without writing one.
                self.assertNotIn(SESSION_KEY, response.wsgi_request.session)

    def test_authenticated_non_staff_user_cannot_open_admin(self):
        # Bypass login to test authorization for an already authenticated user.
        self.client.force_login(self.member)
        url = reverse("admin:index")

        response = self.client.get(url)

        self.assertRedirects(response, admin_login_url(url))

    def test_logout_revokes_access_to_admin(self):
        self.client.force_login(self.staff)

        response = self.client.post(reverse("admin:logout"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SESSION_KEY, response.wsgi_request.session)
        url = reverse("admin:index")
        self.assertRedirects(self.client.get(url), admin_login_url(url))

    @override_settings(**production_transport_settings())
    def test_https_login_with_csrf_sets_secure_session_cookie(self):
        client = Client(enforce_csrf_checks=True)
        login_url = reverse('admin:login')
        client.get(login_url, secure=True)

        response = client.post(
            login_url,
            {'username': self.staff.username, 'password': self.password,
             'next': reverse('admin:index'),
             'csrfmiddlewaretoken': client.cookies['csrftoken'].value},
            secure=True,
            HTTP_ORIGIN='https://testserver',
        )

        self.assertRedirects(
            response, reverse('admin:index'), fetch_redirect_response=False,
        )
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie['secure'])
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(client.get(reverse('admin:index'), secure=True).status_code, 200)

    def test_repeated_failures_lock_account_even_when_client_changes_ip(self):
        login_url = reverse('admin:login')
        for attempt in range(settings.AXES_FAILURE_LIMIT):
            # Independent clients prove that clearing cookies or changing IPs
            # does not reset the server-side account failure counter.
            response = Client().post(
                login_url,
                {'username': self.staff.username, 'password': 'wrong-password'},
                REMOTE_ADDR=f'192.0.2.{attempt + 1}',
                HTTP_X_FORWARDED_FOR=f'198.51.100.{attempt + 1}',
            )
            expected = 429 if attempt == settings.AXES_FAILURE_LIMIT - 1 else 200
            self.assertEqual(response.status_code, expected)

        response = Client().post(
            login_url,
            {'username': self.staff.username, 'password': self.password},
            REMOTE_ADDR='203.0.113.1',
        )
        self.assertEqual(response.status_code, 429)
        self.assertNotIn(SESSION_KEY, response.wsgi_request.session)

    def test_lockout_expires_after_cooloff(self):
        login_url = reverse('admin:login')
        for _ in range(settings.AXES_FAILURE_LIMIT):
            response = self.client.post(
                login_url,
                {'username': self.staff.username, 'password': 'wrong-password'},
            )
        self.assertEqual(response.status_code, 429)
        AccessAttempt.objects.filter(username=self.staff.username).update(
            attempt_time=timezone.now() - settings.AXES_COOLOFF_TIME,
        )

        response = self.client.post(
            login_url,
            {'username': self.staff.username, 'password': self.password,
             'next': reverse('admin:index')},
        )

        self.assertRedirects(response, reverse('admin:index'))

    def test_successful_login_resets_failed_attempts(self):
        login_url = reverse('admin:login')
        for _ in range(settings.AXES_FAILURE_LIMIT - 1):
            self.client.post(
                login_url,
                {'username': self.staff.username, 'password': 'wrong-password'},
            )
        response = self.client.post(
            login_url,
            {'username': self.staff.username, 'password': self.password,
             'next': reverse('admin:index')},
        )
        self.assertRedirects(response, reverse('admin:index'))
        self.client.post(reverse('admin:logout'))

        for _ in range(settings.AXES_FAILURE_LIMIT - 1):
            response = self.client.post(
                login_url,
                {'username': self.staff.username, 'password': 'wrong-password'},
            )
            self.assertEqual(response.status_code, 200)

    def test_changing_usernames_and_forwarded_ips_does_not_bypass_ip_limit(self):
        for attempt in range(settings.AXES_FAILURE_LIMIT):
            response = Client().post(
                reverse('admin:login'),
                {'username': f'unknown-{attempt}', 'password': 'wrong-password'},
                REMOTE_ADDR='192.0.2.100',
                HTTP_X_FORWARDED_FOR=f'198.51.100.{attempt + 1}',
            )
        self.assertEqual(response.status_code, 429)

        response = Client().post(
            reverse('admin:login'),
            {'username': self.staff.username, 'password': self.password},
            REMOTE_ADDR='192.0.2.100',
            HTTP_X_FORWARDED_FOR='203.0.113.10',
        )
        self.assertEqual(response.status_code, 429)
        self.assertNotIn(SESSION_KEY, response.wsgi_request.session)
