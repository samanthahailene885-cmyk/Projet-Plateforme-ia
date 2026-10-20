"""Lecture du texte déjà présent dans un PDF ou un DOCX importé."""
import io
import zipfile
from xml.etree import ElementTree


def extract_report_text(uploaded):
    name = (getattr(uploaded, 'name', '') or '').lower()
    data = uploaded.read()
    try:
        uploaded.seek(0)
    except (AttributeError, OSError):
        pass
    if name.endswith('.docx'):
        return _docx_text(data)
    if name.endswith('.pdf'):
        return _pdf_text(data)
    return ''


def _docx_text(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read('word/document.xml')
    except (KeyError, zipfile.BadZipFile, OSError):
        return ''
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return ''
    parts = [
        node.text.strip()
        for node in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
        if node.text and node.text.strip()
    ]
    return '\n'.join(parts).strip()[:20000]


def _readable(text):
    letters = sum(character.isalpha() for character in text)
    return letters >= 20 and letters >= len(text) * 0.25


def _pdf_text(data):
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        parts = [(page.extract_text() or '').strip() for page in reader.pages]
    except Exception:
        return ''
    text = '\n'.join(part for part in parts if part).strip()
    if not _readable(text):
        return ''
    return text[:20000]
