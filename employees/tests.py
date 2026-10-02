from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authentication.models import User
from employees.models import Employee


class AdminEmployeePageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='boss',
            password='testpass123',
            first_name='Amadou',
            last_name='Diallo',
            role='admin',
        )
        user = User.objects.create_user(
            username='sophie',
            password='testpass123',
            first_name='Sophie',
            last_name='Kouassi',
            email='sophie@racin.ci',
            role='employee',
        )
        Employee.objects.create(user=user, position='designer', department='Création graphique', hire_date=timezone.now().date(), status='active')
        self.client.force_login(self.admin)

    def test_admin_employee_page_matches_layout(self):
        response = self.client.get(reverse('employees:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Effectif total')
        self.assertContains(response, 'Présents aujourd\'hui')
        self.assertContains(response, 'Todo List du jour')
        self.assertContains(response, 'Vue rapide')
        self.assertContains(response, 'Sophie Kouassi')
        self.assertContains(response, 'Ajouter un employé')


class DemoDataTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='boss-demo', password='testpass123', role='admin',
            first_name='Boss', last_name='Agence',
        )
        self.real = User.objects.create_user(
            username='sophie-reelle', password='testpass123', role='employee',
            first_name='Sophie', last_name='Réelle', email='sophie.reelle@racin.ci',
        )
        Employee.objects.create(
            user=self.real, position='designer', department='Création',
            hire_date=timezone.now().date(), status='active',
        )
        self.client.force_login(self.admin)

    def test_employee_cannot_open_the_generator(self):
        self.client.force_login(self.real)
        response = self.client.get(reverse('employees:demo_data'))
        self.assertEqual(response.status_code, 302)

    def test_generate_and_reset_keep_real_records(self):
        from attendance.models import Attendance
        from decision_ai.analytics import assistant_context
        from projects.models import Project
        from tasks.models import Task

        response = self.client.post(reverse('employees:demo_data'), {
            'action': 'generate',
            'employees': '5',
            'projects': '3',
            'tasks': '20',
            'days': '7',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='sophie-reelle', is_demo=False).exists())
        demo_users = User.objects.filter(is_demo=True, role='employee')
        self.assertEqual(demo_users.count(), 5)
        self.assertEqual(Project.objects.filter(is_demo=True).count(), 3)
        self.assertGreaterEqual(Task.objects.filter(project__is_demo=True).count(), 8)

        today = timezone.localdate()
        active = Employee.objects.filter(user__is_demo=True, status='active')
        missing = [
            employee for employee in active
            if not Task.objects.filter(assigned_to=employee, planned_date=today).exists()
        ]
        self.assertGreaterEqual(len(missing), 2)
        without_absence = [
            employee for employee in missing
            if not Attendance.objects.filter(employee=employee, date=today, status='absent').exists()
        ]
        self.assertTrue(without_absence)
        self.assertTrue(Task.objects.filter(project__is_demo=True).exclude(comments='').exists())

        context = assistant_context("Qui n'a pas renseigné sa Todo List aujourd'hui ?", today)
        self.assertIn("pas une absence", context)
        self.assertIn(without_absence[0].full_name, context)

        reset = self.client.post(reverse('employees:demo_data'), {'action': 'reset', 'confirm': 'oui'})
        self.assertEqual(reset.status_code, 302)
        self.assertEqual(User.objects.filter(is_demo=True).count(), 0)
        self.assertEqual(Project.objects.filter(is_demo=True).count(), 0)
        self.assertTrue(User.objects.filter(username='sophie-reelle').exists())
        self.assertTrue(Employee.objects.filter(user=self.real).exists())
