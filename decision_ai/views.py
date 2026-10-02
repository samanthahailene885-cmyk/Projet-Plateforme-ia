import hashlib
from datetime import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from authentication.decorators import admin_required

from .analytics import collect_alerts, day_stats, recorded_answer, workload_rows
from .briefing import agency_brief, alert_brief, difficulty_brief, project_briefs, trend_brief
from .models import AIChat, AISummary
from .services import AIServiceError, DecisionAIService


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


@admin_required
def ai_assistant(request):
    today = timezone.localdate()
    chats = AIChat.objects.filter(user=request.user).order_by('-created_at')[:20]
    total = AIChat.objects.filter(user=request.user).count()
    answered = AIChat.objects.filter(user=request.user).exclude(answer='').count()
    history = []
    for chat in chats:
        local = timezone.localtime(chat.created_at)
        history.append({
            'question': chat.question,
            'answer': chat.answer,
            'when': f"{date_format(local, 'j F Y')} • {local.strftime('%H:%M')}",
        })
    initials = (
        f'{(request.user.first_name[:1] if request.user.first_name else "")}'
        f'{(request.user.last_name[:1] if request.user.last_name else "")}'
    ).upper() or request.user.username[:2].upper()
    return render(request, 'decision_ai/assistant.html', {
        'history': history,
        'question_count': total,
        'response_rate': round(answered * 100 / total) if total else None,
        'today_label': date_format(today, 'l j F Y').capitalize(),
        'initials': initials,
        'display_name': (request.user.get_full_name() or '').strip() or request.user.username,
    })


@admin_required
@require_POST
def ai_chat(request):
    question = (request.POST.get('question') or '').strip()
    if not question:
        return JsonResponse({'error': 'Question vide'}, status=400)
    if len(question) > 2000:
        return JsonResponse({'error': 'La question est trop longue.'}, status=400)

    service = DecisionAIService()
    try:
        answer = service.answer_question(question)
    except AIServiceError:
        answer = recorded_answer(question, timezone.localdate())

    AIChat.objects.create(user=request.user, question=question, answer=answer)
    return JsonResponse({'question': question, 'answer': answer})


@admin_required
def generate_summary(request):
    service = DecisionAIService()
    today = timezone.now().date()
    try:
        summary_content = service.generate_intelligent_summary()
    except AIServiceError:
        summary_content = agency_brief(today)

    AISummary.objects.create(
        generated_by=request.user,
        title=f"Résumé intelligent - {service._get_current_date()}",
        content=summary_content,
        summary_type='daily',
        reference_date=today,
    )
    messages.success(request, 'Résumé intelligent généré avec succès.')
    return redirect('decision_ai:summaries')


@admin_required
def summaries_list(request):
    summaries = AISummary.objects.select_related('generated_by').all()
    return render(request, 'decision_ai/summaries.html', {'summaries': summaries})


ALERT_TYPES = [
    ('absence', 'Absence'),
    ('tache', 'Tâche'),
    ('rapport', 'Rapport'),
    ('permission', 'Permission'),
    ('ia', 'IA'),
    ('projet', 'Projet'),
    ('systeme', 'Système'),
]

ALERT_STATUSES = [
    ('non_resolu', 'Non résolu'),
    ('en_cours', 'En cours'),
    ('en_attente', 'En attente'),
    ('resolu', 'Résolu'),
]

GRAVITES = [
    ('', 'Toutes les alertes'),
    ('critique', 'Alertes critiques'),
    ('importante', 'Alertes importantes'),
    ('info', 'Infos'),
    ('resolu', 'Résolues'),
]

_KIND_STYLE = {
    'Activité': ('tache', 'Tâche', 'orange', 'exclaim'),
    'Projet': ('projet', 'Projet', 'red', 'exclaim'),
    'Remarque': ('ia', 'IA', 'violet', 'spark'),
    'Permission': ('permission', 'Permission', 'green', 'check'),
    'Todo list': ('systeme', 'Système', 'blue', 'info'),
    'Rapport': ('rapport', 'Rapport', 'blue', 'info'),
}

_LEVEL_BUCKET = {
    'high': 'critique',
    'medium': 'importante',
    'low': 'info',
}

_STATUS_STYLE = {
    'non_resolu': ('Non résolu', 'rose'),
    'en_cours': ('En cours', 'orange'),
    'en_attente': ('En attente', 'amber'),
    'resolu': ('Résolu', 'green'),
}

_BUCKET_ORDER = {'critique': 0, 'importante': 1, 'info': 2, 'resolu': 3}


def _alert_key(alert):
    raw = f"{alert.get('kind', '')}|{alert.get('url', '')}|{alert.get('subject', '')}"
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def _open_status(alert):
    if alert.get('kind') == 'Permission':
        return 'en_attente'
    if alert.get('level') == 'medium':
        return 'en_cours'
    return 'non_resolu'


def _present_alerts(alerts, reads):
    from employees.models import Employee

    roles = {
        employee.full_name: employee.get_position_display()
        for employee in Employee.objects.select_related('user')
    }
    rows = []
    for alert in alerts:
        key = _alert_key(alert)
        resolved = key in reads
        type_key, type_label, tone, icon = _KIND_STYLE.get(
            alert.get('kind'),
            ('systeme', alert.get('kind') or 'Système', 'blue', 'info'),
        )
        if resolved:
            status_key = 'resolu'
            bucket = 'resolu'
        else:
            status_key = _open_status(alert)
            bucket = _LEVEL_BUCKET.get(alert.get('level'), 'info')
        status_label, status_tone = _STATUS_STYLE[status_key]
        name = (alert.get('employee') or '').strip()
        if name in roles:
            emitter, role, system = name, roles[name], False
        elif name in ('', '—', 'Non assignée'):
            emitter, role, system = 'Système', '', True
        else:
            emitter, role, system = name, '', False
        title = (alert.get('subject') or '').strip() or type_label
        if alert.get('kind') == 'Permission':
            title = 'Demande de permission'
        elif alert.get('kind') == 'Todo list':
            title = 'Plan du jour absent'
        elif alert.get('kind') == 'Rapport':
            title = 'Rapport non soumis'
        detected = alert.get('detected_on')
        rows.append({
            'key': key,
            'type_key': type_key,
            'type_label': type_label,
            'tone': tone,
            'icon': icon,
            'title': title,
            'description': alert.get('reason') or '',
            'emitter': emitter,
            'role': role,
            'system': system,
            'date_label': date_format(detected, 'j F Y') if detected else '',
            'url': alert.get('url') or '',
            'status_key': status_key,
            'status_label': status_label,
            'status_tone': status_tone,
            'bucket': bucket,
        })
    rows.sort(key=lambda row: _BUCKET_ORDER.get(row['bucket'], 9))
    return rows


def _alert_query(alert_type, statut, gravite, selected, date_filtered, **overrides):
    params = {
        'type': alert_type,
        'statut': statut,
        'gravite': gravite,
        'date': selected.isoformat() if date_filtered else '',
    }
    params.update(overrides)
    return urlencode({key: value for key, value in params.items() if value})


def _alert_center_redirect(request):
    target = reverse('decision_ai:delay_detection')
    query = request.GET.urlencode()
    if query:
        target = f'{target}?{query}'
    return redirect(target)


@admin_required
def delay_detection(request):
    today = timezone.localdate()
    date_filtered = bool(request.GET.get('date'))
    selected = _parse_date(request.GET.get('date')) or today
    alerts = collect_alerts(selected)
    reads = request.session.get('alert_reads') or {}
    if not isinstance(reads, dict):
        reads = {}

    if request.method == 'POST':
        valid = {_alert_key(alert) for alert in alerts}
        action = request.POST.get('action')
        if action == 'mark_all':
            stamp = today.isoformat()
            for key in valid:
                reads[key] = stamp
        elif action == 'toggle':
            key = request.POST.get('key') or ''
            if key in valid:
                if key in reads:
                    reads.pop(key, None)
                else:
                    reads[key] = today.isoformat()
        request.session['alert_reads'] = reads
        request.session.modified = True
        return _alert_center_redirect(request)

    rows = _present_alerts(alerts, reads)
    counts = {
        'critique': sum(row['bucket'] == 'critique' for row in rows),
        'importante': sum(row['bucket'] == 'importante' for row in rows),
        'info': sum(row['bucket'] == 'info' for row in rows),
        'resolu': sum(row['bucket'] == 'resolu' for row in rows),
    }

    alert_type = request.GET.get('type', '')
    if alert_type not in {key for key, _label in ALERT_TYPES}:
        alert_type = ''
    statut = request.GET.get('statut', '')
    if statut not in {key for key, _label in ALERT_STATUSES}:
        statut = ''
    gravite = request.GET.get('gravite', '')
    if gravite not in {'critique', 'importante', 'info', 'resolu'}:
        gravite = ''

    visible = rows
    if alert_type:
        visible = [row for row in visible if row['type_key'] == alert_type]
    if statut:
        visible = [row for row in visible if row['status_key'] == statut]
    if gravite:
        visible = [row for row in visible if row['bucket'] == gravite]

    paginator = Paginator(visible, 8)
    page = paginator.get_page(request.GET.get('page'))
    total = paginator.count
    current = page.number
    window_end = min(paginator.num_pages, max(current + 2, 5))
    window_start = max(1, window_end - 4)
    window_end = min(paginator.num_pages, window_start + 4)
    kept = request.GET.copy()
    kept.pop('page', None)

    return render(request, 'decision_ai/delay_detection.html', {
        'rows': page,
        'page_obj': page,
        'page_numbers': list(range(window_start, window_end + 1)) if total or paginator.num_pages else [],
        'total': total,
        'range_start': page.start_index() if total else 0,
        'range_end': page.end_index() if total else 0,
        'counts': counts,
        'chart_total': sum(counts.values()),
        'alert_types': ALERT_TYPES,
        'alert_statuses': ALERT_STATUSES,
        'gravites': GRAVITES,
        'alert_type': alert_type,
        'statut': statut,
        'gravite': gravite,
        'selected': selected,
        'selected_iso': selected.isoformat(),
        'selected_short': date_format(selected, 'd/m/Y'),
        'date_filtered': date_filtered,
        'filter_query': kept.urlencode(),
        'current_query': request.GET.urlencode(),
        'vigilance': alert_brief(alerts),
        'kpi_links': {
            'critique': _alert_query(alert_type, statut, '' if gravite == 'critique' else 'critique', selected, date_filtered),
            'importante': _alert_query(alert_type, statut, '' if gravite == 'importante' else 'importante', selected, date_filtered),
            'info': _alert_query(alert_type, statut, '' if gravite == 'info' else 'info', selected, date_filtered),
            'resolu': _alert_query(alert_type, statut, '' if gravite == 'resolu' else 'resolu', selected, date_filtered),
        },
    })


@admin_required
def workload_analysis(request):
    today = _parse_date(request.GET.get('date')) or timezone.now().date()
    rows = workload_rows(today)
    return render(request, 'decision_ai/workload_analysis.html', {
        'workload_analysis': rows,
        'today': today,
    })


@admin_required
def monthly_report(request):
    service = DecisionAIService()
    today = timezone.now().date()
    try:
        report_content = service.generate_monthly_report()
    except AIServiceError:
        report_content = agency_brief(today)

    AISummary.objects.create(
        generated_by=request.user,
        title=f"Rapport mensuel - {service._get_current_date()}",
        content=report_content,
        summary_type='monthly',
        reference_date=today,
    )
    messages.success(request, 'Rapport mensuel généré avec succès.')
    return redirect('decision_ai:summaries')


@admin_required
def intelligence_center(request):
    day = _parse_date(request.GET.get('date') or request.POST.get('date')) or timezone.now().date()
    stats = day_stats(day)
    alerts = collect_alerts(day)
    workload = workload_rows(day)
    summary = None
    explanation = None
    ai_error = None
    briefs = {
        'agency': agency_brief(day),
        'difficulties': difficulty_brief(day),
        'projects': project_briefs(day),
        'trends': trend_brief(day),
        'alerts': alert_brief(alerts),
    }

    if request.method == 'POST':
        action = request.POST.get('action') or 'analyze'
        service = DecisionAIService()
        try:
            if action in ('summary', 'analyze'):
                summary = service.summarize_day(day)
            if action == 'analyze' and alerts:
                explanation = service.explain_alerts(alerts)
        except AIServiceError:
            if summary is None and action in ('summary', 'analyze'):
                summary = briefs['agency']
            if action == 'analyze' and explanation is None:
                explanation = briefs['alerts']
        if summary:
            AISummary.objects.create(
                generated_by=request.user,
                title=f"Résumé du {day:%d/%m/%Y}",
                content=summary,
                summary_type='daily',
                reference_date=day,
            )

    saved = AISummary.objects.filter(summary_type='daily', reference_date=day).first()
    return render(request, 'decision_ai/center.html', {
        'day': day,
        'stats': stats,
        'alerts': alerts,
        'workload': workload,
        'summary': summary or (saved.content if saved else briefs['agency']),
        'summary_is_saved': summary is None and saved is not None,
        'explanation': explanation or briefs['alerts'],
        'ai_error': ai_error,
        'briefs': briefs,
    })


@login_required
@require_POST
def improve_remark(request):
    remark = (request.POST.get('remark') or '').strip()
    if len(remark) < 3:
        return JsonResponse(
            {'error': 'Saisissez une remarque avant de demander une reformulation.'},
            status=400,
        )
    if len(remark) > 2000:
        return JsonResponse({'error': 'La remarque est trop longue.'}, status=400)

    try:
        suggestion = DecisionAIService().improve_remark(remark)
    except AIServiceError:
        suggestion = remark
    return JsonResponse({'suggestion': suggestion})
