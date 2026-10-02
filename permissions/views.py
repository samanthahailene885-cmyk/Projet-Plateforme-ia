from datetime import timedelta
from calendar import Calendar

from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.formats import date_format
from .models import PermissionRequest
from .forms import PermissionRequestForm, PermissionApprovalForm, PermissionSearchForm


@login_required
def permission_list(request):
    if request.user.is_admin():
        employee = None
        queryset = PermissionRequest.objects.select_related('employee__user').all()
        form = PermissionRequestForm()
    else:
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
            errors = list(form.non_field_errors())
            for field_errors in form.errors.values():
                errors.extend(field_errors)
            messages.error(
                request,
                errors[0] if errors else 'La demande n\'a pas pu être envoyée. Vérifiez les champs.',
            )
        else:
            form = PermissionRequestForm()

    stats = {
        'total': queryset.count(),
        'pending': queryset.filter(status='pending').count(),
        'approved': queryset.filter(status='approved').count(),
        'rejected': queryset.filter(status='rejected').count(),
    }
    today = timezone.localdate()
    query = (request.GET.get('q') or '').strip()
    status_filter = request.GET.get('status', '')
    period = request.GET.get('periode', '')
    tab = request.GET.get('tab', 'demandes')
    if tab not in ('demandes', 'absences'):
        tab = 'demandes'

    visible = queryset
    if tab == 'absences':
        visible = visible.filter(type='absence')
    else:
        visible = visible.exclude(type='absence')
    if query:
        visible = visible.filter(
            Q(reason__icontains=query)
            | Q(description__icontains=query)
            | Q(employee__user__first_name__icontains=query)
            | Q(employee__user__last_name__icontains=query)
        )
    if status_filter:
        visible = visible.filter(status=status_filter)
    if period == 'mois':
        visible = visible.filter(start_date__year=today.year, start_date__month=today.month)
    elif period == 'avenir':
        visible = visible.filter(end_date__gte=today)

    paginator = Paginator(visible, 7)
    page_obj = paginator.get_page(request.GET.get('page'))

    try:
        year = int(request.GET.get('annee') or today.year)
        month = int(request.GET.get('mois') or today.month)
        if month < 1 or month > 12:
            raise ValueError
    except ValueError:
        year, month = today.year, today.month
    weeks = Calendar(0).monthdayscalendar(year, month)
    marked_days = set()
    for item in queryset.filter(status='approved'):
        cursor = item.start_date
        while cursor <= item.end_date:
            if cursor.year == year and cursor.month == month:
                marked_days.add(cursor.day)
            cursor += timedelta(days=1)
    month_label = date_format(today.replace(year=year, month=month, day=1), 'F Y').capitalize()
    prev_month = month - 1 or 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    absent_today = list(queryset.filter(status='approved', start_date__lte=today, end_date__gte=today))
    initials = (
        f'{(request.user.first_name[:1] if request.user.first_name else "")}'
        f'{(request.user.last_name[:1] if request.user.last_name else "")}'
    ).upper() or request.user.username[:2].upper()

    return render(request, 'permissions/permission_employee.html', {
        'form': form,
        'show_form': request.method == 'POST' or request.GET.get('nouvelle') == '1',
        'page_obj': page_obj,
        'permissions': page_obj.object_list,
        'status_filter': status_filter,
        'period': period,
        'query': query,
        'tab': tab,
        'total_count': paginator.count,
        'stats': stats,
        'today': today,
        'today_label': date_format(today, 'l j F Y').capitalize(),
        'weeks': weeks,
        'marked_days': marked_days,
        'month_label': month_label,
        'cal_year': year,
        'cal_month': month,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'absent_today': absent_today,
        'initials': initials,
        'employee': employee,
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
