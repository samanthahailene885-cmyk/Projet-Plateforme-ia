from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from decision_ai.services import AIServiceError, DecisionAIService, NoSubmittedReportsError
from employees.models import Employee
from reports.models import DailyReport
from reports.synthesis import collect_team_synthesis, compose_team_synthesis, synthesis_prompt

User = get_user_model()


def _report(name, content='', document='', **extra):
    payload = {
        'name': name,
        'content': content,
        'document': document,
        'position': 'Employé',
        'service': 'Création',
        'tasks_completed_note': '',
        'tasks_in_progress_note': '',
        'done': [],
        'doing': [],
        'skipped': [],
        'waiting': [],
        'remarks': [],
        'done_items': [],
        'doing_items': [],
        'skipped_items': [],
        'remark_items': [],
        'has_file': bool(document),
        'filename': '',
        'id': 1,
    }
    payload.update(extra)
    return payload


def _dossier(day, reports, missing=0):
    return {
        'date': day,
        'active': len(reports) + missing,
        'submitted': len(reports),
        'missing': missing,
        'analyzed': len(reports),
        'completed': 0,
        'in_progress': 0,
        'not_done': 0,
        'todo': 0,
        'without_activity': 0,
        'difficulties': 0,
        'projects': [],
        'reports': reports,
    }


class SynthesisReadingTests(TestCase):
    def setUp(self):
        self.day = date(2026, 10, 20)

    def test_free_text_is_not_treated_as_empty_because_status_is_blank(self):
        document = (
            "RAPPORT DE JOURNÉE\n"
            "AVANCEMENT DE LA MAQUETTE CUISINEFACILE\n"
            "OBJECTIF DU JOUR\n"
            "Avancer sur la nouvelle maquette du site CuisineFacile\n"
            "02 — RÉFLEXION SUR LA NOUVELLE PAGE D'ACCUEIL\n"
            "Création d'une réflexion sur la section Hero.\n"
            "Préparation de la structure de la page détail produit.\n"
        )
        text = compose_team_synthesis(_dossier(self.day, [
            _report('Zaina Zaina', document=document),
        ]))
        self.assertIn('CuisineFacile', text)
        self.assertIn('réflexion', text.lower())
        self.assertIn('préparation', text.lower())
        self.assertNotIn('Aucune activité terminée', text)
        self.assertNotIn('aucune activité en cours n’est indiquée', text.lower())
        self.assertIn('Aucun livrable n’est explicitement confirmé', text)

    def test_same_project_is_grouped(self):
        text = compose_team_synthesis(_dossier(self.day, [
            _report('Mme Aminata Sangaré', content="J'ai poursuivi la maquette du projet Campagne."),
            _report('M. Awa Traoré', content="J'ai préparé les visuels du projet Campagne."),
        ]))
        self.assertIn('Campagne', text)
        self.assertIn('Résumé général', text)
        self.assertIn('2. Activités réalisées', text)
        self.assertIn('6. Conclusion et recommandations', text)
        self.assertIn('Mme Aminata Sangaré', text)
        self.assertIn('M. Awa Traoré', text)
        self.assertNotIn('Aucune activité terminée', text)

    def test_different_projects_stay_separate(self):
        text = compose_team_synthesis(_dossier(self.day, [
            _report('Zaina Zaina', content='Réflexion sur la maquette CuisineFacile.'),
            _report('Mariam Bah', content='Préparation de la campagne Marenova.'),
        ]))
        self.assertIn('CuisineFacile', text)
        self.assertIn('Marenova', text)
        self.assertIn('2. Activités réalisées', text)
        self.assertLess(text.find('CuisineFacile'), text.find('Marenova'))

    def test_difficulties_are_separated_from_achievements(self):
        text = compose_team_synthesis(_dossier(self.day, [
            _report(
                'M. Awa Traoré',
                content="Le client bloque la validation du visuel. J'ai préparé la maquette du projet Campagne.",
            ),
        ]))
        self.assertIn('préparation', text.lower())
        self.assertIn('4. Difficultés signalées', text)
        self.assertLess(
            text.lower().find('préparation'),
            text.find('4. Difficultés signalées'),
        )
        self.assertIn('bloque', text.lower())
        self.assertNotIn('Situation des projets', text)
        self.assertNotIn('Actions recommandées', text)

    def test_confirmed_work_and_ongoing_work_are_both_visible(self):
        text = compose_team_synthesis(_dossier(self.day, [
            _report(
                'Mme Aminata Sangaré',
                content="J'ai finalisé la page d'accueil et je poursuis la newsletter du projet Campagne.",
            ),
        ]))
        self.assertIn('2. Activités réalisées', text)
        self.assertIn('3. Activités en cours', text)
        self.assertLess(text.find("page d'accueil"), text.find('3. Activités en cours'))
        self.assertLess(text.find('3. Activités en cours'), text.find('newsletter'))
        self.assertIn("page d'accueil", text)
        self.assertIn('newsletter', text)

    def test_missing_reports_are_not_absences(self):
        text = compose_team_synthesis(_dossier(self.day, [
            _report('Zaina Zaina', content='Préparation de la maquette CuisineFacile.'),
        ], missing=4))
        self.assertIn('CuisineFacile', text)
        self.assertNotIn('Participation aux rapports', text)
        self.assertNotIn('absence', text.lower())

    def test_document_date_and_cited_name_are_flagged(self):
        document = (
            "DATE\n"
            "Lundi 19 mai 2026\n"
            "NOM\n"
            "Abdourahamane\n"
            "Hindoune\n"
            "Réflexion sur la section Hero du site CuisineFacile.\n"
        )
        text = compose_team_synthesis(_dossier(self.day, [
            _report('Zaina Zaina', document=document),
        ]))
        self.assertIn('Zaina Zaina', text)
        self.assertIn('19 mai 2026', text)
        self.assertIn('20 octobre 2026', text)
        self.assertIn('sans modifier les dates', text)
        self.assertNotIn('Actions recommandées', text)
        self.assertNotIn('retard', text.lower())

    def test_many_reports_stay_concise_and_complete(self):
        reports = [
            _report(f'Employé {index}', content=f"Préparation du lot {index} pour le projet Campagne.")
            for index in range(1, 41)
        ]
        dossier = _dossier(self.day, reports)
        text = compose_team_synthesis(dossier)
        prompt = synthesis_prompt(dossier)
        self.assertIn('40 rapports journaliers', text)
        self.assertIn('Résumé général', text)
        self.assertIn('2. Activités réalisées', text)
        self.assertIn('6. Conclusion et recommandations', text)
        self.assertNotIn('Participation aux rapports', text)
        self.assertIn('Employé 1', prompt)
        self.assertIn('Employé 40', prompt)
        self.assertIn('lot 1', text)
        self.assertIn('lot 40', text)
        self.assertNotIn('détail des rapports sources', text)
        self.assertLess(len(text.split('Résumé général')[1].split('2. Activités réalisées')[0]), 1200)
        self.assertNotIn('Aucune activité terminée', text)
        self.assertEqual(prompt.count("Rédige une seule synthèse"), 1)

    def test_empty_day_does_not_invent_a_synthesis(self):
        with patch.object(DecisionAIService, '_complete') as complete:
            with self.assertRaises(NoSubmittedReportsError):
                DecisionAIService().synthesize_submitted_reports(self.day)
            complete.assert_not_called()

    def test_unavailable_model_is_labeled_and_called_once(self):
        admin = User.objects.create_user(
            username='boss-read', password='testpass123', role='admin',
            first_name='Boss', last_name='Agence',
        )
        author = User.objects.create_user(
            username='zaina-read', password='testpass123', role='employee',
            first_name='Zaina', last_name='Zaina', gender='F',
        )
        Employee.objects.create(
            user=author, position='other', department='Création',
            hire_date=self.day, status='active',
        )
        DailyReport.objects.create(
            employee=author, date=timezone.localdate(),
            content='Réflexion sur la maquette CuisineFacile, sans livrable confirmé.',
            ai_generated=False,
        )
        self.client.login(username='boss-read', password='testpass123')
        with patch.object(DecisionAIService, '_complete', side_effect=AIServiceError('panne')) as complete:
            response = self.client.post(reverse('reports:synthesis'), {'date': timezone.localdate().isoformat()})
        complete.assert_called_once()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload['generative'])
        self.assertIn('lecture directe', payload['notice'].lower())
        self.assertIn('CuisineFacile', payload['synthesis'])
        self.assertIn('Zaina Zaina', payload['synthesis'])
        self.assertNotIn('Aucune activité terminée', payload['synthesis'])
        self.assertEqual(admin.username, 'boss-read')

    def test_database_report_without_task_status_keeps_the_written_work(self):
        author = User.objects.create_user(
            username='zaina-db', password='testpass123', role='employee',
            first_name='Zaina', last_name='Zaina',
        )
        Employee.objects.create(
            user=author, position='other', hire_date=self.day, status='active',
        )
        DailyReport.objects.create(
            employee=author, date=self.day,
            content='Préparation de la boutique du site CuisineFacile.',
            ai_generated=False,
        )
        dossier = collect_team_synthesis(self.day)
        text = compose_team_synthesis(dossier)
        self.assertIn('CuisineFacile', text)
        self.assertIn('préparation', text.lower())
        self.assertNotIn('Aucune activité terminée', text)
