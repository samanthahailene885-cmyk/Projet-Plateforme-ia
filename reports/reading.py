"""Lecture factuelle des rapports soumis.

Les statuts vides ne sont pas traités comme une absence de travail.
Aucun fait qui n'est pas dans le texte ou dans la base n'est ajouté.
"""
import re
import unicodedata
from datetime import date, datetime


_DISCLAIMER = (
    "Lecture directe des rapports soumis. "
    "Ce texte reprend uniquement les faits écrits ou enregistrés. "
    "Ce n'est pas une analyse générative."
)

_FILE_NOTE = re.compile(r'^fichier import[ée]\s*:', re.IGNORECASE)
_HEADING = re.compile(r'^\d{1,2}\s*[—–-]\s+\S')
_PROJECT = re.compile(
    r"\b(?:projet|maquette|site|campagne)\s+([A-Za-zÀ-ÿ0-9][\wÀ-ÿ'’-]+)",
    re.IGNORECASE,
)
_DATE_TEXT = re.compile(
    r'\b(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})\b',
    re.IGNORECASE,
)
_DATE_NUM = re.compile(r'\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b')
_DATE_ISO = re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b')

_CONFIRMED = re.compile(
    r'\b(termines?|terminees?|finalises?|finalisees?|acheves?|achevees?|realises?|realisees?|valides?|validees?|publies?|publiees?|boucles?|bouclees?|(?:ete|est) livree?s?)\b'
)
_ONGOING = re.compile(r'\b(en cours|poursuiv\w*|poursuis|poursuit|poursuite)\b')
_PREPARING = re.compile(r'\b(reflexion|preparation|preparee?s?|conception|piste|etude|analyse|organisation|structuration)\b')
_NEXT = re.compile(r'\b(prochaine|prochaines|ensuite|a venir|il faudra|prevoir)\b')
_BLOCK = re.compile(r"\b(difficulte|blocage|bloque\w*|en attente|besoin d'aide|besoin d aide|probleme|retard|impossible)\b")

_MONTHS = {
    'janvier': 1, 'fevrier': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
    'juillet': 7, 'aout': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'decembre': 12,
}
_LABELS = {'date', 'nom', 'objectif', 'objectif du jour', 'rapport de journee'}
_PROJECT_STOP = {
    'du', 'de', 'des', 'la', 'le', 'les', 'un', 'une', 'nouvelle', 'nouveau',
    'page', 'pages', 'accueil', 'section', 'sections', 'jour', 'journee', 'date', 'nom',
    'boutique', 'homepage', 'produit', 'produits', 'hero', 'newsletter', 'recette',
    'recettes', 'temoignage', 'temoignages', 'productrice', 'productrices', 'filtre',
    'filtres', 'categorie', 'categories', 'recherche', 'structure', 'disposition',
    'affichage', 'maquette', 'rapport', 'objectif', 'generale', 'general',
}
_POINT_LIMIT = 8


def _fold(value):
    text = (value or '').replace('’', "'").replace('‘', "'")
    text = unicodedata.normalize('NFD', text)
    return ''.join(char for char in text if unicodedata.category(char) != 'Mn').lower()


def _clean(line):
    line = re.sub(r'^[■•\-\s]+', '', (line or '').strip())
    return re.sub(r'\s+', ' ', line).strip()


def _period(day):
    if isinstance(day, datetime):
        day = day.date()
    if not isinstance(day, date):
        return str(day or '')
    months = (
        'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
        'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
    )
    return f'{day.day} {months[day.month - 1]} {day.year}'


def _join(values):
    values = [value for value in values if value]
    if not values:
        return ''
    if len(values) == 1:
        return values[0]
    return ', '.join(values[:-1]) + ' et ' + values[-1]


def _clip(text, limit=220):
    text = _clean(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + '…'


def _same(left, right):
    folded_left = _fold(left)
    folded_right = _fold(right)
    if not folded_left or not folded_right:
        return False
    return folded_left in folded_right or folded_right in folded_left


def _note_text(report):
    note = (report.get('content') or '').strip()
    if not note or _FILE_NOTE.match(note):
        return ''
    return note


def _lines(text):
    text = (text or '').replace('■', '\n').replace('•', '\n')
    return [_clean(line) for line in text.splitlines() if _clean(line)]


def _is_title(line):
    letters = [char for char in line if char.isalpha()]
    if len(letters) < 8:
        return False
    return sum(char.isupper() for char in letters) / len(letters) > 0.8


def _prefer_name(current, new):
    if not current:
        return new
    if current.isupper() and not new.isupper():
        return new
    return current


def _projects_in(text):
    found = []
    for match in _PROJECT.finditer(text or ''):
        name = match.group(1).strip(".,;:’'")
        if _fold(name) in _PROJECT_STOP or len(name) < 3:
            continue
        for index, current in enumerate(found):
            if _fold(current) == _fold(name):
                found[index] = _prefer_name(current, name)
                break
        else:
            found.append(name)
    return found


def _dates_in(text):
    found = []

    def add(year, month, day):
        try:
            value = date(int(year), int(month), int(day))
        except ValueError:
            return
        if value not in found:
            found.append(value)

    for match in _DATE_ISO.finditer(text or ''):
        add(match.group(1), match.group(2), match.group(3))
    for match in _DATE_NUM.finditer(text or ''):
        add(match.group(3), match.group(2), match.group(1))
    for match in _DATE_TEXT.finditer(text or ''):
        month = _MONTHS.get(_fold(match.group(2)))
        if month:
            add(match.group(3), month, match.group(1))
    return found


def _cited_name(lines):
    for index, line in enumerate(lines):
        if _fold(line) != 'nom':
            continue
        parts = []
        for nxt in lines[index + 1:index + 4]:
            folded = _fold(nxt)
            if folded in _LABELS or _HEADING.match(nxt) or _is_title(nxt):
                break
            if len(nxt.split()) > 3:
                break
            parts.append(nxt)
        cited = ' '.join(parts).strip()
        return cited
    return ''


def _clauses(text):
    result = []
    for piece in re.split(r'(?<=[.!?])\s+', text or ''):
        bits = re.split(r'\s+et\s+', piece, maxsplit=1)
        if len(bits) == 2 and re.match(r"^(je|j'|il|elle|nous|on|ils|elles)\b", _fold(bits[1])):
            result.extend(bits)
        else:
            result.append(piece)
    cleaned = [_clean(part) for part in result if _clean(part)]
    return cleaned or [text]


def _kind(text):
    folded = _fold(text)
    if _BLOCK.search(folded):
        return 'difficulty'
    if _NEXT.search(folded):
        return 'next'
    if _CONFIRMED.search(folded):
        return 'confirmed'
    if _ONGOING.search(folded):
        return 'ongoing'
    if _PREPARING.search(folded):
        return 'preparing'
    return 'described'


def _label(item):
    text = _fold(item['text'])
    if item['kind'] == 'confirmed':
        return 'réalisation confirmée'
    if item['kind'] == 'ongoing':
        return 'activité en cours'
    if item['kind'] == 'preparing':
        if 'reflexion' in text:
            return 'réflexion en cours'
        if 'conception' in text:
            return 'conception en cours'
        if 'piste' in text:
            return 'piste étudiée'
        return 'préparation de la structure'
    if item['kind'] == 'difficulty':
        return 'difficulté signalée'
    if item['kind'] == 'next':
        return 'prochaine étape'
    return 'travail décrit, sans confirmation de livrable'


def _core_activity(text):
    folded = _fold(text)
    folded = re.sub(r'\([^)]*\)', ' ', folded)
    folded = re.sub(r'\[[^\]]*\]', ' ', folded)
    folded = re.sub(
        r'\b(en cours|termines?|terminees?|non realisees?|statut|note dans le rapport comme|dans la base|notee?)\b',
        ' ',
        folded,
    )
    return re.sub(r'[^a-z0-9]+', ' ', folded).strip()


def _collapse_items(items):
    """Une activité ne doit apparaître qu'une fois, même si le texte et la base la redisent."""
    kept = []
    for item in items:
        core = _core_activity(item['text'])
        if not core or core.startswith('rapport du '):
            continue
        match = None
        for current in kept:
            other = _core_activity(current['text'])
            if current['author'] != item['author'] or current['kind'] != item['kind'] or not other:
                continue
            if other == core or other in core or core in other:
                match = current
                break
        if match is None:
            kept.append(item)
            continue
        if len(item['text']) < len(match['text']):
            match['text'] = item['text']
        if item.get('project') and not match.get('project'):
            match['project'] = item['project']
    return kept


def _remember(bucket, item):
    if any(_same(item['text'], current['text']) and current['author'] == item['author'] and current['kind'] == item['kind'] for current in bucket):
        return
    bucket.append(item)


def _linked_projects(report):
    found = []
    for key in ('done_items', 'doing_items', 'skipped_items', 'remark_items'):
        for item in report.get(key) or []:
            name = (item.get('project') or '').strip()
            if name and name not in found:
                found.append(name)
    return found


def _read_report(report, day):
    document = (report.get('document') or '').strip()
    note = _note_text(report)
    lines = _lines(document or note)
    items = []
    heading = ''
    heading_projects = []
    consumed = set()

    cited = _cited_name(lines)
    author_folded = _fold(report.get('name') or '')
    if cited and (_fold(cited) in author_folded or author_folded in _fold(cited)):
        cited = ''

    found_dates = _dates_in(document)
    dates = [
        value for value in found_dates
        if isinstance(day, date) and not isinstance(day, datetime) and value != day
    ]
    linked = _linked_projects(report)

    index = 0
    while index < len(lines):
        line = lines[index]
        folded = _fold(line)
        if folded in _LABELS:
            if folded == 'nom':
                consumed.add(index)
                look = index + 1
                while look < len(lines) and look < index + 4 and _fold(lines[look]) not in _LABELS and not _HEADING.match(lines[look]) and not _is_title(lines[look]) and len(lines[look].split()) <= 3:
                    consumed.add(look)
                    look += 1
                index = look
                continue
            if folded == 'date':
                consumed.add(index)
                if index + 1 < len(lines) and _dates_in(lines[index + 1]):
                    consumed.add(index + 1)
                    index += 2
                    continue
            if folded.startswith('objectif') and index + 1 < len(lines):
                objective = lines[index + 1]
                consumed.update({index, index + 1})
                _remember(items, {
                    'author': report.get('name') or '',
                    'project': (_projects_in(objective) or heading_projects or (linked if len(linked) == 1 else ['']) or [''])[0],
                    'kind': 'next',
                    'text': _clip(objective),
                    'origin': 'objectif',
                })
                index += 2
                continue
            index += 1
            continue
        if _HEADING.match(line) or _is_title(line):
            heading = line
            found_projects = _projects_in(line)
            if found_projects:
                heading_projects = found_projects
            if _kind(line) != 'described':
                project = (heading_projects or (linked if len(linked) == 1 else []))
                _remember(items, {
                    'author': report.get('name') or '',
                    'project': project[0] if project else '',
                    'kind': _kind(line),
                    'text': _clip(re.sub(r'^\d{1,2}\s*[—–-]\s*', '', line)),
                    'origin': 'texte',
                })
            index += 1
            continue
        if index in consumed:
            index += 1
            continue
        if items and re.match(r"^(du|de|des|et|d'|l'|la|le)\b", _fold(line)) and len(line.split()) <= 10:
            items[-1]['text'] = _clip(f"{items[-1]['text']} {line}")
            extra = _projects_in(line)
            if extra:
                heading_projects = extra
                if not items[-1]['project']:
                    items[-1]['project'] = extra[0]
            index += 1
            continue
        named = _projects_in(line) or heading_projects
        if not named and len(linked) == 1:
            named = linked
        project = named[0] if named else ''
        if len(line.split()) >= 3:
            for clause in _clauses(line):
                if len(clause.split()) < 3:
                    continue
                named = _projects_in(clause) or named
                project = named[0] if named else ''
                _remember(items, {
                    'author': report.get('name') or '',
                    'project': project,
                    'kind': _kind(clause),
                    'text': _clip(clause),
                    'origin': 'texte',
                })
        index += 1

    if note and not items:
        named = _projects_in(note)
        if not named and len(linked) == 1:
            named = linked
        kind = 'note' if len(note.split()) < 5 else _kind(note)
        _remember(items, {
            'author': report.get('name') or '',
            'project': named[0] if named else '',
            'kind': kind,
            'text': _clip(note),
            'origin': 'note',
        })
    elif note and document and not any(_same(note, item['text']) for item in items):
        named = _projects_in(note)
        if not named and len(linked) == 1:
            named = linked
        _remember(items, {
            'author': report.get('name') or '',
            'project': named[0] if named else '',
            'kind': _kind(note),
            'text': _clip(note),
            'origin': 'note',
        })

    for raw in (report.get('tasks_completed_note') or '').splitlines():
        text = _clean(raw)
        if text:
            _remember(items, {
                'author': report.get('name') or '',
                'project': linked[0] if len(linked) == 1 else '',
                'kind': 'confirmed',
                'text': _clip(f'{text} (noté dans le rapport comme terminé)'),
                'origin': 'note',
            })
    for raw in (report.get('tasks_in_progress_note') or '').splitlines():
        text = _clean(raw)
        if text:
            _remember(items, {
                'author': report.get('name') or '',
                'project': linked[0] if len(linked) == 1 else '',
                'kind': 'ongoing',
                'text': _clip(f'{text} (noté dans le rapport comme en cours)'),
                'origin': 'note',
            })
    for item in report.get('done_items') or []:
        title = (item.get('title') or '').strip()
        if title:
            _remember(items, {
                'author': report.get('name') or '',
                'project': (item.get('project') or '').strip(),
                'kind': 'confirmed',
                'text': _clip(f'{title} (statut terminé dans la base)'),
                'origin': 'base',
            })
    for item in report.get('doing_items') or []:
        title = (item.get('title') or '').strip()
        if title:
            _remember(items, {
                'author': report.get('name') or '',
                'project': (item.get('project') or '').strip(),
                'kind': 'ongoing',
                'text': _clip(f'{title} (statut en cours dans la base)'),
                'origin': 'base',
            })
    for item in report.get('remark_items') or []:
        remark = (item.get('remark') or '').strip()
        if remark:
            title = (item.get('title') or '').strip()
            text = f'{remark}, sur l’activité « {title} »' if title else remark
            _remember(items, {
                'author': report.get('name') or '',
                'project': (item.get('project') or '').strip(),
                'kind': 'difficulty',
                'text': _clip(text),
                'origin': 'base',
            })

    text_projects = []
    for source in (document, note, heading):
        for name in _projects_in(source):
            if name not in text_projects:
                text_projects.append(name)
    for item in items:
        if item['project'] and item['project'] not in text_projects and item['origin'] == 'texte':
            text_projects.append(item['project'])

    gaps = []
    for value in dates:
        gaps.append(
            f"Le document de {report.get('name') or 'l’employé'} mentionne la date du {_period(value)}, "
            f"différente de la période analysée ({_period(day)}). "
            "Cette différence est signalée sans modifier les dates enregistrées."
        )
    if cited:
        gaps.append(
            f"Le fichier de {report.get('name') or 'l’employé'} cite « {cited} », "
            f"alors que l’auteur enregistré est {report.get('name') or 'inconnu'}."
        )
    for name in text_projects:
        if linked and not any(_same(name, known) for known in linked):
            gaps.append(
                f"Le texte de {report.get('name') or 'l’employé'} cite {name}, "
                f"alors que la base rattache ce rapport à {_join(linked)}."
            )
            break

    spellings = {}
    for name in text_projects + linked + [item['project'] for item in items]:
        if not name:
            continue
        known = spellings.get(_fold(name))
        spellings[_fold(name)] = _prefer_name(known, name)
    for item in items:
        if item['project']:
            item['project'] = spellings.get(_fold(item['project']), item['project'])
    text_projects = []
    for name in spellings.values():
        if name not in linked and name not in text_projects:
            text_projects.append(name)
    for name in linked:
        folded = _fold(name)
        if folded in spellings and spellings[folded] not in text_projects and name not in text_projects:
            continue

    items = _collapse_items(items)
    points = []
    for item in items[:8]:
        if item['kind'] == 'note':
            points.append(f"Note transmise : {item['text']}")
        else:
            points.append(f"{_label(item)} : {item['text']}")
    return {
        'items': items[:8],
        'points': points[:_POINT_LIMIT],
        'cited': cited,
        'date_gaps': gaps,
        'text_projects': text_projects,
        'linked': linked,
        'unreadable': bool(report.get('has_file')) and not document,
    }


def analyze_dossier(dossier):
    day = dossier.get('date')
    if isinstance(day, datetime):
        day = day.date()
    reports = []
    items = []
    gaps = []
    projects = []
    for report in dossier.get('reports') or []:
        reading = _read_report(report, day if isinstance(day, date) else None)
        report['points'] = reading['points']
        reports.append(reading)
        items.extend(reading['items'])
        gaps.extend(reading['date_gaps'])
        if reading['unreadable']:
            gaps.append(
                f"Le fichier de {report.get('name') or 'l’employé'} a été reçu, mais son texte n’a pas pu être lu."
            )
        for name in reading['text_projects'] + reading['linked']:
            if name and name not in projects:
                projects.append(name)
    for name in dossier.get('projects') or []:
        if name and name not in projects:
            projects.append(name)

    work = [item for item in items if item['kind'] in {'confirmed', 'ongoing', 'preparing', 'described'}]
    difficulties = [item for item in items if item['kind'] == 'difficulty']
    steps = [item for item in items if item['kind'] == 'next']
    notes = [item for item in items if item['kind'] == 'note']
    brief = _brief(dossier, work, difficulties, notes, projects, gaps)
    return {
        'items': items,
        'work': work,
        'difficulties': difficulties,
        'steps': steps,
        'notes': notes,
        'gaps': gaps,
        'projects': projects,
        'brief': brief,
        'reports': reports,
    }


def ensure_reading(dossier):
    reading = dossier.get('reading')
    if reading:
        return reading
    reading = analyze_dossier(dossier)
    dossier['reading'] = reading
    dossier['brief'] = reading['brief']
    return reading


def _brief(dossier, work, difficulties, notes, projects, gaps):
    reports = dossier.get('reports') or []
    names = [report.get('name') for report in reports if report.get('name')]
    if len(names) == 1:
        who = f"{names[0]} a soumis un rapport pour le {_period(dossier.get('date'))}."
    elif len(names) <= 4:
        who = (
            f"{len(names)} rapports ont été soumis pour le {_period(dossier.get('date'))}, "
            f"par {_join(names)}."
        )
    else:
        who = f"{len(names)} rapports ont été soumis pour le {_period(dossier.get('date'))}."
    sentences = [who]
    confirmed = [item for item in work if item['kind'] == 'confirmed']
    preparing = [item for item in work if item['kind'] == 'preparing']
    ongoing = [item for item in work if item['kind'] == 'ongoing']
    described = [item for item in work if item['kind'] == 'described']
    if confirmed and (preparing or described or ongoing):
        sentences.append(
            "Certaines réalisations sont confirmées : "
            f"{_join(_clip(item['text'], 90) for item in confirmed[:3])}. "
            "D’autres éléments du texte restent des préparations, des travaux en cours ou des descriptions non confirmées comme livrables."
        )
    elif confirmed:
        sentences.append(
            "Les rapports confirment : "
            f"{_join(_clip(item['text'], 90) for item in confirmed[:3])}."
        )
    elif preparing or described or ongoing:
        kinds = []
        if preparing:
            kinds.append('des réflexions ou des préparations')
        if ongoing:
            kinds.append('des activités encore en cours')
        if described:
            kinds.append('des travaux décrits sans confirmation de livrable')
        project_text = f" concernant {_join(projects[:3])}" if projects else ''
        sentences.append(
            f"Le texte décrit {_join(kinds)}{project_text}. "
            "Aucun livrable n’est explicitement confirmé comme terminé."
        )
    elif notes:
        sentences.append(f"La note transmise indique : {_clip(notes[0]['text'], 160)}.")
    else:
        sentences.append("Les rapports reçus ne décrivent pas de travaux identifiables.")
    if difficulties:
        sentences.append("Des difficultés sont signalées et demandent une vérification.")
    else:
        sentences.append(
            "Les rapports ne font état d’aucune difficulté. "
            "Cela ne permet pas de conclure que le travail se déroule sans obstacle."
        )
    if gaps:
        sentences.append(gaps[0])
    return ' '.join(sentences[:5])


def _bullet(item):
    return f"- {item['author']} — {_label(item)} : {item['text']}"


def render_synthesis(dossier):
    reading = ensure_reading(dossier)
    day = _period(dossier.get('date'))
    parts = [
        _DISCLAIMER,
        '',
        f"### Synthèse de la journée — {day}",
        '',
        '### A. Synthèse exécutive',
        '',
        reading['brief'],
    ]
    work = reading['work']
    authors = {}
    for item in work:
        authors.setdefault(item['author'] or 'Employé', []).append(item)
    for report in dossier.get('reports') or []:
        authors.setdefault(report.get('name') or 'Employé', [])
    if authors:
        parts.extend(['', '### B. Avancées majeures', ''])

        def project_of(rows):
            for item in rows:
                if item.get('project'):
                    return item['project']
            return 'Projet non renseigné'

        ordered = sorted(authors.items(), key=lambda pair: (project_of(pair[1]), pair[0]))
        current = None
        for author, rows in ordered:
            project = project_of(rows)
            if project != current:
                if current is not None:
                    parts.append('')
                parts.append(f'Projet : {project}')
                current = project
            if not rows:
                parts.append(f'- {author} — rapport soumis, sans activité distincte identifiable.')
                continue
            for item in rows[:4]:
                parts.append(_bullet(item))
            extra = len(rows) - 4
            if extra > 0:
                parts.append(
                    f"- {author} — {extra} autre{'s' if extra > 1 else ''} "
                    f"activité{'s' if extra > 1 else ''} dans son rapport."
                )
    return '\n'.join(parts).strip() + '\n'


def prompt_facts(dossier):
    """Faits déjà lus, pour un seul envoi au modèle."""
    reading = ensure_reading(dossier)
    lines = [
        "Lecture déjà établie à partir des textes et de la base. Ne la contredis pas par les seuls statuts.",
        "Un statut vide ne signifie pas qu’aucun travail n’est décrit.",
        "N’invente aucune réalisation, difficulté, retard, projet ou personne.",
        "N’attribue aucun pourcentage d’avancement.",
        "Ne conclus à un retard que si une échéance dépassée est écrite dans les sources.",
        "Distingue une réalisation confirmée d’une réflexion, d’une préparation ou d’une intention.",
        "Les recommandations doivent être explicites et séparées des faits.",
        "Si une date du document diffère de la période, signale-la sans la modifier.",
        "L’auteur est le nom enregistré, même si le fichier en cite un autre.",
        "",
        reading['brief'],
    ]
    reports = dossier.get('reports') or []
    point_limit = 3 if len(reports) > 12 else _POINT_LIMIT
    for report, reading_report in zip(reports, reading['reports']):
        lines.append('')
        lines.append(f"Faits lus pour {report.get('name') or 'employé'} :")
        if reading_report['points']:
            lines.extend(f"- {point}" for point in reading_report['points'][:point_limit])
        else:
            lines.append("- Aucun travail identifiable dans le texte.")
        if reading_report['unreadable']:
            lines.append("- Le fichier reçu n’a pas pu être lu.")
    return '\n'.join(lines)
