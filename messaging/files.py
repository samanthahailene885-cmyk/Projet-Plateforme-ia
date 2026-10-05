"""Pièces jointes de la messagerie, sur le même principe que les justificatifs."""
import os

from django.core.exceptions import ValidationError

from tasks.files import validate_pdf

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    '.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif',
    '.doc', '.docx', '.xls', '.xlsx', '.txt',
}


def _extension(name):
    base = os.path.basename(name or '')
    return os.path.splitext(base)[1].lower()


def validate_message_file(uploaded):
    name = os.path.basename(getattr(uploaded, 'name', '') or '')
    ext = _extension(name)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError('Le fichier doit être un PDF, une image ou un document (Word, Excel, texte).')
    size = getattr(uploaded, 'size', 0) or 0
    if size > MAX_ATTACHMENT_BYTES:
        raise ValidationError('Le fichier ne doit pas dépasser 10 Mo.')
    if ext == '.pdf':
        validate_pdf(uploaded)
        return name, size
    if ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
        header = uploaded.read(16)
        uploaded.seek(0)
        ok = (
            (ext in {'.jpg', '.jpeg'} and header.startswith(b'\xff\xd8'))
            or (ext == '.png' and header.startswith(b'\x89PNG'))
            or (ext == '.gif' and header.startswith(b'GIF8'))
            or (ext == '.webp' and header.startswith(b'RIFF') and header[8:12] == b'WEBP')
        )
        if not ok:
            raise ValidationError(f'« {name} » n\'est pas une image valide.')
    return name, size
