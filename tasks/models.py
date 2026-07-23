from django.db import models
from django.utils.translation import gettext_lazy as _
from projects.models import Project
from employees.models import Employee


class Task(models.Model):
    """
    Modèle Task - Gestion des tâches
    """
    STATUS_CHOICES = [
        ('todo', _('À faire')),
        ('in_progress', _('En cours')),
        ('review', _('En révision')),
        ('completed', _('Terminé')),
        ('cancelled', _('Annulé')),
    ]
    
    PRIORITY_CHOICES = [
        ('low', _('Faible')),
        ('medium', _('Moyen')),
        ('high', _('Haute')),
        ('urgent', _('Urgent')),
    ]
    
    title = models.CharField(
        max_length=200,
        verbose_name=_('Titre')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tasks',
        verbose_name=_('Projet')
    )
    assigned_to = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks',
        verbose_name=_('Assigné à')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='todo',
        verbose_name=_('Statut')
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name=_('Priorité')
    )
    due_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Date limite')
    )
    estimated_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Heures estimées')
    )
    actual_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Heures réelles')
    )
    comments = models.TextField(
        blank=True,
        verbose_name=_('Commentaires')
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
        verbose_name = _('Tâche')
        verbose_name_plural = _('Tâches')
        ordering = ['-priority', 'due_date']
    
    def __str__(self):
        return f"{self.title} - {self.project.name}"
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.due_date and self.due_date < timezone.now().date() and self.status != 'completed'
    
    @property
    def days_remaining(self):
        from django.utils import timezone
        if self.due_date:
            delta = self.due_date - timezone.now().date()
            return delta.days if delta.days > 0 else 0
        return None
