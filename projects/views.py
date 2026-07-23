from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Project
from .forms import ProjectForm, ProjectSearchForm


@login_required
def project_list(request):
    """
    Vue de la liste des projets avec recherche et filtrage
    """
    projects = Project.objects.all()
    
    # Recherche et filtrage
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
    
    context = {
        'projects': projects,
        'form': form,
        'search_query': search_query,
    }
    return render(request, 'projects/project_list.html', context)


@login_required
def project_detail(request, pk):
    """
    Vue de détail d'un projet
    """
    project = get_object_or_404(Project, pk=pk)
    return render(request, 'projects/project_detail.html', {'project': project})


@login_required
def project_create(request):
    """
    Vue de création d'un projet
    """
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            messages.success(request, f'Projet {project.name} créé avec succès.')
            return redirect('projects:detail', pk=project.pk)
    else:
        form = ProjectForm()
    
    return render(request, 'projects/project_form.html', {'form': form, 'title': 'Ajouter un projet'})


@login_required
def project_update(request, pk):
    """
    Vue de mise à jour d'un projet
    """
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


@login_required
def project_delete(request, pk):
    """
    Vue de suppression d'un projet
    """
    project = get_object_or_404(Project, pk=pk)
    
    if request.method == 'POST':
        project.delete()
        messages.success(request, f'Projet {project.name} supprimé avec succès.')
        return redirect('projects:list')
    
    return render(request, 'projects/project_confirm_delete.html', {'project': project})
