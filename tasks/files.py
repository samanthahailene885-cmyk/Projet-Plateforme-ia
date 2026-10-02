"""Vérification des PDF joints aux tâches."""
import os

from django.core.exceptions import ValidationError

MAX_PDF_BYTES = 10 * 1024 * 1024


def validate_pdf(uploaded):
    name = os.path.basename(getattr(uploaded, 'name', '') or '')
    if not name.lower().endswith('.pdf'):
        raise ValidationError(f"« {name or 'Fichier'} » n'est pas un PDF.")
    size = getattr(uploaded, 'size', 0) or 0
    if size > MAX_PDF_BYTES:
        raise ValidationError(f'« {name} » dépasse la taille maximale de 10 Mo.')
    header = uploaded.read(5)
    uploaded.seek(0)
    if header != b'%PDF-':
        raise ValidationError(f"« {name} » n'est pas un fichier PDF valide.")
    content_type = getattr(uploaded, 'content_type', '') or ''
    if content_type and content_type not in ('application/pdf', 'application/x-pdf', 'application/octet-stream'):
        raise ValidationError(f"« {name} » n'est pas un PDF.")
    return name
