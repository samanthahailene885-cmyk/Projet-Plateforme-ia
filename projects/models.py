from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from employees.models import Employee


class Project(models.Model):
    """
    Modèle Project - Gestion des projets de l'agence
    """
    STATUS_CHOICES = [
        ('planning', _('Planification')),
        ('in_progress', _('En cours')),
        ('on_hold', _('En pause')),
        ('completed', _('Terminé')),
        ('cancelled', _('Annulé')),
    ]
    
    PRIORITY_CHOICES = [
        ('low', _('Faible')),
        ('medium', _('Moyen')),
        ('high', _('Haute')),
        ('urgent', _('Urgent')),
    ]
    
    name = models.CharField(
        max_length=200,
        verbose_name=_('Nom du projet')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    client = models.CharField(
        max_length=200,
        verbose_name=_('Client')
    )
    start_date = models.DateField(
        verbose_name=_('Date de début')
    )
    end_date = models.DateField(
        verbose_name=_('Date de fin')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planning',
        verbose_name=_('Statut')
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name=_('Priorité')
    )
    progress = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_('Progression (%)')
    )
    budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Budget')
    )
    assigned_employees = models.ManyToManyField(
        Employee,
        related_name='projects',
        blank=True,
        verbose_name=_('Employés assignés')
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
        verbose_name = _('Projet')
        verbose_name_plural = _('Projets')
        ordering = ['-created_at']
    
    ICON_COLORS = (
        '#F97316', '#8B5CF6', '#14B8A6', '#0F172A', '#EC4899',
        '#2563EB', '#22C55E', '#EAB308', '#EF4444', '#06B6D4',
    )

    def __str__(self):
        return f"{self.name} - {self.client}"

    @property
    def initials(self):
        words = [part for part in self.name.split() if part]
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        return (self.name[:2] or 'PR').upper()

    @property
    def accent_color(self):
        return self.ICON_COLORS[self.pk % len(self.ICON_COLORS)]

    @property
    def deadline_label(self):
        if self.status == 'completed':
            return 'Date de fin'
        if self.status == 'on_hold':
            return 'Dernière mise à jour'
        return 'Prochaine échéance'

    @property
    def deadline_value(self):
        if self.status == 'on_hold':
            return self.updated_at.date()
        return self.end_date
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.end_date < timezone.now().date() and self.status != 'completed'
    
    @property
    def days_remaining(self):
        from django.utils import timezone
        delta = self.end_date - timezone.now().date()
        return delta.days if delta.days > 0 else 0
