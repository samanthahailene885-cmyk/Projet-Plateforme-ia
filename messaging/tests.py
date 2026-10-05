from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from notifications.models import Notification

from .models import Message

User = get_user_model()


class MessagingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='boss', password='pass-boss', role='admin',
            first_name='Boss', last_name='Agence',
        )
        self.ada = User.objects.create_user(
            username='ada', password='pass-ada', role='employee',
            first_name='Ada', last_name='Lovelace',
        )
        self.grace = User.objects.create_user(
            username='grace', password='pass-grace', role='employee',
            first_name='Grace', last_name='Hopper',
        )
        self.ada_client = Client()
        self.ada_client.login(username='ada', password='pass-ada')
        self.grace_client = Client()
        self.grace_client.login(username='grace', password='pass-grace')
        self.admin_client = Client()
        self.admin_client.login(username='boss', password='pass-boss')

    def test_employee_message_reaches_only_the_manager(self):
        response = self.ada_client.post(reverse('messaging:inbox'), {
            'avec': self.admin.pk,
            'message': "Bonjour, j'ai un problème avec le projet TIKO.",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Message.objects.count(), 1)
        note = Notification.objects.get(user=self.admin)
        self.assertEqual(note.title, 'Nouveau message de Ada Lovelace')
        page = self.admin_client.get(note.link)
        self.assertContains(page, 'problème avec le projet TIKO')
        self.assertContains(page, 'bubble-wrap theirs')
        self.assertNotContains(page, 'bubble-wrap mine')
        self.admin_client.post(reverse('messaging:inbox'), {
            'avec': self.ada.pk,
            'message': 'Viens dans mon bureau.',
        })
        self.ada_client.get(reverse('messaging:inbox') + f'?avec={self.admin.pk}')
        boss_page = self.admin_client.get(reverse('messaging:inbox') + f'?avec={self.ada.pk}')
        self.assertContains(boss_page, 'bubble-wrap mine')
        self.assertContains(boss_page, 'bubble-wrap theirs')
        self.assertContains(boss_page, 'ticks seen')
        hidden = self.grace_client.get(reverse('messaging:inbox') + f'?avec={self.ada.pk}')
        self.assertNotContains(hidden, 'projet TIKO', status_code=302)
        self.assertFalse(Message.objects.filter(receiver=self.grace).exists())

    def test_manager_reply_notifies_the_employee(self):
        self.admin_client.post(reverse('messaging:inbox'), {
            'avec': self.ada.pk,
            'message': 'Peux-tu passer dans mon bureau ?',
        })
        note = Notification.objects.get(user=self.ada)
        self.assertEqual(note.title, 'Nouveau message du responsable')
        page = self.ada_client.get(note.link)
        self.assertContains(page, 'passer dans mon bureau')
        self.assertNotContains(
            self.grace_client.get(reverse('messaging:inbox')),
            'passer dans mon bureau',
        )

    def test_opening_a_conversation_marks_it_read(self):
        self.ada_client.post(reverse('messaging:inbox'), {
            'avec': self.admin.pk,
            'message': 'Une information importante.',
        })
        home = self.admin_client.get(reverse('dashboard:home'))
        self.assertContains(home, 'Messagerie')
        self.assertContains(home, 'racin-badge')
        self.admin_client.get(reverse('messaging:inbox') + f'?avec={self.ada.pk}')
        self.assertIsNotNone(Message.objects.get().read_at)
        again = self.admin_client.get(reverse('dashboard:home'))
        self.assertEqual(again.context['sidebar_chat_unread'], 0)
        self.assertTrue(Notification.objects.get(user=self.admin).is_read)

    def test_empty_message_is_refused(self):
        response = self.ada_client.post(reverse('messaging:inbox'), {
            'avec': self.admin.pk,
            'message': '   ',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Message.objects.count(), 0)

    def test_employee_can_send_a_pdf(self):
        uploaded = SimpleUploadedFile('brief.pdf', b'%PDF-1.4\n%%EOF', content_type='application/pdf')
        response = self.ada_client.post(reverse('messaging:inbox'), {
            'avec': self.admin.pk,
            'message': '',
            'attachment': uploaded,
        })
        self.assertEqual(response.status_code, 302)
        item = Message.objects.get()
        self.assertTrue(item.attachment)
        download = self.admin_client.get(reverse('messaging:file', args=[item.pk]))
        self.assertEqual(download.status_code, 200)
        blocked = self.grace_client.get(reverse('messaging:file', args=[item.pk]))
        self.assertEqual(blocked.status_code, 302)
