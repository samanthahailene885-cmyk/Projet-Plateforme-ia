from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Notification


@login_required
def notification_list(request):
    """
    Vue de la liste des notifications de l'utilisateur
    """
    notifications = Notification.objects.filter(user=request.user)
    unread_count = notifications.filter(is_read=False).count()
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    return render(request, 'notifications/notification_list.html', context)


@login_required
def mark_as_read(request, pk):
    """
    Vue pour marquer une notification comme lue
    """
    if request.method == 'POST':
        notification = Notification.objects.filter(pk=pk, user=request.user).first()
        if notification:
            notification.is_read = True
            notification.save()
            return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def mark_all_as_read(request):
    """
    Vue pour marquer toutes les notifications comme lues
    """
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def notification_count(request):
    """
    Vue API pour obtenir le nombre de notifications non lues
    """
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})
