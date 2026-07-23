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
