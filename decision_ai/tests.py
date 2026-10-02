from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from decision_ai.analytics import (
    agency_overview,
    assistant_context,
    collect_alerts,
    day_stats,
    employee_report_payload,
    recorded_answer,
    tasks_on_date,
)
from permissions.models import PermissionRequest
from decision_ai.models import AIChat
from decision_ai.services import AIServiceError, DecisionAIService, compose_employee_report
from employees.models import Employee
from reports.models import DailyReport
from tasks.models import Task

User = get_user_model()


class PlatformDataMixin:
    def setUp(self):
        self.today = timezone.now().date()
        self.admin = User.objects.create_user(
            username='boss', password='pass-boss', role='admin',
            first_name='Boss', last_name='Agence',
        )
        self.user = User.objects.create_user(
            username='ada', password='pass-ada', role='employee',
            first_name='Ada', last_name='Lovelace',
        )
        self.other_user = User.objects.create_user(
            username='grace', password='pass-grace', role='employee',
            first_name='Grace', last_name='Hopper',
        )
        self.employee = Employee.objects.create(
            user=self.user, position='designer', hire_date=self.today, status='active',
        )
        self.other = Employee.objects.create(
            user=self.other_user, position='developer', hire_date=self.today, status='active',
        )
        self.client = Client()
        self.client.login(username='ada', password='pass-ada')
        self.admin_client = Client()
        self.admin_client.login(username='boss', password='pass-boss')


class AnalyticsTests(PlatformDataMixin, TestCase):
    def test_day_stats_use_real_statuses(self):
        Task.objects.create(title='Visuel', assigned_to=self.employee, status='completed', planned_date=self.today)
        Task.objects.create(title='Maquette', assigned_to=self.employee, status='in_progress', planned_date=self.today)
        Task.objects.create(
            title='Publication', assigned_to=self.employee, status='not_done',
            planned_date=self.today, comments='Images client absentes',
        )
        Task.objects.create(title='Autre', assigned_to=self.other, status='todo', planned_date=self.today)

        stats = day_stats(self.today)
        self.assertEqual(stats['planned'], 4)
        self.assertEqual(stats['completed'], 1)
        self.assertEqual(stats['in_progress'], 1)
        self.assertEqual(stats['not_done'], 1)
        self.assertEqual(stats['todo'], 1)
        self.assertEqual(len(stats['remarks']), 1)
        self.assertIn('Images client absentes', stats['remarks'][0]['comment'])

    def test_previous_day_is_kept(self):
        yesterday = self.today - timedelta(days=1)
        Task.objects.create(title='Hier', assigned_to=self.employee, planned_date=yesterday, status='todo')
        Task.objects.create(title='Aujourd', assigned_to=self.employee, planned_date=self.today, status='todo')
        self.assertEqual(tasks_on_date(yesterday, self.employee).get().title, 'Hier')
        self.assertEqual(tasks_on_date(self.today, self.employee).get().title, 'Aujourd')

    def test_overdue_alert_is_rule_based(self):
        Task.objects.create(
            title='Bannière',
            assigned_to=self.employee,
            status='todo',
            due_date=self.today - timedelta(days=3),
            planned_date=self.today - timedelta(days=5),
        )
        alerts = collect_alerts(self.today)
        match = next(alert for alert in alerts if alert['subject'] == 'Bannière')
        self.assertIn('échéance', match['reason'].lower())
        self.assertIn('Date limite', match['evidence'])
        self.assertIn('Vérifier', match['suggestion'])

    def test_assistant_receives_counts_already_computed(self):
        Task.objects.create(
            title='Visuel', assigned_to=self.employee, status='completed', planned_date=self.today,
        )
        Task.objects.create(
            title='Bannière', assigned_to=self.other, status='todo',
            due_date=self.today - timedelta(days=2),
            planned_date=self.today - timedelta(days=4),
        )
        context = assistant_context(
            "Combien d'activités ont été terminées aujourd'hui ?",
            self.today,
        )
        self.assertIn('NE PAS LES RECALCULER', context)
        self.assertIn('Terminées : 1', context)
        self.assertIn('Tâches ouvertes en retard', context)
        self.assertIn(': 1', context.split('Tâches ouvertes en retard', 1)[1][:80])
        self.assertIn('Grace Hopper', context)
        self.assertIn("pas une absence", context)
        self.assertNotIn('Images inventées', context)

    def test_permission_answer_names_the_request(self):
        PermissionRequest.objects.create(
            employee=self.employee,
            type='permission',
            start_date=self.today,
            end_date=self.today,
            reason_choice='personal',
            reason='Rendez-vous',
            status='pending',
        )
        answer = recorded_answer("Comment gérer une demande de permission ?", self.today)
        self.assertIn('1 demande de permission est en attente.', answer)
        self.assertIn('Ada Lovelace — Permission', answer)
        self.assertIn('Motif : Raison personnelle', answer)
        self.assertIn('Permissions et absences', answer)
        self.assertNotIn('en attente :\n1.', answer)
        self.assertNotIn('en attente : 1.', answer)


class AccessTests(PlatformDataMixin, TestCase):
    def test_employee_cannot_open_assistant(self):
        response = self.client.get(reverse('decision_ai:assistant'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/tasks/', response.url)

    def test_employee_cannot_query_agency_chat(self):
        response = self.client.post(reverse('decision_ai:chat'), {'question': 'Résume la journée'})
        self.assertEqual(response.status_code, 302)

    def test_employee_cannot_edit_another_activity(self):
        task = Task.objects.create(title='Secrète', assigned_to=self.other, status='todo', planned_date=self.today)
        response = self.client.post(
            reverse('tasks:update', args=[task.pk]),
            {'title': 'Piratée', 'status': 'completed', 'priority': 'low', 'planned_date': self.today.isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, 'Secrète')

    def test_daily_todo_is_limited_to_the_employee(self):
        Task.objects.create(title='Mienne', assigned_to=self.employee, planned_date=self.today, status='todo')
        Task.objects.create(title='Sienne', assigned_to=self.other, planned_date=self.today, status='todo')
        response = self.client.get(reverse('tasks:daily'))
        self.assertContains(response, 'Mienne')
        self.assertNotContains(response, 'Sienne')

    def test_admin_sees_both_on_daily_todo(self):
        Task.objects.create(title='Mienne', assigned_to=self.employee, planned_date=self.today, status='todo')
        Task.objects.create(title='Sienne', assigned_to=self.other, planned_date=self.today, status='todo')
        response = self.admin_client.get(reverse('tasks:daily'))
        self.assertContains(response, 'Todo Lists du jour')
        self.assertContains(response, 'Ada Lovelace')
        self.assertContains(response, 'Grace Hopper')


class AgencyOverviewTests(PlatformDataMixin, TestCase):
    def test_overview_counts_only_recorded_activities(self):
        Task.objects.create(
            title='Visuel', assigned_to=self.employee, status='completed', planned_date=self.today,
        )
        Task.objects.create(
            title='Maquette', assigned_to=self.employee, status='todo', planned_date=self.today,
        )
        overview = agency_overview(self.today)
        self.assertEqual(overview['planned'], 2)
        self.assertEqual(overview['completed'], 1)
        self.assertEqual(overview['not_started'], 1)
        self.assertEqual(overview['todo_filled'], 1)
        self.assertEqual(overview['todo_missing'], 1)

    def test_manager_dashboard_shows_live_indicators(self):
        response = self.admin_client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Todo lists renseignées')
        self.assertNotContains(response, 'Demandes de permissions en attente')
        self.assertNotContains(response, "Centre d'alertes")
        self.assertNotContains(response, 'Activité récente')
        self.assertNotContains(response, 'Taux moyen de réalisation')

    def test_employee_cannot_open_another_profile(self):
        response = self.client.get(reverse('employees:detail', args=[self.other.pk]))
        self.assertEqual(response.status_code, 302)


class ReportTests(PlatformDataMixin, TestCase):
    def test_save_keeps_the_edited_text(self):
        response = self.client.post(reverse('reports:save'), {
            'date': self.today.isoformat(),
            'content': 'Rapport relu par Ada.',
        })
        self.assertEqual(response.status_code, 302)
        report = DailyReport.objects.get(employee=self.user, date=self.today)
        self.assertEqual(report.content, 'Rapport relu par Ada.')
        self.assertFalse(report.ai_generated)

    def test_employee_can_import_a_pdf_for_the_manager(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        uploaded = SimpleUploadedFile(
            'rapport.pdf',
            b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF',
            content_type='application/pdf',
        )
        response = self.client.post(reverse('reports:upload'), {
            'date': self.today.isoformat(),
            'pdf': uploaded,
        })
        self.assertEqual(response.status_code, 302)
        report = DailyReport.objects.get(employee=self.user, date=self.today)
        self.assertFalse(report.ai_generated)
        self.assertTrue(report.uploaded_pdf)
        download = self.client.get(reverse('reports:pdf', args=[report.pk]))
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download['Content-Type'], 'application/pdf')
        payload = b''.join(download.streaming_content)
        self.assertTrue(payload.startswith(b'%PDF'))

    def test_employee_cannot_read_another_report(self):
        report = DailyReport.objects.create(
            employee=self.other_user, date=self.today, content='Confidentiel', ai_generated=False,
        )
        response = self.client.get(reverse('reports:detail', args=[report.pk]))
        self.assertEqual(response.status_code, 302)

    def test_generate_without_activities_does_not_invent_a_report(self):
        response = self.client.post(reverse('reports:generate'), {'date': self.today.isoformat()})
        self.assertEqual(response.status_code, 302)
        followed = self.client.get(response.url)
        self.assertContains(followed, 'Données insuffisantes')
        self.assertEqual(DailyReport.objects.count(), 0)

    @patch('reports.services.DecisionAIService.generate_employee_report', return_value='Texte produit par le modèle.')
    def test_generate_puts_model_text_in_an_editable_draft(self, _mock):
        Task.objects.create(title='Visuel', assigned_to=self.employee, status='completed', planned_date=self.today)
        response = self.client.post(reverse('reports:generate'), {'date': self.today.isoformat()}, follow=True)
        self.assertContains(response, 'Texte produit par le modèle.')
        self.assertEqual(DailyReport.objects.count(), 0)
        save = self.client.post(reverse('reports:save'), {
            'date': self.today.isoformat(),
            'content': 'Texte produit par le modèle.',
        })
        self.assertEqual(save.status_code, 302)
        report = DailyReport.objects.get()
        self.assertTrue(report.ai_generated)
        self.assertEqual(report.content, 'Texte produit par le modèle.')

    def test_composed_report_is_a_bullet_list(self):
        Task.objects.create(
            title='Carte de visite Onemart',
            assigned_to=self.employee,
            status='in_progress',
            planned_date=self.today,
        )
        text = compose_employee_report(employee_report_payload(self.user, self.today))
        self.assertIn('■ Carte de visite Onemart.', text)
        self.assertNotIn('Bilan global', text)

    def test_admin_reads_the_report_on_the_platform(self):
        report = DailyReport.objects.create(
            employee=self.user,
            date=self.today,
            content='■ Visuel terminé.',
            ai_generated=True,
        )
        response = self.admin_client.get(reverse('reports:detail', args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DATE DU JOUR')
        self.assertContains(response, 'LOVELACE')
        self.assertContains(response, 'Visuel terminé')
        self.assertNotContains(response, 'Générer mon rapport')
        listing = self.admin_client.get(reverse('reports:list'))
        self.assertContains(listing, 'Rapports journaliers')
        self.assertContains(listing, 'Ada Lovelace')
        self.assertContains(listing, 'Voir')

    def test_admin_downloads_the_branded_pdf(self):
        report = DailyReport.objects.create(
            employee=self.user,
            date=self.today,
            content=(
                'Résumé des activités réalisées\nVisuel terminé.\n\n'
                'Activités restant à terminer\nMaquette en cours.\n\n'
                'Difficultés signalées\nAucune remarque.\n\n'
                'Bilan global de la journée\nUne activité terminée.'
            ),
            ai_generated=True,
        )
        response = self.admin_client.get(reverse('reports:pdf', args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn(b'RACIN_Rapport_', response['Content-Disposition'].encode())

    def test_another_employee_cannot_download_the_pdf(self):
        report = DailyReport.objects.create(
            employee=self.user, date=self.today, content='Confidentiel', ai_generated=False,
        )
        other = Client()
        other.login(username='grace', password='pass-grace')
        response = other.get(reverse('reports:pdf', args=[report.pk]))
        self.assertEqual(response.status_code, 302)


@override_settings(OPENAI_API_KEY='')
class AIUnavailableTests(PlatformDataMixin, TestCase):
    def test_assistant_reports_missing_configuration(self):
        response = self.admin_client.post(
            reverse('decision_ai:chat'),
            {'question': 'Combien d\'activités ont été terminées cette semaine ?'},
        )
        self.assertEqual(response.status_code, 200)
        answer = response.json()['answer']
        self.assertNotIn('OpenAI', answer)
        self.assertNotIn('crédit', answer.lower())
        self.assertIn('activités prévues', answer)

    def test_missing_credit_still_returns_recorded_absences(self):
        from attendance.models import Attendance
        Attendance.objects.create(employee=self.other, date=self.today, status='absent')
        response = self.admin_client.post(
            reverse('decision_ai:chat'),
            {'question': "Qui est absent aujourd'hui ?"},
        )
        self.assertEqual(response.status_code, 200)
        answer = response.json()['answer']
        self.assertIn('Grace Hopper', answer)
        self.assertNotIn('Ada Lovelace', answer)
        self.assertIn("n'est pas une absence", answer)
        self.assertNotIn('OpenAI', answer)

    def test_empty_remark_is_rejected(self):
        response = self.client.post(reverse('decision_ai:improve_remark'), {'remark': '  '})
        self.assertEqual(response.status_code, 400)

    def test_summary_without_data_does_not_call_the_model(self):
        service = DecisionAIService()
        with patch.object(service, '_complete', side_effect=AssertionError('API appelée')):
            with self.assertRaises(AIServiceError) as caught:
                service.summarize_day(self.today)
        self.assertIn('insuffisantes', str(caught.exception).lower())


class AlertCenterPageTests(PlatformDataMixin, TestCase):
    def test_admin_page_uses_the_alert_center_layout(self):
        Task.objects.create(
            title='Bannière',
            assigned_to=self.employee,
            status='todo',
            due_date=self.today - timedelta(days=3),
            planned_date=self.today - timedelta(days=5),
        )
        response = self.admin_client.get(reverse('decision_ai:delay_detection'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Centre d'alertes")
        self.assertContains(response, 'Liste des alertes')
        self.assertContains(response, 'Marquer tout comme lu')
        self.assertContains(response, 'Répartition des alertes')
        self.assertContains(response, "Besoin d'une information")
        self.assertContains(response, 'Bannière')
        self.assertContains(response, 'Non résolu')
        self.assertContains(response, 'Ada Lovelace')

    def test_filters_and_mark_all_as_read(self):
        Task.objects.create(
            title='Bannière',
            assigned_to=self.employee,
            status='todo',
            due_date=self.today - timedelta(days=3),
            planned_date=self.today - timedelta(days=5),
        )
        critiques = self.admin_client.get(reverse('decision_ai:delay_detection'), {'gravite': 'critique'})
        self.assertContains(critiques, 'Bannière')
        self.assertNotContains(critiques, "Aucune activité n'est enregistrée")

        tasks_only = self.admin_client.get(reverse('decision_ai:delay_detection'), {'type': 'tache'})
        self.assertContains(tasks_only, 'Bannière')
        self.assertNotContains(tasks_only, "Aucune activité n'est enregistrée")

        self.admin_client.post(reverse('decision_ai:delay_detection'), {'action': 'mark_all'})
        resolved = self.admin_client.get(reverse('decision_ai:delay_detection'), {'gravite': 'resolu'})
        self.assertContains(resolved, 'Bannière')
        self.assertContains(resolved, 'ac-status green">Résolu')
        self.assertNotContains(resolved, 'ac-status rose">Non résolu')


class AssistantPageTests(PlatformDataMixin, TestCase):
    def test_admin_assistant_matches_layout(self):
        AIChat.objects.create(
            user=self.admin,
            question='Qui est absent aujourd\'hui ?',
            answer='Aucun employé absent.',
        )
        response = self.admin_client.get(reverse('decision_ai:assistant'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Assistant IA')
        self.assertContains(response, 'Suggestions rapides')
        self.assertContains(response, 'Questions fréquentes')
        self.assertContains(response, 'Nouvelle conversation')
        self.assertContains(response, 'Historique des conversations')
        self.assertContains(response, 'Le saviez-vous')
        self.assertContains(response, 'Utilisation de l\'assistant')
        self.assertContains(response, 'Qui est absent aujourd\'hui ?')
        self.assertContains(response, '100%')
