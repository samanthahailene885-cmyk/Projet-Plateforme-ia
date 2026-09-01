from django.db import models
from django.utils.translation import gettext_lazy as _
from employees.models import Employee


class PermissionRequest(models.Model):
    """
    Demande de permission / congé / absence.
    """
    TYPE_CHOICES = [
        ('permission', _('Permission')),
        ('annual', _('Congé annuel')),
        ('sick', _('Congé maladie')),
        ('unpaid', _('Congé sans solde')),
        ('absence', _('Absence')),
    ]

    REASON_CHOICES = [
        ('medical', _('Rendez-vous médical')),
        ('vacation', _('Vacances')),
        ('family', _('Raison familiale')),
        ('personal', _('Raison personnelle')),
        ('training', _('Formation')),
        ('other', _('Autre')),
    ]

    STATUS_CHOICES = [
        ('pending', _('En attente')),
        ('approved', _('Approuvée')),
        ('rejected', _('Refusée')),
        ('cancelled', _('Annulée')),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='permission_requests',
        verbose_name=_('Employé')
    )
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name=_('Type de demande')
    )
    start_date = models.DateField(
        verbose_name=_('Date de début')
    )
    end_date = models.DateField(
        verbose_name=_('Date de fin')
    )
    reason_choice = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        blank=True,
        verbose_name=_('Motif')
    )
    reason = models.TextField(
        verbose_name=_('Motif')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    attachment = models.FileField(
        upload_to='permission_attachments/',
        blank=True,
        null=True,
        verbose_name=_('Justificatif')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('Statut')
    )
    admin_comment = models.TextField(
        blank=True,
        verbose_name=_('Commentaire administrateur')
    )
    decided_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Date de décision')
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
        verbose_name = _('Demande de permission')
        verbose_name_plural = _('Demandes de permission')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_type_display()} du {self.start_date} au {self.end_date}"

    @property
    def is_requested_early(self):
        from django.utils import timezone
        delta = self.start_date - timezone.now().date()
        return delta.days >= 3

    @property
    def days_count(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def motif_display(self):
        if self.reason_choice == 'other' and self.reason:
            return self.reason
        if self.reason_choice:
            return self.get_reason_choice_display()
        return self.reason or '—'
