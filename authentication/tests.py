from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class LoginCsrfTests(TestCase):
    def setUp(self):
        User = get_user_model()
        User.objects.create_user(
            username='boss-csrf',
            password='testpass123',
            role='admin',
            first_name='Boss',
        )
        self.client = Client(enforce_csrf_checks=True)

    def test_stale_login_token_returns_to_the_form(self):
        self.client.get('/login/')
        response = self.client.post('/login/', {
            'username': 'boss-csrf',
            'password': 'testpass123',
            'csrfmiddlewaretoken': 'a' * 64,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/?expire=1')
        page = self.client.get(response.url)
        self.assertContains(page, "plus valide")

    def test_current_cookie_secret_logs_the_admin_in(self):
        self.client.get('/login/')
        secret = self.client.cookies['csrftoken'].value
        response = self.client.post('/login/', {
            'username': 'boss-csrf',
            'password': 'testpass123',
            'csrfmiddlewaretoken': secret,
        })
        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)
