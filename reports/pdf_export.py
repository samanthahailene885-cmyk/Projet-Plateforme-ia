import re
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ORANGE = HexColor('#E84E1B')
PAGE_W = 595.5
PAGE_H = 842.25

DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
MONTHS = [
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

ASSETS = Path(__file__).resolve().parent.parent / 'static' / 'reports'
FONT_DIR = ASSETS / 'fonts'
BACKGROUND = ASSETS / 'rapport-fond.png'


def _register_fonts():
    files = {
        'JournalHand': 'ShadowsIntoLightTwo-Regular.ttf',
        'JournalSans': 'Montserrat-Regular.ttf',
        'JournalSans-Med': 'Montserrat-Medium.ttf',
        'JournalSans-Bold': 'Montserrat-SemiBold.ttf',
    }
    registered = set(pdfmetrics.getRegisteredFontNames())
    for name, filename in files.items():
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))


def journal_person_name(user):
    last = (user.last_name or '').strip()
    if last:
        return last.upper()
    full = f'{user.first_name} {user.last_name}'.strip()
    return (full or user.username).upper()


def journal_date_label(day):
    return f'{DAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]} {day.year}'


def journal_bullets(content):
    text = (content or '').replace('\r\n', '\n').strip()
    if not text:
        return []
    bullets = []
    for block in re.split(r'\n\s*\n', text):
        line = ' '.join(part.strip() for part in block.splitlines() if part.strip())
        line = re.sub(r'^[■•\-\s]+', '', line).strip()
        if line:
            bullets.append(line)
    return bullets


def report_reading(report):
    return {
        'name': journal_person_name(report.employee),
        'date_label': journal_date_label(report.date),
        'bullets': journal_bullets(report.content),
    }


def _draw_page(canvas, doc, report):
    canvas.saveState()
    canvas.drawImage(
        str(BACKGROUND), 0, 0, width=PAGE_W, height=PAGE_H,
        preserveAspectRatio=False, mask='auto',
    )
    label = 'DATE DU JOUR : '
    date = journal_date_label(report.date)
    label_size = 8
    date_size = 10
    label_w = canvas.stringWidth(label, 'JournalSans', label_size)
    date_w = canvas.stringWidth(date, 'JournalSans-Bold', date_size)
    pad_x = 12
    width = label_w + date_w + pad_x * 2
    height = 24
    x = min(PAGE_W - 26 - width, 338)
    x = max(x, 250)
    y = PAGE_H - 96
    canvas.setFillColor(ORANGE)
    canvas.roundRect(x, y, width, height, 7, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont('JournalSans', label_size)
    canvas.drawString(x + pad_x, y + 8, label)
    canvas.setFont('JournalSans-Bold', date_size)
    canvas.drawString(x + pad_x + label_w, y + 7.2, date)
    canvas.restoreState()


def build_daily_report_pdf(report):
    _register_fonts()
    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=(PAGE_W, PAGE_H),
        title=f"Rapport journalier — {journal_person_name(report.employee)}",
        author="RAC'IN AFRICA",
        leftMargin=0,
        rightMargin=0,
        topMargin=0,
        bottomMargin=0,
    )
    frame = Frame(
        40, 92, 518, 548,
        id='body', showBoundary=0,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([
        PageTemplate(
            id='sheet',
            frames=[frame],
            onPage=lambda canvas, doc: _draw_page(canvas, doc, report),
        ),
    ])

    name_style = ParagraphStyle(
        'journal-name',
        fontName='JournalHand',
        fontSize=24,
        leading=28,
        textColor=white,
        spaceAfter=18,
    )
    body_style = ParagraphStyle(
        'journal-body',
        fontName='JournalHand',
        fontSize=22,
        leading=27,
        textColor=white,
    )
    story = [Paragraph(escape(journal_person_name(report.employee)), name_style)]
    bullets = journal_bullets(report.content) or ['Aucune activité rédigée pour cette date.']
    for text in bullets:
        square = Table([['']], colWidths=[8], rowHeights=[8])
        square.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), white),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        row = Table(
            [[square, Paragraph(escape(text), body_style)]],
            colWidths=[18, 490],
        )
        row.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (0, 0), 8),
            ('TOPPADDING', (1, 0), (1, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
        ]))
        story.append(row)
    story.append(Spacer(1, 4))
    doc.build(story)
    return buffer.getvalue()
