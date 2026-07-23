from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Attendance
from .forms import AttendanceForm, AttendanceSearchForm


@login_required
def attendance_list(request):
    """
    Vue de la liste des présences
    """
    attendances = Attendance.objects.select_related('employee__user').all()
    
    # Filtrage
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    status_filter = request.GET.get('status', '')
    employee_filter = request.GET.get('employee', '')
    
    if date_from:
        attendances = attendances.filter(date__gte=date_from)
    
    if date_to:
        attendances = attendances.filter(date__lte=date_to)
    
    if status_filter:
        attendances = attendances.filter(status=status_filter)
    
    if employee_filter:
        attendances = attendances.filter(employee_id=employee_filter)
    
    form = AttendanceSearchForm(initial={
        'date_from': date_from,
        'date_to': date_to,
        'status': status_filter,
        'employee': employee_filter
    })
    
    context = {
        'attendances': attendances,
        'form': form,
    }
    return render(request, 'attendance/attendance_list.html', context)


@login_required
def attendance_detail(request, pk):
    """
    Vue de détail d'une présence
    """
    attendance = get_object_or_404(Attendance, pk=pk)
    return render(request, 'attendance/attendance_detail.html', {'attendance': attendance})


@login_required
def attendance_create(request):
    """
    Vue de création d'une présence
    """
    if request.method == 'POST':
        form = AttendanceForm(request.POST)
        if form.is_valid():
            attendance = form.save()
            messages.success(request, f'Présence enregistrée pour {attendance.employee.full_name}.')
            return redirect('attendance:detail', pk=attendance.pk)
    else:
        form = AttendanceForm(initial={'date': timezone.now().date()})
    
    return render(request, 'attendance/attendance_form.html', {'form': form, 'title': 'Enregistrer une présence'})


@login_required
def attendance_update(request, pk):
    """
    Vue de mise à jour d'une présence
    """
    attendance = get_object_or_404(Attendance, pk=pk)
    
    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=attendance)
        if form.is_valid():
            attendance = form.save()
            messages.success(request, f'Présence mise à jour pour {attendance.employee.full_name}.')
            return redirect('attendance:detail', pk=attendance.pk)
    else:
        form = AttendanceForm(instance=attendance)
    
    return render(request, 'attendance/attendance_form.html', {'form': form, 'title': 'Modifier la présence', 'attendance': attendance})


@login_required
def attendance_delete(request, pk):
    """
    Vue de suppression d'une présence
    """
    attendance = get_object_or_404(Attendance, pk=pk)
    
    if request.method == 'POST':
        attendance.delete()
        messages.success(request, 'Présence supprimée avec succès.')
        return redirect('attendance:list')
    
    return render(request, 'attendance/attendance_confirm_delete.html', {'attendance': attendance})
