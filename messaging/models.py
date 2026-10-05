import os

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Message(models.Model):
    """Message direct entre un responsable et un employé."""

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name=_('Expéditeur'),
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages',
        verbose_name=_('Destinataire'),
    )
    message = models.TextField(blank=True, verbose_name=_('Message'))
    attachment = models.FileField(
        upload_to='messages/%Y/%m/',
        blank=True,
        verbose_name=_('Pièce jointe'),
    )
    attachment_size = models.PositiveIntegerField(default=0, verbose_name=_('Taille du fichier'))
    read_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Lu le'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Créé le'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Mis à jour le'))

    class Meta:
        verbose_name = _('Message')
        verbose_name_plural = _('Messages')
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['receiver', 'read_at']),
        ]

    def __str__(self):
        return f'{self.sender_id} → {self.receiver_id}'

    @property
    def attachment_label(self):
        if not self.attachment:
            return ''
        return os.path.basename(self.attachment.name)
