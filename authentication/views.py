from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.views.csrf import csrf_failure as django_csrf_failure
from django.views.generic import CreateView, UpdateView
from .forms import CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm
from .models import User


def login_view(request):
    """
    Fenêtre de connexion isolée : aucun menu ni donnée de la plateforme.
    """
    if request.method == 'GET' and request.user.is_authenticated:
        logout(request)

    if request.method == 'GET' and request.GET.get('expire'):
        messages.warning(
            request,
            "La page de connexion n'est plus valide. Saisissez à nouveau vos identifiants.",
        )

    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if request.POST.get('remember'):
                request.session.set_expiry(60 * 60 * 24 * 30)
            else:
                request.session.set_expiry(0)
            messages.success(request, f'Bienvenue {user.first_name} !')
            return redirect(user.get_home_url_name())
    else:
        form = CustomAuthenticationForm()

    response = render(request, 'authentication/login.html', {'form': form})
    response['Cache-Control'] = 'no-store'
    return response


def csrf_failure(request, reason=""):
    """
    Un jeton périmé sur la connexion renvoie au formulaire, avec un jeton neuf.
    """
    if request.path == reverse('authentication:login'):
        return redirect(f"{reverse('authentication:login')}?expire=1")
    return django_csrf_failure(request, reason=reason)


@login_required
def home_redirect_view(request):
    return redirect(request.user.get_home_url_name())


def logout_view(request):
    """
    Vue de déconnexion
    """
    logout(request)
    messages.info(request, 'Vous avez été déconnecté.')
    return redirect('authentication:login')


class RegisterView(CreateView):
    """
    Vue d'inscription
    """
    model = User
    form_class = CustomUserCreationForm
    template_name = 'authentication/register.html'
    success_url = reverse_lazy('authentication:login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Compte créé avec succès. Vous pouvez maintenant vous connecter.')
        return response


@login_required
def profile_view(request):
    """
    Vue du profil utilisateur
    """
    from tasks.models import Task
    from reports.models import DailyReport
    from attendance.models import Attendance
    from employees.models import Employee
    from django.db.models import Sum, Q
    from datetime import timedelta
    from django.utils import timezone
    
    # Récupérer l'employé associé à l'utilisateur
    try:
        employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        employee = None
    
    # Statistiques des tâches
    if employee:
        assigned_tasks = Task.objects.filter(assigned_to=employee)
        tasks_completed = assigned_tasks.filter(status='completed').count()
        tasks_total = assigned_tasks.count()
        completion_rate = int((tasks_completed / tasks_total * 100) if tasks_total > 0 else 0)
        
        # Heures travaillées (somme des actual_hours des tâches)
        hours_worked = assigned_tasks.aggregate(total_hours=Sum('actual_hours'))['total_hours'] or 0
        hours_worked_int = int(hours_worked)
        hours_worked_min = int((hours_worked - hours_worked_int) * 60)
        hours_worked_str = f"{hours_worked_int}h {hours_worked_min}m" if hours_worked_min > 0 else f"{hours_worked_int}h"
    else:
        tasks_completed = 0
        completion_rate = 0
        hours_worked_str = "0h"
    
    # Rapports envoyés
    reports_sent = DailyReport.objects.filter(employee=request.user).count()
    
    # Activité récente
    recent_activities = [
        {
            'title': 'Rapport quotidien envoyé',
            'description': 'Vous avez envoyé votre rapport quotidien.',
            'time': "Aujourd'hui à 18:45",
            'icon': 'fa-file-alt',
            'color': '#8B5CF6',
            'bg': 'rgba(139,92,246,.12)',
        },
        {
            'title': 'Tâche terminée',
            'description': 'Création de la bannière Facebook',
            'time': "Aujourd'hui à 16:30",
            'icon': 'fa-check',
            'color': '#22C55E',
            'bg': 'rgba(34,197,94,.12)',
        },
        {
            'title': 'Nouvelle tâche assignée',
            'description': 'Conception du visuel pour la campagne JUS\'MO',
            'time': "Aujourd'hui à 10:15",
            'icon': 'fa-tasks',
            'color': '#F97316',
            'bg': 'rgba(249,115,22,.12)',
        },
        {
            'title': 'Demande de permission approuvée',
            'description': 'Congé annuel du 20/07/2025 au 25/07/2025',
            'time': 'Hier à 09:20',
            'icon': 'fa-calendar-check',
            'color': '#EAB308',
            'bg': 'rgba(234,179,8,.12)',
        },
    ]

    # Compétences
    skills = [
        {'name': 'Graphisme', 'percent': 90, 'color': '#22C55E'},
        {'name': 'Design UI/UX', 'percent': 80, 'color': '#8B5CF6'},
        {'name': 'Photoshop', 'percent': 85, 'color': '#F97316'},
        {'name': 'Illustrator', 'percent': 75, 'color': '#2563EB'},
        {'name': 'Communication', 'percent': 95, 'color': '#EC4899'},
    ]

    context = {
        'user': request.user,
        'employee': employee,
        'tasks_completed': tasks_completed,
        'completion_rate': completion_rate,
        'hours_worked': hours_worked_str,
        'reports_sent': reports_sent,
        'recent_activities': recent_activities,
        'skills': skills,
    }
    
    return render(request, 'authentication/profile.html', context)


def _profile_completion(user):
    checks = [
        user.first_name, user.last_name, user.email, user.phone,
        user.photo, user.birth_date, user.gender, user.address, user.bio,
    ]
    filled = sum(1 for value in checks if value)
    return round(filled / len(checks) * 100)


@login_required
def profile_update_view(request):
    """
    Vue de mise à jour du profil
    """
    try:
        employee = request.user.employee_profile
    except Exception:
        employee = None

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profil mis à jour avec succès.')
            return redirect('authentication:profile')
    else:
        form = UserProfileForm(instance=request.user)

    if employee:
        position_label = employee.get_position_display()
    else:
        position_label = request.user.get_role_display()

    return render(request, 'authentication/profile_update.html', {
        'form': form,
        'employee': employee,
        'position_label': position_label,
        'profile_completion': _profile_completion(request.user),
    })
