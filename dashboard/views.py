import json
from datetime import timedelta

from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q
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


@login_required
def employee_home(request):
    """Vue de la page d'accueil de l'employé avec gestion des tâches."""
    try:
        employee = request.user.employee_profile
    except Exception:
        if request.user.role == 'employee':
            employee = Employee.objects.create(
                user=request.user,
                position='other',
                hire_date=timezone.now().date(),
                status='active',
            )
        else:
            employee = Employee.objects.create(
                user=request.user,
                position='project_manager',
                hire_date=timezone.now().date(),
                status='active',
            )

    user_tasks = Task.objects.filter(assigned_to=employee)
    all_projects = Project.objects.all()
    all_employees = Employee.objects.all()

    context = {
        'tasks': user_tasks,
        'projects': all_projects,
        'employees': all_employees,
    }

    return render(request, 'dashboard/employee_home.html', context)
