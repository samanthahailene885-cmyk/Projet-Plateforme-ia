"""Chaîne données → indicateurs. Aucun chiffre du tableau de bord n'est écrit en dur."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboard.metrics import agency_metrics
from decision_ai.services import AIServiceError, DecisionAIService
from employees.models import Employee
from permissions.models import PermissionRequest
from projects.models import Project
from reports.models import DailyReport
from tasks.models import Difficulty, Task

User = get_user_model()


class DataDrivenChainTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.admin = User.objects.create_user(
            username='boss-chain', password='testpass123', role='admin',
            first_name='Boss', last_name='Agence',
        )
        self.awa_user = User.objects.create_user(
            username='awa-chain', password='testpass123', role='employee',
            first_name='Awa', last_name='Traoré',
        )
        self.other_user = User.objects.create_user(
            username='mamadou-chain', password='testpass123', role='employee',
            first_name='Mamadou', last_name='Koné',
        )
        self.awa = Employee.objects.create(
            user=self.awa_user, position='designer', hire_date=self.today, status='active',
        )
        self.other = Employee.objects.create(
            user=self.other_user, position='developer', hire_date=self.today, status='active',
        )
        self.project = Project.objects.create(
            name='Marenova', client='Marenova', start_date=self.today,
            end_date=self.today + timedelta(days=20), status='in_progress',
        )
        self.project.assigned_employees.add(self.awa)

    def test_01_creating_a_task_stores_it(self):
        self.client.login(username='boss-chain', password='testpass123')
        response = self.client.post(reverse('tasks:create'), {
            'title': 'Préparer le visuel de la campagne Marenova',
            'description': 'Préparer le visuel principal de la campagne.',
            'project': self.project.pk,
            'assigned_to': self.awa.pk,
            'status': 'todo',
            'priority': 'high',
            'due_date': (self.today + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        task = Task.objects.get(title='Préparer le visuel de la campagne Marenova')
        self.assertEqual(task.project_id, self.project.pk)

    def test_02_assigned_task_is_visible_to_the_employee(self):
        task = Task.objects.create(
            title='Visuel Marenova', project=self.project, assigned_to=self.awa,
            status='todo', created_by=self.admin,
        )
        self.client.login(username='awa-chain', password='testpass123')
        response = self.client.get(reverse('tasks:detail', args=[task.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visuel Marenova')
        self.assertTrue(self.awa_user.notifications.filter(link__contains=f'/tasks/{task.pk}').exists())

    def test_03_employee_can_start_a_task(self):
        task = Task.objects.create(
            title='Visuel Marenova', project=self.project, assigned_to=self.awa, status='todo',
        )
        self.client.login(username='awa-chain', password='testpass123')
        self.client.post(reverse('tasks:set_status', args=[task.pk]), {'status': 'in_progress'})
        task.refresh_from_db()
        self.assertEqual(task.status, 'in_progress')
        self.assertIsNotNone(task.started_at)

    def test_04_completing_a_task_records_completed_at(self):
        task = Task.objects.create(
            title='Visuel Marenova', project=self.project, assigned_to=self.awa, status='in_progress',
        )
        self.client.login(username='awa-chain', password='testpass123')
        self.client.post(reverse('tasks:complete', args=[task.pk]), {'next': reverse('tasks:detail', args=[task.pk])})
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(timezone.localtime(task.completed_at).date(), self.today)

    def test_05_completed_counter_increases(self):
        before = agency_metrics(self.today)['tasks_completed_today']
        Task.objects.create(
            title='Visuel terminé', project=self.project, assigned_to=self.awa, status='completed',
        )
        self.assertEqual(agency_metrics(self.today)['tasks_completed_today'], before + 1)

    def test_06_todo_list_counter_increases(self):
        before = agency_metrics(self.today)['todo_lists_today']
        Task.objects.create(
            title='Publication Instagram', assigned_to=self.awa, planned_date=self.today, status='todo',
        )
        self.assertEqual(agency_metrics(self.today)['todo_lists_today'], before + 1)

    def test_07_todo_activity_status_is_updated(self):
        task = Task.objects.create(
            title='Modifier page TIKO', assigned_to=self.awa, planned_date=self.today, status='todo',
        )
        self.client.login(username='awa-chain', password='testpass123')
        self.client.post(reverse('tasks:set_status', args=[task.pk]), {
            'status': 'completed',
            'date': self.today.isoformat(),
        })
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')

    def test_08_and_09_uploaded_report_is_stored_for_the_employee(self):
        uploaded = SimpleUploadedFile('Visuel_Marenova.pdf', b'%PDF-1.4\n(Visuel Marenova termine) Tj\n', content_type='application/pdf')
        self.client.login(username='awa-chain', password='testpass123')
        response = self.client.post(reverse('reports:upload'), {'pdf': uploaded, 'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 302)
        report = DailyReport.objects.get(employee=self.awa_user, date=self.today)
        self.assertTrue(report.uploaded_pdf)
        self.assertEqual(report.original_name, 'Visuel_Marenova.pdf')
        self.assertIn('Visuel Marenova termine', report.content)
        self.assertFalse(report.ai_generated)

    def test_10_manager_can_open_the_report(self):
        report = DailyReport.objects.create(
            employee=self.awa_user, date=self.today, content='Rapport d Awa.', ai_generated=False,
            original_name='awa.pdf',
        )
        self.client.login(username='boss-chain', password='testpass123')
        page = self.client.get(reverse('reports:list') + f'?employee={self.awa.pk}&rapport={report.pk}')
        self.assertContains(page, 'Awa Traoré')
        self.assertContains(page, '✓ Soumis')
        self.assertEqual(self.client.get(reverse('reports:pdf', args=[report.pk])).status_code, 200)

    def test_11_and_12_pending_permissions_follow_the_decision(self):
        before = agency_metrics(self.today)['pending_permissions']
        permission = PermissionRequest.objects.create(
            employee=self.awa, type='permission', start_date=self.today,
            end_date=self.today, reason_choice='personal', reason='Rendez-vous', status='pending',
        )
        self.assertEqual(agency_metrics(self.today)['pending_permissions'], before + 1)
        self.client.login(username='boss-chain', password='testpass123')
        self.client.post(reverse('permissions:approve', args=[permission.pk]), {
            'status': 'approved',
            'admin_comment': 'Accordé',
        })
        permission.refresh_from_db()
        self.assertEqual(permission.status, 'approved')
        self.assertEqual(agency_metrics(self.today)['pending_permissions'], before)

    def test_13_a_difficulty_appears_in_attention(self):
        self.client.login(username='awa-chain', password='testpass123')
        self.client.post(reverse('tasks:difficulty_create'), {
            'project': self.project.pk,
            'priority': 'high',
            'description': "Je n'arrive pas à accéder aux fichiers du client.",
        })
        item = Difficulty.objects.get(employee=self.awa)
        self.assertEqual(item.status, 'open')
        self.client.login(username='boss-chain', password='testpass123')
        page = self.client.get(reverse('dashboard:home'))
        self.assertContains(page, 'id="kpi-difficulties">1')
        detail = self.client.get(reverse('tasks:difficulties'))
        self.assertContains(detail, 'fichiers du client')

    def test_14_overdue_task_is_detected_from_its_status(self):
        Task.objects.create(
            title='Bannière en retard', project=self.project, assigned_to=self.awa,
            status='in_progress', due_date=self.today - timedelta(days=1),
        )
        metrics = agency_metrics(self.today)
        self.assertGreaterEqual(metrics['tasks_overdue'], 1)
        self.assertGreaterEqual(metrics['alerts_active'], 1)

    def test_15_dashboard_numbers_come_from_the_database(self):
        Task.objects.create(
            title='Une tâche', project=self.project, assigned_to=self.awa, status='todo',
        )
        self.client.login(username='boss-chain', password='testpass123')
        response = self.client.get(reverse('dashboard:home'))
        metrics = response.context['metrics']
        self.assertEqual(metrics['employees_active'], Employee.objects.filter(status='active').count())
        self.assertEqual(metrics['projects_total'], Project.objects.exclude(status='cancelled').count())
        self.assertEqual(metrics['tasks_total'], Task.objects.exclude(status='cancelled').count())
        self.assertNotContains(response, '>48<')
        self.assertNotContains(response, '>214<')
        self.assertNotContains(response, '24 projets')

    def test_16_an_employee_cannot_see_another_employees_task(self):
        secret = Task.objects.create(
            title='Dossier privé de Mamadou', project=self.project, assigned_to=self.other, status='todo',
        )
        self.client.login(username='awa-chain', password='testpass123')
        response = self.client.get(reverse('tasks:detail', args=[secret.pk]))
        self.assertEqual(response.status_code, 302)
        answer = self.client.post(reverse('decision_ai:employee_chat'), {
            'question': 'Quelles sont mes tâches en cours ?',
        })
        self.assertNotIn('Dossier privé de Mamadou', answer.json().get('answer', ''))

    def test_17_manager_sees_global_counts(self):
        Task.objects.create(title='Tâche Awa', project=self.project, assigned_to=self.awa, status='todo')
        Task.objects.create(title='Tâche Mamadou', project=self.project, assigned_to=self.other, status='in_progress')
        self.client.login(username='boss-chain', password='testpass123')
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.context['metrics']['tasks_total'], 2)
        self.assertEqual(response.context['metrics']['employees_active'], 2)

    def test_18_synthesis_uses_the_supplied_report_text(self):
        DailyReport.objects.create(
            employee=self.awa_user, date=self.today,
            content='Awa a finalisé le visuel Marenova.', ai_generated=False,
        )

        def fake_complete(system, user_content, max_tokens=900):
            self.assertIn('visuel Marenova', user_content)
            return "### Synthèse\n\nAwa a finalisé le visuel Marenova."

        self.client.login(username='boss-chain', password='testpass123')
        with patch.object(DecisionAIService, '_complete', side_effect=fake_complete):
            response = self.client.post(reverse('reports:synthesis'), {'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertIn('visuel Marenova', response.json()['synthesis'])

    def test_19_synthesis_without_reports_invents_nothing(self):
        self.client.login(username='boss-chain', password='testpass123')
        empty = self.today - timedelta(days=4)
        with patch.object(DecisionAIService, '_complete') as complete:
            response = self.client.post(reverse('reports:synthesis'), {'date': empty.isoformat()})
            complete.assert_not_called()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Aucun rapport disponible pour cette date.')

    def test_20_ai_outage_keeps_the_platform_usable(self):
        DailyReport.objects.create(
            employee=self.awa_user, date=self.today, content='Rapport réel.', ai_generated=False,
        )
        self.client.login(username='boss-chain', password='testpass123')
        with patch.object(DecisionAIService, '_complete', side_effect=AIServiceError('panne')):
            response = self.client.post(reverse('reports:synthesis'), {'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 503)
        self.assertIn('indisponible', response.json()['error'].lower())
        page = self.client.get(reverse('dashboard:home'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="kpi-active">')

    def test_metrics_json_matches_the_database(self):
        Task.objects.create(title='Visible', project=self.project, assigned_to=self.awa, status='todo')
        self.client.login(username='boss-chain', password='testpass123')
        response = self.client.get(reverse('dashboard:metrics_json'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        metrics = agency_metrics(self.today)
        self.assertTrue(payload['authenticated'])
        self.assertEqual(payload['metrics']['employees_active'], metrics['employees_active'])
        self.assertEqual(payload['metrics']['tasks_total'], metrics['tasks_total'])
        self.assertEqual(payload['metrics']['projects_total'], metrics['projects_total'])
        self.assertNotIn('48', response.content.decode())
        anonymous = self.client
        anonymous.logout()
        denied = anonymous.get(reverse('dashboard:metrics_json'))
        self.assertEqual(denied.status_code, 401)

    def test_result_file_does_not_complete_the_task(self):
        task = Task.objects.create(
            title='Visuel Marenova', project=self.project, assigned_to=self.awa, status='in_progress',
        )
        uploaded = SimpleUploadedFile('Visuel_Marenova_final.pdf', b'%PDF-1.4 resultat', content_type='application/pdf')
        self.client.login(username='awa-chain', password='testpass123')
        self.client.post(reverse('tasks:result_upload', args=[task.pk]), {'result': uploaded})
        task.refresh_from_db()
        self.assertEqual(task.status, 'in_progress')
        self.assertIsNone(task.completed_at)
        self.assertEqual(task.result_original_name, 'Visuel_Marenova_final.pdf')

    def test_project_without_tasks_is_not_given_a_fake_progress(self):
        empty = Project.objects.create(
            name='Sans activité', client='Client', start_date=self.today,
            end_date=self.today + timedelta(days=5), status='planning',
        )
        self.assertIsNone(empty.live_progress)
        self.project.tasks.create(title='Faite', assigned_to=self.awa, status='completed')
        self.project.tasks.create(title='Reste', assigned_to=self.awa, status='todo')
        self.assertEqual(self.project.live_progress, 50)
