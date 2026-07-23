from django.db import models
from django.utils.translation import gettext_lazy as _
from authentication.models import User


class Employee(models.Model):
    """
    Modèle Employee - Extension du modèle User avec des informations supplémentaires
    """
    STATUS_CHOICES = [
        ('active', _('Actif')),
        ('inactive', _('Inactif')),
        ('on_leave', _('En congé')),
    ]
    
    POSITION_CHOICES = [
        ('designer', _('Designer')),
        ('developer', _('Développeur')),
        ('project_manager', _('Chef de projet')),
        ('marketing', _('Marketing')),
        ('content_writer', _('Rédacteur')),
        ('account_manager', _('Account Manager')),
        ('other', _('Autre')),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='employee_profile',
        verbose_name=_('Utilisateur')
    )
    position = models.CharField(
        max_length=50,
        choices=POSITION_CHOICES,
        verbose_name=_('Poste')
    )
    hire_date = models.DateField(
        verbose_name=_('Date d\'embauche')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_('Statut')
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Département')
    )
    salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Salaire')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Créé le')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Mis à jour le')
    )
    
    class Meta:
        verbose_name = _('Employé')
        verbose_name_plural = _('Employés')
        ordering = ['-hire_date']
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.get_position_display()}"
    
    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"
    
    @property
    def email(self):
        return self.user.email
    
    @property
    def phone(self):
        return self.user.phone
