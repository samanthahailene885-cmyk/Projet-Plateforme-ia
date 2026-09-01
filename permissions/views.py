from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from .models import PermissionRequest
from .forms import PermissionRequestForm, PermissionApprovalForm, PermissionSearchForm


@login_required
def permission_list(request):
    if request.user.is_admin():
        permissions = PermissionRequest.objects.select_related('employee__user').all()
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
        return render(request, 'permissions/permission_list.html', {
            'permissions': permissions,
            'form': form,
        })

    try:
        employee = request.user.employee_profile
        queryset = PermissionRequest.objects.filter(employee=employee)
    except Exception:
        employee = None
        queryset = PermissionRequest.objects.none()

    if request.method == 'POST' and employee:
        form = PermissionRequestForm(request.POST, request.FILES)
        if form.is_valid():
            permission = form.save(commit=False)
            permission.employee = employee
            permission.save()
            messages.success(request, 'Demande de permission envoyée avec succès.')
            return redirect('permissions:list')
    else:
        form = PermissionRequestForm()

    status_filter = request.GET.get('status', '')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    paginator = Paginator(queryset, 8)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'permissions/permission_employee.html', {
        'form': form,
        'page_obj': page_obj,
        'permissions': page_obj.object_list,
        'status_filter': status_filter,
        'total_count': paginator.count,
    })


@login_required
def permission_detail(request, pk):
    permission = get_object_or_404(PermissionRequest, pk=pk)

    if not request.user.is_admin() and permission.employee.user != request.user:
        messages.error(request, 'Vous n\'avez pas le droit de voir cette demande.')
        return redirect('permissions:list')

    return render(request, 'permissions/permission_detail.html', {'permission': permission})


@login_required
def permission_create(request):
    return redirect('permissions:list')


@login_required
def permission_cancel(request, pk):
    if request.method != 'POST':
        return redirect('permissions:list')

    permission = get_object_or_404(PermissionRequest, pk=pk)
    if request.user.is_admin() or permission.employee.user != request.user:
        messages.error(request, 'Vous ne pouvez pas annuler cette demande.')
        return redirect('permissions:list')

    if permission.status != 'pending':
        messages.error(request, 'Seules les demandes en attente peuvent être annulées.')
        return redirect('permissions:list')

    permission.status = 'cancelled'
    permission.decided_at = timezone.now()
    permission.save(update_fields=['status', 'decided_at', 'updated_at'])
    messages.success(request, 'Demande annulée.')
    return redirect('permissions:list')


@login_required
def permission_approve(request, pk):
    if not request.user.is_admin():
        messages.error(request, 'Vous n\'avez pas les droits pour effectuer cette action.')
        return redirect('permissions:list')

    permission = get_object_or_404(PermissionRequest, pk=pk)

    if request.method == 'POST':
        form = PermissionApprovalForm(request.POST, instance=permission)
        if form.is_valid():
            permission = form.save(commit=False)
            permission.decided_at = timezone.now()
            permission.save()
            status = 'approuvée' if permission.status == 'approved' else 'refusée'
            messages.success(request, f'Demande {status} avec succès.')
            return redirect('permissions:detail', pk=permission.pk)
    else:
        form = PermissionApprovalForm(instance=permission)

    return render(request, 'permissions/permission_approve.html', {'form': form, 'permission': permission})
