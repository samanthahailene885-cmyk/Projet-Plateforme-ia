from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from employees.models import Employee
from projects.models import Project
from tasks.models import Task

User = get_user_model()


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.admin = User.objects.create_user(
            username='boss-dash', password='testpass123', role='admin',
            first_name='Awa', last_name='Diallo',
        )
        self.worker = User.objects.create_user(
            username='nina-dash', password='testpass123', role='employee',
            first_name='Nina', last_name='Koné',
        )
        self.employee = Employee.objects.create(
            user=self.worker, position='designer', hire_date=self.today, status='active',
        )
        self.project = Project.objects.create(
            name='Marenova', client='Client', start_date=self.today,
            end_date=self.today + timedelta(days=10), status='in_progress',
        )
        Task.objects.create(
            title='Visuel terminé', project=self.project, assigned_to=self.employee,
            status='completed', planned_date=self.today,
        )
        Task.objects.create(
            title='Maquette en cours', project=self.project, assigned_to=self.employee,
            status='in_progress', planned_date=self.today,
        )
        Task.objects.create(
            title='Bannière en retard', project=self.project, assigned_to=self.employee,
            status='todo', planned_date=self.today, due_date=self.today - timedelta(days=2),
        )
        self.client.login(username='boss-dash', password='testpass123')

    def test_dashboard_uses_recorded_counts(self):
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="kpi-active">1')
        self.assertContains(response, 'id="kpi-total">3')
        self.assertContains(response, 'id="kpi-done">1')
        self.assertContains(response, 'id="kpi-doing">1')
        self.assertContains(response, 'id="kpi-late">1')
        self.assertContains(response, 'Marenova')
        self.assertContains(response, 'Nina Koné')
        self.assertContains(response, 'Visuel terminé')
        self.assertContains(response, 'Activités totales')
        self.assertContains(response, 'Points d\'attention')
        self.assertContains(response, 'activité en retard')
        self.assertNotContains(response, 'Synthèse rapide')
        self.assertNotContains(response, 'État des tâches')
        self.assertNotContains(response, '15 / 18')
        self.assertNotContains(response, 'Amadou Diallo')
        self.assertContains(response, 'Ouvrir l\'assistant')
        self.assertContains(response, reverse('reports:synthesis'))
        self.assertNotContains(response, 'Tâches totales</h3><span class="sup-ico ico-violet"><i class="fas fa-clipboard-list"></i></span></div>\n        <strong id="kpi-total">48')

    def test_employee_cannot_open_the_admin_dashboard(self):
        self.client.login(username='nina-dash', password='testpass123')
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 302)
