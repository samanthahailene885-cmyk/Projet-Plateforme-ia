"""Jeu de données de démonstration, séparé des enregistrements réels.

Les comptes portent is_demo=True. La réinitialisation ne touche pas
les employés, projets ou tâches créés en dehors de ce générateur.
"""
import random
import unicodedata
from contextlib import contextmanager
from datetime import datetime, time, timedelta

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models.signals import post_save
from django.utils import timezone

from attendance.models import Attendance
from authentication.models import User
from employees.models import Employee
from permissions.models import PermissionRequest
from projects.models import Project
from reports.models import DailyReport
from tasks.models import DailyPlan, Difficulty, Task, TaskDocument

DEMO_PASSWORD = 'Demo-Racine-2026'

PEOPLE = [
    ('Fatou', 'Diarra', 'F'),
    ('Mariama', 'Camara', 'F'),
    ('Awa', 'Traoré', 'F'),
    ('Aïcha', 'Touré', 'F'),
    ('Sophie', 'Koné', 'F'),
    ('Mariam', 'Bah', 'F'),
    ('Rokia', 'Coulibaly', 'F'),
    ('Aminata', 'Sangaré', 'F'),
    ('Yao', 'Kouadio', 'M'),
    ('Ibrahim', 'Bah', 'M'),
    ('Moussa', 'Diallo', 'M'),
    ('Sékou', 'Camara', 'M'),
    ('Amadou', 'Koné', 'M'),
    ('Oumar', 'Keita', 'M'),
    ('Cheick', 'Traoré', 'M'),
    ('Abdoulaye', 'Cissé', 'M'),
    ('Nadia', 'Ouédraogo', 'F'),
    ('Kadiatou', 'Sidibé', 'F'),
    ('Jean', 'Koffi', 'M'),
    ('Paul', 'Mensah', 'M'),
]

JOBS = [
    ('developer', 'Développement'),
    ('designer', 'Design graphique'),
    ('community_manager', 'Community Management'),
    ('communication', 'Communication'),
    ('project_manager', 'Administration'),
]

PROJECTS = [
    ('Site web client', 'Pages et parcours du site vitrine.'),
    ('Campagne digitale', 'Diffusion des messages sur les canaux numériques.'),
    ('Identité visuelle', 'Logo, couleurs et déclinaisons graphiques.'),
    ('Gestion des réseaux sociaux', 'Publications et réponses de la semaine.'),
    ('Création de contenus', 'Textes et visuels pour les supports de l\'agence.'),
    ('Application web', 'Écrans et parcours de l\'outil en ligne.'),
    ('Campagne publicitaire', 'Visuels et messages des annonces.'),
    ('Newsletter mensuelle', 'Mise en page et envoi de la lettre d\'information.'),
]

TITLES = {
    'developer': [
        'Corriger la page d\'accueil',
        'Intégrer le formulaire de contact',
        'Vérifier l\'affichage mobile',
        'Mettre à jour les liens du menu',
    ],
    'designer': [
        'Finaliser la maquette du site',
        'Préparer les visuels Facebook',
        'Ajuster la couverture de campagne',
        'Décliner le logo en petit format',
    ],
    'community_manager': [
        'Programmer les publications de la semaine',
        'Répondre aux commentaires en attente',
        'Préparer le calendrier éditorial',
        'Relire les légendes des posts',
    ],
    'communication': [
        'Rédiger le texte de la page services',
        'Relire le communiqué client',
        'Préparer le brief de la campagne',
        'Mettre à jour la présentation commerciale',
    ],
    'project_manager': [
        'Vérifier l\'avancement avec le client',
        'Mettre à jour le planning de livraison',
        'Relancer les éléments manquants',
        'Préparer le point d\'équipe',
    ],
}

REMARKS = [
    'Les éléments validés par le client ne sont pas encore arrivés.',
    'La dernière version du visuel ne correspond plus au texte validé.',
    'L\'accès au compte publicitaire est en attente.',
    'Une information du brief reste à confirmer avant de continuer.',
]

CLIENTS = [
    'Atelier Nord',
    'Maison Kati',
    'Studio Lagon',
    'Coopérative Sahel',
    'Boutique Azalai',
]


def _ascii(value):
    normalized = unicodedata.normalize('NFKD', value)
    return ''.join(char for char in normalized if not unicodedata.combining(char))


def _username(first_name, last_name):
    base = f"demo.{_ascii(first_name)}.{_ascii(last_name)}".lower().replace(' ', '').replace("'", '')
    candidate = base
    index = 2
    while User.objects.filter(username=candidate).exists():
        candidate = f'{base}{index}'
        index += 1
    return candidate


@contextmanager
def _without_admin_notifications():
    """Évite une notification admin pour chaque ligne de démonstration."""
    from notifications.signals import (
        notify_permission_request,
        notify_report_submitted,
        notify_task_event,
    )

    post_save.disconnect(notify_task_event, sender=Task)
    post_save.disconnect(notify_report_submitted, sender=DailyReport)
    post_save.disconnect(notify_permission_request, sender=PermissionRequest)
    try:
        yield
    finally:
        post_save.connect(notify_task_event, sender=Task)
        post_save.connect(notify_report_submitted, sender=DailyReport)
        post_save.connect(notify_permission_request, sender=PermissionRequest)


def demo_counts():
    employees = Employee.objects.filter(user__is_demo=True)
    return {
        'employees': employees.count(),
        'projects': Project.objects.filter(is_demo=True).count(),
        'tasks': Task.objects.filter(project__is_demo=True).count(),
        'plans': DailyPlan.objects.filter(employee__user__is_demo=True).count(),
        'reports': DailyReport.objects.filter(employee__is_demo=True).count(),
        'permissions': PermissionRequest.objects.filter(employee__user__is_demo=True).count(),
        'difficulties': Difficulty.objects.filter(is_demo=True).count(),
        'documents': (
            TaskDocument.objects.filter(task__project__is_demo=True).count()
            + Task.objects.filter(project__is_demo=True).exclude(result_file='').count()
            + DailyReport.objects.filter(employee__is_demo=True).exclude(uploaded_pdf='').count()
        ),
    }


def reset_demo_data():
    """Supprime uniquement les enregistrements marqués comme démonstration."""
    counts = demo_counts()
    with transaction.atomic():
        Difficulty.objects.filter(is_demo=True).delete()
        Difficulty.objects.filter(employee__user__is_demo=True).delete()
        Task.objects.filter(project__is_demo=True).delete()
        Task.objects.filter(assigned_to__user__is_demo=True).delete()
        Project.objects.filter(is_demo=True).delete()
        User.objects.filter(is_demo=True).delete()
    return counts


def _dates(today, days):
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _create_employees(rng, count, today):
    chosen = PEOPLE[:count]
    rng.shuffle(chosen)
    employees = []
    inactive_index = count - 1 if count >= 15 else None
    for index, (first_name, last_name, gender) in enumerate(chosen):
        position, department = JOBS[index % len(JOBS)]
        username = _username(first_name, last_name)
        user = User.objects.create_user(
            username=username,
            email=f'{username}@demo.racin.local',
            password=DEMO_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            role='employee',
            phone=f'+223 70 {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)}',
            gender=gender,
        )
        user.is_demo = True
        user.save(update_fields=['is_demo'])
        status = 'inactive' if index == inactive_index else 'active'
        employee = Employee.objects.create(
            user=user,
            position=position,
            department=department,
            hire_date=today - timedelta(days=rng.randint(40, 700)),
            status=status,
        )
        employees.append(employee)
    return employees


def _create_projects(rng, count, employees, today):
    catalog = PROJECTS[:]
    rng.shuffle(catalog)
    active = [employee for employee in employees if employee.status == 'active']
    projects = []
    patterns = ['in_progress', 'late', 'planning', 'completed']
    for index in range(count):
        name, description = catalog[index % len(catalog)]
        if index >= len(catalog):
            name = f'{name} {index + 1}'
        pattern = patterns[index % len(patterns)]
        if pattern == 'late':
            start, end, status = today - timedelta(days=45), today - timedelta(days=4), 'in_progress'
        elif pattern == 'planning':
            start, end, status = today + timedelta(days=4), today + timedelta(days=40), 'planning'
        elif pattern == 'completed':
            start, end, status = today - timedelta(days=70), today - timedelta(days=8), 'completed'
        else:
            start, end, status = today - timedelta(days=18), today + timedelta(days=20), 'in_progress'
        project = Project.objects.create(
            name=name,
            description=f'{description} Jeu de démonstration, distinct des projets réels.',
            client=f'Démonstration — {CLIENTS[index % len(CLIENTS)]}',
            start_date=start,
            end_date=end,
            status=status,
            priority='high' if pattern == 'late' else 'medium',
            is_demo=True,
        )
        assigned = active[index % len(active):][:3] or active[:1]
        if len(assigned) < 2 and len(active) > 1:
            assigned = active[:2]
        project.assigned_employees.add(*assigned)
        projects.append(project)
    return projects


def _project_for(employee, projects, rng):
    own = [project for project in projects if employee in project.assigned_employees.all()]
    return rng.choice(own or projects)


def _task(employee, project, day, today, kind, title, rng):
    if kind == 'late':
        status, due, comments = 'in_progress', day, ''
    elif kind == 'difficulty':
        status, due, comments = 'in_progress', day, rng.choice(REMARKS)
    elif kind == 'completed' or (day < today and rng.random() < 0.65):
        status, due, comments = 'completed', day, ''
    elif day == today and rng.random() < 0.45:
        status, due, comments = 'in_progress', day + timedelta(days=1), ''
    elif day > today:
        status, due, comments = 'todo', day, ''
    else:
        status, due, comments = rng.choice(['todo', 'in_progress', 'not_done']), day, ''
    if kind == 'completed':
        status, comments = 'completed', ''
    stamps = {}
    moment = timezone.make_aware(datetime.combine(day, time(9, 0)))
    if status in ('in_progress', 'review', 'completed'):
        stamps['started_at'] = moment
    if status == 'completed':
        stamps['completed_at'] = timezone.make_aware(datetime.combine(day, time(17, 0)))
    return Task.objects.create(
        title=title,
        description='Activité de démonstration, créée pour la soutenance.',
        project=project,
        assigned_to=employee,
        status=status,
        priority='urgent' if kind == 'late' else 'high' if kind == 'difficulty' else rng.choice(['low', 'medium', 'medium', 'high']),
        planned_date=day,
        due_date=due,
        block_title=project.name,
        comments=comments,
        estimated_hours=rng.choice([1, 2, 3]),
        **stamps,
    )


def _titles_for(employee, rng):
    pool = TITLES.get(employee.position, TITLES['communication'])[:]
    rng.shuffle(pool)
    return pool


def _create_tasks(rng, employees, projects, today, days, task_count):
    active = [employee for employee in employees if employee.status == 'active']
    dates = _dates(today, days)
    rng.shuffle(active)
    missing_count = 1 if len(active) <= 3 else max(2, len(active) // 3)
    missing_today = set(active[:missing_count])
    present_today = [employee for employee in active if employee not in missing_today]
    titles = {employee.pk: _titles_for(employee, rng) for employee in active}

    def next_title(employee):
        pool = titles[employee.pk]
        if not pool:
            pool.extend(_titles_for(employee, rng))
            titles[employee.pk] = pool
        return pool.pop()

    planned = []
    for employee in present_today:
        planned.append((employee, today, 'today'))
    if present_today and dates[0] < today:
        planned.append((present_today[0], dates[0], 'late'))
    if len(present_today) > 1:
        planned.append((present_today[1], today, 'difficulty'))
    elif present_today:
        planned.append((present_today[0], today, 'difficulty'))

    history_slots = [
        (employee, day)
        for day in dates
        for employee in active
        if not (day == today and employee in missing_today)
    ]
    rng.shuffle(history_slots)
    created = []
    for employee, day, kind in planned:
        if len(created) >= task_count:
            break
        created.append(_task(
            employee, _project_for(employee, projects, rng), day, today, kind, next_title(employee), rng,
        ))
    slot_index = 0
    while len(created) < task_count and history_slots:
        employee, day = history_slots[slot_index % len(history_slots)]
        slot_index += 1
        if slot_index > len(history_slots) * 4:
            break
        created.append(_task(
            employee, _project_for(employee, projects, rng), day, today, 'history', next_title(employee), rng,
        ))
    return created, missing_today


def _create_plans_and_reports(rng, today):
    plans = 0
    reports = 0
    tasks = Task.objects.filter(project__is_demo=True, assigned_to__isnull=False).select_related('assigned_to__user')
    grouped = {}
    for task in tasks:
        grouped.setdefault((task.assigned_to_id, task.planned_date), []).append(task)
    for (employee_id, day), day_tasks in grouped.items():
        if day is None:
            continue
        employee = day_tasks[0].assigned_to
        DailyPlan.objects.update_or_create(
            employee=employee,
            date=day,
            defaults={'objective': f"Avancer sur {day_tasks[0].project.name}."},
        )
        plans += 1
        submit = rng.random() < (0.55 if day == today else 0.8)
        if not submit:
            continue
        done = [task.title for task in day_tasks if task.status == 'completed']
        doing = [task.title for task in day_tasks if task.status in ('in_progress', 'review')]
        waiting = [task.title for task in day_tasks if task.status in ('todo', 'not_done')]
        remarks = [task.comments for task in day_tasks if task.comments]
        content_lines = [f"- {task.title} ({task.get_status_display()})" for task in day_tasks]
        if remarks:
            content_lines.append('Difficultés notées : ' + ' '.join(remarks))
        DailyReport.objects.update_or_create(
            employee=employee.user,
            date=day,
            defaults={
                'content': '\n'.join(content_lines),
                'tasks_completed': '\n'.join(done),
                'tasks_in_progress': '\n'.join(doing + waiting),
                'ai_generated': False,
            },
        )
        reports += 1
    return plans, reports


def _create_permissions(rng, employees, today):
    active = [employee for employee in employees if employee.status == 'active']
    if not active:
        return 0
    specs = [
        ('pending', 'personal', 2),
        ('approved', 'family', -10),
        ('rejected', 'training', -3),
    ]
    created = 0
    for index, (status, reason, offset) in enumerate(specs):
        if index >= len(active):
            break
        start = today + timedelta(days=offset)
        PermissionRequest.objects.create(
            employee=active[index],
            type='permission',
            start_date=start,
            end_date=start + timedelta(days=1),
            reason_choice=reason,
            reason='Demande de démonstration, distincte des demandes réelles.',
            status=status,
            admin_comment='' if status == 'pending' else 'Décision enregistrée pour la démonstration.',
        )
        created += 1
    return created


def _create_difficulties():
    created = 0
    tasks = Task.objects.filter(project__is_demo=True).exclude(comments='').select_related('assigned_to', 'project')
    for task in tasks:
        if not task.assigned_to_id:
            continue
        Difficulty.objects.create(
            employee=task.assigned_to,
            project=task.project,
            task=task,
            description=task.comments,
            reported_on=task.planned_date or timezone.localdate(),
            status='open',
            priority='high',
            is_demo=True,
        )
        created += 1
    return created


def _pdf_bytes(title, lines):
    """Petit PDF lisible, sans bibliothèque externe."""
    def clean(value):
        text = _ascii(value or '').replace('\\', '/').replace('(', '[').replace(')', ']')
        return ' '.join(text.split())[:110]

    body = [clean(title)] + [clean(line) for line in lines if clean(line)]
    ops = ['BT', '/F1 14 Tf', '48 760 Td', '18 TL']
    for index, line in enumerate(body[:26]):
        if index:
            ops.append('T*')
        ops.append(f'({line}) Tj')
    ops.append('ET')
    stream = ('\n'.join(ops) + '\n').encode('latin-1', 'replace')
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
        b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'endstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    output = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f'{number} 0 obj\n'.encode('ascii'))
        output.extend(obj)
        output.extend(b'\nendobj\n')
    xref = len(output)
    output.extend(f'xref\n0 {len(objects) + 1}\n'.encode('ascii'))
    output.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        output.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
    output.extend(
        f'trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode('ascii')
    )
    return bytes(output)


def _file_slug(value):
    slug = _ascii(value or 'document').lower().replace(' ', '_').replace("'", '')
    slug = ''.join(char for char in slug if char.isalnum() or char == '_')
    return slug[:40] or 'document'


def _attach_documents(tasks):
    """Briefs, rendus et rapports PDF, pour ouvrir un document pendant la soutenance."""
    briefs = results = report_files = 0
    for task in tasks:
        who = task.assigned_to.full_name if task.assigned_to_id else 'Un employe'
        project = task.project.name if task.project_id else 'Sans projet'
        if task.status == 'completed' and results < 8:
            name = f'Rendu_{_file_slug(task.title)}.pdf'
            data = _pdf_bytes(task.title, [
                f'Projet : {project}',
                f'Employe : {who}',
                'Document de demonstration.',
                'Ce rendu illustre une activite terminee du tableau de bord.',
            ])
            task.result_file.save(name, ContentFile(data), save=False)
            task.result_original_name = name
            task.result_file_size = len(data)
            task.save(update_fields=['result_file', 'result_original_name', 'result_file_size', 'updated_at'])
            results += 1
        elif task.status in ('todo', 'in_progress', 'review') and briefs < 8:
            name = f'Brief_{_file_slug(project)}.pdf'
            data = _pdf_bytes(f'Brief - {project}', [
                f'Activite : {task.title}',
                f'Employe : {who}',
                'Document de demonstration.',
                'Ce brief accompagne une activite encore ouverte.',
            ])
            document = TaskDocument(
                task=task,
                original_name=name,
                mime_type='application/pdf',
                file_size=len(data),
            )
            document.file.save(name, ContentFile(data), save=True)
            briefs += 1
    reports = DailyReport.objects.filter(employee__is_demo=True).select_related('employee')
    for report in reports:
        user = report.employee
        name = f'Rapport_{report.date:%Y%m%d}_{_file_slug(user.last_name)}.pdf'
        data = _pdf_bytes(f'Rapport du {report.date:%d/%m/%Y}', [
            f'{user.first_name} {user.last_name}',
            *(report.content or 'Rapport de demonstration.').splitlines(),
        ])
        report.uploaded_pdf.save(name, ContentFile(data), save=False)
        report.original_name = name
        report.file_size = len(data)
        report.ai_generated = False
        report.save(update_fields=['uploaded_pdf', 'original_name', 'file_size', 'ai_generated', 'updated_at'])
        report_files += 1
    return briefs + results + report_files


def _mark_one_recorded_absence(missing_today, today):
    """Une absence saisie, distincte des todo lists simplement non remplies."""
    if not missing_today:
        return
    employee = sorted(missing_today, key=lambda item: item.pk)[0]
    Attendance.objects.update_or_create(
        employee=employee,
        date=today,
        defaults={'status': 'absent', 'notes': 'Absence enregistrée pour la démonstration.'},
    )


@transaction.atomic
def generate_demo_data(employee_count, project_count, task_count, days):
    if employee_count not in {5, 10, 15, 20}:
        raise ValueError("Le nombre d'employés doit être 5, 10, 15 ou 20.")
    if not 2 <= project_count <= 8:
        raise ValueError('Le nombre de projets doit être compris entre 2 et 8.')
    if not 8 <= task_count <= 160:
        raise ValueError('Le nombre de tâches doit être compris entre 8 et 160.')
    if not 1 <= days <= 21:
        raise ValueError("Le nombre de jours d'historique doit être compris entre 1 et 21.")

    from decision_ai.analytics import collect_alerts

    reset_demo_data()
    rng = random.Random()
    today = timezone.localdate()
    with _without_admin_notifications():
        employees = _create_employees(rng, employee_count, today)
        projects = _create_projects(rng, project_count, employees, today)
        tasks, missing_today = _create_tasks(rng, employees, projects, today, days, task_count)
        plans, reports = _create_plans_and_reports(rng, today)
        permissions = _create_permissions(rng, employees, today)
        difficulties = _create_difficulties()
        documents = _attach_documents(tasks)
        _mark_one_recorded_absence(missing_today, today)
    alerts = len(collect_alerts(today))
    return {
        'employees': len(employees),
        'projects': len(projects),
        'tasks': len(tasks),
        'plans': plans,
        'reports': reports,
        'documents': documents,
        'permissions': permissions,
        'difficulties': difficulties,
        'alerts': alerts,
        'password': DEMO_PASSWORD,
    }
