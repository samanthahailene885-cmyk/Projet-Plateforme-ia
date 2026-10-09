"""Actions JSON de la plateforme. Réutilise les modèles existants."""
import json
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from attendance.models import Attendance
from authentication.models import User
from employees.models import Employee
from messaging.models import Message
from messaging.services import manager as agency_manager
from messaging.services import notify_message
from notifications.models import Notification
from notifications.signals import _notify_admins, sync_deadline_notifications
from permissions.models import PermissionRequest
from projects.models import Project
from projects.progress import sync_project_progress
from reports.files import validate_report_file
from reports.models import DailyReport
from tasks.models import DailyPlan, Difficulty, Task, TaskDocument

MAX_FILE = 10 * 1024 * 1024
WORK_EXTENSIONS = ('.pdf', '.docx', '.pptx', '.xlsx', '.zip', '.png', '.jpg', '.jpeg', '.webp')
STATUS_LABELS = {
    'todo': 'Non commencée',
    'in_progress': 'En cours',
    'review': 'En révision',
    'completed': 'Terminée',
    'not_done': 'Non réalisée',
    'cancelled': 'Annulée',
}
PRIORITY_LABELS = {'low': 'Faible', 'medium': 'Moyenne', 'high': 'Haute', 'urgent': 'Urgente'}
PROJECT_LABELS = {
    'planning': 'À venir',
    'in_progress': 'En cours',
    'on_hold': 'En pause',
    'completed': 'Terminé',
    'cancelled': 'Archivé',
}


def _json_body(request):
    if request.content_type and 'json' in request.content_type:
        try:
            return json.loads(request.body.decode() or '{}')
        except json.JSONDecodeError:
            return {}
    return request.POST


def _session_user(request):
    card = _user_card(request.user)
    card['can_switch'] = bool(request.user.is_admin() or request.session.get('preview_admin_id'))
    return card


def _user_card(user):
    first = user.first_name or ''
    last = user.last_name or ''
    name = f'{first} {last}'.strip() or user.username
    letters = f'{first[:1]}{last[:1]}'.upper() or user.username[:2].upper()
    return {
        'id': user.pk,
        'username': user.username,
        'first': first,
        'last': last,
        'name': name,
        'initials': letters,
        'role': 'admin' if user.is_admin() else 'employee',
        'job': 'Responsable' if user.is_admin() else 'Employé',
    }


def _employee_for(user):
    if not user.is_authenticated or user.is_admin():
        return None
    return Employee.objects.filter(user=user).first()


def _deny(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Connexion requise.'}, status=401)
    return None


def _person(employee):
    if employee is None:
        return None
    user = employee.user
    return {
        'id': employee.pk,
        'name': _pretty_name(employee.full_name),
        'username': user.username,
        'initials': _user_card(user)['initials'],
        'role': employee.get_position_display(),
        'service': employee.department or 'Agence',
    }


def _project_qs(user):
    qs = Project.objects.prefetch_related('assigned_employees__user', 'tasks')
    if user.is_admin():
        return qs
    employee = _employee_for(user)
    if employee is None:
        return Project.objects.none()
    return qs.filter(Q(assigned_employees=employee) | Q(tasks__assigned_to=employee)).distinct()


def _task_qs(user):
    qs = Task.objects.select_related('project', 'assigned_to__user').prefetch_related('documents')
    if user.is_admin():
        return qs
    employee = _employee_for(user)
    if employee is None:
        return Task.objects.none()
    return qs.filter(assigned_to=employee)


def _task_state(task):
    if task.is_overdue:
        return 'En retard'
    return STATUS_LABELS.get(task.status, task.status)


def _task_payload(task):
    documents = [
        {
            'id': document.pk,
            'name': document.original_name,
            'url': f'/api/taches/{task.pk}/documents/{document.pk}/',
        }
        for document in task.documents.all()
    ]
    return {
        'id': task.pk,
        'title': task.title,
        'description': task.description,
        'project_id': task.project_id,
        'project': task.project.name if task.project_id else '',
        'employee_id': task.assigned_to_id,
        'employee': task.assigned_to.full_name if task.assigned_to_id else '',
        'status': task.status,
        'status_label': _task_state(task),
        'priority': task.priority,
        'priority_label': PRIORITY_LABELS.get(task.priority, task.priority),
        'start_date': task.start_date.isoformat() if task.start_date else '',
        'due_date': task.due_date.isoformat() if task.due_date else '',
        'planned_date': task.planned_date.isoformat() if task.planned_date else '',
        'started_at': task.started_at.isoformat() if task.started_at else '',
        'completed_at': task.completed_at.isoformat() if task.completed_at else '',
        'result_name': task.result_original_name,
        'result_url': f'/api/taches/{task.pk}/fichier/' if task.result_file else '',
        'documents': documents,
        'overdue': task.is_overdue,
        'linked_task': _linked_task_id(task),
    }


def _linked_task_id(task):
    marker = 'liee:'
    text = task.comments or ''
    if text.startswith(marker):
        raw = text.split(':', 1)[1].split()[0]
        return int(raw) if raw.isdigit() else None
    return None


def _project_payload(project):
    people = [_person(item) for item in project.assigned_employees.all()]
    tasks = project.tasks.exclude(status='cancelled')
    total = tasks.count()
    done = tasks.filter(status='completed').count()
    progress = project.live_progress if project.live_progress is not None else project.progress
    return {
        'id': project.pk,
        'name': project.name,
        'description': project.description,
        'client': project.client,
        'owner': 'Responsable',
        'start_date': project.start_date.isoformat(),
        'end_date': project.end_date.isoformat(),
        'status': project.status,
        'status_label': PROJECT_LABELS.get(project.status, project.status),
        'priority': project.priority,
        'priority_label': PRIORITY_LABELS.get(project.priority, project.priority),
        'progress': progress or 0,
        'task_count': total,
        'done_count': done,
        'employees': people,
        'overdue': project.is_overdue,
    }


def _check_work_file(uploaded):
    name = os.path.basename(getattr(uploaded, 'name', '') or '')
    lower = name.lower()
    if not lower.endswith(WORK_EXTENSIONS):
        raise ValueError('Formats acceptés : PDF, DOCX, PPTX, XLSX, ZIP et images.')
    if (uploaded.size or 0) > MAX_FILE:
        raise ValueError('Le fichier dépasse 10 Mo.')
    return name[:255] or 'fichier'


def _store_documents(request, task):
    stored = []
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    uploads = request.FILES.getlist('documents') or request.FILES.getlist('document') or request.FILES.getlist('file')
    for uploaded in uploads:
        name = _check_work_file(uploaded)
        try:
            document = TaskDocument.objects.create(
                task=task,
                original_name=name,
                file=uploaded,
                file_size=uploaded.size or 0,
                mime_type=getattr(uploaded, 'content_type', '') or 'application/octet-stream',
                uploaded_by=request.user,
            )
        except OSError as exc:
            raise ValueError('Le fichier n’a pas pu être enregistré. Réessayez.') from exc
        stored.append(document.original_name)
    return stored


@ensure_csrf_cookie
@require_GET
def session_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'authenticated': False})
    return JsonResponse({'authenticated': True, 'user': _session_user(request)})


def _ensure_zaina():
    """Le compte employé de démonstration est toujours Zaina."""
    user = User.objects.filter(username='nouzou').first()
    if user is None:
        user = User.objects.create_user(
            username='nouzou',
            email='nouzou@racin.africa',
            password='nabihouddine',
            first_name='Zaina',
            last_name='Zaina',
            role='employee',
        )
    changed = []
    if user.role != 'employee':
        user.role = 'employee'
        changed.append('role')
    if not user.is_active:
        user.is_active = True
        changed.append('is_active')
    if (user.first_name or '').strip().lower() in {'', 'zaina'} and user.first_name != 'Zaina':
        user.first_name = 'Zaina'
        changed.append('first_name')
    if (user.last_name or '').strip().lower() in {'', 'zaina'} and user.last_name != 'Zaina':
        user.last_name = 'Zaina'
        changed.append('last_name')
    if changed:
        user.save(update_fields=changed)
    employee = Employee.objects.filter(user=user).first()
    if employee is None:
        employee = Employee.objects.create(
            user=user,
            position='other',
            department='',
            hire_date=timezone.localdate(),
            status='active',
        )
    elif employee.status != 'active':
        employee.status = 'active'
        employee.save(update_fields=['status', 'updated_at'])
    return employee


@require_POST
def login_view(request):
    data = _json_body(request)
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if username.lower() in {'zaina', 'zaina.zaina'}:
        username = 'nouzou'
        _ensure_zaina()
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return JsonResponse({'ok': False, 'error': 'Identifiant ou mot de passe incorrect.'}, status=401)
    login(request, user)
    return JsonResponse({'ok': True, 'user': _session_user(request)})


@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({'ok': True})


@require_POST
def switch_view(request):
    """Passe du responsable à Zaina, puis revient, sans ressaisir le mot de passe."""
    denied = _deny(request)
    if denied:
        return denied
    if request.user.is_admin():
        employee = _ensure_zaina()
        admin_id = request.user.pk
        login(request, employee.user)
        request.session['preview_admin_id'] = admin_id
        return JsonResponse({'ok': True, 'user': _session_user(request)})

    admin_id = request.session.get('preview_admin_id')
    admin = User.objects.filter(pk=admin_id, role='admin', is_active=True).first() if admin_id else None
    if admin is None:
        return JsonResponse({'ok': False, 'error': 'Connectez-vous avec le compte responsable pour revenir.'}, status=403)
    login(request, admin)
    request.session.pop('preview_admin_id', None)
    return JsonResponse({'ok': True, 'user': _session_user(request)})


@require_GET
def employees_view(request):
    denied = _deny(request)
    if denied:
        return denied
    if not request.user.is_admin():
        return JsonResponse({'ok': False, 'error': 'Accès réservé au responsable.'}, status=403)
    today = timezone.localdate()
    leave_ids = set(PermissionRequest.objects.filter(
        status='approved',
        type__in=('annual', 'sick', 'unpaid'),
        start_date__lte=today,
        end_date__gte=today,
    ).values_list('employee_id', flat=True))
    absent_ids = set(Attendance.objects.filter(date=today, status='absent').values_list('employee_id', flat=True))
    absent_ids.update(PermissionRequest.objects.filter(
        status='approved',
        type='absence',
        start_date__lte=today,
        end_date__gte=today,
    ).values_list('employee_id', flat=True))
    rows = Employee.objects.filter(user__role='employee').select_related('user')
    if request.GET.get('tous') == '1':
        rows = rows.exclude(status='inactive')
    else:
        rows = rows.filter(status='active')
    people = []
    for item in rows.order_by('user__first_name', 'user__last_name'):
        card = _person(item)
        if item.status == 'on_leave' or item.pk in leave_ids:
            card['presence'] = 'En congé'
        elif item.pk in absent_ids:
            card['presence'] = 'Absent'
        else:
            card['presence'] = 'Actif'
        people.append(card)
    return JsonResponse({'ok': True, 'employees': people})


@require_http_methods(['GET', 'POST'])
def projects_view(request):
    denied = _deny(request)
    if denied:
        return denied
    if request.method == 'GET':
        query = (request.GET.get('q') or '').strip()
        status = (request.GET.get('status') or '').strip()
        rows = _project_qs(request.user)
        if not status:
            rows = rows.exclude(status='cancelled')
        if query:
            rows = rows.filter(Q(name__icontains=query) | Q(client__icontains=query))
        if status == 'overdue':
            rows = rows.filter(end_date__lt=timezone.localdate()).exclude(status='completed')
        elif status:
            rows = rows.filter(status=status)
        return JsonResponse({'ok': True, 'projects': [_project_payload(item) for item in rows.distinct()]})

    if not request.user.is_admin():
        return JsonResponse({'ok': False, 'error': 'Seul le responsable crée un projet.'}, status=403)
    data = _json_body(request)
    name = (data.get('name') or '').strip()
    client = (data.get('client') or '').strip()
    start = _parse_date(data.get('start_date'))
    end = _parse_date(data.get('end_date'))
    if not name or not client or start is None or end is None:
        return JsonResponse({'ok': False, 'error': 'Nom, client et dates sont obligatoires.'}, status=400)
    if end < start:
        return JsonResponse({'ok': False, 'error': "La date d'échéance est avant la date de début."}, status=400)
    priority = data.get('priority') or 'medium'
    if priority not in dict(Project.PRIORITY_CHOICES):
        priority = 'medium'
    project = Project.objects.create(
        name=name[:200],
        description=(data.get('description') or '').strip(),
        client=client[:200],
        start_date=start,
        end_date=end,
        status='planning',
        priority=priority,
    )
    ids = _id_list(data.get('employees') or data.get('employee_ids'))
    people = list(Employee.objects.filter(pk__in=ids, status='active'))
    if people:
        project.assigned_employees.add(*people)
    for person in people:
        Notification.objects.create(
            user=person.user,
            title='Nouveau projet attribué',
            message=f'Vous êtes associé au projet « {project.name} ».',
            notification_type='info',
            link=f'/projects/{project.pk}/',
        )
    return JsonResponse({'ok': True, 'project': _project_payload(project), 'message': 'Projet créé.'})


@require_http_methods(['GET', 'POST'])
def project_detail_view(request, pk):
    denied = _deny(request)
    if denied:
        return denied
    project = _project_qs(request.user).filter(pk=pk).first()
    if project is None:
        return JsonResponse({'ok': False, 'error': 'Projet introuvable.'}, status=404)
    if request.method == 'GET':
        tasks = _task_qs(request.user).filter(project=project).exclude(status='cancelled')
        return JsonResponse({'ok': True, 'project': _project_payload(project), 'tasks': [_task_payload(item) for item in tasks]})
    if not request.user.is_admin():
        return JsonResponse({'ok': False, 'error': 'Seul le responsable modifie un projet.'}, status=403)
    data = _json_body(request)
    if data.get('delete'):
        project.delete()
        return JsonResponse({'ok': True, 'message': 'Projet supprimé.'})
    if data.get('archive'):
        project.status = 'cancelled'
        project.save(update_fields=['status', 'updated_at'])
        return JsonResponse({'ok': True, 'message': 'Projet archivé.'})
    for field, key in (('name', 'name'), ('description', 'description'), ('client', 'client')):
        if key in data and str(data.get(key) or '').strip():
            setattr(project, field, str(data.get(key)).strip()[:200 if field != 'description' else 5000])
    start = _parse_date(data.get('start_date')) if data.get('start_date') else None
    end = _parse_date(data.get('end_date')) if data.get('end_date') else None
    if start:
        project.start_date = start
    if end:
        project.end_date = end
    if data.get('priority') in dict(Project.PRIORITY_CHOICES):
        project.priority = data.get('priority')
    if data.get('status') in dict(Project.STATUS_CHOICES):
        project.status = data.get('status')
    project.save()
    if 'employees' in data or 'employee_ids' in data:
        ids = _id_list(data.get('employees') or data.get('employee_ids'))
        current = set(project.assigned_employees.values_list('pk', flat=True))
        chosen = list(Employee.objects.filter(pk__in=ids, status='active'))
        project.assigned_employees.set(chosen)
        for person in chosen:
            if person.pk in current:
                continue
            Notification.objects.create(
                user=person.user,
                title='Nouveau projet attribué',
                message=f'Le responsable vous a associé au projet « {project.name} ».',
                notification_type='info',
                link=f'/projects/{project.pk}/',
            )
    return JsonResponse({'ok': True, 'project': _project_payload(project), 'message': 'Projet mis à jour.'})


@require_http_methods(['GET', 'POST'])
def tasks_view(request):
    denied = _deny(request)
    if denied:
        return denied
    if request.method == 'GET':
        rows = _task_qs(request.user).exclude(status='cancelled')
        query = (request.GET.get('q') or '').strip()
        status = (request.GET.get('status') or '').strip()
        project_id = request.GET.get('project') or ''
        if query:
            rows = rows.filter(Q(title__icontains=query) | Q(description__icontains=query))
        if project_id.isdigit():
            rows = rows.filter(project_id=int(project_id))
        if status == 'overdue':
            rows = [item for item in rows if item.is_overdue]
            return JsonResponse({'ok': True, 'tasks': [_task_payload(item) for item in rows]})
        if status:
            rows = rows.filter(status=status)
        planned = request.GET.get('planned') or ''
        if planned:
            day = _parse_date(planned)
            rows = rows.filter(planned_date=day) if day else rows.none()
        return JsonResponse({'ok': True, 'tasks': [_task_payload(item) for item in rows]})

    if not request.user.is_admin():
        return JsonResponse({'ok': False, 'error': 'Seul le responsable attribue une tâche.'}, status=403)
    data = _json_body(request)
    title = (data.get('title') or '').strip()
    if not title:
        return JsonResponse({'ok': False, 'error': 'Le titre est obligatoire.'}, status=400)
    project = Project.objects.filter(pk=data.get('project') or 0).first()
    employee = Employee.objects.filter(pk=data.get('employee') or 0, status='active').first()
    if project is None or employee is None:
        return JsonResponse({'ok': False, 'error': 'Choisissez un projet et un employé.'}, status=400)
    if not project.assigned_employees.filter(pk=employee.pk).exists():
        project.assigned_employees.add(employee)
        Notification.objects.create(
            user=employee.user,
            title='Nouveau projet attribué',
            message=f'Le responsable vous a associé au projet « {project.name} ».',
            notification_type='info',
            link=f'/projects/{project.pk}/',
        )
    priority = data.get('priority') or 'medium'
    if priority not in dict(Task.PRIORITY_CHOICES):
        priority = 'medium'
    task = Task(
        title=title[:200],
        description=(data.get('description') or '').strip(),
        project=project,
        assigned_to=employee,
        priority=priority,
        status='todo',
        start_date=_parse_date(data.get('start_date')),
        due_date=_parse_date(data.get('due_date')),
        created_by=request.user,
    )
    task.save()
    try:
        names = _store_documents(request, task)
    except ValueError as exc:
        names = []
        sync_project_progress(project.pk)
        return JsonResponse({'ok': True, 'task': _task_payload(task), 'message': f'Tâche attribuée à {employee.full_name}. Le fichier n’a pas été joint : {exc}', 'documents': names})
    sync_project_progress(project.pk)
    sync_deadline_notifications()
    message = f'Tâche attribuée avec succès à {employee.full_name}.'
    return JsonResponse({'ok': True, 'task': _task_payload(task), 'message': message, 'documents': names})


@require_http_methods(['GET', 'POST'])
def task_detail_view(request, pk):
    denied = _deny(request)
    if denied:
        return denied
    task = _task_qs(request.user).filter(pk=pk).first()
    if task is None:
        return JsonResponse({'ok': False, 'error': 'Tâche introuvable.'}, status=404)
    if request.method == 'POST':
        if not request.user.is_admin():
            return JsonResponse({'ok': False, 'error': 'Seul le responsable supprime une tâche.'}, status=403)
        if not _json_body(request).get('delete'):
            return JsonResponse({'ok': False, 'error': 'Action inconnue.'}, status=400)
        project_id = task.project_id
        task.delete()
        sync_project_progress(project_id)
        return JsonResponse({'ok': True, 'message': 'Tâche supprimée.'})
    return JsonResponse({'ok': True, 'task': _task_payload(task)})


@require_POST
def task_status_view(request, pk):
    denied = _deny(request)
    if denied:
        return denied
    task = _task_qs(request.user).filter(pk=pk).first()
    if task is None:
        return JsonResponse({'ok': False, 'error': 'Tâche introuvable.'}, status=404)
    if request.user.is_admin() and task.assigned_to_id and task.assigned_to.user_id != request.user.id:
        return JsonResponse({'ok': False, 'error': "Le statut est mis à jour par l'employé assigné."}, status=403)
    status = (_json_body(request).get('status') or request.POST.get('status') or '').strip()
    if status not in dict(Task.STATUS_CHOICES):
        return JsonResponse({'ok': False, 'error': 'Statut inconnu.'}, status=400)
    task.status = status
    task.save()
    sync_project_progress(task.project_id)
    label = 'Tâche démarrée' if status == 'in_progress' else 'Tâche terminée' if status == 'completed' else 'Statut mis à jour'
    return JsonResponse({'ok': True, 'message': label, 'task': _task_payload(task)})


@require_POST
def task_result_view(request, pk):
    denied = _deny(request)
    if denied:
        return denied
    task = _task_qs(request.user).filter(pk=pk).first()
    if task is None:
        return JsonResponse({'ok': False, 'error': 'Tâche introuvable.'}, status=404)
    uploaded = request.FILES.get('result') or request.FILES.get('file')
    if uploaded is None:
        return JsonResponse({'ok': False, 'error': 'Choisissez le fichier à déposer.'}, status=400)
    try:
        name = _check_work_file(uploaded)
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    if task.result_file:
        task.result_file.delete(save=False)
    task.result_file = uploaded
    task.result_original_name = name
    task.result_file_size = uploaded.size or 0
    task.save(update_fields=['result_file', 'result_original_name', 'result_file_size', 'updated_at'])
    if not request.user.is_admin():
        raw = task.assigned_to.full_name if task.assigned_to_id else ''
        who = ' '.join(part[:1].upper() + part[1:] for part in raw.split()) or 'Un employé'
        project = f' Projet : {task.project.name}.' if task.project_id else ''
        for admin in User.objects.filter(role='admin'):
            Notification.objects.create(
                user=admin,
                title=f'Travail reçu : {who}'[:200],
                message=f'{who} a déposé « {name} » pour la tâche « {task.title} ».{project}',
                notification_type='success',
                link=f'/api/taches/{task.pk}/fichier/',
            )
    return JsonResponse({'ok': True, 'message': 'Travail envoyé au responsable.', 'task': _task_payload(task)})


@require_GET
def task_document_view(request, pk, document_id):
    denied = _deny(request)
    if denied:
        return denied
    task = _task_qs(request.user).filter(pk=pk).first()
    document = TaskDocument.objects.filter(pk=document_id, task=task).first() if task else None
    if document is None or not document.file:
        raise Http404
    name = document.original_name or os.path.basename(document.file.name)
    inline = name.lower().endswith('.pdf') and not request.GET.get('telecharger')
    response = FileResponse(document.file.open('rb'), as_attachment=not inline, filename=name)
    if inline:
        response['Content-Disposition'] = f'inline; filename="{name}"'
    return response


@require_GET
def task_result_file_view(request, pk):
    denied = _deny(request)
    if denied:
        return denied
    task = _task_qs(request.user).filter(pk=pk).first()
    if task is None or not task.result_file:
        raise Http404
    name = task.result_original_name or os.path.basename(task.result_file.name)
    lower = name.lower()
    inline = lower.endswith(('.pdf', '.png', '.jpg', '.jpeg', '.webp')) and not request.GET.get('telecharger')
    response = FileResponse(task.result_file.open('rb'), as_attachment=not inline, filename=name)
    if inline:
        response['Content-Disposition'] = f'inline; filename="{name}"'
    return response


def _day_todos(person, day):
    return Task.objects.filter(assigned_to=person, planned_date=day).exclude(status='cancelled').order_by('created_at', 'pk')


def _todo_stamp(plan):
    if plan is None or plan.submitted_at is None:
        return ''
    return timezone.localtime(plan.submitted_at).strftime('%d/%m/%Y %H:%M')


def _todo_state(person, day):
    plan = DailyPlan.objects.filter(employee=person, date=day).first()
    items = _day_todos(person, day)
    sent = bool(plan and plan.submitted_at)
    revised = bool(sent and items.filter(created_at__gt=plan.submitted_at).exists())
    return plan, items, sent, revised


@require_http_methods(['GET', 'POST'])
def todos_view(request):
    denied = _deny(request)
    if denied:
        return denied
    employee = _employee_for(request.user)
    day = _parse_date(request.GET.get('date') or _json_body(request).get('date')) or timezone.localdate()
    if request.user.is_admin():
        target_id = request.GET.get('employee') or request.GET.get('employe') or ''
        people = Employee.objects.filter(status='active').select_related('user').order_by('user__first_name', 'user__last_name')
        if target_id.isdigit():
            people = people.filter(pk=int(target_id))
        board = []
        for person in people:
            plan, items, sent, revised = _todo_state(person, day)
            board.append({
                'employee': _person(person),
                'filled': sent,
                'sent': sent,
                'revised': revised,
                'sent_at': _todo_stamp(plan),
                'done': items.filter(status='completed').count(),
                'doing': items.filter(status='in_progress').count(),
                'waiting': items.filter(status='todo').count(),
                'items': [_task_payload(item) for item in items],
            })
        return JsonResponse({'ok': True, 'date': day.isoformat(), 'board': board})
    if employee is None:
        return JsonResponse({'ok': False, 'error': 'Profil employé introuvable.'}, status=400)
    plan, items, sent, revised = _todo_state(employee, day)
    if request.method == 'GET':
        return JsonResponse({
            'ok': True,
            'date': day.isoformat(),
            'sent': sent,
            'revised': revised,
            'sent_at': _todo_stamp(plan),
            'items': [_task_payload(item) for item in items],
        })
    data = _json_body(request)
    if data.get('send'):
        if not items.exists():
            return JsonResponse({'ok': False, 'error': "Ajoutez au moins une activité avant d'envoyer la Todo List."}, status=400)
        plan, _created = DailyPlan.objects.get_or_create(employee=employee, date=day)
        plan.submitted_at = timezone.now()
        plan.save(update_fields=['submitted_at'])
        count = items.count()
        titles = ', '.join(item.title for item in items[:8])
        who = employee.full_name
        message = f'{who} a transmis sa Todo List du {day:%d/%m/%Y} : {count} activité{"s" if count > 1 else ""}. {titles}'
        for admin in User.objects.filter(role='admin'):
            Notification.objects.create(
                user=admin,
                title=f'Todo List reçue : {who}'[:200],
                message=message[:800],
                notification_type='success',
                link=f'/todos/?employe={employee.pk}',
            )
        return JsonResponse({
            'ok': True,
            'message': 'Todo List envoyée au responsable.',
            'sent': True,
            'sent_at': _todo_stamp(plan),
        })
    title = (data.get('title') or '').strip()
    if len(title) < 2:
        return JsonResponse({'ok': False, 'error': "Indiquez l'activité."}, status=400)
    project = None
    linked = None
    raw_task = str(data.get('task') or '')
    if raw_task.isdigit():
        linked = _task_qs(request.user).filter(pk=int(raw_task)).first()
        project = linked.project if linked else None
    raw_project = str(data.get('project') or '')
    if project is None and raw_project.isdigit():
        project = _project_qs(request.user).filter(pk=int(raw_project)).first()
    activity = Task.objects.create(
        title=title[:200],
        project=project,
        assigned_to=employee,
        status='todo',
        priority='medium',
        planned_date=day,
        created_by=request.user,
        comments=f'liee:{linked.pk}' if linked else 'todo:',
    )
    DailyPlan.objects.get_or_create(employee=employee, date=day)
    return JsonResponse({'ok': True, 'message': 'Activité ajoutée.', 'item': _task_payload(activity)})


@require_http_methods(['GET', 'POST'])
def reports_view(request):
    denied = _deny(request)
    if denied:
        return denied
    day = _parse_date(request.GET.get('date') or request.POST.get('date')) or timezone.localdate()
    if request.user.is_admin() and request.method == 'GET':
        people = Employee.objects.filter(status='active').select_related('user').order_by('user__first_name')
        rows = []
        for person in people:
            report = DailyReport.objects.filter(employee=person.user, date=day).first()
            rows.append({
                'employee_id': person.pk,
                'name': person.full_name,
                'username': person.user.username,
                'submitted': bool(report and report.uploaded_pdf),
                'filename': report.original_name if report else '',
                'url': f'/api/rapports/{report.pk}/fichier/' if report and report.uploaded_pdf else '',
                'sent_at': timezone.localtime(report.updated_at).strftime('%H:%M') if report else '',
            })
        return JsonResponse({'ok': True, 'date': day.isoformat(), 'reports': rows})
    if request.method == 'GET':
        mine = DailyReport.objects.filter(employee=request.user).order_by('-date')
        return JsonResponse({'ok': True, 'reports': [_report_card(item) for item in mine[:20]]})
    uploaded = request.FILES.get('file') or request.FILES.get('pdf')
    if uploaded is None:
        return JsonResponse({'ok': False, 'error': 'Choisissez le fichier du rapport.'}, status=400)
    try:
        filename = validate_report_file(uploaded)
    except Exception as exc:
        message = ' '.join(getattr(exc, 'messages', []) or [str(exc)])
        return JsonResponse({'ok': False, 'error': message}, status=400)
    if _employee_for(request.user) is None and not request.user.is_admin():
        return JsonResponse({'ok': False, 'error': 'Profil employé introuvable.'}, status=400)
    report, _created = DailyReport.objects.get_or_create(
        employee=request.user,
        date=day,
        defaults={'content': 'Rapport importé.', 'ai_generated': False},
    )
    if report.uploaded_pdf:
        report.uploaded_pdf.delete(save=False)
    report.uploaded_pdf = uploaded
    report.original_name = filename[:180]
    report.file_size = uploaded.size or 0
    report.ai_generated = False
    report.content = f'Fichier importé : {filename}.'
    report.save()
    name = _user_card(request.user)['name']
    _notify_admins(
        'Rapport reçu',
        f'Rapport de {name} reçu.',
        'success',
        f'/api/rapports/{report.pk}/fichier/',
    )
    return JsonResponse({'ok': True, 'message': 'Rapport envoyé avec succès', 'report': _report_card(report)})


@require_GET
def report_file_view(request, pk):
    denied = _deny(request)
    if denied:
        return denied
    report = DailyReport.objects.select_related('employee').filter(pk=pk).first()
    if report is None or not report.uploaded_pdf:
        raise Http404
    if not request.user.is_admin() and report.employee_id != request.user.id:
        return JsonResponse({'ok': False, 'error': 'Ce rapport ne vous appartient pas.'}, status=403)
    name = report.original_name or os.path.basename(report.uploaded_pdf.name)
    inline = name.lower().endswith('.pdf')
    response = FileResponse(report.uploaded_pdf.open('rb'), as_attachment=not inline, filename=name)
    if inline:
        response['Content-Disposition'] = f'inline; filename="{name}"'
    return response


@require_http_methods(['GET', 'POST'])
def permissions_view(request):
    denied = _deny(request)
    if denied:
        return denied
    if request.method == 'GET':
        if request.user.is_admin():
            rows = PermissionRequest.objects.select_related('employee__user').order_by('-created_at')
        else:
            employee = _employee_for(request.user)
            rows = PermissionRequest.objects.filter(employee=employee).order_by('-created_at') if employee else PermissionRequest.objects.none()
        return JsonResponse({'ok': True, 'permissions': [_permission_card(item) for item in rows[:40]]})
    employee = _employee_for(request.user)
    if employee is None:
        return JsonResponse({'ok': False, 'error': 'Seul un employé envoie une demande.'}, status=403)
    data = _json_body(request)
    start = _parse_date(data.get('start_date'))
    end = _parse_date(data.get('end_date'))
    reason = (data.get('reason') or '').strip()
    if start is None or end is None or len(reason) < 2:
        return JsonResponse({'ok': False, 'error': 'Dates et motif sont obligatoires.'}, status=400)
    if end < start:
        return JsonResponse({'ok': False, 'error': 'La date de fin est avant la date de début.'}, status=400)
    raw = (data.get('kind') or data.get('type') or 'permission').strip().lower().replace('é', 'e').replace('è', 'e')
    kind = 'annual' if 'cong' in raw else 'absence' if 'absen' in raw else 'permission'
    item = PermissionRequest.objects.create(
        employee=employee,
        type=kind,
        start_date=start,
        end_date=end,
        reason=reason,
        reason_choice='personal',
        status='pending',
    )
    return JsonResponse({'ok': True, 'message': 'Demande envoyée.', 'permission': _permission_card(item)})


@require_POST
def permission_decide_view(request, pk):
    denied = _deny(request)
    if denied:
        return denied
    if not request.user.is_admin():
        return JsonResponse({'ok': False, 'error': 'Seul le responsable décide.'}, status=403)
    item = PermissionRequest.objects.select_related('employee__user').filter(pk=pk).first()
    if item is None:
        return JsonResponse({'ok': False, 'error': 'Demande introuvable.'}, status=404)
    decision = (_json_body(request).get('status') or '').strip()
    if decision not in ('approved', 'rejected'):
        return JsonResponse({'ok': False, 'error': 'Décision inconnue.'}, status=400)
    item.status = decision
    item.decided_at = timezone.now()
    item.save(update_fields=['status', 'decided_at', 'updated_at'])
    label = 'acceptée' if decision == 'approved' else 'refusée'
    Notification.objects.create(
        user=item.employee.user,
        title='Décision de permission',
        message=f'Votre demande du {item.start_date:%d/%m/%Y} a été {label}.',
        notification_type='success' if decision == 'approved' else 'warning',
        link='/api/permissions/',
    )
    return JsonResponse({'ok': True, 'message': f'Demande {label}.', 'permission': _permission_card(item)})


@require_http_methods(['GET', 'POST'])
def difficulties_view(request):
    denied = _deny(request)
    if denied:
        return denied
    if request.method == 'GET':
        if request.user.is_admin():
            rows = Difficulty.objects.select_related('employee__user', 'project', 'task')
        else:
            employee = _employee_for(request.user)
            rows = Difficulty.objects.filter(employee=employee).select_related('project', 'task') if employee else Difficulty.objects.none()
        return JsonResponse({'ok': True, 'difficulties': [_difficulty_card(item) for item in rows.order_by('-created_at')[:40]]})
    employee = _employee_for(request.user)
    if employee is None:
        return JsonResponse({'ok': False, 'error': 'Le signalement se fait depuis l\'espace employé.'}, status=403)
    data = _json_body(request)
    description = (data.get('description') or '').strip()
    if len(description) < 5:
        return JsonResponse({'ok': False, 'error': 'Décrivez le problème.'}, status=400)
    priority = data.get('priority') or 'medium'
    if priority not in dict(Difficulty.PRIORITY_CHOICES):
        priority = 'medium'
    project = _project_qs(request.user).filter(pk=data.get('project') or 0).first()
    task = _task_qs(request.user).filter(pk=data.get('task') or 0).first()
    item = Difficulty.objects.create(
        employee=employee,
        project=project or (task.project if task else None),
        task=task,
        description=description,
        reported_on=timezone.localdate(),
        priority=priority,
        status='open',
    )
    _notify_admins(
        'Difficulté signalée',
        f'{employee.full_name} : {description[:180]}',
        'warning',
        '/api/difficultes/',
    )
    return JsonResponse({'ok': True, 'message': 'Signalement envoyé.', 'difficulty': _difficulty_card(item)})


@require_GET
def alerts_view(request):
    denied = _deny(request)
    if denied:
        return denied
    if not request.user.is_admin():
        return JsonResponse({'ok': False, 'error': 'Accès réservé au responsable.'}, status=403)
    sync_deadline_notifications()
    today = timezone.localdate()
    soon = today + timedelta(days=2)
    alerts = []
    late_tasks = Task.objects.select_related('assigned_to__user', 'project').exclude(status__in=Task.CLOSED_STATUSES).filter(due_date__lt=today)
    for task in late_tasks[:12]:
        who = task.assigned_to.full_name if task.assigned_to_id else 'Non assignée'
        alerts.append({'kind': 'retard', 'title': 'Tâche en retard', 'text': f'« {task.title} » — {who}', 'tone': 'danger'})
    soon_tasks = Task.objects.select_related('assigned_to__user').exclude(status__in=Task.CLOSED_STATUSES).filter(due_date__gte=today, due_date__lte=soon)
    for task in soon_tasks[:8]:
        alerts.append({'kind': 'echeance', 'title': 'Tâche proche de l\'échéance', 'text': f'« {task.title} » le {task.due_date:%d/%m/%Y}', 'tone': 'warning'})
    for item in Difficulty.objects.filter(status='open').select_related('employee__user')[:8]:
        alerts.append({'kind': 'difficulte', 'title': 'Difficulté signalée', 'text': f'{item.employee.full_name} : {item.description[:140]}', 'tone': 'warning'})
    for project in Project.objects.filter(end_date__lt=today).exclude(status__in=['completed', 'cancelled'])[:8]:
        alerts.append({'kind': 'projet', 'title': 'Projet en retard', 'text': project.name, 'tone': 'danger'})
    pending = PermissionRequest.objects.filter(status='pending').select_related('employee__user')
    for item in pending[:8]:
        alerts.append({'kind': 'permission', 'title': 'Permission en attente', 'text': f'{item.employee.full_name} — {item.reason[:80]}', 'tone': 'info'})
    filled = set(DailyPlan.objects.filter(date=today, submitted_at__isnull=False).values_list('employee_id', flat=True))
    missing = Employee.objects.filter(status='active').exclude(pk__in=filled).select_related('user')
    for person in missing[:12]:
        alerts.append({'kind': 'todo', 'title': 'Todo List non renseignée', 'text': person.full_name, 'tone': 'info'})
    return JsonResponse({'ok': True, 'alerts': alerts})


@require_http_methods(['GET', 'POST'])
def notifications_view(request):
    denied = _deny(request)
    if denied:
        return denied
    if request.method == 'POST':
        data = _json_body(request)
        if data.get('all'):
            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        elif str(data.get('id') or '').isdigit():
            Notification.objects.filter(user=request.user, pk=int(data['id'])).update(is_read=True)
    rows = Notification.objects.filter(user=request.user).order_by('-created_at')[:30]
    return JsonResponse({
        'ok': True,
        'unread': Notification.objects.filter(user=request.user, is_read=False).count(),
        'notifications': [
            {
                'id': item.pk,
                'title': item.title,
                'message': item.message,
                'type': item.notification_type,
                'link': item.link,
                'read': item.is_read,
                'created_at': timezone.localtime(item.created_at).strftime('%d/%m/%Y %H:%M'),
            }
            for item in rows
        ],
    })


@require_http_methods(['GET', 'POST'])
def messages_view(request):
    denied = _deny(request)
    if denied:
        return denied
    boss = agency_manager()
    if request.user.is_admin():
        partner_id = request.GET.get('with') or _json_body(request).get('with') or ''
        partner = Employee.objects.select_related('user').filter(pk=partner_id).first() if str(partner_id).isdigit() else None
        if request.method == 'POST':
            if partner is None:
                return JsonResponse({'ok': False, 'error': 'Choisissez un employé.'}, status=400)
            return _send_message(request, partner.user)
        people = list(Employee.objects.filter(status='active').select_related('user'))
        people.sort(key=lambda person: (person.user.username != 'nouzou', person.full_name.lower()))
        contacts = []
        for person in people:
            last = _pair(request.user, person.user).order_by('-created_at').first()
            card = _person(person)
            card['preview'] = (last.message if last else '')[:120]
            card['time'] = timezone.localtime(last.created_at).strftime('%H:%M') if last else ''
            card['unread'] = _pair(request.user, person.user).filter(sender=person.user, read_at__isnull=True).count()
            contacts.append(card)
        return JsonResponse({
            'ok': True,
            'contacts': contacts,
            'messages': _thread(request.user, partner.user) if partner else [],
        })
    if boss is None:
        return JsonResponse({'ok': False, 'error': 'Aucun responsable disponible.'}, status=400)
    if request.method == 'POST':
        data = _json_body(request)
        if data.get('kind') == 'meeting':
            text = f"{_user_card(request.user)['name']} souhaite vous parler."
            message = Message.objects.create(sender=request.user, receiver=boss, message=text)
            notify_message(message)
            Notification.objects.create(
                user=boss,
                title=f"Appel demandé par {_user_card(request.user)['name']}"[:200],
                message=text,
                notification_type='warning',
                link='/api/messages/',
            )
            return JsonResponse({'ok': True, 'message': 'Demande envoyée au responsable.'})
        return _send_message(request, boss)
    unread = _pair(request.user, boss).filter(sender=boss, read_at__isnull=True).count()
    if request.GET.get('apercu') == '1':
        last = _pair(request.user, boss).filter(sender=boss).select_related('sender').order_by('-created_at').first()
        card = _user_card(boss)
        latest = None
        if last:
            latest = {
                'author': card['name'],
                'initials': card['initials'],
                'text': last.message,
                'at': _ago(last.created_at),
                'fresh': last.read_at is None,
            }
        return JsonResponse({'ok': True, 'contact': card, 'unread': unread, 'latest': latest})
    return JsonResponse({
        'ok': True,
        'contact': _user_card(boss),
        'unread': unread,
        'messages': _thread(request.user, boss),
    })


def _send_message(request, receiver):
    data = _json_body(request)
    text = (data.get('text') or request.POST.get('text') or '').strip()
    if not text and not request.FILES.get('file'):
        return JsonResponse({'ok': False, 'error': 'Écrivez un message.'}, status=400)
    message = Message.objects.create(sender=request.user, receiver=receiver, message=text)
    notify_message(message)
    return JsonResponse({'ok': True, 'message': 'Message envoyé.'})


def _ago(moment):
    minutes = int((timezone.now() - moment).total_seconds() // 60)
    if minutes < 1:
        return "À l'instant"
    if minutes < 60:
        return f'Il y a {minutes} min'
    hours = minutes // 60
    if hours < 24:
        return f'Il y a {hours} h'
    return timezone.localtime(moment).strftime('%d/%m %H:%M')


def _pair(user, partner):
    return Message.objects.filter(Q(sender=user, receiver=partner) | Q(sender=partner, receiver=user))


def _thread(user, partner):
    rows = _pair(user, partner).select_related('sender').order_by('created_at')
    Message.objects.filter(sender=partner, receiver=user, read_at__isnull=True).update(read_at=timezone.now())
    return [
        {
            'id': item.pk,
            'mine': item.sender_id == user.id,
            'author': _user_card(item.sender)['name'],
            'text': item.message,
            'at': timezone.localtime(item.created_at).strftime('%d/%m %H:%M'),
        }
        for item in rows
    ]


def _report_card(report):
    return {
        'id': report.pk,
        'date': report.date.isoformat(),
        'name': report.original_name or 'Rapport',
        'url': f'/api/rapports/{report.pk}/fichier/' if report.uploaded_pdf else '',
        'sent_at': timezone.localtime(report.updated_at).strftime('%d/%m/%Y %H:%M'),
    }


def _permission_card(item):
    labels = {'pending': 'En attente', 'approved': 'Acceptée', 'rejected': 'Refusée', 'cancelled': 'Annulée'}
    return {
        'id': item.pk,
        'employee': item.employee.full_name,
        'start_date': item.start_date.isoformat(),
        'end_date': item.end_date.isoformat(),
        'reason': item.reason,
        'status': item.status,
        'status_label': labels.get(item.status, item.status),
    }


def _difficulty_card(item):
    return {
        'id': item.pk,
        'employee': item.employee.full_name,
        'project': item.project.name if item.project_id else '',
        'task': item.task.title if item.task_id else '',
        'description': item.description,
        'priority': item.priority,
        'status': item.status,
    }


def _parse_date(value):
    if not value:
        return None
    try:
        return timezone.datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _pretty_name(name):
    parts = [part for part in (name or '').split() if part]
    return ' '.join(part[:1].upper() + part[1:] for part in parts) or 'Un employé'


def _admin_only(request):
    denied = _deny(request)
    if denied:
        return denied
    if not request.user.is_admin():
        return JsonResponse({'ok': False, 'error': 'Réservé au responsable.'}, status=403)
    return None


@require_GET
def documents_view(request):
    """Documents réellement enregistrés : briefs, rendus et rapports."""
    denied = _admin_only(request)
    if denied:
        return denied
    today = timezone.localdate()
    rows = []
    briefs = TaskDocument.objects.select_related('task__assigned_to__user', 'task__project').order_by('-created_at')
    for document in briefs[:40]:
        task = document.task
        person = task.assigned_to
        when = timezone.localtime(document.created_at)
        rows.append({
            'id': f'brief-{document.pk}',
            'name': _pretty_name(person.full_name) if person else 'Un employé',
            'initials': _user_card(person.user)['initials'] if person else 'DO',
            'meta': document.original_name or 'Brief',
            'project': task.project.name if task.project_id else '',
            'status': 'En attente' if task.status not in Task.CLOSED_STATUSES else 'Traité',
            'time': 'Aujourd’hui' if when.date() == today else f'{when:%d/%m/%Y}',
            'url': f'/api/taches/{task.pk}/documents/{document.pk}/',
            'stamp': document.created_at.isoformat(),
        })
    results = Task.objects.exclude(result_file='').select_related('assigned_to__user', 'project').order_by('-updated_at')
    for task in results[:40]:
        person = task.assigned_to
        when = timezone.localtime(task.updated_at)
        rows.append({
            'id': f'result-{task.pk}',
            'name': _pretty_name(person.full_name) if person else 'Un employé',
            'initials': _user_card(person.user)['initials'] if person else 'DO',
            'meta': task.result_original_name or 'Rendu',
            'project': task.project.name if task.project_id else '',
            'status': 'Traité',
            'time': 'Aujourd’hui' if when.date() == today else f'{when:%d/%m/%Y}',
            'url': f'/api/taches/{task.pk}/fichier/',
            'stamp': task.updated_at.isoformat(),
        })
    reports = DailyReport.objects.exclude(uploaded_pdf='').select_related('employee').order_by('-created_at')
    for report in reports[:40]:
        user = report.employee
        when = timezone.localtime(report.created_at)
        rows.append({
            'id': f'report-{report.pk}',
            'name': _pretty_name(f'{user.first_name} {user.last_name}'),
            'initials': _user_card(user)['initials'],
            'meta': report.original_name or 'Rapport',
            'project': '',
            'status': 'Traité',
            'time': 'Aujourd’hui' if when.date() == today else f'{when:%d/%m/%Y}',
            'url': f'/api/rapports/{report.pk}/fichier/',
            'stamp': report.created_at.isoformat(),
        })
    rows.sort(key=lambda item: item['stamp'], reverse=True)
    pending = sum(1 for item in rows if item['status'] == 'En attente')
    processed = sum(1 for item in rows if item['status'] == 'Traité')
    total = pending + processed
    for item in rows:
        item.pop('stamp', None)
    return JsonResponse({
        'ok': True,
        'pending': pending,
        'processed': processed,
        'completion': round(processed * 100 / total) if total else 0,
        'documents': rows[:24],
    })


@require_http_methods(['GET', 'POST'])
def demonstration_view(request):
    """Génère ou retire le jeu de démonstration, sans toucher aux comptes réels."""
    denied = _admin_only(request)
    if denied:
        return denied
    from employees.demo import DEMO_PASSWORD, demo_counts, generate_demo_data, reset_demo_data

    if request.method == 'GET':
        counts = demo_counts()
        counts['password'] = DEMO_PASSWORD
        return JsonResponse({'ok': True, **counts})
    payload = _json_body(request)
    action = payload.get('action') or request.POST.get('action')
    try:
        if action == 'reset':
            if str(payload.get('confirm') or request.POST.get('confirm')) not in {'oui', 'true', '1'}:
                return JsonResponse({'ok': False, 'error': 'Confirmez la suppression des données de démonstration.'}, status=400)
            removed = reset_demo_data()
            return JsonResponse({
                'ok': True,
                'message': 'Les données de démonstration ont été retirées. Les comptes réels sont conservés.',
                **removed,
            })
        summary = generate_demo_data(
            employee_count=int(payload.get('employees') or request.POST.get('employees') or 10),
            project_count=int(payload.get('projects') or request.POST.get('projects') or 4),
            task_count=int(payload.get('tasks') or request.POST.get('tasks') or 24),
            days=int(payload.get('days') or request.POST.get('days') or 7),
        )
    except (TypeError, ValueError) as exc:
        return JsonResponse({'ok': False, 'error': str(exc) or 'Quantités invalides.'}, status=400)
    return JsonResponse({
        'ok': True,
        'message': (
            f"{summary['employees']} employés, {summary['projects']} projets, "
            f"{summary['tasks']} tâches, {summary['reports']} rapports et "
            f"{summary['documents']} documents ont été préparés pour le tableau de bord."
        ),
        **summary,
    })


def _id_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        value = [part for part in value.split(',') if part.strip()]
    ids = []
    for item in value:
        text = str(item).strip()
        if text.isdigit():
            ids.append(int(text))
    return ids
