from django.db import models
from django.utils.translation import gettext_lazy as _
from employees.models import Employee


class Attendance(models.Model):
    """
    Modèle Attendance - Suivi de la présence des employés
    """
    STATUS_CHOICES = [
        ('present', _('Présent')),
        ('absent', _('Absent')),
        ('late', _('Retard')),
    ]
    
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name=_('Employé')
    )
    date = models.DateField(
        verbose_name=_('Date')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='present',
        verbose_name=_('Statut')
    )
    check_in_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_('Heure d\'arrivée')
    )
    check_out_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_('Heure de départ')
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes')
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
        verbose_name = _('Présence')
        verbose_name_plural = _('Présences')
        ordering = ['-date', 'employee']
        unique_together = ['employee', 'date']
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.date} - {self.get_status_display()}"
    
    @property
    def is_late(self):
        if self.check_in_time:
            return self.check_in_time > models.TimeField().to_python('09:00:00')
        return False
