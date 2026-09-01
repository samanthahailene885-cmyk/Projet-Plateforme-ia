from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from authentication.decorators import admin_required
from employees.models import Employee
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
    return projects.filter(assigned_employees=employee).distinct()


@login_required
def project_list(request):
    """
    Liste des projets : vue admin complète, vue employé (mes projets).
    """
    base_qs = _visible_projects(request)

    if not request.user.is_admin():
        return _employee_project_list(request, base_qs)

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

    if status_filter:
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
        member_count=Count('assigned_employees', distinct=True)
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
    })


@login_required
def project_detail(request, pk):
    project = get_object_or_404(
        Project.objects.prefetch_related('assigned_employees__user'),
        pk=pk,
    )
    if not request.user.is_admin():
        employee = _employee_or_none(request.user)
        if not employee or not project.assigned_employees.filter(pk=employee.pk).exists():
            messages.error(request, "Vous n'avez pas accès à ce projet.")
            return redirect('projects:list')
    return render(request, 'projects/project_detail.html', {'project': project})


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
