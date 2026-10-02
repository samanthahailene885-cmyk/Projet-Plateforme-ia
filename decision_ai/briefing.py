"""Textes factuels construits uniquement à partir des décomptes déjà calculés."""
from datetime import timedelta

from django.db.models import Q

from decision_ai.analytics import (
    CLOSED,
    IN_PROGRESS,
    agency_overview,
    day_stats,
    employee_report_payload,
    period_stats,
)
from employees.models import Employee
from projects.models import Project
from reports.models import DailyReport
from tasks.models import Task

MONTHS = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]


def _french_date(day):
    return f'{day.day} {MONTHS[day.month - 1]} {day.year}'


def _n(count, one, many):
    return f'{count} {one if count == 1 else many}'


def narrate_employee_day(payload):
    """Paragraphe du rapport à partir des activités enregistrées. Rien n'est inventé."""
    tasks = [task for task in payload['tasks'] if task['status_code'] != 'cancelled']
    if not tasks:
        return ''
    name = payload['employee_name']
    done = [task['title'] for task in tasks if task['status_code'] == 'completed']
    doing = [task['title'] for task in tasks if task['status_code'] in IN_PROGRESS]
    waiting = [task['title'] for task in tasks if task['status_code'] == 'todo']
    skipped = [task['title'] for task in tasks if task['status_code'] == 'not_done']
    projects = []
    for task in tasks:
        if task['project'] != 'Sans projet' and task['project'] not in projects:
            projects.append(task['project'])
    titles = ', '.join(task['title'] for task in tasks[:6])
    sentences = [f'Au cours de la journée, {name} a enregistré : {titles}.']
    if projects:
        sentences.append('Ces activités concernent ' + ', '.join(projects) + '.')
    bits = []
    if done:
        bits.append(f"{_n(len(done), 'activité a été finalisée', 'activités ont été finalisées')} ({', '.join(done[:4])})")
    if doing:
        bits.append(f"{_n(len(doing), 'activité reste en cours', 'activités restent en cours')} ({', '.join(doing[:4])})")
    if waiting:
        bits.append(_n(len(waiting), 'activité est non commencée', 'activités sont non commencées'))
    if skipped:
        bits.append(_n(len(skipped), 'activité est non réalisée', 'activités sont non réalisées'))
    if bits:
        sentences.append('. '.join(bit[0].upper() + bit[1:] for bit in bits) + '.')
    remarks = [(task['title'], task['comments']) for task in tasks if task['comments']]
    if remarks:
        title, comment = remarks[0]
        sentences.append(f'Une difficulté a été signalée sur « {title} » : {comment}')
        if len(remarks) > 1:
            sentences.append(f'{len(remarks)} remarques sont enregistrées au total.')
    else:
        sentences.append("Aucune difficulté n'est signalée sur ces activités.")
    return ' '.join(sentences)


def generate_reports_for_day(day):
    """Crée les rapports manquants des employés qui ont une todo list. N'écrase pas un rapport déjà envoyé."""
    from reports.services import ReportGenerator

    people = list(
        Employee.objects.select_related('user')
        .filter(status='active')
        .order_by('user__first_name', 'user__last_name')
    )
    existing = set(DailyReport.objects.filter(date=day).values_list('employee_id', flat=True))
    analyzed = generated = already = missing = 0
    for person in people:
        analyzed += 1
        if person.user_id in existing:
            already += 1
            continue
        payload = employee_report_payload(person.user, day)
        if payload['counts']['planned'] == 0:
            missing += 1
            continue
        DailyReport.objects.create(
            employee=person.user,
            date=day,
            content=narrate_employee_day(payload),
            tasks_completed=ReportGenerator.task_lines(person.user, day, {'completed'}),
            tasks_in_progress=ReportGenerator.task_lines(person.user, day, {'in_progress', 'review'}),
            ai_generated=True,
        )
        generated += 1
    return {
        'analyzed': analyzed,
        'generated': generated,
        'already': already,
        'missing': missing,
    }


def agency_brief(day):
    stats = day_stats(day)
    overview = agency_overview(day)
    late = Task.objects.filter(due_date__lt=day).exclude(status__in=CLOSED).count()
    projects = list(Project.objects.filter(status='in_progress').order_by('name')[:8])
    project_names = ', '.join(project.name for project in projects) if projects else 'aucun projet en cours'
    return (
        f"Résumé de l'activité du {_french_date(day)}. "
        f"L'agence compte {overview['active_employees']} employés actifs. "
        f"{overview['todo_filled']} ont renseigné une todo list et {overview['todo_missing']} ne l'ont pas fait. "
        f"Une todo list manquante n'est pas une absence. "
        f"Parmi les activités du jour, {stats['completed']} sont terminées, "
        f"{stats['in_progress']} sont en cours et {stats['todo']} ne sont pas commencées. "
        f"{late} tâches ouvertes ont une échéance dépassée. "
        f"Les projets en cours sont : {project_names}. "
        f"{len(stats['remarks'])} difficulté(s) signalée(s). "
        f"{overview['reports_today']} rapports soumis. "
        f"{overview['permissions_pending']} demandes de permission en attente."
    )


def difficulty_brief(day):
    remarks = day_stats(day)['remarks']
    if not remarks:
        return "Aucune difficulté n'est enregistrée aujourd'hui."
    themes = [
        ('une validation ou un retour client', ('client', 'validation', 'valider')),
        ('un point technique', ('technique', 'bug', 'erreur', 'bloqu')),
    ]
    used = set()
    lines = [
        f"{len(remarks)} remarque(s) sont enregistrées aujourd'hui, "
        f"pour {len({item['employee'] for item in remarks})} employé(s)."
    ]
    for label, words in themes:
        matched = [
            item for item in remarks
            if any(word in item['comment'].lower() for word in words)
        ]
        if matched:
            used.update(id(item) for item in matched)
            lines.append(f"{len(matched)} remarque(s) mentionnent {label}.")
    other = [item for item in remarks if id(item) not in used]
    if other and used:
        lines.append(f"{len(other)} autre(s) remarque(s) ne correspondent pas à ces mots.")
    for item in remarks[:8]:
        lines.append(f"- {item['employee']} / {item['task']} : {item['comment']}")
    return '\n'.join(lines)


def project_briefs(day):
    rows = []
    projects = Project.objects.exclude(status='cancelled').order_by('name')[:12]
    for project in projects:
        tasks = project.tasks.exclude(status='cancelled')
        late = tasks.filter(due_date__lt=day).exclude(status__in=CLOSED).count()
        if project.status not in ('in_progress', 'planning') and late == 0 and project.end_date >= day:
            continue
        done = tasks.filter(status='completed').count()
        doing = tasks.filter(status__in=IN_PROGRESS).count()
        remark = tasks.exclude(comments='').order_by('-updated_at').first()
        text = (
            f"Le projet {project.name} est {project.get_status_display().lower()}. "
            f"Avancement enregistré : {project.progress} %. "
            f"{_n(done, 'tâche est terminée', 'tâches sont terminées')}, "
            f"{_n(doing, 'tâche est en cours', 'tâches sont en cours')}, "
            f"{_n(late, 'tâche présente un retard', 'tâches présentent un retard')}."
        )
        if remark and (remark.comments or '').strip():
            text += f" Difficulté signalée : {remark.comments.strip()}"
        if project.end_date < day and project.status not in ('completed', 'cancelled'):
            text += f" La date de fin ({project.end_date:%d/%m/%Y}) est dépassée."
        rows.append({'name': project.name, 'progress': project.progress, 'text': text, 'late': late})
    return rows


def projects_needing_attention(day):
    rows = [row for row in project_briefs(day) if row['late'] or 'dépassée' in row['text']]
    if not rows:
        return "Aucun projet enregistré ne présente de tâche en retard ni de date de fin dépassée."
    return "Projets qui demandent une vérification :\n" + '\n'.join(f"- {row['text']}" for row in rows)


def trend_brief(day):
    start = day - timedelta(days=day.weekday())
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=6)
    current = period_stats(start, day)
    previous = period_stats(previous_start, previous_end)

    def remarks_between(begin, end):
        return Task.objects.filter(
            Q(planned_date__gte=begin, planned_date__lte=end)
            | Q(planned_date__isnull=True, due_date__gte=begin, due_date__lte=end)
        ).exclude(comments='').count()

    late_now = Task.objects.filter(due_date__lt=day).exclude(status__in=CLOSED).count()
    still_open_from_previous = Task.objects.filter(
        due_date__gte=previous_start,
        due_date__lte=previous_end,
    ).exclude(status__in=CLOSED).count()
    done_delta = current['completed'] - previous['completed']
    if done_delta > 0:
        done_sentence = (
            f"Le nombre d'activités passées au statut terminé est plus élevé "
            f"cette semaine ({current['completed']}) que la semaine précédente ({previous['completed']})."
        )
    elif done_delta < 0:
        done_sentence = (
            f"Le nombre d'activités passées au statut terminé est plus faible "
            f"cette semaine ({current['completed']}) que la semaine précédente ({previous['completed']})."
        )
    else:
        done_sentence = (
            f"Le nombre d'activités passées au statut terminé est le même "
            f"cette semaine et la semaine précédente ({current['completed']})."
        )
    return (
        f"{done_sentence} "
        f"Activités prévues : {current['planned']} cette semaine, {previous['planned']} la semaine précédente. "
        f"Remarques saisies : {remarks_between(start, day)} cette semaine, "
        f"{remarks_between(previous_start, previous_end)} la semaine précédente. "
        f"{late_now} tâches ouvertes ont aujourd'hui une échéance dépassée. "
        f"{still_open_from_previous} tâches dont l'échéance était la semaine précédente ne sont toujours pas terminées."
    )


def alert_brief(alerts):
    if not alerts:
        return "Aucune situation nécessitant une attention n'est détectée dans les données enregistrées."
    grouped = {}
    lines = []
    for alert in alerts:
        if alert['kind'] == 'Activité' and 'dépassée' in alert['reason']:
            grouped.setdefault(alert['project'], []).append(alert['subject'])
    for project, titles in list(grouped.items())[:8]:
        shown = ', '.join(titles[:4])
        lines.append(
            f"Le projet {project} présente {_n(len(titles), 'tâche en retard', 'tâches en retard')} : {shown}."
        )
    for alert in alerts:
        if alert['kind'] == 'Activité' and 'dépassée' in alert['reason']:
            continue
        if len(lines) >= 12:
            break
        lines.append(f"{alert['kind']} — {alert['subject']} : {alert['reason']} {alert['evidence']}")
    return '\n'.join(lines)
