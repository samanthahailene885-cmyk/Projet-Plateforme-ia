from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import DailyReport
from .services import ReportGenerator


FRENCH_DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
FRENCH_MONTHS = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
]
TIME_SLOTS = [
    '09:00 - 11:30', '11:30 - 13:00', '14:00 - 16:00',
    '16:00 - 17:30', '09:30 - 12:00', '13:30 - 15:00',
]


def _format_french_date(date):
    return f"{FRENCH_DAYS[date.weekday()]} {date.day} {FRENCH_MONTHS[date.month - 1]} {date.year}"


def _get_or_create_employee(user):
    try:
        return user.employee_profile
    except Exception:
        if user.role == 'employee':
            from employees.models import Employee
            return Employee.objects.create(
                user=user,
                position='other',
                hire_date=timezone.now().date(),
                status='active'
            )
        return None


def _build_report_context(user, report=None, report_date=None):
    """Construit le contexte partagé pour la page Mon rapport (style WorkFlow)."""
    from tasks.models import Task

    today = report_date or timezone.now().date()
    employee = _get_or_create_employee(user)

    if employee is None:
        return None

    completed_tasks = Task.objects.filter(
        assigned_to=employee,
        status='completed',
        updated_at__date=today
    )
    in_progress_tasks = Task.objects.filter(
        assigned_to=employee,
        status='in_progress'
    )
    todo_tasks = Task.objects.filter(
        assigned_to=employee,
        status='todo'
    )

    stats = {
        'tasks_completed': completed_tasks.count(),
        'tasks_in_progress': in_progress_tasks.count(),
        'tasks_remaining': todo_tasks.count(),
        'total_tasks': Task.objects.filter(assigned_to=employee).count(),
    }

    tasks_planned = stats['tasks_completed'] + stats['tasks_in_progress'] + stats['tasks_remaining']
    stats['tasks_planned'] = max(tasks_planned, stats['tasks_completed'] + stats['tasks_in_progress'])
    stats['productivity'] = (
        int((stats['tasks_completed'] / stats['tasks_planned']) * 100)
        if stats['tasks_planned'] > 0 else 0
    )

    total_minutes = 0
    for task in completed_tasks:
        total_minutes += int(float(task.actual_hours) * 60) if task.actual_hours else 90
    for task in in_progress_tasks:
        total_minutes += 45
    hours, minutes = total_minutes // 60, total_minutes % 60
    stats['hours_worked'] = f"{hours}h {minutes:02d}min" if minutes else f"{hours}h"

    activities = []
    idx = 0
    for task in completed_tasks:
        activities.append({
            'title': task.title,
            'description': task.description or f"Travail sur {task.project.name if task.project else 'le projet'}",
            'status': 'completed',
            'status_class': 'done',
            'status_label': 'Terminée',
            'time': TIME_SLOTS[idx % len(TIME_SLOTS)],
        })
        idx += 1
    for task in in_progress_tasks:
        activities.append({
            'title': task.title,
            'description': task.description or f"En cours sur {task.project.name if task.project else 'le projet'}",
            'status': 'in_progress',
            'status_class': 'progress',
            'status_label': 'En cours',
            'time': TIME_SLOTS[idx % len(TIME_SLOTS)],
        })
        idx += 1
    for task in todo_tasks[:3]:
        activities.append({
            'title': task.title,
            'description': task.description or f"À planifier pour {task.project.name if task.project else 'le projet'}",
            'status': 'todo',
            'status_class': 'todo',
            'status_label': 'À faire',
            'time': TIME_SLOTS[idx % len(TIME_SLOTS)],
        })
        idx += 1

    if report:
        ai_summary = report.content
        is_submitted = True
    else:
        generator = ReportGenerator()
        ai_summary = generator.generate_daily_report(user)
        is_submitted = False

    last_report = DailyReport.objects.filter(
        employee=user
    ).exclude(pk=report.pk if report else None).order_by('-created_at').first()

    return {
        'today': today,
        'formatted_date': _format_french_date(today),
        'stats': stats,
        'activities': activities,
        'ai_summary': ai_summary,
        'last_report': last_report,
        'report': report,
        'is_submitted': is_submitted,
    }


@login_required
def report_list(request):
    if request.user.is_admin():
        reports = DailyReport.objects.select_related('employee').all()
    else:
        return redirect('reports:create')

    context = {'reports': reports}
    return render(request, 'reports/report_list.html', context)


@login_required
def report_detail(request, pk):
    report = get_object_or_404(DailyReport, pk=pk)

    if not request.user.is_admin() and report.employee != request.user:
        messages.error(request, 'Vous n\'avez pas le droit de voir ce rapport.')
        return redirect('reports:create')

    context = _build_report_context(report.employee, report=report, report_date=report.date)
    if context is None:
        messages.error(request, 'Profil employé introuvable.')
        return redirect('reports:create')

    return render(request, 'reports/report_create.html', context)


@login_required
def report_create(request):
    today = timezone.now().date()
    employee = _get_or_create_employee(request.user)

    if employee is None:
        messages.error(request, 'Vous devez avoir un profil employé pour accéder à votre rapport.')
        return redirect('dashboard:employee_home')

    existing_report = DailyReport.objects.filter(
        employee=request.user,
        date=today
    ).first()

    context = _build_report_context(
        request.user,
        report=existing_report,
        report_date=today
    )

    return render(request, 'reports/report_create.html', context)


@login_required
def report_generate(request):
    today = timezone.now().date()
    employee = _get_or_create_employee(request.user)

    if employee is None:
        messages.error(request, 'Vous devez avoir un profil employé pour générer un rapport.')
        return redirect('reports:create')

    existing_report = DailyReport.objects.filter(
        employee=request.user,
        date=today
    ).first()

    if existing_report:
        messages.info(request, 'Votre rapport du jour a déjà été envoyé.')
        return redirect('reports:create')

    from tasks.models import Task
    generator = ReportGenerator()
    report_content = generator.generate_daily_report(request.user)

    completed_tasks = Task.objects.filter(
        assigned_to=employee,
        status='completed',
        updated_at__date=today
    )
    in_progress_tasks = Task.objects.filter(
        assigned_to=employee,
        status='in_progress'
    )

    DailyReport.objects.create(
        employee=request.user,
        date=today,
        content=report_content,
        tasks_completed='\n'.join([task.title for task in completed_tasks]),
        tasks_in_progress='\n'.join([task.title for task in in_progress_tasks]),
        ai_generated=False
    )

    messages.success(request, 'Rapport envoyé avec succès !')
    return redirect('reports:create')
