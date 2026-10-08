"""Chaîne responsable → employé → base → indicateurs, via l'API JSON."""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from dashboard.metrics import agency_metrics
from employees.models import Employee
from projects.models import Project
from tasks.models import DailyPlan, Task

User = get_user_model()


class WorkFlowTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.admin = User.objects.create_user(
            username='boss-flow', password='testpass123', role='admin', first_name='Amadou', last_name='Mensah',
        )
        self.awa_user = User.objects.create_user(
            username='awa-flow', password='testpass123', role='employee', first_name='Awa', last_name='Traoré',
        )
        self.other_user = User.objects.create_user(
            username='mamadou-flow', password='testpass123', role='employee', first_name='Mamadou', last_name='Koné',
        )
        self.awa = Employee.objects.create(user=self.awa_user, position='designer', hire_date=self.today, status='active')
        self.other = Employee.objects.create(user=self.other_user, position='developer', hire_date=self.today, status='active')

    def test_full_chain_updates_the_database_and_hides_other_employees(self):
        self.client.login(username='boss-flow', password='testpass123')
        created = self.client.post('/api/projets/', data={
            'name': 'Campagne Marenova',
            'client': 'Marenova',
            'description': 'Campagne',
            'start_date': self.today.isoformat(),
            'end_date': self.today.isoformat(),
            'priority': 'high',
            'employees': [self.awa.pk, self.other.pk],
        }, content_type='application/json')
        self.assertEqual(created.status_code, 200, created.content)
        project_id = created.json()['project']['id']

        brief = SimpleUploadedFile('Brief_Marenova.pdf', b'%PDF-1.4 brief', content_type='application/pdf')
        assigned = self.client.post('/api/taches/', data={
            'title': 'Préparer le visuel principal',
            'description': 'Visuel',
            'project': project_id,
            'employee': self.awa.pk,
            'priority': 'high',
            'due_date': self.today.isoformat(),
            'documents': brief,
        })
        self.assertEqual(assigned.status_code, 200, assigned.content)
        task_id = assigned.json()['task']['id']
        document_id = assigned.json()['task']['documents'][0]['id']
        self.assertIn('Awa', assigned.json()['message'])

        self.client.logout()
        self.client.login(username='awa-flow', password='testpass123')
        hidden = self.client.get('/api/taches/')
        titles = [item['title'] for item in hidden.json()['tasks']]
        self.assertIn('Préparer le visuel principal', titles)
        self.client.logout()
        self.client.login(username='mamadou-flow', password='testpass123')
        foreign = self.client.get(f'/api/taches/{task_id}/')
        self.assertEqual(foreign.status_code, 404)
        self.client.logout()
        self.client.login(username='awa-flow', password='testpass123')

        download = self.client.get(f'/api/taches/{task_id}/documents/{document_id}/')
        self.assertEqual(download.status_code, 200)
        started = self.client.post(f'/api/taches/{task_id}/statut/', data={'status': 'in_progress'}, content_type='application/json')
        self.assertEqual(started.json()['task']['status'], 'in_progress')
        self.assertTrue(Task.objects.get(pk=task_id).started_at)

        result = SimpleUploadedFile('Visuel_Marenova_final.pdf', b'%PDF-1.4 final', content_type='application/pdf')
        uploaded = self.client.post(f'/api/taches/{task_id}/resultat/', data={'result': result})
        self.assertEqual(uploaded.status_code, 200, uploaded.content)
        self.assertEqual(Task.objects.get(pk=task_id).status, 'in_progress')

        done = self.client.post(f'/api/taches/{task_id}/statut/', data={'status': 'completed'}, content_type='application/json')
        self.assertEqual(done.json()['task']['status'], 'completed')
        self.assertEqual(Project.objects.get(pk=project_id).progress, 100)

        todo = self.client.post('/api/todos/', data={'title': 'Finaliser le visuel Marenova', 'task': task_id}, content_type='application/json')
        self.assertEqual(todo.status_code, 200, todo.content)
        self.assertTrue(DailyPlan.objects.filter(employee=self.awa, date=self.today).exists())
        activity_id = todo.json()['item']['id']
        self.client.post(f'/api/taches/{activity_id}/statut/', data={'status': 'completed'}, content_type='application/json')

        report = SimpleUploadedFile('Rapport_jour.pdf', b'%PDF-1.4 rapport', content_type='application/pdf')
        sent = self.client.post('/api/rapports/', data={'file': report, 'date': self.today.isoformat()})
        self.assertEqual(sent.status_code, 200, sent.content)

        permission = self.client.post('/api/permissions/', data={
            'start_date': self.today.isoformat(),
            'end_date': self.today.isoformat(),
            'reason': 'personnel',
        }, content_type='application/json')
        self.assertEqual(permission.status_code, 200, permission.content)
        permission_id = permission.json()['permission']['id']

        difficulty = self.client.post('/api/difficultes/', data={
            'project': project_id,
            'description': "Je n'arrive pas à accéder au fichier.",
            'priority': 'high',
        }, content_type='application/json')
        self.assertEqual(difficulty.status_code, 200, difficulty.content)

        self.client.logout()
        self.client.login(username='boss-flow', password='testpass123')
        board = self.client.get(f'/api/rapports/?date={self.today.isoformat()}')
        awa_row = next(item for item in board.json()['reports'] if item['username'] == 'awa-flow')
        self.assertTrue(awa_row['submitted'])
        opened = self.client.get(awa_row['url'])
        self.assertEqual(opened.status_code, 200)

        decision = self.client.post(f'/api/permissions/{permission_id}/', data={'status': 'approved'}, content_type='application/json')
        self.assertEqual(decision.json()['permission']['status'], 'approved')

        metrics = agency_metrics(self.today)
        self.assertEqual(metrics['tasks_completed_today'], Task.objects.filter(completed_at__date=self.today).count())
        self.assertGreaterEqual(metrics['todo_lists_today'], 1)
        self.assertGreaterEqual(metrics['reports_submitted_today'], 1)
        self.assertGreaterEqual(metrics['difficulties_open'], 1)
        self.assertEqual(metrics['employees_active'], 2)
