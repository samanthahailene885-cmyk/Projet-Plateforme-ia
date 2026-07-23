from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect


def admin_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin():
            messages.error(request, 'Accès réservé aux administrateurs.')
            return redirect('tasks:list')
        return view_func(request, *args, **kwargs)
    return wrapper
