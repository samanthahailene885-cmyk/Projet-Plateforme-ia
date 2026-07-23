from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db.models import Q
from .models import Employee
from .forms import EmployeeForm, EmployeeSearchForm


@login_required
def employee_list(request):
    """
    Vue de la liste des employés avec recherche et filtrage
    """
    employees = Employee.objects.select_related('user').all()
    
    # Recherche et filtrage
    search_query = request.GET.get('search', '')
    position_filter = request.GET.get('position', '')
    status_filter = request.GET.get('status', '')
    
    if search_query:
        employees = employees.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(position__icontains=search_query)
        )
    
    if position_filter:
        employees = employees.filter(position=position_filter)
    
    if status_filter:
        employees = employees.filter(status=status_filter)
    
    form = EmployeeSearchForm(initial={
        'search': search_query,
        'position': position_filter,
        'status': status_filter
    })
    
    context = {
        'employees': employees,
        'form': form,
        'search_query': search_query,
    }
    return render(request, 'employees/employee_list.html', context)


@login_required
def employee_detail(request, pk):
    """
    Vue de détail d'un employé
    """
    employee = get_object_or_404(Employee, pk=pk)
    return render(request, 'employees/employee_detail.html', {'employee': employee})


@login_required
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


@login_required
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


@login_required
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
