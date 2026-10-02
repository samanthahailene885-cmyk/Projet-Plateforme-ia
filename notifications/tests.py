from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from notifications.models import Notification

User = get_user_model()


class PatronNotificationPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='amadou',
            password='pass-boss',
            role='admin',
            first_name='Amadou',
            last_name='Diallo',
        )
        Notification.objects.create(
            user=self.admin,
            title='Nouvelle Todo List',
            message='Sophie Kouassi a créé sa Todo List pour aujourd’hui.',
            notification_type='info',
            link='/tasks/todo/',
        )
        Notification.objects.create(
            user=self.admin,
            title='Demande de permission',
            message='Fatou Traoré a envoyé une demande de permission.',
            notification_type='warning',
            link='/permissions/1/',
            is_read=True,
        )

    def test_patron_page_matches_layout(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bonjour, Amadou Diallo')
        self.assertContains(response, 'Responsable de l\'agence')
        self.assertContains(response, 'Résumé des notifications')
        self.assertContains(response, 'Actions rapides')
        self.assertContains(response, 'Restez informé')
        self.assertContains(response, 'Nouvelle Todo List')
        self.assertContains(response, 'Todo Lists')
        self.assertContains(response, 'Non lues')

    def test_filter_demandes(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('notifications:list'), {'filtre': 'demandes'})
        self.assertContains(response, 'Demande de permission')
        self.assertNotContains(response, 'Nouvelle Todo List')

    def test_search(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('notifications:list'), {'q': 'Sophie'})
        self.assertContains(response, 'Nouvelle Todo List')
        self.assertNotContains(response, 'Demande de permission')
