import mimetypes
import os
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, HttpResponse, JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from authentication.decorators import admin_required
from decision_ai.analytics import employee_report_payload
from decision_ai.briefing import generate_reports_for_day
from decision_ai.models import AISummary
from decision_ai.services import (
    AIServiceError,
    DecisionAIService,
    NoSubmittedReportsError,
    compose_employee_report,
)

from .files import validate_report_file
from .models import DailyReport
from .synthesis import (
    SYNTHESIS_TYPE,
    analyzed_count_from_title,
    collect_team_synthesis,
    synthesis_title,
    synthesis_to_html,
)
from .pdf_export import (
    build_daily_report_pdf,
    journal_date_label,
    journal_person_name,
    journal_bullets,
    report_reading,
)
from .services import ReportGenerator


FRENCH_DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
FRENCH_MONTHS = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

STATUS_CLASS = {
    'completed': 'done',
    'in_progress': 'progress',
    'review': 'progress',
    'todo': 'todo',
    'not_done': 'todo',
    'cancelled': 'todo',
}


def _format_french_date(date):
    return f"{FRENCH_DAYS[date.weekday()]} {date.day} {FRENCH_MONTHS[date.month - 1]} {date.year}"


def _format_size(num):
    mega = num / (1024 * 1024)
    if mega >= 0.1:
        text = f'{mega:.1f}'
        if text.endswith('.0'):
            text = text[:-2]
        return f'{text} Mo'
    kilo = num / 1024
    if kilo >= 1:
        return f'{kilo:.0f} Ko'
    return f'{num} o'


def _report_history(user):
    rows = []
    reports = DailyReport.objects.filter(employee=user).order_by('-updated_at')
    for report in reports:
        stored = ''
        size = '—'
        if report.uploaded_pdf:
            stored = os.path.basename(report.uploaded_pdf.name)
            try:
                size = _format_size(report.uploaded_pdf.size)
            except OSError:
                size = '—'
        filename = report.original_name or stored or f"Rapport_journalier_{report.date.strftime('%d-%m-%Y')}.pdf"
        is_pdf = filename.lower().endswith('.pdf')
        view_url = reverse('reports:pdf', args=[report.pk])
        if is_pdf:
            view_url += '?inline=1'
        sent = timezone.localtime(report.updated_at)
        rows.append({
            'sent_at': sent.strftime('%d/%m/%Y %H:%M'),
            'stamp': sent.strftime('%Y%m%d%H%M'),
            'filename': filename,
            'size': size,
            'view_url': view_url,
            'download_url': reverse('reports:pdf', args=[report.pk]),
            'is_word': filename.lower().endswith('.docx'),
        })
    return rows


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _get_or_create_employee(user):
    try:
        return user.employee_profile
    except Exception:
        if user.role == 'employee':
            from employees.models import Employee
            return Employee.objects.create(
                user=user,
                position='other',
                hire_date=timezone.now().date(),
                status='active',
            )
        return None


def _draft_key(user, day):
    return f'report_draft_{user.pk}_{day.isoformat()}'


def _build_report_context(user, report=None, report_date=None, draft=None, read_only=False):
    today = report_date or timezone.now().date()
    employee = _get_or_create_employee(user)
    if employee is None and not user.is_admin():
        return None

    payload = employee_report_payload(user, today)
    counts = payload['counts']
    planned = counts['planned']
    stats = {
        'tasks_completed': counts['completed'],
        'tasks_in_progress': counts['in_progress'],
        'tasks_remaining': counts['todo'],
        'tasks_not_done': counts['not_done'],
        'tasks_planned': planned,
        'productivity': int((counts['completed'] / planned) * 100) if planned else 0,
        'hours_worked': (
            f"{payload['hours_total']} h"
            if payload['hours_known'] else 'Non renseigné'
        ),
    }

    activities = []
    for task in payload['tasks']:
        activities.append({
            'title': task['title'],
            'description': task['comments'] or task['description'] or 'Aucune remarque renseignée',
            'status': task['status_code'],
            'status_class': STATUS_CLASS.get(task['status_code'], 'todo'),
            'status_label': task['status'],
            'time': task['project'],
        })

    if draft:
        ai_summary = draft
        from_ai_draft = True
    elif report:
        ai_summary = report.content
        from_ai_draft = report.ai_generated
    else:
        ai_summary = ''
        from_ai_draft = False

    return {
        'today': today,
        'report_date': today,
        'prev_date': today - timedelta(days=1),
        'next_date': today + timedelta(days=1),
        'formatted_date': _format_french_date(today),
        'journal_name': journal_person_name(user),
        'journal_date': journal_date_label(today),
        'stats': stats,
        'activities': activities,
        'ai_summary': ai_summary,
        'from_ai_draft': from_ai_draft,
        'report_history': _report_history(user),
        'report': report,
        'is_submitted': bool(report) and not draft,
        'read_only': read_only,
        'data_sufficient': planned > 0,
    }


@login_required
def report_list(request):
    if not request.user.is_admin():
        return redirect('reports:create')
    return _admin_report_board(request)


def _period(request):
    today = timezone.localdate()
    periode = (request.GET.get('periode') or 'all').strip()
    start = _parse_date(request.GET.get('debut'))
    end = _parse_date(request.GET.get('fin'))
    if periode == 'week':
        start = today - timedelta(days=today.weekday())
        end = today
    elif periode == 'month':
        start = today.replace(day=1)
        end = today
    elif start and end:
        periode = 'range'
    else:
        periode = 'all'
        start = None
        end = None
    if start and end and start > end:
        start, end = end, start
    return periode, start, end


def _query(base, **extra):
    from urllib.parse import urlencode

    data = {key: value for key, value in {**base, **extra}.items() if value not in ('', None)}
    encoded = urlencode(data)
    return f'?{encoded}' if encoded else '?'


def _file_card(report):
    stored = ''
    size = '—'
    if report.uploaded_pdf:
        stored = os.path.basename(report.uploaded_pdf.name)
        try:
            size = _format_size(report.uploaded_pdf.size)
        except OSError:
            size = '—'
    filename = report.original_name or stored or f"Rapport_journalier_{report.date.strftime('%d-%m-%Y')}.pdf"
    lower = filename.lower()
    is_word = lower.endswith('.docx')
    sent = timezone.localtime(report.updated_at)
    preview = reverse('reports:pdf', args=[report.pk])
    if not is_word:
        preview += '?inline=1'
    short_months = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
    owner = report.employee
    owner_name = (owner.get_full_name() or '').strip() or owner.username
    return {
        'pk': report.pk,
        'owner': owner_name,
        'filename': filename,
        'size': size,
        'sent_label': sent.strftime('%d/%m/%Y - %H:%M'),
        'sent_compact': f"{sent.day} {short_months[sent.month - 1]} {sent.year}",
        'is_word': is_word,
        'is_pdf': not is_word,
        'preview_url': preview,
        'download_url': reverse('reports:pdf', args=[report.pk]),
        'text': (report.content or '').strip(),
        'report_date': report.date,
    }


_IMPORTED = {
    'Rapport importé en PDF.',
    "Rapport importé par l'employé.",
    'Rapport importe.',
}


def _reading_block(cards, person_name=''):
    sentences = []
    for card in cards:
        text = card['text']
        if text and text not in _IMPORTED:
            sentences.append(f"{card['filename']} : {text}")
        else:
            sentences.append(f"Le fichier {card['filename']} a été envoyé le {card['sent_label']}.")
    if not sentences:
        return "Aucun rapport n'a été envoyé sur cette période. La lecture IA n'a rien à analyser."
    who = f"Rapports de {person_name}. " if person_name else ''
    return who + ' '.join(sentences)


def _admin_report_board(request):
    from employees.models import Employee
    from messaging.services import is_online

    day = _parse_date(request.GET.get('date')) or timezone.localdate()
    periode, start, end = _period(request)
    people = list(
        Employee.objects.select_related('user')
        .filter(status='active')
        .order_by('user__first_name', 'user__last_name')
    )
    reports = DailyReport.objects.filter(
        employee_id__in=[person.user_id for person in people],
    ).select_related('employee')
    if start:
        reports = reports.filter(date__gte=start)
    if end:
        reports = reports.filter(date__lte=end)
    reports = list(reports.order_by('-updated_at'))

    search = (request.GET.get('q') or request.GET.get('search') or '').strip()
    base = {
        'periode': '' if periode == 'all' else periode,
        'q': search,
        'debut': start.isoformat() if periode == 'range' and start else '',
        'fin': end.isoformat() if periode == 'range' and end else '',
    }
    colors = ['#7c3aed', '#db2777', '#ea580c', '#0d9488', '#2563eb', '#16a34a', '#ca8a04', '#e11d48']
    by_user = {}
    for report in reports:
        by_user.setdefault(report.employee_id, []).append(_file_card(report))

    submitted_today = set(
        DailyReport.objects.filter(
            date=day,
            employee_id__in=[person.user_id for person in people],
        ).values_list('employee_id', flat=True)
    )
    directory = []
    for person in people:
        name = (person.full_name or '').strip() or person.user.username
        if search and search.lower() not in name.lower() and search.lower() not in (person.email or '').lower():
            continue
        files = by_user.get(person.user_id, [])
        day_card = next((card for card in files if card.get('report_date') == day), None)
        user = person.user
        photo = user.photo.url if getattr(user, 'photo', None) else ''
        directory.append({
            'pk': person.pk,
            'user_id': person.user_id,
            'name': name,
            'role': person.get_position_display(),
            'service': (person.department or '').strip(),
            'initials': (
                f'{(user.first_name[:1] if user.first_name else "")}'
                f'{(user.last_name[:1] if user.last_name else "")}'
            ).upper() or user.username[:2].upper(),
            'color': colors[person.pk % len(colors)],
            'photo': photo,
            'count': len(files),
            'online': is_online(user),
            'files': files,
            'submitted': person.user_id in submitted_today,
            'href': _query(base, employee=person.pk, rapport=day_card['pk']) if day_card else _query(base, employee=person.pk),
        })

    chosen_id = (request.GET.get('employee') or '').strip()
    selected = next((item for item in directory if str(item['pk']) == chosen_id), None)
    report_id = (request.GET.get('rapport') or '').strip()
    visible_files = selected['files'] if selected else [
        card for item in directory for card in item['files']
    ]
    opened = None
    if selected and selected['files']:
        opened = next((card for card in selected['files'] if str(card['pk']) == report_id), selected['files'][0])
    elif not selected and report_id:
        opened = next((card for card in visible_files if str(card['pk']) == report_id), None)

    for card in visible_files:
        owner = selected['pk'] if selected else next(
            (item['pk'] for item in directory if any(item_card['pk'] == card['pk'] for item_card in item['files'])),
            '',
        )
        card['href'] = _query(base, employee=owner, rapport=card['pk'])

    synthesis = collect_team_synthesis(day)
    latest = (
        AISummary.objects.filter(summary_type=SYNTHESIS_TYPE, reference_date=day)
        .order_by('-created_at')
        .first()
    )
    latest_local = timezone.localtime(latest.created_at) if latest else None
    saved_count = analyzed_count_from_title(latest.title) if latest else None
    reading_source = selected['files'] if selected else [card for item in directory for card in item['files']]
    if start and end:
        range_label = f"{start:%d/%m/%Y} - {end:%d/%m/%Y}"
    elif periode == 'week':
        range_label = 'Cette semaine'
    elif periode == 'month':
        range_label = 'Ce mois'
    else:
        range_label = 'Tous les rapports'
    return render(request, 'reports/report_list.html', {
        'day': day,
        'today': timezone.localdate(),
        'day_label': f"{day.day} {FRENCH_MONTHS[day.month - 1]} {day.year}",
        'periode': periode,
        'range_label': range_label,
        'start': start,
        'end': end,
        'search': search,
        'directory': directory,
        'employee_total': len(directory),
        'report_total': sum(item['count'] for item in directory),
        'selected': selected,
        'files': visible_files,
        'opened': opened,
        'all_href': _query(base),
        'week_href': _query({**base, 'periode': 'week', 'debut': '', 'fin': ''}),
        'month_href': _query({**base, 'periode': 'month', 'debut': '', 'fin': ''}),
        'synthesis_stats': synthesis,
        'latest_synthesis': latest,
        'synthesis_html': synthesis_to_html(latest.content) if latest else '',
        'synthesis_analyzed': saved_count if saved_count is not None else synthesis['analyzed'],
        'last_synthesis_label': (
            f"{latest_local:%d/%m/%Y} à {latest_local:%H:%M}" if latest_local else ''
        ),
        'reading': _reading_block(reading_source, selected['name'] if selected else ''),
    })


SYNTHESIS_UNAVAILABLE = (
    "Impossible de générer la synthèse IA pour le moment. "
    "Le service d'IA est actuellement indisponible."
)


@admin_required
@require_POST
def team_synthesis(request):
    """Synthèse unique des rapports soumis. L'échec de l'API ne produit aucun texte inventé."""
    day = _parse_date(request.POST.get('date')) or timezone.localdate()
    try:
        text, dossier = DecisionAIService().synthesize_submitted_reports(day)
    except NoSubmittedReportsError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    except AIServiceError:
        return JsonResponse({'ok': False, 'error': SYNTHESIS_UNAVAILABLE}, status=503)

    summary = AISummary.objects.create(
        generated_by=request.user,
        title=synthesis_title(day, dossier['analyzed']),
        content=text,
        summary_type=SYNTHESIS_TYPE,
        reference_date=day,
    )
    generated = timezone.localtime(summary.created_at)
    return JsonResponse({
        'ok': True,
        'synthesis': text,
        'html': synthesis_to_html(text),
        'analyzed': dossier['analyzed'],
        'missing': dossier['missing'],
        'date_label': f"{day.day} {FRENCH_MONTHS[day.month - 1]} {day.year}",
        'generated_at': f"{generated:%d/%m/%Y} à {generated:%H:%M}",
        'stats': {
            'submitted': dossier['submitted'],
            'missing': dossier['missing'],
            'analyzed': dossier['analyzed'],
            'difficulties': dossier['difficulties'],
            'completed': dossier['completed'],
            'in_progress': dossier['in_progress'],
        },
    })


@admin_required
def team_report(request):
    """Un seul rapport de la journée, un bloc par employé, sans texte inventé."""
    from employees.models import Employee

    day = _parse_date(request.GET.get('date')) or timezone.localdate()
    people = list(
        Employee.objects.select_related('user')
        .order_by('user__first_name', 'user__last_name')
    )
    stored = {
        report.employee_id: report
        for report in DailyReport.objects.filter(
            date=day,
            employee_id__in=[person.user_id for person in people],
        )
    }
    colors = ['#7c3aed', '#db2777', '#ea580c', '#0d9488', '#2563eb', '#16a34a', '#ca8a04', '#e11d48']
    sections = []
    for person in people:
        user = person.user
        initials = ((user.first_name or '')[:1] + (user.last_name or '')[:1]).upper() or user.username[:2].upper()
        common = {
            'name': person.full_name,
            'role': person.get_position_display(),
            'initials': initials,
            'color': colors[person.pk % len(colors)],
        }
        report = stored.get(person.user_id)
        if report and (report.content or '').strip():
            sections.append({
                **common,
                'state': 'Soumis',
                'bullets': journal_bullets(report.content),
                'report': report,
            })
            continue
        payload = employee_report_payload(person.user, day)
        if payload['counts']['planned'] == 0:
            sections.append({**common, 'state': 'Sans activité', 'bullets': [], 'report': None})
            continue
        sections.append({
            **common,
            'state': 'Activités enregistrées',
            'bullets': journal_bullets(compose_employee_report(payload)),
            'report': None,
        })
    submitted_count = sum(1 for section in sections if section['state'] == 'Soumis')
    activity_count = sum(1 for section in sections if section['state'] == 'Activités enregistrées')
    return render(request, 'reports/report_team.html', {
        'day': day,
        'day_label': _format_french_date(day),
        'sections': sections,
        'submitted_count': submitted_count,
        'activity_count': activity_count,
        'empty_count': len(sections) - submitted_count - activity_count,
        'people_count': len(sections),
    })


@admin_required
@require_POST
def generate_day_reports(request):
    day = _parse_date(request.POST.get('date')) or timezone.localdate()
    messages.error(
        request,
        "Les rapports sont importés par les employés. Aucun rapport n'a été généré automatiquement.",
    )
    return redirect(f"{reverse('reports:list')}?date={day.isoformat()}")


@login_required
def report_detail(request, pk):
    report = get_object_or_404(DailyReport, pk=pk)
    if not request.user.is_admin() and report.employee_id != request.user.id:
        messages.error(request, "Vous ne pouvez consulter que vos propres rapports.")
        return redirect('reports:create')

    if request.user.is_admin():
        return render(request, 'reports/report_read.html', {
            'report': report,
            'reading': report_reading(report),
        })

    context = _build_report_context(
        report.employee,
        report=report,
        report_date=report.date,
        read_only=False,
    )
    if context is None:
        messages.error(request, 'Profil employé introuvable.')
        return redirect('dashboard:employee_home')
    return render(request, 'reports/report_create.html', context)


@login_required
def report_create(request):
    report_date = _parse_date(request.GET.get('date')) or timezone.now().date()
    employee = _get_or_create_employee(request.user)
    if employee is None and not request.user.is_admin():
        messages.error(request, 'Vous devez avoir un profil employé pour accéder à votre rapport.')
        return redirect('dashboard:employee_home')

    existing_report = DailyReport.objects.filter(
        employee=request.user,
        date=report_date,
    ).first()
    draft = None
    if request.GET.get('draft'):
        draft = request.session.get(_draft_key(request.user, report_date))

    context = _build_report_context(
        request.user,
        report=existing_report,
        report_date=report_date,
        draft=draft,
        read_only=False,
    )
    imported = (request.GET.get('importe') or '').replace('\\', '/').split('/')[-1].strip()
    if not imported and existing_report and existing_report.uploaded_pdf:
        imported = os.path.basename(existing_report.uploaded_pdf.name)
    if imported and len(imported) <= 180 and '..' not in imported:
        context['imported_name'] = imported
    return render(request, 'reports/report_create.html', context)


@login_required
@require_POST
def report_generate(request):
    report_date = _parse_date(request.POST.get('date')) or timezone.now().date()
    messages.error(
        request,
        "Le rapport n'est pas rédigé par l'IA. Importez votre fichier PDF ou DOCX.",
    )
    return redirect(f"{reverse('reports:create')}?date={report_date.isoformat()}")


@login_required
@require_POST
def report_save(request):
    report_date = _parse_date(request.POST.get('date')) or timezone.now().date()
    content = (request.POST.get('content') or '').strip()
    extra = (request.POST.get('extra_remark') or '').strip()
    if extra:
        content = f"{content}\n\nRemarque ajoutée lors de la validation :\n{extra}".strip()
    if not content:
        messages.error(request, "Le rapport est vide. Générez-le ou rédigez-le avant de l'enregistrer.")
        return redirect(f"{reverse('reports:create')}?date={report_date.isoformat()}")

    draft = request.session.get(_draft_key(request.user, report_date))
    ai_generated = bool(draft) and content == draft

    DailyReport.objects.update_or_create(
        employee=request.user,
        date=report_date,
        defaults={
            'content': content,
            'tasks_completed': ReportGenerator.task_lines(request.user, report_date, {'completed'}),
            'tasks_in_progress': ReportGenerator.task_lines(
                request.user, report_date, {'in_progress', 'review'}
            ),
            'ai_generated': ai_generated,
        },
    )
    request.session.pop(_draft_key(request.user, report_date), None)
    messages.success(
        request,
        'Rapport validé. Le responsable peut télécharger le PDF dans Rapports.',
    )
    return redirect(f"{reverse('reports:create')}?date={report_date.isoformat()}")


@login_required
@require_POST
def report_upload(request):
    """L'employé envoie son propre PDF au responsable, sans génération IA."""
    report_date = _parse_date(request.POST.get('date')) or timezone.now().date()
    if _get_or_create_employee(request.user) is None and not request.user.is_admin():
        messages.error(request, 'Vous devez avoir un profil employé pour envoyer un rapport.')
        return redirect('reports:create')

    uploaded = request.FILES.get('pdf') or request.FILES.get('file')
    if uploaded is None:
        messages.error(request, 'Choisissez un fichier PDF ou Word à envoyer.')
        return redirect('reports:create')
    try:
        validate_report_file(uploaded)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
        return redirect('reports:create')

    filename = os.path.basename(getattr(uploaded, 'name', '') or '').replace('\\', '/').split('/')[-1]
    filename = filename[:180] or 'rapport'
    report, _created = DailyReport.objects.get_or_create(
        employee=request.user,
        date=report_date,
        defaults={
            'content': 'Rapport importé en PDF.',
            'ai_generated': False,
        },
    )
    if report.uploaded_pdf:
        report.uploaded_pdf.delete(save=False)
    report.uploaded_pdf = uploaded
    report.original_name = filename
    report.file_size = uploaded.size or 0
    report.ai_generated = False
    from .extract import extract_report_text
    extracted = ''
    try:
        extracted = extract_report_text(uploaded)
    except Exception:
        extracted = ''
    report.content = extracted or (
        f"Fichier importé : {filename}. Le texte du fichier n'a pas pu être lu automatiquement."
    )
    report.save()

    from notifications.signals import _notify_admins

    name = f'{request.user.first_name} {request.user.last_name}'.strip() or request.user.username
    _notify_admins(
        'Rapport importé',
        f'{name} a envoyé son rapport du {report_date:%d/%m/%Y}.',
        'success',
        reverse('reports:detail', args=[report.pk]),
    )
    messages.success(request, f'Vous avez importé {filename}.')
    from urllib.parse import quote
    return redirect(
        f"{reverse('reports:create')}?date={report_date.isoformat()}&importe={quote(filename)}"
    )


@login_required
def report_pdf(request, pk):
    report = get_object_or_404(DailyReport.objects.select_related('employee'), pk=pk)
    if not request.user.is_admin() and report.employee_id != request.user.id:
        messages.error(request, 'Vous ne pouvez télécharger que vos propres rapports.')
        return redirect('reports:create')

    if report.uploaded_pdf:
        try:
            stored = os.path.basename(report.uploaded_pdf.name)
            content_type = mimetypes.guess_type(stored)[0] or 'application/octet-stream'
            if stored.lower().endswith('.pdf'):
                content_type = 'application/pdf'
            inline = request.GET.get('inline') == '1' and content_type == 'application/pdf'
            handle = report.uploaded_pdf.open('rb')
            response = FileResponse(handle, content_type=content_type)
            response['Content-Disposition'] = (
                f"{'inline' if inline else 'attachment'}; filename=\"{stored}\""
            )
            response['X-Frame-Options'] = 'SAMEORIGIN'
            return response
        except OSError:
            pass

    filename = f"RACIN_Rapport_{report.employee.last_name or report.employee.username}_{report.date.isoformat()}.pdf"
    disposition = 'inline' if request.GET.get('inline') == '1' else 'attachment'
    response = HttpResponse(build_daily_report_pdf(report), content_type='application/pdf')
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    response['X-Frame-Options'] = 'SAMEORIGIN'
    return response
