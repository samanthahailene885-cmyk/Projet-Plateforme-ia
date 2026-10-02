from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from authentication.models import User
from employees.models import Employee
from projects.models import Project
from tasks.models import Task


class EmployeeProjectListTests(TestCase):
    def setUp(self):
        self.employee_user = User.objects.create_user(
            username='emp_proj',
            password='testpass123',
            role='employee',
            first_name='Zaina',
            last_name='Zaina',
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            position='marketing',
            hire_date=date(2024, 1, 1),
        )
        self.admin = User.objects.create_user(
            username='admin_proj',
            password='testpass123',
            role='admin',
        )
        today = date(2026, 8, 24)
        self.active = Project.objects.create(
            name='Campagne publicitaire JUS MO',
            description='Campagne 360',
            client='Jusmo',
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=5),
            status='in_progress',
            progress=75,
        )
        self.paused = Project.objects.create(
            name='Audit marque',
            description='En pause',
            client='Horizon',
            start_date=today - timedelta(days=40),
            end_date=today + timedelta(days=40),
            status='on_hold',
            progress=40,
        )
        self.done = Project.objects.create(
            name='Brochure annuelle',
            description='Terminee',
            client='Corp',
            start_date=today - timedelta(days=80),
            end_date=today - timedelta(days=5),
            status='completed',
            progress=100,
        )
        other = Project.objects.create(
            name='Projet non assigne',
            description='Invisible',
            client='X',
            start_date=today,
            end_date=today + timedelta(days=10),
            status='in_progress',
            progress=10,
        )
        self.active.assigned_employees.add(self.employee)
        self.paused.assigned_employees.add(self.employee)
        self.done.assigned_employees.add(self.employee)

    def test_employee_sees_only_assigned_projects(self):
        self.client.login(username='emp_proj', password='testpass123')
        response = self.client.get(reverse('projects:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_employee.html')
        self.assertContains(response, 'Mes projets')
        self.assertContains(response, 'Campagne publicitaire JUS MO')
        self.assertNotContains(response, 'Projet non assigne')
        self.assertEqual(response.context['kpi_active'], 1)
        self.assertEqual(response.context['kpi_completed'], 1)
        self.assertEqual(response.context['kpi_on_hold'], 1)

    def test_employee_tab_filters_completed(self):
        self.client.login(username='emp_proj', password='testpass123')
        response = self.client.get(reverse('projects:list'), {'tab': 'completed'})
        self.assertContains(response, 'Brochure annuelle')
        self.assertNotContains(response, 'Campagne publicitaire JUS MO')

    def test_admin_keeps_management_list(self):
        self.client.login(username='admin_proj', password='testpass123')
        response = self.client.get(reverse('projects:list'))
        self.assertTemplateUsed(response, 'projects/project_list.html')
        self.assertContains(response, 'Projet non assigne')


class ProjectProgressFromTasksTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='worker', password='testpass123', role='employee',
            first_name='Awa', last_name='Diallo',
        )
        self.employee = Employee.objects.create(
            user=self.user, position='designer', hire_date=date(2024, 1, 1),
        )
        today = date(2026, 9, 22)
        self.project = Project.objects.create(
            name='Site vitrine',
            client='Client',
            start_date=today,
            end_date=today + timedelta(days=10),
            status='planning',
            progress=0,
        )
        self.project.assigned_employees.add(self.employee)
        self.tasks = [
            Task.objects.create(
                title=f'Tâche {index}',
                project=self.project,
                assigned_to=self.employee,
                planned_date=today,
                status='todo',
            )
            for index in (1, 2)
        ]

    def test_finishing_tasks_updates_project_page(self):
        self.project.refresh_from_db()
        self.assertEqual(self.project.progress, 0)
        self.assertEqual(self.project.status, 'planning')

        self.tasks[0].status = 'completed'
        self.tasks[0].save()
        self.project.refresh_from_db()
        self.assertEqual(self.project.progress, 50)
        self.assertEqual(self.project.status, 'in_progress')

        self.tasks[1].status = 'completed'
        self.tasks[1].save()
        self.project.refresh_from_db()
        self.assertEqual(self.project.progress, 100)
        self.assertEqual(self.project.status, 'completed')

        self.client.login(username='worker', password='testpass123')
        response = self.client.get(reverse('projects:list'))
        self.assertEqual(response.context['kpi_completed'], 1)
        self.assertEqual(response.context['kpi_active'], 0)
        self.assertContains(response, '2/2')


class ProjectDetailPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_detail', password='testpass123', role='admin',
            first_name='Amadou', last_name='Diallo',
        )
        self.lead_user = User.objects.create_user(
            username='lead_detail', password='testpass123', role='employee',
            first_name='Sophie', last_name='Kouassi',
        )
        self.lead = Employee.objects.create(
            user=self.lead_user, position='project_manager', hire_date=date(2024, 1, 1),
        )
        today = date.today()
        self.project = Project.objects.create(
            name='Campagne digitale',
            client='Marenova',
            description='Création et gestion d’une campagne digitale pour la marque Marenova.',
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=15),
            status='in_progress',
            progress=40,
        )
        self.project.assigned_employees.add(self.lead)
        Task.objects.create(
            title='Visuels Instagram', project=self.project, assigned_to=self.lead,
            status='completed', priority='high', due_date=today,
        )
        Task.objects.create(
            title='Calendrier éditorial', project=self.project, assigned_to=self.lead,
            status='in_progress', priority='medium', due_date=today + timedelta(days=2),
            comments='Attente des visuels.',
        )
        Task.objects.create(
            title='Analyse des performances', project=self.project, assigned_to=self.lead,
            status='todo', priority='low', due_date=today - timedelta(days=1),
        )
        Task.objects.create(
            title='Tâche annulée', project=self.project, assigned_to=self.lead,
            status='cancelled', due_date=today,
        )

    def test_detail_page_uses_real_project_data(self):
        self.client.login(username='admin_detail', password='testpass123')
        response = self.client.get(reverse('projects:detail', args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Campagne digitale')
        self.assertContains(response, 'Marenova')
        self.assertContains(response, "Vue d'ensemble")
        self.assertContains(response, 'Sophie Kouassi')
        self.assertContains(response, 'En retard')
        self.assertContains(response, 'Aucun document')
        self.assertNotContains(response, 'Brief de campagne.pdf')
        self.assertNotContains(response, 'Tâche annulée')
        self.assertEqual(len(response.context['task_late']), 1)
        self.assertEqual(len(response.context['task_done']), 1)
        self.assertEqual(len(response.context['task_doing']), 1)
        self.assertEqual(response.context['leader'], self.lead)

    def test_comments_tab_shows_stored_remarks_only(self):
        self.client.login(username='admin_detail', password='testpass123')
        response = self.client.get(reverse('projects:detail', args=[self.project.pk]) + '?onglet=commentaires')
        self.assertContains(response, 'Attente des visuels.')
        self.assertContains(response, 'Calendrier éditorial')
