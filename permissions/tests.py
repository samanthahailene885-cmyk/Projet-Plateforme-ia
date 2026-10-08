from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authentication.models import User
from employees.models import Employee
from permissions.models import PermissionRequest


class EmployeePermissionsPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='emp_perm_test',
            password='testpass123',
            first_name='Zaina',
            last_name='Test',
            role='employee',
        )
        self.employee = Employee.objects.create(
            user=self.user,
            position='developer',
            hire_date=timezone.now().date(),
        )
        self.client.force_login(self.user)

    def test_employee_page_shows_form_and_history(self):
        response = self.client.get(reverse('permissions:list') + '?nouvelle=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mes permissions')
        self.assertContains(response, 'Permissions et absences')
        self.assertContains(response, 'Envoyer la demande')

    def test_employee_can_submit_request(self):
        start = timezone.now().date() + timedelta(days=5)
        end = start + timedelta(days=1)
        response = self.client.post(reverse('permissions:list'), {
            'type': 'permission',
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'reason_choice': 'medical',
            'description': 'Consultation prévue',
            'other_reason': '',
        })
        self.assertEqual(response.status_code, 302)
        req = PermissionRequest.objects.get(employee=self.employee)
        self.assertEqual(req.status, 'pending')
        self.assertEqual(req.reason, 'Rendez-vous médical')
        self.assertEqual(req.description, 'Consultation prévue')
