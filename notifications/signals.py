from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

from permissions.models import PermissionRequest
from reports.models import DailyReport
from tasks.models import Task


def _notify_admins(title, message, notification_type, link):
    from authentication.models import User
    from notifications.models import Notification

    today = timezone.now().date()
    for admin in User.objects.filter(role='admin'):
        already = Notification.objects.filter(
            user=admin,
            link=link,
            title=title,
            created_at__date=today,
        ).exists()
        if already:
            continue
        Notification.objects.create(
            user=admin,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link,
        )


@receiver(pre_save, sender=Task)
def remember_task_comment(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_comments = ''
        instance._previous_assignee_id = None
        return
    previous = Task.objects.filter(pk=instance.pk).values_list('comments', 'assigned_to_id').first()
    instance._previous_comments = (previous[0] if previous else '') or ''
    instance._previous_assignee_id = previous[1] if previous else None


def _notify_assignee(instance, reassigned=False):
    from notifications.models import Notification

    employee = instance.assigned_to
    if employee is None:
        return
    user = employee.user
    if not reassigned and instance.created_by_id == user.id:
        return
    author = ''
    if instance.created_by_id:
        author = (instance.created_by.get_full_name() or '').strip() or instance.created_by.username
    author = author or 'Le responsable'
    label = (instance.title or '').strip()
    if label:
        label = label[0].upper() + label[1:]
    project_name = instance.project.name if instance.project_id else ''
    headline = label
    if project_name and project_name.lower() not in label.lower():
        headline = f'{label} — {project_name}'
    title = f'Nouvelle tâche : {headline}.'[:200]
    project = f' Projet : {project_name}.' if project_name else ''
    if reassigned:
        message = f'{author} vous a réattribué « {instance.title} ».{project}'
    else:
        message = f'{author} vous a attribué « {instance.title} ».{project} Ouvrez la tâche pour télécharger le brief.'
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type='info',
        link=f'/tasks/{instance.pk}/',
    )


@receiver(post_save, sender=Task)
def notify_task_event(sender, instance, created, **kwargs):
    who = instance.assigned_to.full_name if instance.assigned_to_id else 'Un employé'
    link = reverse('tasks:detail', args=[instance.pk])
    if created:
        creator = instance.created_by
        personal = (instance.comments or '').startswith('todo:')
        if not personal and (creator is None or not creator.is_admin()):
            _notify_admins(
                'Todo list mise à jour',
                f'{who} a enregistré « {instance.title} ».',
                'info',
                link,
            )
        _notify_assignee(instance)
        return
    previous_assignee = getattr(instance, '_previous_assignee_id', None)
    if instance.assigned_to_id and instance.assigned_to_id != previous_assignee:
        _notify_assignee(instance, reassigned=True)
    comments = (instance.comments or '').strip()
    previous = (getattr(instance, '_previous_comments', '') or '').strip()
    if comments and comments != previous:
        _notify_admins(
            'Difficulté signalée',
            f'{who} a ajouté une remarque sur « {instance.title} ».',
            'warning',
            link,
        )


def sync_deadline_notifications():
    """Une alerte par tâche et par jour lorsque l'échéance approche ou est dépassée."""
    from datetime import timedelta

    from notifications.models import Notification

    today = timezone.localdate()
    soon = today + timedelta(days=2)
    tasks = Task.objects.select_related('assigned_to__user', 'project').exclude(
        status__in=Task.CLOSED_STATUSES,
    ).filter(due_date__isnull=False, due_date__lte=soon)
    for task in tasks:
        if not task.assigned_to_id:
            continue
        overdue = task.due_date < today
        link = reverse('tasks:detail', args=[task.pk])
        kind = 'danger' if overdue else 'warning'
        title = (f'Tâche en retard : {task.title}' if overdue else f'Échéance proche : {task.title}')[:200]
        already = Notification.objects.filter(
            user=task.assigned_to.user,
            link=link,
            notification_type=kind,
            created_at__date=today,
        ).exists()
        if already:
            continue
        when = task.due_date.strftime('%d/%m/%Y')
        if overdue:
            message = f'« {task.title} » a dépassé sa date limite du {when}.'
        else:
            message = f'« {task.title} » arrive à échéance le {when}.'
        Notification.objects.create(
            user=task.assigned_to.user,
            title=title,
            message=message,
            notification_type=kind,
            link=link,
        )
        if overdue:
            _notify_admins(title, message, 'danger', link)


@receiver(post_save, sender=DailyReport)
def notify_report_submitted(sender, instance, created, **kwargs):
    if not created:
        return
    name = f'{instance.employee.first_name} {instance.employee.last_name}'.strip() or instance.employee.username
    _notify_admins(
        'Rapport journalier soumis',
        f'{name} a validé le rapport du {instance.date:%d/%m/%Y}.',
        'success',
        reverse('reports:detail', args=[instance.pk]),
    )


@receiver(post_save, sender=PermissionRequest)
def notify_permission_request(sender, instance, created, **kwargs):
    if not created:
        return
    piece = ' Un justificatif est joint à la demande.' if instance.attachment else ''
    _notify_admins(
        'Nouvelle demande de permission',
        f'{instance.employee.full_name} a envoyé une demande ({instance.get_type_display()}).{piece}',
        'warning',
        reverse('permissions:detail', args=[instance.pk]),
    )
