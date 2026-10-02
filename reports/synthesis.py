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
    name = f'{user.first_name} {user.last_name}'.strip() or user.username
    if user.gender == 'F':
        return f'Mme {name}'
    if user.gender == 'M':
        return f'M. {name}'
    return name


def _activity_item(task):
    return {
        'title': (task.title or '').strip(),
        'project': task.project.name if task.project_id else '',
        'remark': (task.comments or '').strip(),
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
        .filter(status='active')
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
        remarks = [task for task in tasks if (task.comments or '').strip()]
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


def compose_team_synthesis(dossier):
    """Synthèse unique rédigée uniquement avec les rapports et activités enregistrés."""
    reports = dossier['reports']
    clauses = []
    for report in reports:
        text = _plain_content(report['content'])
        who = report['name']
        if report.get('position'):
            who = f"{who} ({report['position']})"
        clauses.append(f"{who} a indiqué : {text}" if text else f"{who} a soumis un rapport.")
    opening = 'Au cours de la journée, ' + ' '.join(clauses)

    submitted = dossier['submitted']
    missing = dossier['missing']
    report_word = 'rapport journalier a été analysé' if submitted == 1 else 'rapports journaliers ont été analysés'
    follow = f"{submitted} {report_word}."
    if missing == 1:
        follow += " 1 employé n'a pas encore soumis son rapport pour cette journée."
    elif missing:
        follow += f" {missing} employés n'ont pas encore soumis leur rapport pour cette journée."
    if missing:
        follow += " Un rapport non soumis ne signifie pas une absence."

    done = _activity_sentences(reports, 'done_items')
    doing = _activity_sentences(reports, 'doing_items')
    skipped = _activity_sentences(reports, 'skipped_items')
    remarks = _activity_sentences(reports, 'remark_items')
    projects = dossier['projects']

    if done:
        done_text = ' '.join(done)
    else:
        done_text = "D'après les rapports soumis, aucune activité terminée n'est indiquée."
    if doing:
        doing_text = ' '.join(doing)
    else:
        doing_text = "D'après les rapports soumis, aucune activité en cours n'est indiquée."
    if remarks:
        difficulty_text = ' '.join(remarks)
    else:
        difficulty_text = "D'après les rapports soumis, aucune difficulté particulière n'a été signalée."
    if projects:
        project_text = "Les rapports et les activités enregistrées concernent " + _join_names(projects) + "."
    else:
        project_text = "Aucun projet n'est renseigné sur les activités liées aux rapports soumis."

    attention = []
    if missing:
        if missing == 1:
            attention.append("1 rapport n'a pas été soumis. Cela n'indique pas une absence.")
        else:
            attention.append(f"{missing} rapports n'ont pas été soumis. Cela n'indique pas une absence.")
    if dossier['in_progress']:
        count = dossier['in_progress']
        label = 'activité reste en cours' if count == 1 else 'activités restent en cours'
        attention.append(f"{count} {label}.")
    if dossier['not_done']:
        count = dossier['not_done']
        label = 'activité est non réalisée' if count == 1 else 'activités sont non réalisées'
        attention.append(f"{count} {label}.")
    if remarks:
        attention.append(difficulty_text)
    attention_text = ' '.join(attention) if attention else (
        "Aucun point d'attention supplémentaire n'apparaît dans les rapports soumis."
    )

    conclusion = (
        f"{submitted} {report_word}. "
        + project_text
        + f" {dossier['completed']} "
        + ('activité est terminée' if dossier['completed'] == 1 else 'activités sont terminées')
        + f" et {dossier['in_progress']} "
        + ('reste en cours.' if dossier['in_progress'] == 1 else 'restent en cours.')
    )
    if skipped:
        conclusion += ' ' + ' '.join(skipped)

    return '\n\n'.join([
        "### Synthèse de l'activité de l'équipe",
        opening,
        follow,
        "### Activités réalisées",
        done_text,
        "### Activités en cours",
        doing_text,
        "### Difficultés signalées",
        difficulty_text,
        "### Projets concernés",
        project_text,
        "### Points d'attention",
        attention_text,
        "### Conclusion",
        conclusion,
    ])


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
