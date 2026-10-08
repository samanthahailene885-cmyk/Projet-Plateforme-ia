"""Indicateurs du tableau de bord, calculés uniquement sur les enregistrements."""
from datetime import timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from decision_ai.analytics import IN_PROGRESS, collect_alerts
from employees.models import Employee
from permissions.models import PermissionRequest
from projects.models import Project
from reports.models import DailyReport
from tasks.models import DailyPlan, Difficulty, Task


CLOSED = Task.CLOSED_STATUSES


def _open_as_of(day):
    return Task.objects.exclude(status__in=['cancelled', 'not_done']).filter(
        Q(completed_at__isnull=True) | Q(completed_at__date__gt=day)
    )


def activity_state(day):
    """Répartition exclusive des tâches telles qu'elles étaient à cette date."""
    open_tasks = _open_as_of(day)
    overdue = open_tasks.filter(due_date__lt=day)
    overdue_ids = set(overdue.values_list('pk', flat=True))
    in_progress = open_tasks.filter(started_at__date__lte=day).exclude(pk__in=overdue_ids)
    not_started = open_tasks.filter(
        Q(started_at__isnull=True) | Q(started_at__date__gt=day)
    ).exclude(pk__in=overdue_ids)
    completed = Task.objects.filter(status='completed', completed_at__date__lte=day).count()
    rows = [
        ('Terminées', completed, '#10B981'),
        ('En cours', in_progress.count(), '#2563EB'),
        ('Non commencées', not_started.count(), '#F59E0B'),
        ('En retard', len(overdue_ids), '#EF4444'),
    ]
    total = sum(item[1] for item in rows)
    return {
        'labels': [item[0] for item in rows],
        'values': [item[1] for item in rows],
        'colors': [item[2] for item in rows],
        'total': total,
        'empty': total == 0,
        'rows': [
            {'label': label, 'count': count, 'color': color}
            for label, count, color in rows
        ],
    }


def activity_series(end, days):
    """Pour chaque jour : terminées ce jour-là, et stocks réels en cours / en retard."""
    labels, done, doing, waiting, late = [], [], [], [], []
    total = 0
    start = end - timedelta(days=days - 1)
    for offset in range(days):
        day = start + timedelta(days=offset)
        labels.append(f'{day.day:02d}/{day.month:02d}')
        state = activity_state(day)
        done_count = Task.objects.filter(completed_at__date=day).count()
        doing_count = state['values'][1]
        waiting_count = state['values'][2]
        late_count = state['values'][3]
        done.append(done_count)
        doing.append(doing_count)
        waiting.append(waiting_count)
        late.append(late_count)
        total += done_count + doing_count + waiting_count + late_count
    return {
        'labels': labels,
        'completed': done,
        'in_progress': doing,
        'not_started': waiting,
        'late': late,
        'empty': total == 0,
    }


def agency_metrics(day):
    today = timezone.localdate()
    active_employees = Employee.objects.filter(status='active')
    active_ids = set(active_employees.values_list('pk', flat=True))
    active_user_ids = set(active_employees.values_list('user_id', flat=True))

    filled = set(
        DailyPlan.objects.filter(date=day, employee_id__in=active_ids).values_list('employee_id', flat=True)
    )
    filled.update(
        Task.objects.filter(planned_date=day, assigned_to_id__in=active_ids)
        .exclude(status='cancelled')
        .values_list('assigned_to_id', flat=True)
    )
    filled.discard(None)
    filled &= active_ids

    submitted_user_ids = set(
        DailyReport.objects.filter(date=day, employee_id__in=active_user_ids).values_list('employee_id', flat=True)
    )
    projects = Project.objects.exclude(status='cancelled')
    tasks = Task.objects.exclude(status='cancelled')
    if day == today:
        in_progress = tasks.filter(status__in=IN_PROGRESS).count()
        not_started = tasks.filter(status='todo').count()
        overdue = tasks.filter(due_date__lt=day).exclude(status__in=CLOSED).count()
    else:
        state = activity_state(day)
        in_progress = state['values'][1]
        not_started = state['values'][2]
        overdue = state['values'][3]

    alerts = collect_alerts(day)
    difficulties = Difficulty.objects.filter(status='open').select_related('employee__user', 'project')
    return {
        'employees_active': len(active_ids),
        'employees_total': Employee.objects.count(),
        'projects_total': projects.count(),
        'projects_in_progress': projects.filter(status='in_progress').count(),
        'projects_completed': projects.filter(status='completed').count(),
        'projects_upcoming': projects.filter(status='planning').count(),
        'tasks_total': tasks.count(),
        'tasks_completed': tasks.filter(status='completed').count(),
        'tasks_completed_today': tasks.filter(completed_at__date=day).count(),
        'tasks_in_progress': in_progress,
        'tasks_not_started': not_started,
        'tasks_overdue': overdue,
        'todo_lists_today': len(filled),
        'todo_lists_missing': len(active_ids - filled),
        'reports_submitted_today': len(submitted_user_ids),
        'reports_missing_today': len(active_user_ids - submitted_user_ids),
        'pending_permissions': PermissionRequest.objects.filter(status='pending').count(),
        'difficulties_open': difficulties.count(),
        'alerts_active': len(alerts),
        'difficulty_rows': [
            {
                'who': item.employee.full_name,
                'project': item.project.name if item.project_id else 'Sans projet',
                'text': item.description,
                'url': reverse('tasks:difficulties'),
            }
            for item in difficulties.order_by('-reported_on', '-created_at')[:4]
        ],
        'alert_rows': [
            {
                'title': alert['subject'],
                'text': alert['reason'],
                'url': alert['url'],
            }
            for alert in alerts[:4]
        ],
    }
