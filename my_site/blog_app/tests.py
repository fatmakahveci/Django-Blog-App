from django.test import SimpleTestCase
from django.urls import reverse


class HomeViewTests(SimpleTestCase):
    def test_home_returns_expected_greeting(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hello world!")
