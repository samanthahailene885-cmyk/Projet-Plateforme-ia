from django.conf import settings
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
        ('not_done', _('Non réalisée')),
        ('cancelled', _('Annulé')),
    ]

    CLOSED_STATUSES = ('completed', 'cancelled', 'not_done')
    
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
    start_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Date de début')
    )
    due_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Date limite')
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tasks',
        verbose_name=_('Créée par'),
    )
    planned_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Jour prévu'),
        help_text=_('Journée de la todo list à laquelle cette activité est rattachée.')
    )
    block_title = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_('Bloc du plan'),
        help_text=_('Titre du groupe affiché sur le plan de travail, par exemple « Analyse du site actuel ».')
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

    PRIORITY_LABELS = {
        'low': 'Faible',
        'medium': 'Moyenne',
        'high': 'Élevée',
        'urgent': 'Urgente',
    }

    def __str__(self):
        if self.project_id:
            return f"{self.title} - {self.project.name}"
        return self.title
    
    @property
    def priority_label(self):
        return self.PRIORITY_LABELS.get(self.priority, self.get_priority_display())

    @property
    def is_overdue(self):
        from django.utils import timezone
        return bool(
            self.due_date
            and self.due_date < timezone.now().date()
            and self.status not in self.CLOSED_STATUSES
        )
    
    @property
    def days_remaining(self):
        from django.utils import timezone
        if self.due_date:
            delta = self.due_date - timezone.now().date()
            return delta.days if delta.days > 0 else 0
        return None


class DailyPlan(models.Model):
    """En-tête du plan de travail d'une journée pour un employé."""
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='daily_plans',
        verbose_name=_('Employé')
    )
    date = models.DateField(verbose_name=_('Date'))
    objective = models.CharField(
        max_length=220,
        blank=True,
        verbose_name=_('Objectif du jour')
    )

    class Meta:
        verbose_name = _('Plan du jour')
        verbose_name_plural = _('Plans du jour')
        unique_together = ['employee', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.employee.full_name} — {self.date}"


class TaskDocument(models.Model):
    """PDF joint à une tâche par le responsable."""
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_('Tâche'),
    )
    original_name = models.CharField(max_length=255, verbose_name=_('Nom du fichier'))
    file = models.FileField(upload_to='task_documents/%Y/%m/', verbose_name=_('Fichier'))
    file_size = models.PositiveIntegerField(default=0, verbose_name=_('Taille'))
    mime_type = models.CharField(max_length=100, default='application/pdf', verbose_name=_('Type MIME'))
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_task_documents',
        verbose_name=_('Ajouté par'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Ajouté le'))

    class Meta:
        verbose_name = _('Document de tâche')
        verbose_name_plural = _('Documents de tâche')
        ordering = ['original_name']

    def __str__(self):
        return self.original_name

    @property
    def size_label(self):
        size = self.file_size or 0
        if size < 1024:
            return f'{size} o'
        if size < 1024 * 1024:
            return f'{size / 1024:.1f} Ko'
        return f'{size / (1024 * 1024):.1f} Mo'
