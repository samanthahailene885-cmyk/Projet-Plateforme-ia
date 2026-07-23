from django.db import models
from django.utils.translation import gettext_lazy as _
from authentication.models import User


class Notification(models.Model):
    """
    Modèle Notification - Système de notifications en temps réel
    """
    NOTIFICATION_TYPES = [
        ('info', _('Information')),
        ('success', _('Succès')),
        ('warning', _('Avertissement')),
        ('danger', _('Danger')),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Utilisateur')
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_('Titre')
    )
    message = models.TextField(
        verbose_name=_('Message')
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='info',
        verbose_name=_('Type de notification')
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name=_('Lu')
    )
    link = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Lien')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Créé le')
    )
    
    class Meta:
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
