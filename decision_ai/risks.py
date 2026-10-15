"""Analyse des risques opérationnels à partir des enregistrements.

Une situation ne crée qu'une alerte. Tant qu'elle persiste, l'analyse
met à jour la même ligne. Elle est marquée résolue quand la cause disparaît.
"""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from decision_ai.models import OperationalAlert
from projects.models import Project
from tasks.models import Difficulty, Task

RELEVANT = 45
CLOSED = Task.CLOSED_STATUSES


def severity_for(score):
    if score >= 75:
        return 'high'
    if score >= 55:
        return 'medium'
    return 'low'


def _cap(score):
    return max(0, min(100, score))


def _task_bits(task, today):
    parts = []
    score = 0
    if task.due_date and task.due_date < today:
        late = (today - task.due_date).days
        gained = min(30, late * 5)
        score += 40 + gained
        parts.append(f'Retard de {late} jour(s) : +{40 + gained}')
    elif task.due_date and task.due_date >= today:
        left = (task.due_date - today).days
        gained = 20 if left == 0 else 12
        score += gained
        parts.append(f'Échéance dans {left} jour(s) : +{gained}')
    priority_gain = {'urgent': 20, 'high': 12, 'medium': 4}.get(task.priority, 0)
    if priority_gain:
        score += priority_gain
        parts.append(f'Priorité {task.get_priority_display().lower()} : +{priority_gain}')
    if task.status == 'todo':
        score += 8
        parts.append('Activité non commencée : +8')
    return score, parts


def _signals(today):
    signals = []
    horizon = today + timedelta(days=2)

    tasks = (
        Task.objects.exclude(status__in=CLOSED)
        .filter(due_date__isnull=False, due_date__lte=horizon)
        .select_related('project', 'assigned_to__user')
    )
    open_difficulties = Difficulty.objects.filter(status='open').select_related('task', 'project', 'employee__user')
    difficulty_by_task = {}
    for item in open_difficulties:
        if item.task_id:
            difficulty_by_task.setdefault(item.task_id, []).append(item)

    late_by_project = {}
    for task in tasks:
        score, parts = _task_bits(task, today)
        linked = difficulty_by_task.get(task.pk, [])
        if linked:
            score += 15
            parts.append(f'{len(linked)} difficulté(s) ouverte(s) : +15')
        if task.due_date >= today and task.priority == 'urgent':
            score += 15
            parts.append('Échéance urgente : +15')
        score = _cap(score)
        if score < RELEVANT:
            continue
        overdue = task.due_date < today
        kind = 'task_late' if overdue else 'task_soon'
        project_name = task.project.name if task.project_id else 'Sans projet'
        who = task.assigned_to.full_name if task.assigned_to_id else 'Non assignée'
        if overdue:
            cause = f"L'échéance du {task.due_date:%d/%m/%Y} est dépassée et « {task.title} » n'est pas terminée."
            recommendation = "Vérifier l'avancement avec l'employé et confirmer si l'échéance doit être revue."
        else:
            cause = f"« {task.title} » arrive à échéance le {task.due_date:%d/%m/%Y} et reste prioritaire."
            recommendation = "Vérifier que les éléments nécessaires sont prêts avant l'échéance."
        if linked:
            cause += f' Difficulté signalée : {linked[0].description.strip()[:180]}'
        signals.append({
            'fingerprint': f'{kind}:{task.pk}',
            'kind': kind,
            'severity': severity_for(score),
            'subject': task.title,
            'project': task.project,
            'task': task,
            'cause': cause,
            'recommendation': recommendation,
            'due_date': task.due_date,
            'score': score,
            'score_detail': f'{project_name} · {who}. ' + '. '.join(parts) + f'. Total {score}/100.',
            'url': reverse('tasks:detail', args=[task.pk]),
        })
        if overdue and task.project_id:
            bucket = late_by_project.setdefault(task.project_id, {'project': task.project, 'count': 0})
            bucket['count'] += 1

    for bucket in late_by_project.values():
        if bucket['count'] < 2:
            continue
        project = bucket['project']
        score = _cap(35 + bucket['count'] * 12)
        if score < RELEVANT:
            continue
        signals.append({
            'fingerprint': f'project_pile:{project.pk}',
            'kind': 'project_pile',
            'severity': severity_for(score),
            'subject': project.name,
            'project': project,
            'task': None,
            'cause': f'{bucket["count"]} activités de ce projet ont une échéance dépassée.',
            'recommendation': 'Revoir les activités en retard et leur impact sur la date de fin.',
            'due_date': project.end_date,
            'score': score,
            'score_detail': (
                f'{bucket["count"]} activités en retard : +{35 + bucket["count"] * 12}. '
                f'Avancement saisi : {project.progress} %. Total {score}/100.'
            ),
            'url': reverse('projects:detail', args=[project.pk]),
        })

    late_projects = Project.objects.filter(end_date__lt=today).exclude(status__in=['completed', 'cancelled'])
    for project in late_projects:
        days = (today - project.end_date).days
        gained = min(40, days * 4)
        score = 30 + gained
        parts = [f'Fin dépassée de {days} jour(s) : +{30 + gained}']
        if project.progress < 50:
            score += 15
            parts.append('Avancement inférieur à 50 % : +15')
        if project.status == 'on_hold':
            score += 10
            parts.append('Projet en pause : +10')
        score = _cap(score)
        if score < RELEVANT:
            continue
        signals.append({
            'fingerprint': f'project_end:{project.pk}',
            'kind': 'project_end',
            'severity': severity_for(score),
            'subject': project.name,
            'project': project,
            'task': None,
            'cause': f'La date de fin du {project.end_date:%d/%m/%Y} est dépassée et le projet n\'est pas terminé.',
            'recommendation': 'Vérifier si la date de fin ou le statut du projet doit être mis à jour.',
            'due_date': project.end_date,
            'score': score,
            'score_detail': '. '.join(parts) + f'. Total {score}/100.',
            'url': reverse('projects:detail', args=[project.pk]),
        })

    covered_tasks = {signal['task'].pk for signal in signals if signal.get('task') is not None}
    for item in open_difficulties:
        if item.task_id and item.task_id in covered_tasks:
            continue
        if item.task_id and item.task and item.task.status in CLOSED:
            continue
        score = 35
        parts = ['Difficulté ouverte : +35']
        priority_gain = {'high': 15, 'medium': 6}.get(item.priority, 0)
        if priority_gain:
            score += priority_gain
            parts.append(f'Priorité {item.get_priority_display().lower()} : +{priority_gain}')
        if item.task_id and item.task and item.task.due_date and item.task.due_date < today:
            score += 20
            parts.append('Tâche liée déjà en retard : +20')
        score = _cap(score)
        if score < RELEVANT:
            continue
        project = item.project or (item.task.project if item.task_id and item.task and item.task.project_id else None)
        task = item.task if item.task_id else None
        if task is not None:
            url = reverse('tasks:detail', args=[task.pk])
            subject = task.title
            due = task.due_date
        elif project is not None:
            url = reverse('projects:detail', args=[project.pk])
            subject = project.name
            due = project.end_date
        else:
            url = reverse('tasks:difficulties')
            subject = item.employee.full_name
            due = None
        signals.append({
            'fingerprint': f'difficulty:{item.pk}',
            'kind': 'difficulty',
            'severity': severity_for(score),
            'subject': subject,
            'project': project,
            'task': task,
            'cause': f'{item.employee.full_name} a signalé : {item.description.strip()[:240]}',
            'recommendation': 'Lire le signalement et confirmer si le blocage est traité.',
            'due_date': due,
            'score': score,
            'score_detail': '. '.join(parts) + f'. Total {score}/100.',
            'url': url,
        })
    return signals


def sync_operational_alerts(today=None):
    """Crée, met à jour ou résout les alertes. Ne duplique pas une situation ouverte."""
    today = today or timezone.localdate()
    signals = _signals(today)
    seen = []
    fresh = []
    for signal in signals:
        seen.append(signal['fingerprint'])
        row = OperationalAlert.objects.filter(fingerprint=signal['fingerprint']).first()
        if row is None:
            row = OperationalAlert.objects.create(
                status='open', first_seen=today, last_seen=today, notified=False, **signal,
            )
            fresh.append(row)
            continue
        reopened = row.status != 'open'
        for key, value in signal.items():
            setattr(row, key, value)
        row.status = 'open'
        row.resolved_on = None
        row.last_seen = today
        if reopened:
            row.notified = False
        row.save()
        if reopened:
            fresh.append(row)
    stale = OperationalAlert.objects.filter(status='open')
    if seen:
        stale = stale.exclude(fingerprint__in=seen)
    stale.update(status='resolved', resolved_on=today)
    from notifications.signals import _notify_admins
    for row in fresh:
        if row.notified:
            continue
        kind = 'danger' if row.severity == 'high' else 'warning' if row.severity == 'medium' else 'info'
        _notify_admins(
            f'Risque opérationnel : {row.subject}'[:200],
            f'{row.cause} {row.recommendation}'[:500],
            kind,
            row.url,
        )
        OperationalAlert.objects.filter(pk=row.pk).update(notified=True)
    return OperationalAlert.objects.filter(status='open')


def public_risk(row):
    return {
        'fingerprint': row.fingerprint,
        'risk_score': row.score,
        'risk_level': row.severity,
        'risk_cause': row.cause,
        'risk_recommendation': row.recommendation,
        'risk_due': row.due_date,
        'risk_detail': row.score_detail,
        'project_name': row.project.name if row.project_id else '',
        'task_title': row.task.title if row.task_id else row.subject,
    }


def enrich_alerts(alerts, today):
    """Ajoute le score aux alertes déjà produites, sans les dédoubler."""
    if today != timezone.localdate():
        return alerts
    sync_operational_alerts(today)
    rows = list(OperationalAlert.objects.filter(status='open').select_related('project', 'task'))
    by_task = {row.task_id: row for row in rows if row.task_id and row.kind in ('task_late', 'task_soon')}
    piles = {row.project_id: row for row in rows if row.kind == 'project_pile' and row.project_id}
    ends = {row.project_id: row for row in rows if row.kind == 'project_end' and row.project_id}
    used = set()
    for alert in alerts:
        url = alert.get('url') or ''
        row = None
        if alert.get('kind') == 'Activité' and '/tasks/' in url:
            pk = _url_pk(url)
            row = by_task.get(pk)
        elif alert.get('kind') == 'Projet' and '/projects/' in url:
            pk = _url_pk(url)
            if 'Plusieurs' in (alert.get('reason') or ''):
                row = piles.get(pk)
            elif 'date de fin' in (alert.get('reason') or ''):
                row = ends.get(pk)
        if row is None:
            continue
        alert.update(public_risk(row))
        used.add(row.pk)
    for row in rows:
        if row.kind != 'difficulty' or row.pk in used:
            continue
        if row.task_id and row.task_id in by_task:
            continue
        data = public_risk(row)
        alerts.append({
            'subject': row.subject,
            'kind': 'Difficulté',
            'project': data['project_name'] or 'Sans projet',
            'employee': '',
            'level': 'high' if row.severity == 'high' else 'medium',
            'reason': row.cause,
            'evidence': row.score_detail,
            'suggestion': row.recommendation,
            'url': row.url,
            'detected_on': row.last_seen,
            **data,
        })
        used.add(row.pk)
    return alerts


def _url_pk(url):
    chunk = (url or '').rstrip('/').split('/')[-1]
    return int(chunk) if chunk.isdigit() else None


def risk_board():
    """Indicateurs et classement pour le tableau de bord. Pas une seconde liste d'alertes."""
    today = timezone.localdate()
    sync_operational_alerts(today)
    rows = list(
        OperationalAlert.objects.filter(status='open').select_related('project').order_by('-score')
    )
    projects = {}
    for row in rows:
        if not row.project_id:
            continue
        bucket = projects.setdefault(row.project_id, {
            'name': row.project.name,
            'score': 0,
            'count': 0,
            'level': row.get_severity_display(),
            'cause': row.cause,
        })
        bucket['count'] += 1
        if row.score >= bucket['score']:
            bucket['score'] = row.score
            bucket['level'] = row.get_severity_display()
            bucket['cause'] = row.cause
    ranked = sorted(projects.values(), key=lambda item: (-item['score'], item['name']))[:5]
    return {
        'open': len(rows),
        'high': sum(row.severity == 'high' for row in rows),
        'medium': sum(row.severity == 'medium' for row in rows),
        'low': sum(row.severity == 'low' for row in rows),
        'projects': ranked,
    }


def api_risk_fields(row):
    due = row.due_date.strftime('%d/%m/%Y') if row.due_date else ''
    page = 'tasks' if row.task_id else 'projects' if row.project_id else ''
    return {
        'id': row.fingerprint,
        'project': row.project.name if row.project_id else '',
        'task': row.task.title if row.task_id else '',
        'severity': row.get_severity_display(),
        'cause': row.cause,
        'due': due,
        'recommendation': row.recommendation,
        'score': row.score,
        'detail': row.score_detail,
        'page': page,
        'url': row.url,
    }
