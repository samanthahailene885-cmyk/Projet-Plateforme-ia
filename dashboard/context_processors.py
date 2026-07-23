from django.utils import timezone
from permissions.models import PermissionRequest
from reports.models import DailyReport
from notifications.models import Notification


def sidebar_counts(request):
    """Compteurs pour les badges de la barre latérale (admin uniquement)."""
    if not request.user.is_authenticated or not request.user.is_admin():
        return {}

    today = timezone.now().date()
    return {
        'sidebar_pending_permissions': PermissionRequest.objects.filter(status='pending').count(),
        'sidebar_reports_count': DailyReport.objects.filter(date__gte=today.replace(day=1)).count(),
        'sidebar_unread_messages': Notification.objects.filter(
            user=request.user, is_read=False
        ).count(),
    }
