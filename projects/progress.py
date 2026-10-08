"""Recalcule l'avancement d'un projet à partir de ses tâches enregistrées."""
from django.utils import timezone

from projects.models import Project


def sync_project_progress(project_id):
    """Met à jour le pourcentage et, si besoin, le statut du projet."""
    if not project_id:
        return None
    project = Project.objects.filter(pk=project_id).first()
    if project is None:
        return None

    tasks = project.tasks.exclude(status='cancelled')
    total = tasks.count()
    if total == 0:
        return project

    done = tasks.filter(status='completed').count()
    remaining = tasks.exclude(status__in=['completed', 'not_done']).count()
    progress = round(done * 100 / total)
    update_fields = ['progress', 'updated_at']
    project.progress = progress

    if project.status not in ('on_hold', 'cancelled'):
        if remaining == 0 and done == total:
            if project.status != 'completed':
                project.status = 'completed'
                update_fields.append('status')
        elif remaining > 0 and project.status in ('planning', 'completed') and done > 0:
            project.status = 'in_progress'
            update_fields.append('status')
        elif remaining > 0 and project.status == 'completed':
            project.status = 'in_progress'
            update_fields.append('status')

    project.save(update_fields=update_fields)
    return project


def attach_project_if_missing(task):
    """Crée ou retrouve un projet pour une activité qui n'en a pas encore."""
    if task.project_id or not task.assigned_to_id or not task.pk:
        return task.project_id
    if (task.comments or '').startswith('todo:'):
        return None

    name = (task.block_title or task.title or '').strip()[:200]
    if not name:
        return None

    project = Project.objects.filter(
        name__iexact=name,
        assigned_employees=task.assigned_to,
    ).first()
    if project is None:
        start = task.planned_date or task.due_date or timezone.now().date()
        end = task.due_date or task.planned_date or start
        if end < start:
            end = start
        project = Project.objects.create(
            name=name,
            client='Non renseigné',
            start_date=start,
            end_date=end,
            status='planning',
            priority=task.priority or 'medium',
        )
        project.assigned_employees.add(task.assigned_to)

    type(task).objects.filter(pk=task.pk).update(project_id=project.pk)
    task.project_id = project.pk
    return project.pk


def link_employee_tasks(employee):
    from tasks.models import Task

    for task in Task.objects.filter(assigned_to=employee, project__isnull=True):
        project_id = attach_project_if_missing(task)
        sync_project_progress(project_id)


def sync_queryset(projects):
    ids = projects.filter(tasks__isnull=False).values_list('pk', flat=True).distinct()
    for project_id in ids:
        sync_project_progress(project_id)
