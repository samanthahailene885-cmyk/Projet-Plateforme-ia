"""Vérification des rapports importés par l'employé."""
import os

from django.core.exceptions import ValidationError

MAX_REPORT_BYTES = 10 * 1024 * 1024


def validate_report_file(uploaded):
    name = os.path.basename(getattr(uploaded, 'name', '') or '')
    lower = name.lower()
    size = getattr(uploaded, 'size', 0) or 0
    if size > MAX_REPORT_BYTES:
        raise ValidationError(f'« {name or "Fichier"} » dépasse la taille maximale de 10 Mo.')
    if lower.endswith('.pdf'):
        return _validate_pdf(uploaded, name)
    if lower.endswith('.docx'):
        return _validate_docx(uploaded, name)
    raise ValidationError('Formats acceptés : PDF et DOCX.')


def _validate_pdf(uploaded, name):
    header = uploaded.read(5)
    uploaded.seek(0)
    if header != b'%PDF-':
        raise ValidationError(f"« {name} » n'est pas un fichier PDF valide.")
    content_type = getattr(uploaded, 'content_type', '') or ''
    if content_type and content_type not in (
        'application/pdf', 'application/x-pdf', 'application/octet-stream',
    ):
        raise ValidationError(f"« {name} » n'est pas un PDF.")
    return name


def _validate_docx(uploaded, name):
    header = uploaded.read(4)
    uploaded.seek(0)
    if header != b'PK\x03\x04':
        raise ValidationError(f"« {name} » n'est pas un fichier Word valide.")
    content_type = getattr(uploaded, 'content_type', '') or ''
    allowed = {
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/octet-stream',
        'application/zip',
    }
    if content_type and content_type not in allowed:
        raise ValidationError(f"« {name} » n'est pas un fichier Word.")
    return name
