from django.utils import timezone
from permissions.models import PermissionRequest
from reports.models import DailyReport
from notifications.models import Notification
from tasks.models import Task


MONTHS = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]
DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']


def _header(user):
    today = timezone.localdate()
    name = (user.get_full_name() or '').strip() or user.username
    initials = (
        f'{(user.first_name[:1] if user.first_name else "")}'
        f'{(user.last_name[:1] if user.last_name else "")}'
    ).upper() or user.username[:2].upper()
    return {
        'header_name': name,
        'header_initials': initials,
        'header_role': 'Responsable' if user.is_admin() else 'Employé',
        'header_date_label': f'{DAYS[today.weekday()]} {today.day} {MONTHS[today.month - 1]} {today.year}',
    }


def sidebar_counts(request):
    """Compteurs pour les badges de la barre latérale."""
    if not request.user.is_authenticated:
        return {}

    unread = Notification.objects.filter(user=request.user, is_read=False).count()
    header = _header(request.user)

    if request.user.is_admin():
        today = timezone.now().date()
        return {
            **header,
            'sidebar_pending_permissions': PermissionRequest.objects.filter(status='pending').count(),
            'sidebar_reports_count': DailyReport.objects.filter(date__gte=today.replace(day=1)).count(),
            'sidebar_unread_messages': unread,
        }

    try:
        employee = request.user.employee_profile
    except Exception:
        return {**header, 'sidebar_unread_messages': unread}

    return {
        **header,
        'sidebar_task_count': Task.objects.filter(
            assigned_to=employee
        ).exclude(status__in=['completed', 'cancelled']).count(),
        'sidebar_pending_permissions': PermissionRequest.objects.filter(
            employee=employee, status='pending'
        ).count(),
        'sidebar_unread_messages': unread,
    }
