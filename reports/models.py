from django.db import models
from django.utils.translation import gettext_lazy as _
from authentication.models import User


class DailyReport(models.Model):
    """
    Modèle DailyReport - Rapports quotidiens générés par l'IA
    """
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='daily_reports',
        verbose_name=_('Employé')
    )
    date = models.DateField(
        verbose_name=_('Date')
    )
    content = models.TextField(
        verbose_name=_('Contenu du rapport')
    )
    tasks_completed = models.TextField(
        blank=True,
        verbose_name=_('Tâches terminées')
    )
    tasks_in_progress = models.TextField(
        blank=True,
        verbose_name=_('Tâches en cours')
    )
    ai_generated = models.BooleanField(
        default=True,
        verbose_name=_('Généré par IA')
    )
    uploaded_pdf = models.FileField(
        upload_to='reports/imported/%Y/%m/',
        blank=True,
        verbose_name=_('PDF importé'),
        help_text=_("Rapport PDF envoyé par l'employé, sans génération par l'IA."),
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
        verbose_name = _('Rapport quotidien')
        verbose_name_plural = _('Rapports quotidiens')
        ordering = ['-date']
        unique_together = ['employee', 'date']
    
    def __str__(self):
        return f"Rapport de {self.employee.username} - {self.date}"
