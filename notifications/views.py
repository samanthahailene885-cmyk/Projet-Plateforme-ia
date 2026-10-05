from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.formats import date_format

from .models import Notification

FILTERS = [
    ('', 'Toutes'),
    ('demandes', 'Demandes'),
    ('todo', 'Todo Lists'),
    ('rapports', 'Rapports'),
    ('activites', 'Activités'),
    ('projets', 'Projets'),
    ('systeme', 'Système'),
]

STYLES = {
    'todo': ('fa-clipboard-list', 'blue', 'Todo Lists'),
    'done': ('fa-check', 'green', 'Activités'),
    'permission': ('fa-exclamation', 'amber', 'Permissions'),
    'report': ('fa-file-alt', 'violet', 'Rapports'),
    'alert': ('fa-exclamation-triangle', 'red', 'Activités'),
    'project': ('fa-folder', 'violet', 'Projets'),
    'employee': ('fa-user', 'green', 'Employés'),
    'system': ('fa-cog', 'blue', 'Système'),
    'info': ('fa-info', 'blue', 'Système'),
}


def _style_for(notification):
    blob = f'{notification.title} {notification.message} {notification.link}'.lower()
    if '/messagerie/' in blob or 'nouveau message' in notification.title.lower():
        return 'systeme', 'info'
    if 'permission' in blob or 'demande' in blob:
        return 'demandes', 'permission'
    if 'rapport' in blob:
        return 'rapports', 'report'
    if 'difficult' in blob or 'retard' in blob and 'projet' not in blob:
        return 'activites', 'alert'
    if 'projet' in blob:
        return 'projets', 'project'
    if 'employé' in blob or 'employe' in blob:
        return 'employes', 'employee'
    if 'maintenance' in blob or 'système' in blob or 'systeme' in blob:
        return 'systeme', 'system'
    if 'todo' in blob:
        return 'todo', 'todo'
    if 'termin' in blob or 'activité' in blob or 'activite' in blob:
        return 'activites', 'done'
    if '/tasks/' in blob:
        return 'activites', 'done' if notification.notification_type == 'success' else 'alert'
    if notification.notification_type == 'success':
        return 'activites', 'done'
    if notification.notification_type == 'warning':
        return 'demandes', 'permission'
    if notification.notification_type == 'danger':
        return 'activites', 'alert'
    return 'systeme', 'info'


def _when_label(created_at):
    local = timezone.localtime(created_at)
    today = timezone.localdate()
    clock = local.strftime('%H:%M')
    if local.date() == today:
        return f"Aujourd'hui à {clock}"
    if local.date() == today - timedelta(days=1):
        return f'Hier à {clock}'
    return f'{date_format(local, "j F")} à {clock}'


@login_required
def notification_list(request):
    """
    Vue de la liste des notifications de l'utilisateur
    """
    all_notifications = Notification.objects.filter(user=request.user)
    now = timezone.localtime()
    today = now.date()
    week_start = today - timedelta(days=today.weekday())

    prepared = []
    for notification in all_notifications:
        category, style_key = _style_for(notification)
        icon, tone, chip = STYLES[style_key]
        notification.category = category
        notification.icon = icon
        notification.tone = tone
        notification.chip = chip
        notification.when = _when_label(notification.created_at)
        prepared.append(notification)

    active_filter = request.GET.get('filtre', '')
    if active_filter not in {key for key, _label in FILTERS}:
        active_filter = ''
    query = (request.GET.get('q') or '').strip()

    visible = prepared
    if active_filter:
        visible = [item for item in visible if item.category == active_filter]
    if query:
        needle = query.lower()
        visible = [
            item for item in visible
            if needle in item.title.lower() or needle in item.message.lower() or needle in item.chip.lower()
        ]

    context = {
        'notifications': visible,
        'unread_count': all_notifications.filter(is_read=False).count(),
        'today_count': all_notifications.filter(created_at__date=today).count(),
        'week_count': all_notifications.filter(created_at__date__gte=week_start).count(),
        'filters': FILTERS,
        'active_filter': active_filter,
        'query': query,
        'today_label': date_format(today, 'l j F Y').capitalize(),
        'initials': (
            f'{(request.user.first_name[:1] if request.user.first_name else "")}'
            f'{(request.user.last_name[:1] if request.user.last_name else "")}'
        ).upper() or request.user.username[:2].upper(),
    }
    return render(request, 'notifications/notification_list.html', context)


@login_required
def mark_as_read(request, pk):
    """
    Vue pour marquer une notification comme lue
    """
    if request.method == 'POST':
        notification = Notification.objects.filter(pk=pk, user=request.user).first()
        if notification:
            notification.is_read = True
            notification.save()
            return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def mark_all_as_read(request):
    """
    Vue pour marquer toutes les notifications comme lues
    """
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def notification_count(request):
    """
    Vue API pour obtenir le nombre de notifications non lues
    """
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})
