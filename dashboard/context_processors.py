from django.utils import timezone
from permissions.models import PermissionRequest
from reports.models import DailyReport
from notifications.models import Notification
from tasks.models import Task


def sidebar_counts(request):
    """Compteurs pour les badges de la barre latérale."""
    if not request.user.is_authenticated:
        return {}

    unread = Notification.objects.filter(user=request.user, is_read=False).count()

    if request.user.is_admin():
        today = timezone.now().date()
        return {
            'sidebar_pending_permissions': PermissionRequest.objects.filter(status='pending').count(),
            'sidebar_reports_count': DailyReport.objects.filter(date__gte=today.replace(day=1)).count(),
            'sidebar_unread_messages': unread,
        }

    try:
        employee = request.user.employee_profile
    except Exception:
        return {'sidebar_unread_messages': unread}

    return {
        'sidebar_task_count': Task.objects.filter(
            assigned_to=employee
        ).exclude(status__in=['completed', 'cancelled']).count(),
        'sidebar_pending_permissions': PermissionRequest.objects.filter(
            employee=employee, status='pending'
        ).count(),
        'sidebar_unread_messages': unread,
    }
