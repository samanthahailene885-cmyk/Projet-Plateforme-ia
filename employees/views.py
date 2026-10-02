from django.core.paginator import Paginator
from django.db.models import Max
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from authentication.decorators import admin_required
from django.utils import timezone
from attendance.models import Attendance
from permissions.models import PermissionRequest
from tasks.models import DailyPlan, Task
from .models import Employee
from .forms import EmployeeForm

AVATAR_COLORS = ['#7c3aed', '#db2777', '#ea580c', '#0d9488', '#2563eb', '#16a34a', '#ca8a04', '#e11d48']
MONTHS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
DAYS_FR = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']


def _initials(employee):
    first = (employee.user.first_name or '')[:1]
    last = (employee.user.last_name or '')[:1]
    letters = (first + last).upper()
    return letters or (employee.user.username or '?')[:2].upper()


def _presence_for(employee, attendance_status, on_leave, absent_request):
    if employee.status == 'inactive':
        return 'other', 'Inactif'
    if employee.status == 'on_leave' or on_leave:
        return 'leave', 'En congé'
    if attendance_status == 'absent' or absent_request:
        return 'absent', 'Absent'
    return 'active', 'Actif'


def _todo_state(task_statuses, has_plan):
    if 'in_progress' in task_statuses:
        return 'progress', 'En cours'
    if task_statuses or has_plan:
        return 'filled', 'Renseignée'
    return 'empty', 'Non renseignée'


@admin_required
def employee_list(request):
    today = timezone.localdate()
    now = timezone.localtime()
    all_employees = list(Employee.objects.select_related('user').order_by('user__first_name', 'user__last_name'))
    ids = [employee.pk for employee in all_employees]

    attendance = {
        row['employee_id']: row['status']
        for row in Attendance.objects.filter(employee_id__in=ids, date=today).values('employee_id', 'status')
    }
    approved = PermissionRequest.objects.filter(
        employee_id__in=ids,
        status='approved',
        start_date__lte=today,
        end_date__gte=today,
    )
    on_leave_ids = set(approved.filter(type__in=['annual', 'sick']).values_list('employee_id', flat=True))
    absent_ids = set(approved.filter(type__in=['absence', 'permission', 'unpaid']).values_list('employee_id', flat=True))

    tasks_today = Task.objects.filter(assigned_to_id__in=ids, planned_date=today).values('assigned_to_id', 'status')
    statuses_by_employee = {}
    for row in tasks_today:
        statuses_by_employee.setdefault(row['assigned_to_id'], set()).add(row['status'])
    plans = set(DailyPlan.objects.filter(employee_id__in=ids, date=today).exclude(objective='').values_list('employee_id', flat=True))
    last_task = {
        row['assigned_to_id']: row['last']
        for row in Task.objects.filter(assigned_to_id__in=ids).values('assigned_to_id').annotate(last=Max('updated_at'))
    }

    rows = []
    for employee in all_employees:
        presence_key, presence_label = _presence_for(
            employee,
            attendance.get(employee.pk),
            employee.pk in on_leave_ids,
            employee.pk in absent_ids,
        )
        todo_key, todo_label = _todo_state(statuses_by_employee.get(employee.pk, set()), employee.pk in plans)
        activity = last_task.get(employee.pk) or employee.user.last_login
        if activity:
            local_activity = timezone.localtime(activity)
            activity_label = local_activity.strftime('%H:%M') if local_activity.date() == today else local_activity.strftime('%d/%m')
        else:
            activity_label = '—'
        employee.presence_key = presence_key
        employee.presence_label = presence_label
        employee.todo_key = todo_key
        employee.todo_label = todo_label
        employee.activity_label = activity_label
        employee.initials = _initials(employee)
        employee.avatar_color = AVATAR_COLORS[employee.pk % len(AVATAR_COLORS)]
        employee.service_label = employee.department or 'Non renseigné'
        rows.append(employee)

    stats = {
        'total': len(rows),
        'present': sum(1 for row in rows if row.presence_key == 'active'),
        'absent': sum(1 for row in rows if row.presence_key == 'absent'),
        'leave': sum(1 for row in rows if row.presence_key == 'leave'),
        'other': sum(1 for row in rows if row.presence_key == 'other'),
        'new_month': sum(1 for row in rows if row.hire_date.year == today.year and row.hire_date.month == today.month),
    }

    search_query = request.GET.get('search', '').strip()
    service_filter = request.GET.get('service', '')
    position_filter = request.GET.get('position', '')
    presence_filter = request.GET.get('presence', '')
    filtered = rows
    if search_query:
        needle = search_query.lower()
        filtered = [
            row for row in filtered
            if needle in row.full_name.lower()
            or needle in (row.email or '').lower()
            or needle in (row.user.username or '').lower()
        ]
    if service_filter:
        filtered = [row for row in filtered if row.department == service_filter]
    if position_filter:
        filtered = [row for row in filtered if row.position == position_filter]
    if presence_filter:
        filtered = [row for row in filtered if row.presence_key == presence_filter]

    paginator = Paginator(filtered, 8)
    page_obj = paginator.get_page(request.GET.get('page'))
    services = sorted({row.department for row in rows if row.department})
    query = request.GET.copy()
    query.pop('page', None)

    return render(request, 'employees/employee_list.html', {
        'page_obj': page_obj,
        'employees': page_obj.object_list,
        'stats': stats,
        'services': services,
        'positions': Employee.POSITION_CHOICES,
        'search_query': search_query,
        'service_filter': service_filter,
        'position_filter': position_filter,
        'presence_filter': presence_filter,
        'querystring': query.urlencode(),
        'today_label': f"{DAYS_FR[now.weekday()].capitalize()} {now.day} {MONTHS_FR[now.month - 1]} {now.year}",
        'admin_initials': ((request.user.first_name or '')[:1] + (request.user.last_name or '')[:1]).upper() or 'AD',
    })


@login_required
def employee_detail(request, pk):
    """
    Vue de détail d'un employé
    """
    employee = get_object_or_404(Employee.objects.select_related('user'), pk=pk)
    if not request.user.is_admin() and employee.user_id != request.user.id:
        messages.error(request, 'Vous ne pouvez consulter que votre propre fiche.')
        return redirect('dashboard:employee_home')

    from decision_ai.analytics import tasks_on_date
    from reports.models import DailyReport

    today = timezone.now().date()
    activities = tasks_on_date(today, employee).order_by('status', 'title')
    return render(request, 'employees/employee_detail.html', {
        'employee': employee,
        'today': today,
        'activities': activities,
        'todo_filled': activities.exists(),
        'remarks': activities.exclude(comments=''),
        'reports': DailyReport.objects.filter(employee=employee.user).order_by('-date')[:8],
    })


@admin_required
def employee_create(request):
    """
    Vue de création d'un employé
    """
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Employé {employee.full_name} créé avec succès.')
            return redirect('employees:detail', pk=employee.pk)
    else:
        form = EmployeeForm()
    
    return render(request, 'employees/employee_form.html', {'form': form, 'title': 'Ajouter un employé'})


@admin_required
def employee_update(request, pk):
    """
    Vue de mise à jour d'un employé
    """
    employee = get_object_or_404(Employee, pk=pk)
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Employé {employee.full_name} mis à jour avec succès.')
            return redirect('employees:detail', pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee)
    
    return render(request, 'employees/employee_form.html', {'form': form, 'title': 'Modifier l\'employé', 'employee': employee})


@admin_required
def employee_delete(request, pk):
    """
    Vue de suppression d'un employé
    """
    employee = get_object_or_404(Employee, pk=pk)
    
    if request.method == 'POST':
        user = employee.user
        employee.delete()
        user.delete()
        messages.success(request, f'Employé {employee.full_name} supprimé avec succès.')
        return redirect('employees:list')
    
    return render(request, 'employees/employee_confirm_delete.html', {'employee': employee})


@admin_required
def demo_data(request):
    """Générateur de données de démonstration, réservé au responsable."""
    from employees.demo import DEMO_PASSWORD, demo_counts, generate_demo_data, reset_demo_data

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'reset':
                if request.POST.get('confirm') != 'oui':
                    messages.error(request, 'Cochez la confirmation avant de supprimer les données de démonstration.')
                else:
                    removed = reset_demo_data()
                    messages.success(
                        request,
                        'Données de démonstration supprimées. '
                        f"Employés : {removed['employees']}. Projets : {removed['projects']}. "
                        f"Tâches : {removed['tasks']}. Rapports : {removed['reports']}. "
                        'Les données réelles n\'ont pas été modifiées.',
                    )
            elif action == 'generate':
                summary = generate_demo_data(
                    employee_count=int(request.POST.get('employees') or 0),
                    project_count=int(request.POST.get('projects') or 0),
                    task_count=int(request.POST.get('tasks') or 0),
                    days=int(request.POST.get('days') or 0),
                )
                messages.success(
                    request,
                    'Données de démonstration générées. '
                    f"Employés : {summary['employees']}. Projets : {summary['projects']}. "
                    f"Tâches : {summary['tasks']}. Todo lists : {summary['plans']}. "
                    f"Rapports : {summary['reports']}. Permissions : {summary['permissions']}. "
                    f"Alertes calculées aujourd'hui : {summary['alerts']}. "
                    f"Mot de passe des comptes de démonstration : {summary['password']}. "
                    'Ces enregistrements ne représentent pas l\'activité réelle de l\'agence.',
                )
        except (TypeError, ValueError) as exc:
            messages.error(request, str(exc) or 'Les quantités demandées ne sont pas valides.')
        return redirect('employees:demo_data')

    return render(request, 'employees/demo_data.html', {
        'counts': demo_counts(),
        'demo_password': DEMO_PASSWORD,
    })
