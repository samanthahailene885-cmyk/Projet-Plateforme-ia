from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from authentication.models import User
from employees.models import Employee
from projects.models import Project


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
