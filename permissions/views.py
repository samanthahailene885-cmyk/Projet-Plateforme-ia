from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import PermissionRequest
from .forms import PermissionRequestForm, PermissionApprovalForm, PermissionSearchForm


@login_required
def permission_list(request):
    """
    Vue de la liste des demandes de permission
    """
    # Si l'utilisateur est admin, il voit toutes les demandes
    if request.user.is_admin():
        permissions = PermissionRequest.objects.select_related('employee__user').all()
    else:
        # Sinon, l'utilisateur ne voit que ses propres demandes
        try:
            employee = request.user.employee_profile
            permissions = PermissionRequest.objects.filter(employee=employee)
        except:
            permissions = PermissionRequest.objects.none()
    
    # Filtrage
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    
    if status_filter:
        permissions = permissions.filter(status=status_filter)
    
    if type_filter:
        permissions = permissions.filter(type=type_filter)
    
    form = PermissionSearchForm(initial={
        'status': status_filter,
        'type': type_filter
    })
    
    context = {
        'permissions': permissions,
        'form': form,
    }
    return render(request, 'permissions/permission_list.html', context)


@login_required
def permission_detail(request, pk):
    """
    Vue de détail d'une demande de permission
    """
    permission = get_object_or_404(PermissionRequest, pk=pk)
    
    # Vérifier que l'utilisateur a le droit de voir cette demande
    if not request.user.is_admin() and permission.employee.user != request.user:
        messages.error(request, 'Vous n\'avez pas le droit de voir cette demande.')
        return redirect('permissions:list')
    
    return render(request, 'permissions/permission_detail.html', {'permission': permission})


@login_required
def permission_create(request):
    """
    Vue de création d'une demande de permission
    """
    if request.method == 'POST':
        form = PermissionRequestForm(request.POST)
        if form.is_valid():
            try:
                employee = request.user.employee_profile
                permission = form.save(commit=False)
                permission.employee = employee
                permission.save()
                messages.success(request, 'Demande de permission envoyée avec succès.')
                return redirect('permissions:detail', pk=permission.pk)
            except:
                messages.error(request, 'Vous devez avoir un profil employé pour faire une demande.')
                return redirect('permissions:list')
    else:
        form = PermissionRequestForm()
    
    return render(request, 'permissions/permission_form.html', {'form': form, 'title': 'Nouvelle demande de permission'})


@login_required
def permission_approve(request, pk):
    """
    Vue d'approbation/refus de permission (admin uniquement)
    """
    if not request.user.is_admin():
        messages.error(request, 'Vous n\'avez pas les droits pour effectuer cette action.')
        return redirect('permissions:list')
    
    permission = get_object_or_404(PermissionRequest, pk=pk)
    
    if request.method == 'POST':
        form = PermissionApprovalForm(request.POST, instance=permission)
        if form.is_valid():
            form.save()
            status = 'approuvée' if permission.status == 'approved' else 'refusée'
            messages.success(request, f'Demande {status} avec succès.')
            return redirect('permissions:detail', pk=permission.pk)
    else:
        form = PermissionApprovalForm(instance=permission)
    
    return render(request, 'permissions/permission_approve.html', {'form': form, 'permission': permission})
