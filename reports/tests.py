from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from decision_ai.models import AISummary
from decision_ai.services import AIServiceError, DecisionAIService, NoSubmittedReportsError
from employees.models import Employee
from projects.models import Project
from reports.models import DailyReport
from reports.synthesis import (
    collect_team_synthesis,
    compose_team_synthesis,
    synthesis_prompt,
    synthesis_to_html,
)
from tasks.models import Task

User = get_user_model()


class TeamReportTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.admin = User.objects.create_user(
            username='boss-report', password='testpass123', role='admin',
            first_name='Boss', last_name='Agence',
        )
        self.ada = User.objects.create_user(
            username='ada-report', password='testpass123', role='employee',
            first_name='Aminata', last_name='Sangare',
        )
        self.awa = User.objects.create_user(
            username='awa-report', password='testpass123', role='employee',
            first_name='Awa', last_name='Traore',
        )
        self.ada_employee = Employee.objects.create(
            user=self.ada, position='project_manager', hire_date=self.today, status='active',
        )
        Employee.objects.create(
            user=self.awa, position='designer', hire_date=self.today, status='active',
        )
        DailyReport.objects.create(
            employee=self.ada, date=self.today,
            content='■ Visuel de la campagne terminé.', ai_generated=False,
        )
        Task.objects.create(
            title='Montage de la vidéo', project=None, assigned_to=self.ada_employee,
            status='completed', planned_date=self.today,
        )
        self.client.login(username='boss-report', password='testpass123')

    def test_list_button_opens_the_team_report(self):
        response = self.client.get(reverse('reports:list'))
        self.assertContains(response, reverse('reports:generate_day'))
        self.assertContains(response, 'Générer les rapports du jour')

    def test_generate_day_reports_once_for_employees_with_activities(self):
        fatou = User.objects.create_user(
            username='fatou-report', password='testpass123', role='employee',
            first_name='Fatou', last_name='Diarra',
        )
        fatou_employee = Employee.objects.create(
            user=fatou, position='designer', hire_date=self.today, status='active',
        )
        Task.objects.create(
            title='Conception des visuels', assigned_to=fatou_employee,
            status='completed', planned_date=self.today, comments='Validation des visuels en attente.',
        )
        response = self.client.post(reverse('reports:generate_day'), {'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 302)
        created = DailyReport.objects.get(employee=fatou, date=self.today)
        self.assertIn('Fatou Diarra', created.content)
        self.assertIn('Conception des visuels', created.content)
        self.assertIn('Validation des visuels en attente.', created.content)
        self.assertEqual(DailyReport.objects.filter(employee=self.ada, date=self.today).count(), 1)
        self.assertFalse(DailyReport.objects.filter(employee=self.awa, date=self.today).exists())
        again = self.client.post(reverse('reports:generate_day'), {'date': self.today.isoformat()})
        self.assertEqual(again.status_code, 302)
        self.assertEqual(DailyReport.objects.filter(employee=fatou, date=self.today).count(), 1)

    def test_team_report_is_one_document_for_every_employee(self):
        response = self.client.get(reverse('reports:team'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rapport journalier de l')
        self.assertContains(response, 'Aminata Sangare')
        self.assertContains(response, 'Visuel de la campagne terminé')
        self.assertContains(response, 'Awa Traore')
        self.assertContains(response, 'Aucune activité enregistrée')

    def test_employee_cannot_open_the_team_report(self):
        self.client.login(username='awa-report', password='testpass123')
        response = self.client.get(reverse('reports:team'))
        self.assertEqual(response.status_code, 302)


class TeamSynthesisTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.admin = User.objects.create_user(
            username='boss-synth', password='testpass123', role='admin',
            first_name='Boss', last_name='Agence',
        )
        self.aminata = User.objects.create_user(
            username='aminata-synth', password='testpass123', role='employee',
            first_name='Aminata', last_name='Sangaré', gender='F',
        )
        self.awa = User.objects.create_user(
            username='awa-synth', password='testpass123', role='employee',
            first_name='Awa', last_name='Traoré', gender='M',
        )
        self.absent_name = User.objects.create_user(
            username='moussa-synth', password='testpass123', role='employee',
            first_name='Moussa', last_name='Keïta',
        )
        self.aminata_employee = Employee.objects.create(
            user=self.aminata, position='project_manager', department='Création',
            hire_date=self.today, status='active',
        )
        self.awa_employee = Employee.objects.create(
            user=self.awa, position='developer', department='Digital',
            hire_date=self.today, status='active',
        )
        Employee.objects.create(
            user=self.absent_name, position='designer', hire_date=self.today, status='active',
        )
        self.project = Project.objects.create(
            name='Identité visuelle', client='Marenova',
            start_date=self.today, end_date=self.today,
        )
        Task.objects.create(
            title='Mise à jour du planning', project=self.project,
            assigned_to=self.aminata_employee, status='in_progress', planned_date=self.today,
        )
        Task.objects.create(
            title='Correction de la page d accueil', project=self.project,
            assigned_to=self.awa_employee, status='completed', planned_date=self.today,
            comments='Validation du client en attente',
        )
        Task.objects.create(
            title='Tâche non soumise', assigned_to=Employee.objects.get(user=self.absent_name),
            status='completed', planned_date=self.today, comments='Remarque à ignorer',
        )
        DailyReport.objects.create(
            employee=self.aminata, date=self.today,
            content="J'ai poursuivi la mise à jour du planning de livraison.",
            tasks_in_progress='Mise à jour du planning',
            ai_generated=False,
        )
        DailyReport.objects.create(
            employee=self.awa, date=self.today,
            content="J'ai corrigé la page d'accueil.",
            tasks_completed='Correction de la page d accueil',
            ai_generated=False,
        )
        DailyReport.objects.create(
            employee=self.aminata, date=self.today - timedelta(days=1),
            content='Rapport de la veille qui ne doit pas entrer dans la synthèse.',
        )
        self.client.login(username='boss-synth', password='testpass123')

    def test_dossier_uses_only_submitted_reports_for_the_selected_date(self):
        dossier = collect_team_synthesis(self.today)
        self.assertEqual(dossier['submitted'], 2)
        self.assertEqual(dossier['missing'], 1)
        self.assertEqual(dossier['analyzed'], 2)
        self.assertEqual(dossier['completed'], 1)
        self.assertEqual(dossier['in_progress'], 1)
        self.assertEqual(dossier['difficulties'], 1)
        self.assertEqual(dossier['projects'], ['Identité visuelle'])
        prompt = synthesis_prompt(dossier)
        self.assertIn('Mme Aminata Sangaré', prompt)
        self.assertIn("J'ai poursuivi la mise à jour du planning de livraison.", prompt)
        self.assertIn('M. Awa Traoré', prompt)
        self.assertIn('Validation du client en attente', prompt)
        self.assertIn('Identité visuelle', prompt)
        self.assertNotIn('Moussa', prompt)
        self.assertNotIn('Tâche non soumise', prompt)
        self.assertNotIn('Remarque à ignorer', prompt)
        self.assertNotIn('Rapport de la veille', prompt)
        self.assertIn('ne signifie pas', prompt.lower())

    def test_page_shows_backend_counts_and_the_synthesis_button(self):
        response = self.client.get(reverse('reports:list'))
        self.assertContains(response, 'Générer la synthèse IA')
        self.assertContains(response, 'Générer les rapports du jour')
        self.assertContains(response, 'id="stat-submitted">2')
        self.assertContains(response, 'id="stat-missing">1')
        self.assertContains(response, 'id="stat-difficulties">1')
        self.assertContains(response, 'id="stat-completed">1')
        self.assertContains(response, 'id="stat-progress">1')

    def test_synthesis_is_saved_from_the_model_response(self):
        text = (
            "### Synthèse de l'activité de l'équipe\n\n"
            "Aminata a poursuivi le planning.\n\n"
            "### Difficultés signalées\n\n"
            "Validation du client en attente."
        )
        dossier = collect_team_synthesis(self.today)
        with patch.object(DecisionAIService, 'synthesize_submitted_reports', return_value=(text, dossier)):
            response = self.client.post(
                reverse('reports:synthesis'),
                {'date': self.today.isoformat()},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['analyzed'], 2)
        self.assertIn('<h3>Synthèse de l&#x27;activité de l&#x27;équipe</h3>', payload['html'])
        self.assertNotIn('<script', payload['html'])
        saved = AISummary.objects.get(summary_type='team_daily_synthesis', reference_date=self.today)
        self.assertEqual(saved.content, text)
        page = self.client.get(reverse('reports:list'))
        self.assertContains(page, 'Dernière synthèse :')
        self.assertContains(page, 'Aminata a poursuivi le planning.')

    def test_unavailable_model_still_summarizes_the_stored_reports(self):
        with patch.object(
            DecisionAIService,
            '_complete',
            side_effect=AIServiceError("Le compte OpenAI n'a plus de crédit."),
        ):
            response = self.client.post(reverse('reports:synthesis'), {'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        text = payload['synthesis']
        self.assertNotIn('crédit', text.lower())
        self.assertNotIn('OpenAI', text)
        self.assertIn('Mme Aminata Sangaré', text)
        self.assertIn("mise à jour du planning de livraison", text)
        self.assertIn('Validation du client en attente', text)
        self.assertIn('Identité visuelle', text)
        self.assertNotIn('Moussa', text)
        self.assertNotIn('Tâche non soumise', text)
        self.assertIn("### Synthèse de l'activité de l'équipe", text)
        self.assertIn('### Difficultés signalées', text)
        saved = AISummary.objects.get(summary_type='team_daily_synthesis', reference_date=self.today)
        self.assertEqual(saved.content, text)
        direct = compose_team_synthesis(collect_team_synthesis(self.today))
        self.assertEqual(direct, text)

    def test_empty_day_does_not_call_the_model(self):
        other = self.today - timedelta(days=3)
        with patch.object(DecisionAIService, '_complete') as complete:
            with self.assertRaises(NoSubmittedReportsError):
                DecisionAIService().synthesize_submitted_reports(other)
            complete.assert_not_called()
        response = self.client.post(reverse('reports:synthesis'), {'date': other.isoformat()})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Aucun rapport', response.json()['error'])
        self.assertEqual(AISummary.objects.count(), 0)

    def test_model_output_is_escaped(self):
        html = synthesis_to_html('### Titre\n\n<script>alert(1)</script>')
        self.assertIn('<h3>Titre</h3>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)

    def test_employee_cannot_generate_the_synthesis(self):
        self.client.login(username='awa-synth', password='testpass123')
        response = self.client.post(reverse('reports:synthesis'), {'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 302)
