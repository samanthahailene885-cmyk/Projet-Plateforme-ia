"""Dossier factuel des rapports soumis, pour une seule synthèse d'équipe.

Les décomptes sont calculés ici. Le modèle de langage ne fait que les reformuler.
"""
import html
import re

from django.utils import timezone

from decision_ai.analytics import IN_PROGRESS, tasks_on_date
from employees.models import Employee
from reports.models import DailyReport


SYNTHESIS_TYPE = 'team_daily_synthesis'

_TITLE_COUNT = re.compile(r'\((\d+) rapports?\)')


def _person_name(user):
    raw = f'{user.first_name} {user.last_name}'.strip() or user.username
    name = ' '.join(part[:1].upper() + part[1:] for part in raw.split() if part)
    if user.gender == 'F':
        return f'Mme {name}'
    if user.gender == 'M':
        return f'M. {name}'
    return name


def _public_remark(task):
    remark = (task.comments or '').strip()
    marker = remark.lower()
    if not remark or marker == 'todo:' or marker.startswith(('todo:', 'liee:')):
        return ''
    return remark


def _activity_item(task):
    return {
        'title': (task.title or '').strip(),
        'project': task.project.name if task.project_id else '',
        'remark': _public_remark(task),
    }


def _activity_line(task):
    item = _activity_item(task)
    project = item['project'] or 'Sans projet'
    line = f"- {item['title']} | projet : {project}"
    if item['remark']:
        line += f" | remarque : {item['remark']}"
    return line


def _section(title, lines):
    body = '\n'.join(lines) if lines else 'Non renseigné.'
    return f'{title} :\n{body}'


def _document_text(report):
    uploaded = getattr(report, 'uploaded_pdf', None)
    if not uploaded:
        return ''
    try:
        from reports.extract import extract_report_text
        return extract_report_text(uploaded).strip()[:8000]
    except Exception:
        return ''


def collect_team_synthesis(day):
    """Rapports soumis du jour et activités liées. Aucun texte n'est inventé."""
    people = list(
        Employee.objects.select_related('user')
        .filter(status='active', user__role='employee')
        .order_by('user__first_name', 'user__last_name', 'pk')
    )
    stored = {
        report.employee_id: report
        for report in DailyReport.objects.filter(
            date=day,
            employee_id__in=[person.user_id for person in people],
        )
    }

    reports = []
    completed = in_progress = not_done = todo = difficulties = 0
    without_activity = 0
    projects = []

    for person in people:
        tasks = [
            task for task in tasks_on_date(day, person).select_related('project')
            if task.status != 'cancelled'
        ]
        report = stored.get(person.user_id)
        submitted = report is not None and bool((report.content or '').strip())
        if not tasks:
            without_activity += 1
        if not submitted:
            continue

        done = [task for task in tasks if task.status == 'completed']
        doing = [task for task in tasks if task.status in IN_PROGRESS]
        skipped = [task for task in tasks if task.status == 'not_done']
        waiting = [task for task in tasks if task.status == 'todo']
        remarks = [task for task in tasks if _public_remark(task)]
        completed += len(done)
        in_progress += len(doing)
        not_done += len(skipped)
        todo += len(waiting)
        difficulties += len(remarks)
        for task in tasks:
            if task.project_id and task.project.name not in projects:
                projects.append(task.project.name)

        user = person.user
        reports.append({
            'name': _person_name(user),
            'position': person.get_position_display(),
            'service': (person.department or '').strip() or 'Non renseigné',
            'content': report.content.strip(),
            'document': _document_text(report),
            'id': report.pk,
            'filename': report.original_name or '',
            'has_file': bool(report.uploaded_pdf),
            'activity_date': report.date.isoformat(),
            'submitted_at': timezone.localtime(report.updated_at).strftime('%d/%m/%Y %H:%M') if report.updated_at else '',
            'tasks_completed_note': (report.tasks_completed or '').strip(),
            'tasks_in_progress_note': (report.tasks_in_progress or '').strip(),
            'done': [_activity_line(task) for task in done],
            'doing': [_activity_line(task) for task in doing],
            'skipped': [_activity_line(task) for task in skipped],
            'waiting': [_activity_line(task) for task in waiting],
            'remarks': [_activity_line(task) for task in remarks],
            'done_items': [_activity_item(task) for task in done],
            'doing_items': [_activity_item(task) for task in doing],
            'skipped_items': [_activity_item(task) for task in skipped],
            'remark_items': [_activity_item(task) for task in remarks],
        })

    submitted = len(reports)
    dossier = {
        'date': day,
        'active': len(people),
        'submitted': submitted,
        'missing': len(people) - submitted,
        'analyzed': submitted,
        'difficulties': difficulties,
        'completed': completed,
        'in_progress': in_progress,
        'not_done': not_done,
        'todo': todo,
        'without_activity': without_activity,
        'projects': projects,
        'reports': reports,
    }
    return _with_reading(dossier)


def _with_reading(dossier):
    from reports.reading import ensure_reading
    ensure_reading(dossier)
    return dossier


def synthesis_prompt(dossier):
    from reports.reading import prompt_facts

    dossier = _with_reading(dossier)
    day = dossier['date']
    lines = [
        f"Date analysée : {day:%d/%m/%Y}",
        f"Employés actifs : {dossier['active']}",
        f"Rapports soumis analysés : {dossier['submitted']}",
        f"Rapports non soumis : {dossier['missing']}",
        (
            "Un rapport non soumis signifie seulement que l'employé n'a pas envoyé "
            "son rapport. Cela ne signifie pas qu'il est absent."
        ),
        f"Employés actifs sans activité enregistrée pour cette date : {dossier['without_activity']}",
        "Ce nombre ne décrit pas des absences.",
        f"Activités terminées (décompte système) : {dossier['completed']}",
        f"Activités en cours (décompte système) : {dossier['in_progress']}",
        f"Activités non réalisées (décompte système) : {dossier['not_done']}",
        f"Activités encore à faire (décompte système) : {dossier['todo']}",
        (
            "Difficultés signalées (décompte système) : "
            f"{dossier['difficulties']} remarque(s) saisie(s) sur les activités "
            "des employés qui ont soumis un rapport."
        ),
        "Projets reliés à ces activités : "
        + (', '.join(dossier['projects']) if dossier['projects'] else 'aucun'),
        '',
        "Rapports soumis, et uniquement ceux-ci :",
    ]
    if not dossier['reports']:
        lines.append("Aucun rapport soumis.")
    excerpt_limit = 500 if len(dossier['reports']) > 8 else 2500
    for index, report in enumerate(dossier['reports'], start=1):
        document = (report.get('document') or '').strip()
        if len(document) > excerpt_limit:
            document = document[:excerpt_limit].rstrip() + '… [extrait]'
        lines.extend([
            '',
            f"--- Rapport {index} ---",
            f"Employé : {report['name']}",
            f"Poste : {report['position']}",
            f"Service : {report['service']}",
            "Texte du rapport soumis :",
            report['content'],
            "Texte lu dans le fichier importé :",
            document or "Aucun texte n'a pu être lu dans le fichier.",
            _section('Activités réalisées', report['done']),
            _section('Activités en cours', report['doing']),
            _section('Activités non réalisées', report['skipped']),
            _section('Activités encore à faire', report['waiting']),
            _section('Remarques enregistrées sur les activités', report['remarks']),
            _section('Tâches terminées notées dans le rapport', [
                line for line in report['tasks_completed_note'].splitlines() if line.strip()
            ]),
            _section('Tâches en cours notées dans le rapport', [
                line for line in report['tasks_in_progress_note'].splitlines() if line.strip()
            ]),
        ])
    lines.extend([
        '',
        "Rédige une seule synthèse globale, pas une succession de résumés individuels.",
        "Réponds uniquement avec ces deux sections :",
        "### A. Synthèse exécutive",
        "### B. Avancées majeures",
        "N'ajoute pas de situation des projets, de points de vigilance, de recommandations ni de participation.",
        "Le texte lu dans chaque fichier est la source principale. Les statuts vides ne prouvent pas l'absence de travail.",
        "Ne présente pas une réflexion ou une préparation comme un livrable terminé.",
        "Si le texte d'un fichier n'a pas pu être lu, dis-le et ne reconstitue pas le document à partir de son nom.",
        "Ne recopie pas les rapports les uns après les autres.",
        "Ne cite aucun employé absent de cette liste.",
        "N'écris pas qu'un rapport manquant est une absence.",
        "",
        prompt_facts(dossier),
    ])
    return '\n'.join(lines)


def compose_team_synthesis(dossier):
    """Lecture structurée des rapports. Ce n'est pas une analyse générative."""
    from reports.reading import render_synthesis
    return render_synthesis(dossier)


def synthesis_title(day, analyzed):
    label = 'rapport' if analyzed == 1 else 'rapports'
    return f"Synthèse d'équipe du {day:%d/%m/%Y} ({analyzed} {label})"


def analyzed_count_from_title(title):
    match = _TITLE_COUNT.search(title or '')
    if not match:
        return None
    return int(match.group(1))


def synthesis_to_html(text):
    """Transforme les titres Markdown en HTML échappé. Le texte du modèle n'est pas interprété."""
    blocks = []
    paragraph = []
    items = []

    def flush_items():
        if not items:
            return
        blocks.append('<ul>' + ''.join(f'<li>{item}</li>' for item in items) + '</ul>')
        items.clear()

    def flush():
        flush_items()
        if not paragraph:
            return
        blocks.append('<p>' + '<br>'.join(paragraph) + '</p>')
        paragraph.clear()

    for raw in (text or '').replace('\r\n', '\n').splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith('### '):
            flush()
            blocks.append(f'<h3>{html.escape(line[4:].strip())}</h3>')
            continue
        if line.startswith('- '):
            if paragraph:
                flush()
            items.append(html.escape(line[2:].strip()))
            continue
        flush_items()
        paragraph.append(html.escape(line))
    flush()
    return '\n'.join(blocks)
