from django.db import models
from django.utils.translation import gettext_lazy as _
from authentication.models import User


class AISummary(models.Model):
    """
    Modèle AISummary - Résumés intelligents générés par l'IA
    """
    generated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ai_summaries',
        verbose_name=_('Généré par')
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_('Titre')
    )
    content = models.TextField(
        verbose_name=_('Contenu')
    )
    summary_type = models.CharField(
        max_length=50,
        verbose_name=_('Type de résumé')
    )
    reference_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Date concernée')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Créé le')
    )
    
    class Meta:
        verbose_name = _('Résumé IA')
        verbose_name_plural = _('Résumés IA')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.created_at.strftime('%d/%m/%Y')}"


class AIChat(models.Model):
    """
    Modèle AIChat - Historique des conversations avec l'assistant IA
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ai_chats',
        verbose_name=_('Utilisateur')
    )
    question = models.TextField(
        verbose_name=_('Question')
    )
    answer = models.TextField(
        verbose_name=_('Réponse')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Créé le')
    )
    
    class Meta:
        verbose_name = _('Conversation IA')
        verbose_name_plural = _('Conversations IA')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%d/%m/%Y %H:%i')}"


class OperationalAlert(models.Model):
    """Risque opérationnel suivi dans le Centre d'alerte existant.

    L'identifiant stable empêche de recréer la même situation à chaque analyse.
    """

    KIND_CHOICES = [
        ('task_late', _('Tâche en retard')),
        ('task_soon', _('Échéance proche')),
        ('project_pile', _('Tâches en retard sur un projet')),
        ('project_end', _('Fin de projet dépassée')),
        ('difficulty', _('Difficulté ouverte')),
    ]
    SEVERITY_CHOICES = [
        ('high', _('Élevé')),
        ('medium', _('À suivre')),
        ('low', _('Modéré')),
    ]
    STATUS_CHOICES = [
        ('open', _('Ouvert')),
        ('resolved', _('Résolu')),
    ]

    fingerprint = models.CharField(max_length=80, unique=True, verbose_name=_('Identifiant stable'))
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, verbose_name=_('Situation'))
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, verbose_name=_('Gravité'))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open', verbose_name=_('Suivi'))
    subject = models.CharField(max_length=200, verbose_name=_('Sujet'))
    project = models.ForeignKey(
        'projects.Project', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='operational_alerts', verbose_name=_('Projet'),
    )
    task = models.ForeignKey(
        'tasks.Task', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='operational_alerts', verbose_name=_('Tâche'),
    )
    cause = models.TextField(verbose_name=_('Cause détectée'))
    recommendation = models.TextField(verbose_name=_('Recommandation'))
    due_date = models.DateField(null=True, blank=True, verbose_name=_('Échéance'))
    score = models.PositiveSmallIntegerField(verbose_name=_('Score'))
    score_detail = models.TextField(verbose_name=_('Explication du score'))
    url = models.CharField(max_length=300, blank=True, verbose_name=_('Lien'))
    first_seen = models.DateField(verbose_name=_('Détecté le'))
    last_seen = models.DateField(verbose_name=_('Revu le'))
    resolved_on = models.DateField(null=True, blank=True, verbose_name=_('Résolu le'))
    notified = models.BooleanField(default=False, verbose_name=_('Responsable prévenu'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Alerte opérationnelle')
        verbose_name_plural = _('Alertes opérationnelles')
        ordering = ['-score', '-last_seen']

    def __str__(self):
        return f'{self.subject} ({self.get_severity_display()})'
