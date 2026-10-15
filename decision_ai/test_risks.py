from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from decision_ai.analytics import collect_alerts
from decision_ai.models import OperationalAlert
from decision_ai.risks import risk_board, sync_operational_alerts
from employees.models import Employee
from notifications.models import Notification
from projects.models import Project
from tasks.models import Task

User = get_user_model()


class OperationalRiskTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.admin = User.objects.create_user(
            username='boss', password='pass-boss', role='admin', first_name='Boss', last_name='Agence',
        )
        user = User.objects.create_user(
            username='ada', password='pass-ada', role='employee', first_name='Ada', last_name='Lovelace',
        )
        self.employee = Employee.objects.create(
            user=user, position='designer', hire_date=self.today, status='active',
        )
        self.project = Project.objects.create(
            name='Campagne Tiko', client='Tiko', start_date=self.today - timedelta(days=20),
            end_date=self.today + timedelta(days=10), status='in_progress', progress=40,
        )

    def test_same_overdue_task_updates_one_alert(self):
        task = Task.objects.create(
            title='Bannière', project=self.project, assigned_to=self.employee, status='todo',
            due_date=self.today - timedelta(days=3), priority='high',
        )
        sync_operational_alerts(self.today)
        first = OperationalAlert.objects.get(fingerprint=f'task_late:{task.pk}')
        self.assertEqual(first.status, 'open')
        self.assertGreaterEqual(first.score, 45)
        self.assertIn('3 jour', first.score_detail)
        self.assertEqual(Notification.objects.filter(user=self.admin, link=first.url, title__startswith='Risque opérationnel').count(), 1)

        task.priority = 'urgent'
        task.save(update_fields=['priority'])
        sync_operational_alerts(self.today)
        rows = OperationalAlert.objects.filter(fingerprint=f'task_late:{task.pk}')
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().pk, first.pk)
        self.assertGreater(rows.get().score, first.score)
        self.assertEqual(Notification.objects.filter(user=self.admin, link=first.url, title__startswith='Risque opérationnel').count(), 1)

    def test_resolved_situation_is_not_recreated(self):
        task = Task.objects.create(
            title='Bannière', project=self.project, assigned_to=self.employee, status='todo',
            due_date=self.today - timedelta(days=2),
        )
        sync_operational_alerts(self.today)
        row = OperationalAlert.objects.get(fingerprint=f'task_late:{task.pk}')
        task.status = 'completed'
        task.save(update_fields=['status'])
        sync_operational_alerts(self.today)
        row.refresh_from_db()
        self.assertEqual(row.status, 'resolved')
        self.assertEqual(row.resolved_on, self.today)

        task.status = 'todo'
        task.save(update_fields=['status'])
        sync_operational_alerts(self.today)
        reopened = OperationalAlert.objects.get(fingerprint=f'task_late:{task.pk}')
        self.assertEqual(reopened.pk, row.pk)
        self.assertEqual(reopened.status, 'open')
        self.assertEqual(OperationalAlert.objects.filter(fingerprint=f'task_late:{task.pk}').count(), 1)

    def test_ordinary_upcoming_task_is_not_an_alert(self):
        Task.objects.create(
            title='Relecture', project=self.project, assigned_to=self.employee, status='in_progress',
            due_date=self.today + timedelta(days=1), priority='medium',
        )
        sync_operational_alerts(self.today)
        self.assertFalse(OperationalAlert.objects.filter(kind='task_soon').exists())

    def test_project_ranking_uses_recorded_risks_only(self):
        Task.objects.create(
            title='Visuel', project=self.project, assigned_to=self.employee, status='todo',
            due_date=self.today - timedelta(days=4), priority='urgent',
        )
        Task.objects.create(
            title='Texte', project=self.project, assigned_to=self.employee, status='in_progress',
            due_date=self.today - timedelta(days=1),
        )
        board = risk_board()
        self.assertEqual(board['projects'][0]['name'], 'Campagne Tiko')
        self.assertGreaterEqual(board['open'], 2)
        self.assertGreater(board['high'] + board['medium'] + board['low'], 0)

    def test_center_keeps_the_existing_alert_and_adds_the_score(self):
        Task.objects.create(
            title='Bannière', project=self.project, assigned_to=self.employee, status='todo',
            due_date=self.today - timedelta(days=3),
        )
        alerts = collect_alerts(self.today)
        match = next(alert for alert in alerts if alert['subject'] == 'Bannière' and alert['kind'] == 'Activité')
        self.assertIn('échéance', match['reason'].lower())
        self.assertGreaterEqual(match['risk_score'], 45)
        self.assertIn('jour', match['risk_detail'])
        subjects = [alert['subject'] for alert in alerts if alert['kind'] == 'Activité' and alert['subject'] == 'Bannière']
        self.assertEqual(len(subjects), 1)

    def test_employee_cannot_read_the_alert_center_api(self):
        client = self.client
        client.login(username='ada', password='pass-ada')
        response = client.get('/api/alertes/')
        self.assertEqual(response.status_code, 403)
