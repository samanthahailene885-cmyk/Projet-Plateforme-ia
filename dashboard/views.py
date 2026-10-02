import calendar
from datetime import datetime, timedelta

from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.contrib.auth.decorators import login_required

from authentication.decorators import admin_required
from employees.models import Employee
from projects.models import Project
from tasks.models import Task
from permissions.models import PermissionRequest
from attendance.models import Attendance
from reports.models import DailyReport
from decision_ai.analytics import IN_PROGRESS, day_stats, tasks_on_date

FRENCH_DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
FRENCH_MONTHS = {
    1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril',
    5: 'mai', 6: 'juin', 7: 'juillet', 8: 'août',
    9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre',
}
CLOSED = Task.CLOSED_STATUSES


def _projects_needing_attention(today):
    horizon = today + timedelta(days=7)
    late_filter = Q(tasks__due_date__lt=today) & ~Q(tasks__status__in=list(CLOSED))
    annotated = Project.objects.exclude(status='cancelled').annotate(
        late_tasks=Count('tasks', filter=late_filter, distinct=True),
    )
    rows = []
    seen = set()
    for project in annotated.filter(late_tasks__gt=0).order_by('-late_tasks', 'name')[:4]:
        noun = 'tâche' if project.late_tasks == 1 else 'tâches'
        rows.append({'project': project, 'level': 'danger', 'text': f'{project.late_tasks} {noun} en retard'})
        seen.add(project.pk)
    for project in annotated.filter(
        end_date__gte=today,
        end_date__lte=horizon,
    ).exclude(status__in=['completed', 'cancelled']).exclude(pk__in=seen).order_by('end_date')[:3]:
        rows.append({'project': project, 'level': 'warning', 'text': 'Échéance proche'})
        seen.add(project.pk)
    if len(rows) < 4:
        for project in Project.objects.filter(status='in_progress').exclude(pk__in=seen).order_by('name')[:4 - len(rows)]:
            rows.append({'project': project, 'level': 'ok', 'text': 'Avancement normal'})
    return rows


def _format_french_date(date):
    return f"{FRENCH_DAYS[date.weekday()]} {date.day} {FRENCH_MONTHS[date.month]} {date.year}"


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _pct(part, total):
    if not total:
        return 0
    return round(part * 100 / total)


def _person_name(user):
    name = f'{user.first_name} {user.last_name}'.strip()
    return name or user.username


def _activity_series(end, days):
    """Comptes réels des activités rattachées à chaque jour. Aucune valeur n'est écrite à la main."""
    labels, done, doing, waiting, late = [], [], [], [], []
    total = 0
    start = end - timedelta(days=days - 1)
    for offset in range(days):
        day = start + timedelta(days=offset)
        labels.append(f'{day.day:02d}/{day.month:02d}')
        qs = tasks_on_date(day)
        late_count = qs.filter(due_date__lt=day).exclude(status__in=CLOSED).count()
        done_count = qs.filter(status='completed').count()
        doing_count = qs.exclude(due_date__lt=day).filter(status__in=IN_PROGRESS).count()
        waiting_count = qs.exclude(due_date__lt=day).filter(status='todo').count()
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


def _project_bars():
    rows = list(
        Project.objects.exclude(status='cancelled')
        .annotate(activity_count=Count('tasks', filter=~Q(tasks__status='cancelled')))
        .filter(activity_count__gt=0)
        .order_by('-activity_count', 'name')
    )
    shown = rows[:5]
    labels = [row.name for row in shown]
    values = [row.activity_count for row in shown]
    rest = rows[5:]
    if rest:
        labels.append('Autres')
        values.append(sum(row.activity_count for row in rest))
    peak = max(values) if values else 0
    return {
        'labels': labels,
        'values': values,
        'rows': [{'name': name, 'count': count} for name, count in zip(labels, values)],
        'peak': peak,
        'empty': not values,
    }


def _project_donut(day):
    late_ids = list(
        Project.objects.filter(end_date__lt=day)
        .exclude(status__in=['completed', 'cancelled'])
        .values_list('pk', flat=True)
    )
    slices = [
        ('En cours', Project.objects.filter(status='in_progress').exclude(pk__in=late_ids).count(), '#10B981'),
        ('Terminés', Project.objects.filter(status='completed').count(), '#2563EB'),
        ('En retard', len(late_ids), '#EF4444'),
        ('En attente', Project.objects.filter(status__in=['planning', 'on_hold']).exclude(pk__in=late_ids).count(), '#F59E0B'),
    ]
    total = sum(item[1] for item in slices)
    return {
        'labels': [item[0] for item in slices],
        'values': [item[1] for item in slices],
        'colors': [item[2] for item in slices],
        'total': total,
        'rows': [
            {'label': label, 'count': count, 'color': color, 'percent': _pct(count, total)}
            for label, count, color in slices
        ],
        'empty': total == 0,
    }


def _delta(current, previous):
    """Pourcentage seulement si la période précédente contient assez d'activités."""
    if previous < 5:
        return None
    value = round((current - previous) * 100 / previous)
    if abs(value) > 100:
        return None
    return value


def _window_totals(end, days):
    series = _activity_series(end, days)
    return {
        'total': sum(series['completed']) + sum(series['in_progress']) + sum(series['not_started']) + sum(series['late']),
        'completed': sum(series['completed']),
        'in_progress': sum(series['in_progress']),
        'late': sum(series['late']),
    }


def _initials(name):
    parts = [part for part in (name or '').split() if part and part != '—']
    if not parts:
        return '—'
    return ''.join(part[0] for part in parts[:2]).upper()


def _ago(moment):
    minutes = int((timezone.now() - moment).total_seconds() // 60)
    if minutes < 1:
        return "À l'instant"
    if minutes < 60:
        return f'Il y a {minutes} min'
    hours = minutes // 60
    if hours < 24:
        return f'Il y a {hours} h'
    return f'Il y a {hours // 24} j'


def _action_label(kind, status_key):
    if kind == 'report':
        return 'a soumis un rapport journalier'
    if kind == 'permission':
        return 'a demandé une permission'
    if kind == 'difficulty':
        return 'a signalé une difficulté'
    if kind == 'project':
        return 'projet mis à jour'
    if status_key == 'done':
        return 'a terminé une activité'
    if status_key == 'progress':
        return 'a une activité en cours'
    return 'a une activité enregistrée'


def _status_key(status):
    if status == 'completed':
        return 'done'
    if status in IN_PROGRESS:
        return 'progress'
    if status == 'pending':
        return 'wait'
    return 'todo'


def _recent_rows():
    rows = []
    for task in Task.objects.select_related('assigned_to__user', 'project').order_by('-updated_at')[:16]:
        has_remark = bool((task.comments or '').strip()) and task.status != 'completed'
        rows.append({
            'when': task.updated_at,
            'who': task.assigned_to.full_name if task.assigned_to_id else '—',
            'type': 'Difficulté' if has_remark else 'Tâche',
            'kind': 'difficulty' if has_remark else 'task',
            'project': task.project.name if task.project_id else '—',
            'detail': task.title,
            'status': task.get_status_display(),
            'status_key': _status_key(task.status),
            'url': reverse('tasks:detail', args=[task.pk]),
        })
    for report in DailyReport.objects.select_related('employee').order_by('-updated_at')[:8]:
        rows.append({
            'when': report.updated_at,
            'who': _person_name(report.employee),
            'type': 'Rapport',
            'kind': 'report',
            'project': '—',
            'detail': f'Rapport du {report.date:%d/%m/%Y}',
            'status': 'Soumis',
            'status_key': 'done',
            'url': reverse('reports:detail', args=[report.pk]),
        })
    for perm in PermissionRequest.objects.select_related('employee__user').order_by('-created_at')[:8]:
        rows.append({
            'when': perm.created_at,
            'who': perm.employee.full_name,
            'type': 'Permission',
            'kind': 'permission',
            'project': '—',
            'detail': perm.get_type_display(),
            'status': perm.get_status_display(),
            'status_key': 'wait' if perm.status == 'pending' else 'done',
            'url': reverse('permissions:detail', args=[perm.pk]),
        })
    for project in Project.objects.order_by('-updated_at')[:6]:
        late = project.end_date < timezone.localdate() and project.status not in ('completed', 'cancelled')
        rows.append({
            'when': project.updated_at,
            'who': '—',
            'type': 'Projet',
            'kind': 'project',
            'project': project.name,
            'detail': project.get_status_display(),
            'status': 'En retard' if late else project.get_status_display(),
            'status_key': 'late' if late else _status_key(project.status),
            'url': reverse('projects:detail', args=[project.pk]),
        })
    rows.sort(key=lambda item: item['when'], reverse=True)
    prepared = []
    for row in rows[:12]:
        local = timezone.localtime(row['when'])
        row['when_label'] = f'{local:%d/%m/%Y %H:%M}'
        row['ago'] = _ago(row['when'])
        row['initials'] = _initials(row['who'])
        row['action'] = _action_label(row['kind'], row['status_key'])
        prepared.append(row)
    return prepared


def _recent_feed():
    rows = _recent_rows()
    people = [row for row in rows if row['who'] != '—']
    return (people or rows)[:4]


def _quick_brief(day):
    stats = day_stats(day)
    late = tasks_on_date(day).filter(due_date__lt=day).exclude(status__in=CLOSED).count()
    remarks = len(stats['remarks'])
    if not stats['planned'] and not remarks:
        return "Aucune activité enregistrée pour cette date."
    text = (
        f"{stats['planned']} activités sont prévues pour cette date. "
        f"{stats['completed']} sont terminées, {stats['in_progress']} sont en cours "
        f"et {late} présentent un retard."
    )
    if remarks == 1:
        text += " 1 difficulté est signalée."
    elif remarks:
        text += f" {remarks} difficultés sont signalées."
    return text


@admin_required
def dashboard_home(request):
    """Tableau de bord responsable. Tous les chiffres viennent des enregistrements."""
    today = timezone.localdate()
    selected = _parse_date(request.GET.get('date')) or today
    try:
        window = int(request.GET.get('range') or 7)
    except ValueError:
        window = 7
    if window not in (7, 14, 30):
        window = 7

    active_tasks = Task.objects.exclude(status='cancelled')
    series = _activity_series(selected, window)
    bars = _project_bars()
    donut = _project_donut(selected)
    current_week = _window_totals(selected, 7)
    previous_week = _window_totals(selected - timedelta(days=7), 7)
    week_start = selected - timedelta(days=selected.weekday())
    employees_total = Employee.objects.count()
    active_employees = Employee.objects.filter(status='active').count()
    new_employees = Employee.objects.filter(
        status='active', hire_date__gte=week_start, hire_date__lte=selected,
    ).count()
    tasks_late = active_tasks.filter(due_date__lt=selected).exclude(status__in=CLOSED).count()
    projects_due_soon = Project.objects.filter(
        end_date__gte=selected,
        end_date__lte=selected + timedelta(days=7),
    ).exclude(status__in=['completed', 'cancelled']).count()
    difficulties = len(day_stats(selected)['remarks'])
    from notifications.signals import sync_deadline_notifications
    sync_deadline_notifications()
    task_state = {
        'todo': active_tasks.filter(status='todo').count(),
        'in_progress': active_tasks.filter(status='in_progress').count(),
        'review': active_tasks.filter(status='review').count(),
        'completed': active_tasks.filter(status='completed').count(),
        'late': tasks_late,
    }
    user = request.user
    full_name = (user.get_full_name() or '').strip() or user.username
    initials = (
        f'{(user.first_name[:1] if user.first_name else "")}'
        f'{(user.last_name[:1] if user.last_name else "")}'
    ).upper() or user.username[:2].upper()
    return render(request, 'dashboard/dashboard.html', {
        'today': today,
        'selected': selected,
        'window': window,
        'today_formatted': _format_french_date(selected),
        'kpis': {
            'active_employees': active_employees,
            'employees_total': employees_total,
            'new_employees': new_employees,
            'tasks_total': active_tasks.count(),
            'tasks_completed': active_tasks.filter(status='completed').count(),
            'tasks_in_progress': active_tasks.filter(status__in=IN_PROGRESS).count(),
            'tasks_late': tasks_late,
            'total_delta': _delta(current_week['total'], previous_week['total']),
            'done_delta': _delta(current_week['completed'], previous_week['completed']),
            'doing_delta': _delta(current_week['in_progress'], previous_week['in_progress']),
            'late_delta': _delta(current_week['late'], previous_week['late']),
        },
        'attention': {
            'late': tasks_late,
            'due_soon': projects_due_soon,
            'difficulties': difficulties,
        },
        'task_state': task_state,
        'watch_projects': _projects_needing_attention(selected),
        'quick_brief': _quick_brief(selected),
        'series': series,
        'project_bars': bars,
        'project_donut': donut,
        'recent_rows': _recent_feed(),
        'unread_notifications': user.notifications.filter(is_read=False).count(),
        'profile_name': full_name,
        'profile_initials': initials,
        'chart_payload': {'series': series, 'bars': bars, 'donut': donut},
    })


@admin_required
def dashboard_search(request):
    query = (request.GET.get('q') or '').strip()
    employees = []
    projects = []
    tasks = []
    if query:
        employees = Employee.objects.select_related('user').filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
        )[:12]
        projects = Project.objects.filter(
            Q(name__icontains=query) | Q(client__icontains=query)
        )[:12]
        tasks = Task.objects.select_related('project', 'assigned_to__user').filter(
            Q(title__icontains=query) | Q(comments__icontains=query)
        )[:12]
    return render(request, 'dashboard/search.html', {
        'query': query,
        'employees': employees,
        'projects': projects,
        'tasks': tasks,
    })


def _get_or_create_employee(user):
    try:
        return user.employee_profile
    except Exception:
        position = 'other' if user.role == 'employee' else 'project_manager'
        return Employee.objects.create(
            user=user,
            position=position,
            hire_date=timezone.now().date(),
            status='active',
        )


def _compute_hours_worked(employee, today):
    attendance = Attendance.objects.filter(employee=employee, date=today).first()
    if attendance and attendance.check_in_time and attendance.check_out_time:
        check_in = datetime.combine(today, attendance.check_in_time)
        check_out = datetime.combine(today, attendance.check_out_time)
        total_minutes = int((check_out - check_in).total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        return f"{hours}h {minutes:02d}m"

    total_hours = Task.objects.filter(
        assigned_to=employee,
        status='completed',
        updated_at__date=today,
    ).aggregate(total=Sum('actual_hours'))['total']

    if total_hours:
        hours = int(total_hours)
        minutes = int((total_hours - hours) * 60)
        return f"{hours}h {minutes:02d}m"

    return "0h 00m"


def _build_recent_activities(user, employee, limit=5):
    activities = []

    for task in Task.objects.filter(
        assigned_to=employee, status='completed'
    ).select_related('project').order_by('-updated_at')[:limit]:
        activities.append({
            'icon': 'check',
            'color': 'green',
            'text': f'Vous avez terminé la tâche « {task.title} »',
            'time': task.updated_at,
        })

    for report in DailyReport.objects.filter(employee=user).order_by('-created_at')[:3]:
        activities.append({
            'icon': 'paper-plane',
            'color': 'blue',
            'text': 'Votre rapport quotidien a été envoyé',
            'time': report.created_at,
        })

    for notif in user.notifications.order_by('-created_at')[:limit]:
        activities.append({
            'icon': 'bell',
            'color': 'orange',
            'text': notif.message,
            'time': notif.created_at,
        })

    for perm in PermissionRequest.objects.filter(
        employee=employee, status='approved'
    ).order_by('-updated_at')[:2]:
        activities.append({
            'icon': 'calendar-check',
            'color': 'purple',
            'text': f'Votre demande de {perm.get_type_display().lower()} a été approuvée',
            'time': perm.updated_at,
        })

    activities.sort(key=lambda item: item['time'], reverse=True)
    return activities[:limit]


def _format_relative_time(dt):
    now = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    diff = now - dt
    minutes = int(diff.total_seconds() // 60)
    if minutes < 1:
        return "À l'instant"
    if minutes < 60:
        return f"Il y a {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"Il y a {hours}h"
    days = hours // 24
    return f"Il y a {days}j"


@login_required
def employee_home(request):
    """Tableau de bord employé — vue principale."""
    from notifications.signals import sync_deadline_notifications
    sync_deadline_notifications()
    employee = _get_or_create_employee(request.user)
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    search_query = request.GET.get('search', '').strip()
    if search_query:
        return redirect(f'/tasks/?search={search_query}')

    user_tasks = Task.objects.filter(assigned_to=employee).select_related('project')

    today_tasks_qs = user_tasks.filter(
        Q(due_date=today) | Q(status__in=['todo', 'in_progress', 'review'])
    ).exclude(status='cancelled').order_by('due_date', '-priority')

    tasks_today_count = today_tasks_qs.count()
    completed_today = user_tasks.filter(
        status='completed', updated_at__date=today
    ).count()

    completion_rate = round(
        (completed_today / tasks_today_count * 100) if tasks_today_count else 0
    )

    tasks_yesterday = user_tasks.filter(
        Q(due_date=yesterday) | Q(updated_at__date=yesterday)
    ).exclude(status='cancelled').count()
    completed_yesterday = user_tasks.filter(
        status='completed', updated_at__date=yesterday
    ).count()
    rate_yesterday = round(
        (completed_yesterday / tasks_yesterday * 100) if tasks_yesterday else 0
    )
    completion_trend = completion_rate - rate_yesterday

    employee_projects = Project.objects.filter(
        Q(assigned_employees=employee) | Q(tasks__assigned_to=employee)
    ).distinct()
    active_projects_count = employee_projects.filter(status='in_progress').count()
    total_projects_count = employee_projects.exclude(status='cancelled').count()
    projects_list = employee_projects.exclude(status='cancelled').order_by('-updated_at')[:4]

    next_task = user_tasks.filter(
        due_date__gte=today
    ).exclude(status__in=['completed', 'cancelled']).order_by('due_date').first()

    today_report = DailyReport.objects.filter(
        employee=request.user, date=today
    ).first()

    calendar_tasks = user_tasks.filter(
        due_date__year=today.year,
        due_date__month=today.month,
    ).exclude(status='cancelled')

    calendar_days = {}
    for task in calendar_tasks:
        if task.due_date:
            calendar_days.setdefault(task.due_date.day, []).append(task)

    today_events = []
    for task in calendar_tasks.filter(due_date=today).order_by('due_date'):
        today_events.append({
            'time': task.updated_at.strftime('%H:%M') if task.updated_at else '09:00',
            'title': task.title,
            'subtitle': task.project.name if task.project else 'Sans projet',
            'color': 'green' if task.priority in ('high', 'urgent') else 'blue',
        })

    for perm in PermissionRequest.objects.filter(
        employee=employee, start_date=today, status='approved'
    ):
        today_events.append({
            'time': '10:00',
            'title': perm.get_type_display(),
            'subtitle': perm.reason[:40],
            'color': 'orange',
        })

    cal = calendar.Calendar(firstweekday=0)
    month_weeks = cal.monthdayscalendar(today.year, today.month)

    activities = _build_recent_activities(request.user, employee)
    for activity in activities:
        activity['relative_time'] = _format_relative_time(activity['time'])

    unread_notifications = request.user.notifications.filter(is_read=False).count()

    context = {
        'today_formatted': _format_french_date(today),
        'today': today,
        'first_name': request.user.first_name or request.user.username,
        'position': employee.get_position_display(),
        'tasks_today_count': tasks_today_count,
        'completed_today': completed_today,
        'completion_rate': completion_rate,
        'completion_trend': completion_trend,
        'hours_worked': _compute_hours_worked(employee, today),
        'active_projects_count': active_projects_count,
        'total_projects_count': total_projects_count,
        'next_deadline': next_task.due_date if next_task else None,
        'next_deadline_task': next_task.title if next_task else None,
        'today_tasks': today_tasks_qs[:6],
        'projects_list': projects_list,
        'today_report': today_report,
        'activities': activities,
        'month_weeks': month_weeks,
        'calendar_month': FRENCH_MONTHS[today.month].capitalize(),
        'calendar_year': today.year,
        'calendar_today': today.day,
        'calendar_days': calendar_days,
        'today_events': today_events[:4],
        'unread_notifications': unread_notifications,
    }

    return render(request, 'dashboard/employee_home.html', context)
