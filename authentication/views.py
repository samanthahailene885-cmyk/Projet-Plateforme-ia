from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from .forms import CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm
from .models import User


def login_view(request):
    """
    Vue de connexion
    """
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bienvenue {user.first_name} !')
            return redirect(user.get_home_url_name())
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'authentication/login.html', {'form': form})


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
    return render(request, 'authentication/profile.html', {'user': request.user})


@login_required
def profile_update_view(request):
    """
    Vue de mise à jour du profil
    """
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profil mis à jour avec succès.')
            return redirect('authentication:profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'authentication/profile_update.html', {'form': form})
