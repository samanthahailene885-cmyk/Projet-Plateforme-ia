from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
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

    previous_reports = DailyReport.objects.filter(employee=user).order_by('-date')
    if report:
        previous_reports = previous_reports.exclude(pk=report.pk)

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
        'previous_reports': previous_reports[:8],
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


def _admin_report_board(request):
    from django.core.paginator import Paginator
    from decision_ai.analytics import tasks_on_date
    from employees.models import Employee

    day = _parse_date(request.GET.get('date')) or timezone.localdate()
    people = list(Employee.objects.select_related('user').order_by('user__first_name', 'user__last_name'))
    reports = {
        report.employee_id: report
        for report in DailyReport.objects.filter(date=day, employee_id__in=[person.user_id for person in people])
    }
    colors = ['#7c3aed', '#db2777', '#ea580c', '#0d9488', '#2563eb', '#16a34a', '#ca8a04', '#e11d48']
    rows = []
    for person in people:
        report = reports.get(person.user_id)
        tasks = list(tasks_on_date(day, person))
        countable = [task for task in tasks if task.status != 'cancelled']
        done = sum(1 for task in countable if task.status == 'completed')
        planned = len(countable)
        open_count = planned - done
        if report:
            state_key, state_label = 'done', 'Soumis'
            kind_key = 'ai' if report.ai_generated else 'manual'
            kind_label = 'IA' if report.ai_generated else 'Manuel'
        else:
            state_key, state_label = 'wait', 'En attente'
            kind_key, kind_label = '', '—'
        rows.append({
            'employee': person,
            'report': report,
            'initials': ((person.user.first_name or '')[:1] + (person.user.last_name or '')[:1]).upper() or person.user.username[:2].upper(),
            'color': colors[person.pk % len(colors)],
            'service': person.department or 'Non renseigné',
            'planned': planned,
            'done': done,
            'open': open_count,
            'state_key': state_key,
            'state_label': state_label,
            'kind_key': kind_key,
            'kind_label': kind_label,
            'submitted_at': timezone.localtime(report.created_at) if report else None,
        })

    search = (request.GET.get('search') or request.GET.get('q') or '').strip()
    service = (request.GET.get('service') or '').strip()
    state = (request.GET.get('state') or request.GET.get('status') or '').strip()
    if state == 'submitted':
        state = 'done'
    if state == 'pending':
        state = 'wait'
    kind = (request.GET.get('kind') or '').strip()
    employee_id = (request.GET.get('employee') or '').strip()
    filtered = rows
    if employee_id.isdigit():
        filtered = [row for row in filtered if str(row['employee'].pk) == employee_id]
    if search:
        needle = search.lower()
        filtered = [
            row for row in filtered
            if needle in row['employee'].full_name.lower() or needle in (row['employee'].email or '').lower()
        ]
    if service:
        filtered = [row for row in filtered if row['employee'].department == service]
    if state:
        filtered = [row for row in filtered if row['state_key'] == state]
    if kind:
        filtered = [row for row in filtered if row['kind_key'] == kind]

    submitted = [row for row in rows if row['state_key'] == 'done']
    stats = {
        'total_people': len(rows),
        'submitted': len(submitted),
        'waiting': len(rows) - len(submitted),
        'ai': sum(1 for row in submitted if row['kind_key'] == 'ai'),
        'manual': sum(1 for row in submitted if row['kind_key'] == 'manual'),
    }
    paginator = Paginator(filtered, 8)
    page_obj = paginator.get_page(request.GET.get('page'))
    parts = stats['ai'] + stats['manual'] + stats['waiting']
    stats['ai_deg'] = round(stats['ai'] * 360 / parts) if parts else 0
    stats['manual_deg'] = round(stats['manual'] * 360 / parts) if parts else 0
    services = sorted({row['employee'].department for row in rows if row['employee'].department})
    query = request.GET.copy()
    query.pop('page', None)
    synthesis = collect_team_synthesis(day)
    latest = (
        AISummary.objects.filter(summary_type=SYNTHESIS_TYPE, reference_date=day)
        .order_by('-created_at')
        .first()
    )
    latest_local = timezone.localtime(latest.created_at) if latest else None
    saved_count = analyzed_count_from_title(latest.title) if latest else None
    return render(request, 'reports/report_list.html', {
        'day': day,
        'today': timezone.localdate(),
        'day_label': f"{day.day} {FRENCH_MONTHS[day.month - 1]} {day.year}",
        'rows': page_obj.object_list,
        'page_obj': page_obj,
        'stats': stats,
        'services': services,
        'people': people,
        'employee_id': employee_id,
        'search': search,
        'service': service,
        'state': state,
        'kind': kind,
        'querystring': query.urlencode(),
        'synthesis_stats': synthesis,
        'latest_synthesis': latest,
        'synthesis_html': synthesis_to_html(latest.content) if latest else '',
        'synthesis_analyzed': saved_count if saved_count is not None else synthesis['analyzed'],
        'last_synthesis_label': (
            f"{latest_local:%d/%m/%Y} à {latest_local:%H:%M}" if latest_local else ''
        ),
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
    result = generate_reports_for_day(day)
    messages.success(
        request,
        f"{result['analyzed']} employés analysés. "
        f"{result['generated']} rapports générés. "
        f"{result['already']} rapports déjà existants. "
        f"{result['missing']} employé(s) sans todo list.",
    )
    return redirect(f"{reverse('reports:team')}?date={day.isoformat()}")


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
    return render(request, 'reports/report_create.html', context)


@login_required
@require_POST
def report_generate(request):
    report_date = _parse_date(request.POST.get('date')) or timezone.now().date()
    if _get_or_create_employee(request.user) is None and not request.user.is_admin():
        messages.error(request, 'Vous devez avoir un profil employé pour générer un rapport.')
        return redirect('reports:create')

    try:
        content = ReportGenerator().generate_daily_report(request.user, report_date)
    except AIServiceError as exc:
        messages.error(request, str(exc))
        return redirect(f"{reverse('reports:create')}?date={report_date.isoformat()}")

    request.session[_draft_key(request.user, report_date)] = content
    request.session.modified = True
    messages.success(
        request,
        "Rapport préparé à partir de vos activités enregistrées. Vous pouvez le modifier, puis le valider.",
    )
    return redirect(f"{reverse('reports:create')}?date={report_date.isoformat()}&draft=1")


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
def report_pdf(request, pk):
    report = get_object_or_404(DailyReport.objects.select_related('employee'), pk=pk)
    if not request.user.is_admin() and report.employee_id != request.user.id:
        messages.error(request, 'Vous ne pouvez télécharger que vos propres rapports.')
        return redirect('reports:create')

    filename = f"RACIN_Rapport_{report.employee.last_name or report.employee.username}_{report.date.isoformat()}.pdf"
    response = HttpResponse(build_daily_report_pdf(report), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
