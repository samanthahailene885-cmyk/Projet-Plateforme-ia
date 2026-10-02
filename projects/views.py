from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format

from authentication.decorators import admin_required
from employees.models import Employee
from tasks.models import Task
from .forms import ProjectForm, ProjectSearchForm
from .models import Project


def _employee_or_none(user):
    try:
        return user.employee_profile
    except Employee.DoesNotExist:
        return None


def _visible_projects(request):
    projects = Project.objects.prefetch_related('assigned_employees').all()
    if request.user.is_admin():
        return projects
    employee = _employee_or_none(request.user)
    if not employee:
        return Project.objects.none()
    return projects.filter(
        Q(assigned_employees=employee) | Q(tasks__assigned_to=employee)
    ).distinct()


@login_required
def project_list(request):
    """
    Liste des projets : vue admin complète, vue employé (mes projets).
    """
    from projects.progress import link_employee_tasks, sync_queryset
    if not request.user.is_admin():
        employee = _employee_or_none(request.user)
        if employee:
            link_employee_tasks(employee)
    base_qs = _visible_projects(request)
    sync_queryset(base_qs)

    if not request.user.is_admin():
        return _employee_project_list(request, _visible_projects(request))

    projects = base_qs
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')

    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(client__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if status_filter == 'late':
        projects = projects.filter(end_date__lt=timezone.now().date()).exclude(
            status__in=['completed', 'cancelled']
        )
    elif status_filter:
        projects = projects.filter(status=status_filter)

    if priority_filter:
        projects = projects.filter(priority=priority_filter)

    form = ProjectSearchForm(initial={
        'search': search_query,
        'status': status_filter,
        'priority': priority_filter
    })

    return render(request, 'projects/project_list.html', {
        'projects': projects,
        'form': form,
        'search_query': search_query,
    })


def _employee_project_list(request, base_qs):
    today = timezone.now().date()
    week_end = today + timedelta(days=7)

    kpi_active = base_qs.filter(status__in=['planning', 'in_progress']).count()
    kpi_completed = base_qs.filter(status='completed').count()
    kpi_on_hold = base_qs.filter(status='on_hold').count()
    kpi_teams = Employee.objects.filter(projects__in=base_qs).distinct().count()
    kpi_deadlines = base_qs.filter(
        end_date__gte=today,
        end_date__lte=week_end,
        status__in=['planning', 'in_progress', 'on_hold'],
    ).count()

    tab_counts = {
        'all': base_qs.exclude(status='cancelled').count(),
        'in_progress': base_qs.filter(status__in=['planning', 'in_progress']).count(),
        'on_hold': kpi_on_hold,
        'completed': kpi_completed,
    }

    search_query = request.GET.get('search', '').strip()
    tab = request.GET.get('tab', 'all')
    sort = request.GET.get('sort', 'recent')
    layout = request.GET.get('layout', 'list')
    if layout not in ('list', 'grid'):
        layout = 'list'

    projects = base_qs
    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(client__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if tab == 'in_progress':
        projects = projects.filter(status__in=['planning', 'in_progress'])
    elif tab == 'on_hold':
        projects = projects.filter(status='on_hold')
    elif tab == 'completed':
        projects = projects.filter(status='completed')
    else:
        tab = 'all'
        projects = projects.exclude(status='cancelled')

    sort_map = {
        'recent': '-created_at',
        'name': 'name',
        'deadline': 'end_date',
        'progress': '-progress',
    }
    if sort not in sort_map:
        sort = 'recent'
    projects = projects.annotate(
        member_count=Count('assigned_employees', distinct=True),
        task_total=Count('tasks', filter=~Q(tasks__status='cancelled'), distinct=True),
        task_done=Count('tasks', filter=Q(tasks__status='completed'), distinct=True),
    ).order_by(sort_map[sort])

    paginator = Paginator(projects, 5)
    page_obj = paginator.get_page(request.GET.get('page'))

    query = {
        'search': search_query,
        'tab': tab,
        'sort': sort,
        'layout': layout,
    }
    querystring = urlencode({k: v for k, v in query.items() if v})

    return render(request, 'projects/project_employee.html', {
        'page_obj': page_obj,
        'projects': page_obj.object_list,
        'search_query': search_query,
        'tab': tab,
        'sort': sort,
        'layout': layout,
        'querystring': querystring,
        'tab_counts': tab_counts,
        'kpi_active': kpi_active,
        'kpi_completed': kpi_completed,
        'kpi_on_hold': kpi_on_hold,
        'kpi_teams': kpi_teams,
        'kpi_deadlines': kpi_deadlines,
        'total_count': paginator.count,
        'has_unlinked_tasks': Task.objects.filter(
            assigned_to=_employee_or_none(request.user),
            project__isnull=True,
        ).exclude(status='cancelled').exists() if _employee_or_none(request.user) else False,
    })


@login_required
def project_detail(request, pk):
    project = get_object_or_404(
        Project.objects.prefetch_related('assigned_employees__user'),
        pk=pk,
    )
    if not request.user.is_admin():
        employee = _employee_or_none(request.user)
        participates = employee and (
            project.assigned_employees.filter(pk=employee.pk).exists()
            or project.tasks.filter(assigned_to=employee).exists()
        )
        if not participates:
            messages.error(request, "Vous n'avez pas accès à ce projet.")
            return redirect('projects:list')
    from projects.progress import sync_project_progress
    sync_project_progress(project.pk)
    project.refresh_from_db()

    today = timezone.localdate()
    tasks = list(
        project.tasks.select_related('assigned_to__user').exclude(status='cancelled').order_by('due_date', 'title')
    )
    late = [task for task in tasks if task.is_overdue]
    late_ids = {task.pk for task in late}
    done = [task for task in tasks if task.status == 'completed']
    doing = [task for task in tasks if task.status in ('in_progress', 'review') and task.pk not in late_ids]
    waiting = [task for task in tasks if task.status in ('todo', 'not_done') and task.pk not in late_ids]
    team = list(project.assigned_employees.select_related('user').order_by('user__last_name', 'user__first_name'))
    leader = next((member for member in team if member.position == 'project_manager'), team[0] if team else None)
    comments = [task for task in tasks if (task.comments or '').strip()]
    tab = request.GET.get('onglet', 'apercu')
    if tab not in {'apercu', 'taches', 'membres', 'documents', 'commentaires'}:
        tab = 'apercu'
    if project.is_overdue:
        remaining_label = 'Échéance dépassée'
    elif project.days_remaining == 1:
        remaining_label = '1 jour'
    else:
        remaining_label = f'{project.days_remaining} jours'
    user = request.user
    initials = (
        f'{(user.first_name[:1] if user.first_name else "")}'
        f'{(user.last_name[:1] if user.last_name else "")}'
    ).upper() or user.username[:2].upper()

    profile = _employee_or_none(user)
    return render(request, 'projects/project_detail.html', {
        'project': project,
        'tasks': tasks,
        'shown_tasks': tasks if tab == 'taches' else sorted(tasks, key=lambda task: task.updated_at, reverse=True)[:6],
        'task_done': done,
        'task_doing': doing,
        'task_waiting': waiting,
        'task_late': late,
        'team': team,
        'leader': leader,
        'comments': comments,
        'tab': tab,
        'remaining_label': remaining_label,
        'today_label': date_format(today, 'l j F Y').capitalize(),
        'viewer_initials': initials,
        'viewer_name': (user.get_full_name() or '').strip() or user.username,
        'viewer_role': 'Responsable' if user.is_admin() else (profile.get_position_display() if profile else 'Employé'),
    })


@login_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            if not request.user.is_admin():
                employee = _employee_or_none(request.user)
                if employee:
                    project.assigned_employees.add(employee)
            messages.success(request, f'Projet {project.name} créé avec succès.')
            return redirect('projects:detail', pk=project.pk)
    else:
        form = ProjectForm()

    return render(request, 'projects/project_form.html', {'form': form, 'title': 'Ajouter un projet'})


@admin_required
def project_update(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save()
            messages.success(request, f'Projet {project.name} mis à jour avec succès.')
            return redirect('projects:detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project)

    return render(request, 'projects/project_form.html', {'form': form, 'title': 'Modifier le projet', 'project': project})


@admin_required
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if request.method == 'POST':
        project.delete()
        messages.success(request, f'Projet {project.name} supprimé avec succès.')
        return redirect('projects:list')

    return render(request, 'projects/project_confirm_delete.html', {'project': project})
