"""Lecture du texte déjà présent dans un PDF ou un DOCX importé."""
import io
import re
import zipfile
from xml.etree import ElementTree


def extract_report_text(uploaded):
    name = (getattr(uploaded, 'name', '') or '').lower()
    data = uploaded.read()
    uploaded.seek(0)
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


def _pdf_text(data):
    chunks = []
    for match in re.finditer(br'\(((?:\\\)|[^)]){3,})\)', data):
        raw = match.group(1).replace(b'\\(', b'(').replace(b'\\)', b')').replace(b'\\n', b'\n')
        text = raw.decode('latin-1', errors='ignore').strip()
        letters = sum(character.isalpha() for character in text)
        if letters >= 3:
            chunks.append(text)
    return '\n'.join(chunks).strip()[:20000]
