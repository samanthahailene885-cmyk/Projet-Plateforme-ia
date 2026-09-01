import calendar
import json
from datetime import timedelta, datetime, time

from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Q, Sum
from django.contrib.auth.decorators import login_required

from authentication.decorators import admin_required
from employees.models import Employee
from projects.models import Project
from tasks.models import Task
from permissions.models import PermissionRequest
from attendance.models import Attendance
from reports.models import DailyReport
from decision_ai.services import DecisionAIService

FRENCH_MONTHS = {
    1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril',
    5: 'mai', 6: 'juin', 7: 'juillet', 8: 'août',
    9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre',
}


def _format_french_date(date):
    return f"{date.day} {FRENCH_MONTHS[date.month]} {date.year}"


def _compute_productivity(today):
    """Calcule les données de productivité hebdomadaire pour le graphique."""
    week_start = today - timedelta(days=6)
    prev_week_start = today - timedelta(days=13)
    prev_week_end = today - timedelta(days=7)

    daily_counts = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        daily_counts.append(
            Task.objects.filter(status='completed', updated_at__date=day).count()
        )

    week_completed = Task.objects.filter(
        status='completed', updated_at__date__gte=week_start
    ).count()
    active_tasks = Task.objects.exclude(status__in=['completed', 'cancelled']).count()
    total_for_rate = week_completed + active_tasks
    productivity_rate = round((week_completed / total_for_rate * 100) if total_for_rate else 0)

    prev_completed = Task.objects.filter(
        status='completed',
        updated_at__date__gte=prev_week_start,
        updated_at__date__lte=prev_week_end,
    ).count()
    prev_total = prev_completed + active_tasks
    prev_rate = round((prev_completed / prev_total * 100) if prev_total else 0)

    return {
        'labels': ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
        'data': daily_counts,
        'rate': productivity_rate,
        'trend': productivity_rate - prev_rate,
    }


@admin_required
def dashboard_home(request):
    """Tableau de bord responsable — vue principale."""
    today = timezone.now().date()
    ai_service = DecisionAIService()

    total_employees = Employee.objects.count()

    today_attendance = Attendance.objects.filter(date=today)
    present_count = today_attendance.filter(status='present').count()
    absent_count = today_attendance.filter(status='absent').count()

    overdue_qs = Task.objects.filter(
        due_date__lt=today
    ).exclude(status='completed').select_related('project', 'assigned_to__user')
    overdue_tasks_count = overdue_qs.count()
    overdue_tasks_list = []
    for task in overdue_qs[:5]:
        overdue_tasks_list.append({
            'task': task,
            'days_late': (today - task.due_date).days,
        })

    completed_tasks_today = Task.objects.filter(
        status='completed', updated_at__date=today
    ).count()
    total_tasks = Task.objects.count()

    active_projects = Project.objects.filter(status='in_progress').count()

    pending_permissions_count = PermissionRequest.objects.filter(status='pending').count()
    pending_permissions_list = PermissionRequest.objects.filter(
        status='pending'
    ).select_related('employee__user')[:5]

    recent_reports = DailyReport.objects.select_related('employee').order_by('-created_at')[:5]

    project_status_data = {
        'completed': Project.objects.filter(status='completed').count(),
        'in_progress': Project.objects.filter(status='in_progress').count(),
        'on_hold': Project.objects.filter(status='on_hold').count(),
        'cancelled': Project.objects.filter(status='cancelled').count(),
    }
    total_projects_chart = sum(project_status_data.values()) - Project.objects.filter(status='planning').count()
    total_projects_chart = (
        project_status_data['completed']
        + project_status_data['in_progress']
        + project_status_data['on_hold']
        + project_status_data['cancelled']
    )

    overdue_task_count = Task.objects.filter(
        due_date__lt=today
    ).exclude(status='completed').count()
    task_status_data = {
        'completed': Task.objects.filter(status='completed').count(),
        'in_progress': Task.objects.filter(status='in_progress').count(),
        'pending': Task.objects.filter(status__in=['todo', 'review']).count(),
        'overdue': overdue_task_count,
    }

    productivity = _compute_productivity(today)

    at_risk_raw = ai_service.detect_project_delays()
    seen_ids = set()
    at_risk_projects = []
    for item in at_risk_raw:
        pid = item['project'].id
        if pid not in seen_ids:
            seen_ids.add(pid)
            at_risk_projects.append(item)

    workload = ai_service.analyze_workload()
    overloaded = [w for w in workload if w['workload_level'] == 'overloaded']
    overloaded_departments = set()
    for w in overloaded:
        dept = w['employee'].department or w['employee'].get_position_display()
        overloaded_departments.add(dept)

    unread_notifications = request.user.notifications.filter(is_read=False).count()

    context = {
        'today_formatted': _format_french_date(today),
        'total_employees': total_employees,
        'present_count': present_count,
        'absent_count': absent_count,
        'active_projects': active_projects,
        'completed_tasks_today': completed_tasks_today,
        'overdue_tasks_count': overdue_tasks_count,
        'overdue_tasks_list': overdue_tasks_list,
        'total_tasks': total_tasks,
        'pending_permissions_count': pending_permissions_count,
        'pending_permissions_list': pending_permissions_list,
        'recent_reports': recent_reports,
        'project_status_data': project_status_data,
        'total_projects_chart': total_projects_chart,
        'task_status_data': task_status_data,
        'productivity': productivity,
        'productivity_labels_json': json.dumps(productivity['labels']),
        'productivity_data_json': json.dumps(productivity['data']),
        'at_risk_projects': at_risk_projects[:3],
        'at_risk_count': len(at_risk_projects),
        'overloaded_departments': list(overloaded_departments),
        'unread_notifications': unread_notifications,
        'today': today,
    }

    return render(request, 'dashboard/dashboard.html', context)


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
        assigned_employees=employee
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
