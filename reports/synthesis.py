"""Dossier factuel des rapports soumis, pour une seule synthèse d'équipe.

Les décomptes sont calculés ici. Le modèle de langage ne fait que les reformuler.
"""
import html
import re

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
    body = '\n'.join(lines) if lines else 'Aucune.'
    return f'{title} :\n{body}'


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
    return {
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


def synthesis_prompt(dossier):
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
    for index, report in enumerate(dossier['reports'], start=1):
        lines.extend([
            '',
            f"--- Rapport {index} ---",
            f"Employé : {report['name']}",
            f"Poste : {report['position']}",
            f"Service : {report['service']}",
            "Texte du rapport soumis :",
            report['content'],
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
        "Rédige une seule synthèse globale à partir de ces seuls éléments.",
        "Ne recopie pas les rapports les uns après les autres.",
        "Ne cite aucun employé absent de cette liste.",
    ])
    return '\n'.join(lines)


def _plain_content(content):
    parts = []
    for block in re.split(r'\n\s*\n', content or ''):
        line = ' '.join(piece.strip() for piece in block.splitlines() if piece.strip())
        line = re.sub(r'^[■•\-\s]+', '', line).strip()
        if line:
            parts.append(line if line[-1] in '.!?' else line + '.')
    return ' '.join(parts)


def _join_names(values):
    values = [value for value in values if value]
    if not values:
        return ''
    if len(values) == 1:
        return values[0]
    return ', '.join(values[:-1]) + ' et ' + values[-1]


def _activity_sentences(reports, key):
    sentences = []
    for report in reports:
        for item in report[key]:
            if not item['title']:
                continue
            sentence = f"{report['name']} : {item['title']}"
            if item['project']:
                sentence += f", projet {item['project']}"
            if item['remark']:
                sentence += f". Remarque enregistrée : {item['remark']}"
            if sentence[-1] not in '.!?':
                sentence += '.'
            sentences.append(sentence)
    return sentences


_MONTHS = (
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
)


def _titles(reports, key):
    found = []
    for report in reports:
        for item in report[key]:
            title = (item.get('title') or '').strip()
            if title and title not in found:
                found.append(title)
    return found


def _remarks(reports):
    found = []
    for report in reports:
        for item in report['remark_items']:
            remark = (item.get('remark') or '').strip()
            if not remark or remark in found:
                continue
            title = (item.get('title') or '').strip()
            found.append(f'{remark}, sur l’activité « {title} »' if title else remark)
    return found


def _count_word(count, capital=False):
    words = {
        1: 'une', 2: 'deux', 3: 'trois', 4: 'quatre', 5: 'cinq',
        6: 'six', 7: 'sept', 8: 'huit', 9: 'neuf', 10: 'dix',
        11: 'onze', 12: 'douze',
    }
    word = words.get(count, str(count))
    return word[:1].upper() + word[1:] if capital else word


def _file_names(reports):
    found = []
    for report in reports:
        text = _plain_content(report.get('content') or '')
        match = re.search(r'Fichier import[ée]\s*:\s*(\S+)', text, flags=re.IGNORECASE)
        if not match:
            continue
        name = match.group(1).strip().rstrip('.')
        if name and name not in found:
            found.append(name)
    return found


def compose_team_synthesis(dossier):
    """Texte continu, rédigé uniquement avec les rapports et activités enregistrés."""
    reports = dossier['reports']
    day = dossier['date']
    authors = _join_names(report['name'] for report in reports)
    done = _titles(reports, 'done_items')
    doing = _titles(reports, 'doing_items')
    skipped = _titles(reports, 'skipped_items')
    remarks = _remarks(reports)
    projects = [name for name in dossier['projects'] if name]
    files = _file_names(reports)
    completed = dossier['completed']
    in_progress = dossier['in_progress']
    missing = dossier['missing']

    if dossier['submitted'] == 1:
        opening = f"L’analyse du rapport journalier soumis par {authors}"
    else:
        opening = f"L’analyse des rapports journaliers soumis par {authors}"
    opening += " montre l’activité enregistrée pour cette journée."
    if done:
        label = 'activité a été réalisée' if len(done) == 1 else 'activités ont été réalisées'
        opening += f" {_count_word(len(done), capital=True)} {label} : {_join_names(done)}."
    else:
        opening += " Aucune activité terminée n’est indiquée dans ces rapports."
    if files:
        opening += f" Le document transmis est {_join_names(files)}."

    if doing:
        if len(doing) == 1:
            progress = f"Une activité reste en cours et nécessite un suivi afin de respecter les échéances prévues : {doing[0]}."
        else:
            progress = (
                f"{_count_word(len(doing), capital=True)} activités restent en cours et nécessitent un suivi "
                f"afin de respecter les échéances prévues : {_join_names(doing)}."
            )
    elif completed:
        progress = "Les activités liées aux rapports soumis sont terminées. Aucune activité ne reste en cours."
    else:
        progress = "Aucune activité en cours n’est indiquée dans les rapports soumis."

    if remarks:
        difficulty = (
            "Des difficultés ont également été signalées, notamment concernant "
            f"{_join_names(remarks)}. Ces situations peuvent nécessiter une intervention "
            "ou un accompagnement du responsable."
        )
    else:
        difficulty = "Aucune difficulté particulière n’a été signalée dans les rapports soumis."

    unfinished = skipped
    if projects:
        subject = f"Le projet {projects[0]}" if len(projects) == 1 else f"Les projets {_join_names(projects)}"
        verb = "concentre" if len(projects) == 1 else "concentrent"
        project_text = f"{subject} {verb} les activités enregistrées dans les rapports soumis."
        if unfinished or doing:
            project_text += (
                " Une attention particulière devra être accordée aux activités qui n’ont pas encore été finalisées"
                + (f" : {_join_names(unfinished)}." if unfinished else ".")
            )
    else:
        project_text = "Aucun projet n’est rattaché aux activités des rapports soumis."
        if unfinished:
            project_text += f" Les activités non finalisées sont : {_join_names(unfinished)}."

    if missing == 1:
        missing_text = "Un employé n’a pas encore soumis son rapport journalier. Un rapport non soumis ne signifie pas une absence."
    elif missing:
        missing_text = (
            f"{_count_word(missing, capital=True)} employés n’ont pas encore soumis leur rapport journalier. "
            "Un rapport non soumis ne signifie pas une absence."
        )
    else:
        missing_text = "Tous les employés actifs ont soumis leur rapport pour cette journée."

    if completed and in_progress:
        closing = (
            "En conclusion, l’activité globale de l’équipe présente un avancement réel, "
            f"avec {_count_word(completed)} {'tâche finalisée' if completed == 1 else 'tâches finalisées'} "
            f"et {_count_word(in_progress)} {'autre toujours en cours' if in_progress == 1 else 'autres toujours en cours'}."
        )
    elif completed:
        closing = (
            "En conclusion, les activités liées aux rapports soumis sont finalisées : "
            f"{_count_word(completed)} {'tâche est terminée' if completed == 1 else 'tâches sont terminées'} "
            "et aucune ne reste en cours."
        )
    elif in_progress:
        closing = (
            "En conclusion, les activités enregistrées sont encore en cours et demandent un suivi du responsable."
        )
    else:
        closing = "En conclusion, les rapports soumis ne font apparaître aucune activité terminée ni en cours."
    closing += (
        " Cette synthèse permet au responsable d’obtenir rapidement une vision globale de la journée "
        "sans avoir à consulter individuellement chaque rapport."
    )

    title = f"### Synthèse de la journée — {day.day:02d} {_MONTHS[day.month - 1]} {day.year}"
    return '\n\n'.join([title, opening, progress, difficulty, project_text, missing_text, closing])


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

    def flush():
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
        paragraph.append(html.escape(line))
    flush()
    return '\n'.join(blocks)
