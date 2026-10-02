"""Calculs factuels pour l'aide à la décision.

Les décomptes sont faits ici, en base. Le modèle de langage ne reçoit
que ces résultats déjà calculés et ne doit pas les recalculer.
"""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from django.urls import reverse

from attendance.models import Attendance
from employees.models import Employee
from permissions.models import PermissionRequest
from projects.models import Project
from reports.models import DailyReport
from tasks.models import Task


CLOSED = Task.CLOSED_STATUSES
IN_PROGRESS = ('in_progress', 'review')


def tasks_on_date(day, employee=None):
    """Activités rattachées à un jour, sans effacer les jours précédents."""
    qs = Task.objects.select_related('project', 'assigned_to__user').filter(
        Q(planned_date=day) | Q(planned_date__isnull=True, due_date=day)
    )
    if employee is not None:
        qs = qs.filter(assigned_to=employee)
    return qs


def _counts(qs):
    return {
        'planned': qs.count(),
        'completed': qs.filter(status='completed').count(),
        'in_progress': qs.filter(status__in=IN_PROGRESS).count(),
        'todo': qs.filter(status='todo').count(),
        'not_done': qs.filter(status='not_done').count(),
        'cancelled': qs.filter(status='cancelled').count(),
    }


def day_stats(day, employee=None):
    qs = tasks_on_date(day, employee=employee)
    stats = _counts(qs)
    stats['date'] = day
    remarks = []
    for task in qs.exclude(comments='').order_by('title'):
        remarks.append({
            'task': task.title,
            'project': task.project.name if task.project_id else 'Sans projet',
            'employee': task.assigned_to.full_name if task.assigned_to_id else 'Non assignée',
            'status': task.get_status_display(),
            'comment': task.comments.strip(),
        })
    stats['remarks'] = remarks
    stats['reports'] = DailyReport.objects.filter(date=day).count()
    if employee is None:
        stats['active_employees'] = Employee.objects.filter(status='active').count()
    return stats


def period_stats(start, end):
    planned = Task.objects.filter(
        Q(planned_date__gte=start, planned_date__lte=end)
        | Q(planned_date__isnull=True, due_date__gte=start, due_date__lte=end)
    )
    completed = Task.objects.filter(
        status='completed',
        updated_at__date__gte=start,
        updated_at__date__lte=end,
    )
    return {
        'start': start,
        'end': end,
        'planned': planned.count(),
        'completed': completed.count(),
        'in_progress': planned.filter(status__in=IN_PROGRESS).count(),
        'not_done': planned.filter(status='not_done').count(),
        'todo': planned.filter(status='todo').count(),
    }


def collect_alerts(today):
    """Règles explicites. Aucun modèle de machine learning."""
    alerts = []
    soon = today + timedelta(days=2)

    overdue = (
        Task.objects.filter(due_date__lt=today)
        .exclude(status__in=CLOSED)
        .select_related('project', 'assigned_to__user')
        .order_by('due_date')
    )
    for task in overdue[:40]:
        days_late = (today - task.due_date).days
        alerts.append({
            'subject': task.title,
            'kind': 'Activité',
            'project': task.project.name if task.project_id else 'Sans projet',
            'employee': task.assigned_to.full_name if task.assigned_to_id else 'Non assignée',
            'level': 'high',
            'reason': "L'échéance est dépassée et l'activité n'est pas terminée.",
            'evidence': (
                f"Date limite : {task.due_date:%d/%m/%Y}. "
                f"Statut : {task.get_status_display()}. "
                f"Retard constaté : {days_late} jour(s)."
            ),
            'suggestion': "Vérifier l'avancement et confirmer si l'échéance doit être revue.",
            'url': reverse('tasks:detail', args=[task.pk]),
            'detected_on': today,
        })

    upcoming = (
        Task.objects.filter(
            due_date__gte=today,
            due_date__lte=soon,
            priority__in=['high', 'urgent'],
        )
        .exclude(status__in=CLOSED)
        .select_related('project', 'assigned_to__user')
        .order_by('due_date')
    )
    for task in upcoming[:20]:
        alerts.append({
            'subject': task.title,
            'kind': 'Activité',
            'project': task.project.name if task.project_id else 'Sans projet',
            'employee': task.assigned_to.full_name if task.assigned_to_id else 'Non assignée',
            'level': 'medium',
            'reason': "Activité prioritaire dont l'échéance est dans les deux prochains jours.",
            'evidence': (
                f"Date limite : {task.due_date:%d/%m/%Y}. "
                f"Priorité : {task.get_priority_display()}. "
                f"Statut : {task.get_status_display()}."
            ),
            'suggestion': "Vérifier que les éléments nécessaires sont disponibles avant l'échéance.",
            'url': reverse('tasks:detail', args=[task.pk]),
            'detected_on': today,
        })

    open_overdue = (
        Task.objects.filter(due_date__lt=today, project__isnull=False)
        .exclude(status__in=CLOSED)
        .select_related('project')
    )
    by_project = {}
    for task in open_overdue:
        bucket = by_project.setdefault(task.project_id, {'project': task.project, 'count': 0})
        bucket['count'] += 1
    for bucket in by_project.values():
        if bucket['count'] < 2:
            continue
        project = bucket['project']
        alerts.append({
            'subject': project.name,
            'kind': 'Projet',
            'project': project.name,
            'employee': project.client,
            'level': 'high',
            'reason': "Plusieurs activités de ce projet ont une échéance dépassée.",
            'evidence': (
                f"{bucket['count']} activité(s) non terminée(s) après leur date limite. "
                f"Fin de projet indiquée : {project.end_date:%d/%m/%Y}. "
                f"Avancement saisi : {project.progress} %."
            ),
            'suggestion': "Vérifier les activités en retard de ce projet et leur impact sur la date de fin.",
            'url': reverse('projects:detail', args=[project.pk]),
            'detected_on': today,
        })

    late_projects = Project.objects.filter(end_date__lt=today).exclude(
        status__in=['completed', 'cancelled']
    )
    for project in late_projects[:20]:
        alerts.append({
            'subject': project.name,
            'kind': 'Projet',
            'project': project.name,
            'employee': project.client,
            'level': 'medium',
            'reason': "La date de fin du projet est dépassée et le projet n'est pas marqué terminé.",
            'evidence': (
                f"Date de fin : {project.end_date:%d/%m/%Y}. "
                f"Statut : {project.get_status_display()}. "
                f"Avancement saisi : {project.progress} %."
            ),
            'suggestion': "Vérifier si la date de fin ou le statut du projet doit être mis à jour.",
            'url': reverse('projects:detail', args=[project.pk]),
            'detected_on': today,
        })

    remarked = (
        tasks_on_date(today)
        .exclude(comments='')
        .exclude(status='completed')
        .select_related('project', 'assigned_to__user')
    )
    for task in remarked[:15]:
        alerts.append({
            'subject': task.title,
            'kind': 'Remarque',
            'project': task.project.name if task.project_id else 'Sans projet',
            'employee': task.assigned_to.full_name if task.assigned_to_id else 'Non assignée',
            'level': 'medium',
            'reason': "Une remarque a été saisie sur une activité qui n'est pas terminée.",
            'evidence': f"Statut : {task.get_status_display()}. Remarque : {task.comments.strip()[:400]}",
            'suggestion': "Lire la remarque et vérifier s'il s'agit d'un blocage à traiter.",
            'url': reverse('tasks:detail', args=[task.pk]),
            'detected_on': today,
        })

    for perm in PermissionRequest.objects.filter(status='pending').select_related('employee__user')[:15]:
        alerts.append({
            'subject': perm.employee.full_name,
            'kind': 'Permission',
            'project': perm.get_type_display(),
            'employee': perm.employee.full_name,
            'level': 'medium',
            'reason': "Une demande de permission est en attente de décision.",
            'evidence': (
                f"Du {perm.start_date:%d/%m/%Y} au {perm.end_date:%d/%m/%Y}. "
                f"Motif : {perm.motif_display[:300]}"
            ),
            'suggestion': "Ouvrir la demande pour l'accepter ou la refuser.",
            'url': reverse('permissions:detail', args=[perm.pk]),
            'detected_on': today,
        })

    filled_ids = set(tasks_on_date(today).values_list('assigned_to_id', flat=True))
    filled_ids.discard(None)
    missing = Employee.objects.select_related('user').filter(status='active').exclude(pk__in=filled_ids)
    for employee in missing[:20]:
        alerts.append({
            'subject': employee.full_name,
            'kind': 'Todo list',
            'project': '—',
            'employee': employee.full_name,
            'level': 'low',
            'reason': "Aucune activité n'est enregistrée pour cette date. Ce n'est pas une absence.",
            'evidence': f"Poste : {employee.get_position_display()}. Date contrôlée : {today:%d/%m/%Y}.",
            'suggestion': "Vérifier avec l'employé si le plan du jour doit encore être saisi.",
            'url': f"{reverse('tasks:daily')}?date={today.isoformat()}&employee={employee.pk}",
            'detected_on': today,
        })

    reported_ids = set(DailyReport.objects.filter(date=today).values_list('employee_id', flat=True))
    without_report = [
        employee.full_name
        for employee in Employee.objects.select_related('user').filter(status='active').order_by('user__last_name')
        if employee.user_id not in reported_ids
    ]
    if without_report:
        shown = ', '.join(without_report[:12])
        extra = '' if len(without_report) <= 12 else f' et {len(without_report) - 12} autre(s)'
        alerts.append({
            'subject': 'Rapports non soumis',
            'kind': 'Rapport',
            'project': '—',
            'employee': 'Système',
            'level': 'low',
            'reason': "Des employés actifs n'ont pas de rapport enregistré pour cette date.",
            'evidence': f"{len(without_report)} employé(s) : {shown}{extra}.",
            'suggestion': "Générer les rapports du jour à partir des activités déjà saisies, ou demander l'envoi du rapport.",
            'url': reverse('reports:list') + f'?date={today.isoformat()}',
            'detected_on': today,
        })

    return alerts


def agency_overview(today):
    """Indicateurs du jour, calculés uniquement sur les enregistrements."""
    active = Employee.objects.filter(status='active')
    planned = tasks_on_date(today)
    filled_ids = set(planned.values_list('assigned_to_id', flat=True))
    filled_ids.discard(None)
    filled = active.filter(pk__in=filled_ids).count()
    counts = _counts(planned)
    late_projects = Project.objects.filter(end_date__lt=today).exclude(
        status__in=['completed', 'cancelled']
    )
    return {
        'active_employees': active.count(),
        'todo_filled': filled,
        'todo_missing': active.exclude(pk__in=filled_ids).count(),
        'planned': counts['planned'],
        'completed': counts['completed'],
        'in_progress': counts['in_progress'],
        'not_started': counts['todo'],
        'not_done': counts['not_done'],
        'projects_active': Project.objects.filter(status='in_progress').count(),
        'projects_late': late_projects.count(),
        'reports_today': DailyReport.objects.filter(date=today).count(),
        'permissions_pending': PermissionRequest.objects.filter(status='pending').count(),
    }


def recent_events(limit=12):
    """Fil construit à partir des dates déjà enregistrées, du plus récent au plus ancien."""
    events = []
    for task in Task.objects.select_related('assigned_to__user', 'project').order_by('-updated_at')[:24]:
        who = task.assigned_to.full_name if task.assigned_to_id else 'Non assignée'
        created_gap = (task.updated_at - task.created_at).total_seconds()
        if task.status == 'completed':
            kind = 'Activité terminée'
        elif (task.comments or '').strip() and created_gap > 5:
            kind = 'Difficulté signalée'
        elif created_gap < 5:
            kind = 'Todo list créée'
        else:
            kind = 'Activité mise à jour'
        events.append({
            'kind': kind,
            'who': who,
            'label': task.title,
            'when': task.updated_at,
            'url': reverse('tasks:detail', args=[task.pk]),
        })
    for report in DailyReport.objects.select_related('employee').order_by('-updated_at')[:12]:
        name = f'{report.employee.first_name} {report.employee.last_name}'.strip() or report.employee.username
        events.append({
            'kind': 'Rapport soumis',
            'who': name,
            'label': report.date.strftime('%d/%m/%Y'),
            'when': report.updated_at,
            'url': reverse('reports:detail', args=[report.pk]),
        })
    for perm in PermissionRequest.objects.select_related('employee__user').order_by('-created_at')[:12]:
        events.append({
            'kind': 'Demande de permission',
            'who': perm.employee.full_name,
            'label': perm.get_type_display(),
            'when': perm.created_at,
            'url': reverse('permissions:detail', args=[perm.pk]),
        })
    for project in Project.objects.order_by('-updated_at')[:8]:
        events.append({
            'kind': 'Projet enregistré',
            'who': project.client or 'Client non renseigné',
            'label': project.name,
            'when': project.updated_at,
            'url': reverse('projects:detail', args=[project.pk]),
        })
    events.sort(key=lambda item: item['when'], reverse=True)
    return events[:limit]


def project_delay_risks(today=None):
    """Liste courte utilisée par le tableau de bord responsable."""
    today = today or timezone.now().date()
    risks = []
    seen = set()
    projects = Project.objects.filter(status__in=['planning', 'in_progress', 'on_hold'])
    for project in projects:
        days_remaining = project.days_remaining
        if project.end_date < today:
            reason = 'Date de fin dépassée'
            level = 'high'
        elif days_remaining is not None and days_remaining <= 7:
            reason = 'Date de fin dans les 7 jours'
            level = 'high' if days_remaining <= 3 else 'medium'
        elif project.progress < 50 and days_remaining is not None and days_remaining < 14:
            reason = 'Avancement saisi inférieur à 50 % à moins de 14 jours de la fin'
            level = 'high'
        else:
            continue
        if project.id in seen:
            continue
        seen.add(project.id)
        risks.append({
            'project': project,
            'risk_level': level,
            'days_remaining': days_remaining,
            'reason': reason,
        })
    return risks


def workload_rows(today):
    """Volumes d'activités. Ne mesure pas le temps de travail ni la performance."""
    current_start = today - timedelta(days=6)
    previous_end = today - timedelta(days=7)
    previous_start = today - timedelta(days=13)
    rows = []
    employees = Employee.objects.select_related('user').filter(status='active').order_by('user__last_name')
    for employee in employees:
        current = tasks_between(employee, current_start, today)
        previous = tasks_between(employee, previous_start, previous_end)
        open_now = employee.assigned_tasks.exclude(status__in=CLOSED).count()
        in_progress = employee.assigned_tasks.filter(status__in=IN_PROGRESS).count()
        high_priority = employee.assigned_tasks.filter(
            priority__in=['high', 'urgent']
        ).exclude(status__in=CLOSED).count()
        level = 'observed'
        note = (
            "Indicateur descriptif : nombre d'activités, pas une mesure du temps de travail "
            "ni de la performance."
        )
        if current['planned'] >= 8 and current['planned'] >= previous['planned'] + 3:
            level = 'high_volume'
            note = (
                "Le nombre d'activités prévues sur 7 jours est plus élevé que sur la période précédente. "
                "Cela peut mériter une vérification. Ce n'est pas un jugement de performance."
            )
        elif open_now >= 8:
            level = 'high_volume'
            note = (
                "Plusieurs activités restent ouvertes. À vérifier avec l'employé "
                "si certaines sont bloquées ou mal datées."
            )
        rows.append({
            'employee': employee,
            'planned': current['planned'],
            'previous_planned': previous['planned'],
            'in_progress': in_progress,
            'unfinished': open_now,
            'not_done': current['not_done'],
            'high_priority_tasks': high_priority,
            'total_tasks': open_now,
            'workload_level': level,
            'recommendation': note,
        })
    return rows


def tasks_between(employee, start, end):
    qs = employee.assigned_tasks.filter(
        Q(planned_date__gte=start, planned_date__lte=end)
        | Q(planned_date__isnull=True, due_date__gte=start, due_date__lte=end)
    )
    return _counts(qs)


def _fmt_stats(stats):
    return (
        f"Date : {stats['date']:%d/%m/%Y}\n"
        f"Activités prévues : {stats['planned']}\n"
        f"Terminées : {stats['completed']}\n"
        f"En cours (y compris en révision) : {stats['in_progress']}\n"
        f"À faire : {stats['todo']}\n"
        f"Non réalisées : {stats['not_done']}\n"
        f"Annulées : {stats['cancelled']}\n"
        f"Rapports journaliers enregistrés : {stats['reports']}"
    )


def _fmt_tasks(qs, limit=40):
    lines = []
    for task in qs.order_by('title')[:limit]:
        project = task.project.name if task.project_id else 'Sans projet'
        person = task.assigned_to.full_name if task.assigned_to_id else 'Non assignée'
        comment = task.comments.strip() if task.comments else 'aucune'
        due = task.due_date.strftime('%d/%m/%Y') if task.due_date else 'non renseignée'
        lines.append(
            f"- {task.title} | employé : {person} | projet : {project} | "
            f"statut : {task.get_status_display()} | échéance : {due} | remarque : {comment}"
        )
    return '\n'.join(lines) if lines else 'Aucune activité.'


def _fmt_alerts(alerts):
    if not alerts:
        return "Aucune alerte produite par les règles."
    lines = []
    for alert in alerts[:20]:
        lines.append(
            f"- {alert['kind']} : {alert['subject']} | {alert['reason']} | "
            f"Données : {alert['evidence']}"
        )
    return '\n'.join(lines)


def _names(employees):
    return ', '.join(employees) if employees else 'aucun'


def assistant_context(question, today):
    """Sélectionne uniquement les blocs utiles à la question, déjà chiffrés."""
    q = (question or '').lower()
    today_stats = day_stats(today)
    stats = today_stats
    overview = agency_overview(today)
    active = list(
        Employee.objects.select_related('user')
        .filter(status='active')
        .order_by('user__last_name', 'user__first_name')
    )
    planned_today = tasks_on_date(today)
    filled_ids = set(planned_today.values_list('assigned_to_id', flat=True))
    filled_ids.discard(None)
    filled = [employee.full_name for employee in active if employee.pk in filled_ids]
    missing = [employee.full_name for employee in active if employee.pk not in filled_ids]
    late_open = (
        Task.objects.filter(due_date__lt=today)
        .exclude(status__in=CLOSED)
        .count()
    )
    sent = DailyReport.objects.filter(date=today).select_related('employee')
    sent_ids = set(sent.values_list('employee_id', flat=True))
    reports_sent = []
    reports_missing = []
    for employee in active:
        if employee.user_id in sent_ids:
            reports_sent.append(employee.full_name)
        else:
            reports_missing.append(employee.full_name)
    alerts = collect_alerts(today)
    empty_day = (
        today_stats['planned'] == 0
        and today_stats['reports'] == 0
        and late_open == 0
        and not today_stats['remarks']
    )
    blocks = [
        (
            "JOURNÉE SANS SAISIE. Aucune activité, aucune todo list et aucun rapport "
            "ne sont enregistrés pour aujourd'hui. Réponds que rien n'a été saisi. "
            "Ne cite aucun employé comme ayant travaillé.\n"
            if empty_day else ""
        )
        + "CHIFFRES DÉFINITIFS, CALCULÉS PAR LE SYSTÈME. NE PAS LES RECALCULER.\n"
        + _fmt_stats(stats)
        + f"\nEmployés actifs : {overview['active_employees']}"
        + f"\nTodo lists renseignées aujourd'hui : {overview['todo_filled']}"
        + f"\nEmployés actifs sans todo list aujourd'hui : {overview['todo_missing']}"
        + "\nUne todo list manquante n'est pas une absence."
        + f"\nAvec une todo list ({len(filled)}) : {_names(filled)}"
        + f"\nSans todo list ({len(missing)}) : {_names(missing)}"
        + f"\nTâches ouvertes en retard (échéance dépassée, hors terminées, annulées et non réalisées) : {late_open}"
        + f"\nProjets en cours : {overview['projects_active']}"
        + f"\nProjets dont la date de fin est dépassée : {overview['projects_late']}"
        + f"\nRapports soumis aujourd'hui : {len(reports_sent)} ({_names(reports_sent)})"
        + f"\nRapports manquants parmi les employés actifs : {len(reports_missing)} ({_names(reports_missing)})"
        + f"\nPermissions en attente : {overview['permissions_pending']}"
        + f"\nDifficultés signalées aujourd'hui (remarques enregistrées) : {len(stats['remarks'])}"
        + f"\nAlertes produites par les règles : {len(alerts)}"
    ]

    wants_week = 'semaine' in q
    wants_tasks = any(word in q for word in (
        'activité', 'activite', 'tâche', 'tache', 'prévu', 'prevu', 'aujourd',
        'reste', 'terminer', 'terminée', 'terminee', 'résume', 'resume', 'todo',
    ))
    wants_alerts = any(word in q for word in (
        'retard', 'échéance', 'echeance', 'alerte', 'risque', 'attention',
    ))
    wants_remarks = any(word in q for word in (
        'difficult', 'remarque', 'blocage', 'problème', 'probleme',
    ))
    wants_projects = 'projet' in q
    wants_people = any(word in q for word in (
        'employé', 'employe', 'qui ', 'équipe', 'equipe',
    ))
    wants_reports = 'rapport' in q
    wants_attendance = any(word in q for word in ('absent', 'présen', 'presen', 'retardataire'))
    wants_permissions = any(word in q for word in ('permission', 'congé', 'conge'))
    wants_todo = any(word in q for word in ('todo', 'renseign', 'rempli'))

    if wants_alerts or 'vigilance' in q or 'résume' in q or 'resume' in q:
        wants_alerts = True

    if wants_week or 'terminé' in q or 'termine' in q:
        start = today - timedelta(days=today.weekday())
        week = period_stats(start, today)
        blocks.append(
            "PÉRIODE, CALCULÉE PAR LE SYSTÈME\n"
            f"Du {week['start']:%d/%m/%Y} au {week['end']:%d/%m/%Y}\n"
            f"Activités prévues sur la période : {week['planned']}\n"
            f"Activités passées au statut terminé sur la période : {week['completed']}\n"
            f"En cours parmi les activités prévues : {week['in_progress']}\n"
            f"Non réalisées parmi les activités prévues : {week['not_done']}\n"
            f"Encore à faire : {week['todo']}"
        )

    if wants_alerts or wants_projects:
        blocks.append("ALERTES PRODUITES PAR LES RÈGLES\n" + _fmt_alerts(alerts))

    if wants_remarks:
        if stats['remarks']:
            lines = [
                f"- {item['employee']} / {item['task']} ({item['status']}) : {item['comment'][:400]}"
                for item in stats['remarks'][:20]
            ]
            blocks.append("REMARQUES SAISIES\n" + '\n'.join(lines))
        else:
            blocks.append("REMARQUES SAISIES\nAucune remarque enregistrée pour cette date.")

    if wants_projects:
        lines = []
        for project in Project.objects.all().order_by('name')[:30]:
            late = project.tasks.filter(due_date__lt=today).exclude(status__in=CLOSED).count()
            lines.append(
                f"- {project.name} | client : {project.client} | "
                f"statut : {project.get_status_display()} | avancement saisi : {project.progress} % | "
                f"fin : {project.end_date:%d/%m/%Y} | activités en retard : {late}"
            )
        blocks.append("PROJETS\n" + ('\n'.join(lines) if lines else 'Aucun projet.'))

    if wants_people or wants_attendance or wants_todo:
        lines = []
        missing = []
        filled = []
        for employee in Employee.objects.select_related('user').filter(status='active').order_by('user__last_name'):
            counts = _counts(tasks_on_date(today, employee))
            if counts['planned']:
                filled.append(employee.full_name)
                state = f"todo list renseignée ({counts['planned']} activité(s))"
            else:
                missing.append(employee.full_name)
                state = "todo list non renseignée aujourd'hui, ce n'est pas une absence"
            lines.append(
                f"- {employee.full_name} | poste : {employee.get_position_display()} | "
                f"{state} | terminées : {counts['completed']} | "
                f"en cours : {counts['in_progress']} | non réalisées : {counts['not_done']}"
            )
        blocks.append(
            "EMPLOYÉS ACTIFS\n"
            + ('\n'.join(lines) if lines else 'Aucun employé actif enregistré.')
            + "\n\nCOMPARAISON TODO LIST DU JOUR\n"
            + "Les employés actifs sont comparés aux activités dont le jour prévu est aujourd'hui.\n"
            + "Ne pas conclure qu'un employé est absent uniquement parce que sa todo list manque.\n"
            + f"Avec une todo list ({len(filled)}) : {', '.join(filled) if filled else 'aucun'}\n"
            + f"Sans todo list ({len(missing)}) : {', '.join(missing) if missing else 'aucun'}"
        )

    if wants_permissions:
        pending = PermissionRequest.objects.filter(status='pending').select_related('employee__user')
        if pending.exists():
            lines = [
                f"- {item.employee.full_name} | {item.get_type_display()} | "
                f"du {item.start_date:%d/%m/%Y} au {item.end_date:%d/%m/%Y} | "
                f"motif : {item.motif_display} | statut : {item.get_status_display()}"
                for item in pending[:20]
            ]
            blocks.append("PERMISSIONS EN ATTENTE\n" + '\n'.join(lines))
        else:
            blocks.append("PERMISSIONS EN ATTENTE\nAucune demande en attente.")

    if wants_attendance:
        attendance = Attendance.objects.filter(date=today).select_related('employee__user')
        if attendance.exists():
            lines = [
                f"- {row.employee.full_name} : {row.get_status_display()}"
                for row in attendance
            ]
            blocks.append("PRÉSENCES ENREGISTRÉES AUJOURD'HUI\n" + '\n'.join(lines))
        else:
            blocks.append("PRÉSENCES ENREGISTRÉES AUJOURD'HUI\nAucune présence saisie pour cette date.")

    if wants_reports:
        sent = DailyReport.objects.filter(date=today).select_related('employee')
        names = [f"{r.employee.first_name} {r.employee.last_name}".strip() or r.employee.username for r in sent]
        missing = []
        sent_ids = set(sent.values_list('employee_id', flat=True))
        for employee in Employee.objects.select_related('user').filter(status='active'):
            if employee.user_id not in sent_ids:
                missing.append(employee.full_name)
        blocks.append(
            "RAPPORTS\n"
            f"Enregistrés ({len(names)}) : {', '.join(names) if names else 'aucun'}\n"
            f"Employés actifs sans rapport pour cette date : {', '.join(missing) if missing else 'aucun'}"
        )

    if wants_tasks or len(blocks) == 1:
        blocks.append("ACTIVITÉS DU JOUR\n" + _fmt_tasks(tasks_on_date(today)))

    blocks.append(
        "Si la question porte sur une information absente de ces blocs, "
        "réponds qu'elle n'est pas disponible dans les données enregistrées. "
        "N'invente aucun nom, aucun chiffre et aucune activité."
    )
    return '\n\n'.join(blocks)


def recorded_answer(question, today):
    """Réponse factuelle, sans modèle de langage. Aucun nom ni chiffre n'est inventé."""
    q = (question or '').lower()
    sections = []

    def wants(*words):
        return any(word in q for word in words)

    if wants('absent', 'présen', 'presen'):
        absent = Attendance.objects.filter(date=today, status='absent').select_related('employee__user')
        names = [row.employee.full_name for row in absent]
        if names:
            sections.append("Absents enregistrés aujourd'hui : " + ', '.join(names) + '.')
        else:
            sections.append("Aucune absence n'est enregistrée aujourd'hui.")
        sections.append("Une todo list manquante n'est pas une absence.")

    if wants('todo', 'renseign', 'rempli'):
        active = Employee.objects.select_related('user').filter(status='active').order_by('user__last_name', 'user__first_name')
        filled_ids = set(tasks_on_date(today).values_list('assigned_to_id', flat=True))
        filled_ids.discard(None)
        missing = [employee.full_name for employee in active if employee.pk not in filled_ids]
        if missing:
            sections.append(
                "Employés actifs sans todo list aujourd'hui : " + ', '.join(missing) + '.'
            )
        else:
            sections.append("Tous les employés actifs ont une todo list aujourd'hui.")
        sections.append("Une todo list manquante n'est pas une absence.")

    if wants('en cours', 'toujours en cours'):
        doing = Task.objects.filter(status__in=IN_PROGRESS).select_related('assigned_to__user', 'project').order_by('title')
        total = doing.count()
        if total:
            lines = []
            for task in doing[:12]:
                person = task.assigned_to.full_name if task.assigned_to_id else 'Non assignée'
                lines.append(f'- {task.title} ({person})')
            extra = '' if total <= 12 else f'\nEt {total - 12} autre(s).'
            sections.append(f'Activités au statut en cours : {total}.\n' + '\n'.join(lines) + extra)
        else:
            sections.append("Aucune activité n'est au statut en cours.")

    if wants('difficult', 'remarque', 'blocage'):
        from decision_ai.briefing import difficulty_brief
        sections.append(difficulty_brief(today))

    if wants('attention', 'vigilance') or (wants('projet', 'avancement') and wants('retard')):
        from decision_ai.briefing import projects_needing_attention
        sections.append(projects_needing_attention(today))
    elif wants('projet', 'avancement'):
        from decision_ai.briefing import project_briefs
        rows = project_briefs(today)
        if rows:
            sections.append('\n'.join(row['text'] for row in rows[:8]))
        else:
            sections.append("Aucun projet en cours n'est enregistré.")

    if wants('tendance', 'hier', 'précédente', 'precedente'):
        from decision_ai.briefing import trend_brief
        sections.append(trend_brief(today))

    if wants('permission', 'congé', 'conge'):
        pending = PermissionRequest.objects.filter(status='pending').select_related('employee__user')
        total = pending.count()
        if total:
            lines = []
            for item in pending[:12]:
                lines.append(
                    f"{item.employee.full_name} — {item.get_type_display()}, "
                    f"du {item.start_date:%d/%m/%Y} au {item.end_date:%d/%m/%Y}. "
                    f"Motif : {item.motif_display}. Statut : {item.get_status_display()}."
                )
            head = (
                f"{total} demande de permission est en attente."
                if total == 1
                else f"{total} demandes de permission sont en attente."
            )
            extra = '' if total <= 12 else f"\nEt {total - 12} autre(s)."
            guide = ''
            if wants('gérer', 'gerer', 'comment', 'traiter', 'approuv', 'refus'):
                guide = (
                    "\nPour la traiter, ouvrez Permissions et absences, "
                    "puis approuvez ou refusez la demande."
                    if total == 1
                    else "\nPour les traiter, ouvrez Permissions et absences, "
                    "puis approuvez ou refusez chaque demande."
                )
            sections.append(head + '\n' + '\n'.join(lines) + extra + guide)
        else:
            sections.append('Aucune demande de permission en attente.')

    if wants('rapport') and wants('génér', 'gener'):
        sections.append(
            "Le rapport se génère depuis la page Rapports, à partir des activités déjà enregistrées pour la date choisie."
        )

    if wants('performance', 'taux', 'complét', 'complet'):
        stats = day_stats(today)
        if stats['planned']:
            percent = round(stats['completed'] * 100 / stats['planned'])
            sections.append(
                f"Parmi les {stats['planned']} activités prévues aujourd'hui, "
                f"{stats['completed']} sont terminées, soit {percent} %. "
                "Ce pourcentage est un décompte, pas un jugement de performance."
            )
        else:
            sections.append("Aucune activité n'est prévue aujourd'hui, donc aucun taux n'est calculé.")

    day_story = wants('aujourd', 'passé', 'passe', 'journée', 'journee', 'arriv') or not sections
    if day_story:
        from reports.synthesis import collect_team_synthesis, compose_team_synthesis
        dossier = collect_team_synthesis(today)
        if dossier['analyzed']:
            sections.append(compose_team_synthesis(dossier))
    if wants('semaine', 'récap', 'recap', 'résume', 'resume', 'agence') or day_story:
        from decision_ai.briefing import agency_brief
        sections.append(agency_brief(today))
        if wants('semaine'):
            start = today - timedelta(days=today.weekday())
            week = period_stats(start, today)
            sections.append(
                f"Depuis lundi : {week['planned']} activités prévues, "
                f"{week['completed']} passées au statut terminé."
            )

    return '\n\n'.join(sections)


def employee_report_payload(user, day):
    try:
        employee = user.employee_profile
    except Exception:
        employee = None
    qs = tasks_on_date(day, employee) if employee else Task.objects.none()
    tasks = []
    hours = []
    for task in qs.order_by('status', 'title'):
        tasks.append({
            'title': task.title,
            'status': task.get_status_display(),
            'status_code': task.status,
            'project': task.project.name if task.project_id else 'Sans projet',
            'comments': (task.comments or '').strip(),
            'description': (task.description or '').strip(),
            'actual_hours': task.actual_hours,
        })
        if task.actual_hours is not None:
            hours.append(task.actual_hours)
    counts = _counts(qs)
    return {
        'date': day,
        'employee_name': f"{user.first_name} {user.last_name}".strip() or user.username,
        'tasks': tasks,
        'counts': counts,
        'hours_known': bool(hours),
        'hours_total': sum(hours) if hours else None,
    }


def format_employee_payload(payload):
    counts = payload['counts']
    lines = [
        f"Date du rapport : {payload['date']:%d/%m/%Y}",
        f"Employé : {payload['employee_name']}",
        f"Activités prévues : {counts['planned']}",
        f"Terminées : {counts['completed']}",
        f"En cours : {counts['in_progress']}",
        f"À faire : {counts['todo']}",
        f"Non réalisées : {counts['not_done']}",
        f"Annulées : {counts['cancelled']}",
    ]
    if payload['hours_known']:
        lines.append(f"Heures réelles saisies (somme) : {payload['hours_total']}")
    else:
        lines.append("Heures réelles : non renseignées. Ne pas estimer de durée.")
    lines.append("Détail des activités enregistrées :")
    if not payload['tasks']:
        lines.append("Aucune activité enregistrée pour cette date.")
    for task in payload['tasks']:
        remark = task['comments'] or 'aucune remarque'
        lines.append(
            f"- {task['title']} | statut : {task['status']} | projet : {task['project']} | "
            f"remarque : {remark}"
        )
    lines.append(
        "Rédige le rapport uniquement avec ces éléments. "
        "Si une rubrique n'a pas de donnée, indique que l'information n'est pas renseignée."
    )
    return '\n'.join(lines)
