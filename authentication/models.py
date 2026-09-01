from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Modèle utilisateur personnalisé avec rôle et photo de profil
    """
    ROLE_CHOICES = [
        ('admin', _('Administrateur')),
        ('employee', _('Employé')),
    ]
    
    GENDER_CHOICES = [
        ('M', _('Homme')),
        ('F', _('Femme')),
        ('O', _('Autre')),
    ]
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='employee',
        verbose_name=_('Rôle')
    )
    photo = models.ImageField(
        upload_to='profile_photos/',
        blank=True,
        null=True,
        verbose_name=_('Photo de profil')
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Téléphone')
    )
    birth_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Date de naissance')
    )
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        null=True,
        verbose_name=_('Genre')
    )
    address = models.TextField(
        blank=True,
        verbose_name=_('Adresse')
    )
    bio = models.TextField(
        blank=True,
        verbose_name=_('Bio')
    )
    
    class Meta:
        verbose_name = _('Utilisateur')
        verbose_name_plural = _('Utilisateurs')
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"
    
    def is_admin(self):
        return self.role == 'admin'

    def get_home_url_name(self):
        return 'dashboard:home' if self.is_admin() else 'dashboard:employee_home'
