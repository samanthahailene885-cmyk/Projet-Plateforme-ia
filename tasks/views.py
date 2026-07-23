from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Task
from .forms import TaskForm, TaskSearchForm


@login_required
def task_list(request):
    """
    Vue de la liste des tâches avec recherche et filtrage
    """
    tasks = Task.objects.select_related('project', 'assigned_to__user').all()
    
    # Filtrer par employé si ce n'est pas un admin
    if not request.user.is_admin():
        try:
            employee = request.user.employee_profile
            tasks = tasks.filter(assigned_to=employee)
        except:
            pass
    
    # Recherche et filtrage
    search_query = request.GET.get('search', '')
    project_filter = request.GET.get('project', '')
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    assigned_filter = request.GET.get('assigned_to', '')
    
    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if project_filter:
        tasks = tasks.filter(project_id=project_filter)
    
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    
    if assigned_filter:
        tasks = tasks.filter(assigned_to_id=assigned_filter)
    
    form = TaskSearchForm(initial={
        'search': search_query,
        'project': project_filter,
        'status': status_filter,
        'priority': priority_filter,
        'assigned_to': assigned_filter
    })
    
    context = {
        'tasks': tasks,
        'form': form,
        'search_query': search_query,
    }
    return render(request, 'tasks/task_list.html', context)


@login_required
def task_detail(request, pk):
    """
    Vue de détail d'une tâche
    """
    task = get_object_or_404(Task, pk=pk)
    return render(request, 'tasks/task_detail.html', {'task': task})


@login_required
def task_create(request):
    """
    Vue de création d'une tâche
    """
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            # Si assigned_to n'est pas défini et que l'utilisateur a un profil employé, l'assigner à lui-même
            if not task.assigned_to:
                try:
                    task.assigned_to = request.user.employee_profile
                except:
                    pass
            task.save()
            messages.success(request, f'Tâche {task.title} créée avec succès.')
            return redirect('tasks:detail', pk=task.pk)
        else:
            # Afficher les erreurs de formulaire pour le débogage
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = TaskForm()

    return render(request, 'tasks/task_form.html', {'form': form, 'title': 'Ajouter une tâche'})


@login_required
def task_update(request, pk):
    """
    Vue de mise à jour d'une tâche
    """
    task = get_object_or_404(Task, pk=pk)
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save()
            messages.success(request, f'Tâche {task.title} mise à jour avec succès.')
            return redirect('tasks:detail', pk=task.pk)
    else:
        form = TaskForm(instance=task)
    
    return render(request, 'tasks/task_form.html', {'form': form, 'title': 'Modifier la tâche', 'task': task})


@login_required
def task_delete(request, pk):
    """
    Vue de suppression d'une tâche
    """
    task = get_object_or_404(Task, pk=pk)

    if request.method == 'POST':
        task.delete()
        messages.success(request, f'Tâche {task.title} supprimée avec succès.')
        return redirect('tasks:list')

    return render(request, 'tasks/task_confirm_delete.html', {'task': task})


@login_required
def task_complete(request, pk):
    """
    Vue pour marquer une tâche comme terminée
    """
    task = get_object_or_404(Task, pk=pk)

    # Vérifier que l'utilisateur a le droit de modifier cette tâche
    if not request.user.is_admin() and task.assigned_to != request.user.employee_profile:
        messages.error(request, 'Vous n\'avez pas le droit de modifier cette tâche.')
        return redirect('tasks:list')

    if request.method == 'POST':
        task.status = 'completed'
        task.save()
        messages.success(request, f'Tâche {task.title} marquée comme terminée.')
        return redirect('tasks:list')

    return redirect('tasks:list')
