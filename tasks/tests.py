from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from employees.models import Employee
from notifications.models import Notification
from projects.models import Project
from tasks.models import Task, TaskDocument

User = get_user_model()


class TaskAssignmentTests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.admin = User.objects.create_user(
            username='boss-task', password='testpass123', role='admin',
            first_name='Awa', last_name='Diallo',
        )
        self.worker = User.objects.create_user(
            username='nina-task', password='testpass123', role='employee',
            first_name='Nina', last_name='Koné',
        )
        self.other = User.objects.create_user(
            username='moussa-task', password='testpass123', role='employee',
            first_name='Moussa', last_name='Traoré',
        )
        self.employee = Employee.objects.create(
            user=self.worker, position='designer', hire_date=today, status='active',
        )
        self.other_employee = Employee.objects.create(
            user=self.other, position='developer', hire_date=today, status='active',
        )
        self.project = Project.objects.create(
            name='Refonte site client', client='Client', start_date=today,
            end_date=today + timedelta(days=20), status='in_progress',
        )

    def test_admin_assigns_task_and_employee_is_notified(self):
        self.client.login(username='boss-task', password='testpass123')
        response = self.client.post(reverse('tasks:create'), {
            'title': 'Analyse du site actuel',
            'description': 'Repérer les pages à revoir.',
            'project': self.project.pk,
            'assigned_to': self.employee.pk,
            'priority': 'high',
            'status': 'todo',
            'start_date': timezone.localdate().isoformat(),
            'due_date': (timezone.localdate() + timedelta(days=3)).isoformat(),
            'comments': 'Commencer par la page d accueil.',
        })
        task = Task.objects.get(title='Analyse du site actuel')
        self.assertRedirects(response, reverse('tasks:detail', args=[task.pk]))
        self.assertEqual(task.assigned_to, self.employee)
        self.assertEqual(task.created_by, self.admin)
        self.assertTrue(Notification.objects.filter(
            user=self.worker, title__startswith='Nouvelle tâche assignée',
        ).exists())

        self.client.login(username='nina-task', password='testpass123')
        page = self.client.get(reverse('tasks:list'))
        self.assertContains(page, 'Analyse du site actuel')
        self.client.login(username='moussa-task', password='testpass123')
        hidden = self.client.get(reverse('tasks:detail', args=[task.pk]))
        self.assertEqual(hidden.status_code, 302)

    def test_employee_cannot_open_a_private_pdf(self):
        task = Task.objects.create(
            title='Brief', project=self.project, assigned_to=self.employee,
            status='todo', priority='medium', created_by=self.admin,
        )
        document = TaskDocument.objects.create(
            task=task,
            original_name='Brief_client.pdf',
            file=SimpleUploadedFile('Brief_client.pdf', b'%PDF-1.4 test', content_type='application/pdf'),
            file_size=12,
            mime_type='application/pdf',
            uploaded_by=self.admin,
        )
        self.client.login(username='moussa-task', password='testpass123')
        response = self.client.get(reverse('tasks:document', args=[task.pk, document.pk]))
        self.assertEqual(response.status_code, 404)
        self.client.login(username='nina-task', password='testpass123')
        allowed = self.client.get(reverse('tasks:document', args=[task.pk, document.pk]))
        self.assertEqual(allowed.status_code, 200)

    def test_non_pdf_is_rejected(self):
        self.client.login(username='boss-task', password='testpass123')
        response = self.client.post(reverse('tasks:create'), {
            'title': 'Maquette',
            'project': self.project.pk,
            'assigned_to': self.employee.pk,
            'priority': 'medium',
            'status': 'todo',
            'documents': SimpleUploadedFile('notes.txt', b'bonjour', content_type='text/plain'),
        })
        task = Task.objects.get(title='Maquette')
        self.assertRedirects(response, reverse('tasks:detail', args=[task.pk]))
        self.assertEqual(task.documents.count(), 0)
