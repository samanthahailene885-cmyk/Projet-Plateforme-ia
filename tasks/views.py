from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, IntegerField, Count
from django.http import FileResponse, Http404
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode
from datetime import datetime, timedelta
from employees.models import Employee
from projects.models import Project
from .files import validate_pdf
from .models import DailyPlan, Task, TaskDocument
from .forms import TaskForm


def _employee(user):
    try:
        return user.employee_profile
    except Exception:
        return None


def _can_manage_task(user, task):
    if user.is_admin():
        return True
    employee = _employee(user)
    return employee is not None and task.assigned_to_id == employee.id


def _safe_next(request, fallback):
    target = request.POST.get('next') or fallback
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    if isinstance(target, str) and target.startswith('/') and not target.startswith('//'):
        return target
    return fallback


def _user_tasks(request):
    tasks = Task.objects.select_related('project', 'assigned_to__user').all()
    if request.user.is_admin():
        return tasks
    employee = _employee(request.user)
    if employee is None:
        return tasks.none()
    return tasks.filter(assigned_to=employee)


def _store_documents(request, task):
    if not request.user.is_admin():
        return []
    errors = []
    for uploaded in request.FILES.getlist('documents'):
        try:
            original_name = validate_pdf(uploaded)
        except ValidationError as exc:
            errors.extend(exc.messages)
            continue
        TaskDocument.objects.create(
            task=task,
            original_name=original_name[:255],
            file=uploaded,
            file_size=uploaded.size or 0,
            mime_type='application/pdf',
            uploaded_by=request.user,
        )
    return errors


def _apply_task_filters(tasks, request):
    search_query = request.GET.get('search', '').strip()
    project_filter = request.GET.get('project', '')
    priority_filter = request.GET.get('priority', '')
    assigned_filter = request.GET.get('assigned_to', '')
    tab = request.GET.get('tab') or request.GET.get('status') or 'all'
    sort = request.GET.get('sort', 'due_date')

    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(comments__icontains=search_query)
        )
    if project_filter.isdigit():
        tasks = tasks.filter(project_id=int(project_filter))
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    if assigned_filter.isdigit() and request.user.is_admin():
        tasks = tasks.filter(assigned_to_id=int(assigned_filter))
    if tab in ('todo', 'in_progress', 'completed', 'review', 'cancelled', 'not_done'):
        tasks = tasks.filter(status=tab)
    elif tab == 'overdue':
        tasks = tasks.filter(_overdue_q())

    if sort == 'title':
        tasks = tasks.order_by('title')
    elif sort == 'priority':
        tasks = tasks.annotate(
            _prio=Case(
                When(priority='urgent', then=0),
                When(priority='high', then=1),
                When(priority='medium', then=2),
                When(priority='low', then=3),
                default=4,
                output_field=IntegerField(),
            )
        ).order_by('_prio', 'due_date')
    elif sort == 'status':
        tasks = tasks.order_by('status', 'due_date')
    else:
        tasks = tasks.order_by('due_date', 'title')
    return tasks, {
        'search_query': search_query,
        'project_filter': project_filter,
        'priority_filter': priority_filter,
        'assigned_filter': assigned_filter,
        'tab': tab,
        'sort': sort,
    }


def _overdue_q():
    today = timezone.now().date()
    return Q(due_date__lt=today) & ~Q(status__in=['completed', 'cancelled', 'not_done'])


@login_required
def task_list(request):
    """Liste des tâches : toutes pour le responsable, les siennes pour l'employé."""
    from notifications.signals import sync_deadline_notifications
    sync_deadline_notifications()

    base_qs = _user_tasks(request)
    count_todo = base_qs.filter(status='todo').count()
    count_in_progress = base_qs.filter(status='in_progress').count()
    count_completed = base_qs.filter(status='completed').count()
    count_overdue = base_qs.filter(_overdue_q()).count()
    count_all = base_qs.count()

    tasks, filters = _apply_task_filters(base_qs.annotate(document_count=Count('documents')), request)
    paginator = Paginator(tasks, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    kept = {}
    for key in ('search', 'project', 'priority', 'assigned_to', 'sort', 'tab', 'status'):
        value = request.GET.get(key)
        if value:
            kept[key] = value
    page_qs = urlencode(kept)

    return render(request, 'tasks/task_list.html', {
        'tasks': page_obj.object_list,
        'page_obj': page_obj,
        'page_qs': page_qs,
        'is_admin_view': request.user.is_admin(),
        'count_all': count_all,
        'count_todo': count_todo,
        'count_in_progress': count_in_progress,
        'count_completed': count_completed,
        'count_overdue': count_overdue,
        'projects': Project.objects.exclude(status='cancelled').order_by('name'),
        'employees': Employee.objects.select_related('user').order_by('user__first_name', 'user__last_name'),
        'priorities': Task.PRIORITY_LABELS.items(),
        'statuses': Task.STATUS_CHOICES,
        **filters,
    })


@login_required
def task_detail(request, pk):
    """
    Vue de détail d'une tâche
    """
    task = get_object_or_404(
        Task.objects.select_related('project', 'assigned_to__user', 'created_by').prefetch_related('documents'),
        pk=pk,
    )
    if not _can_manage_task(request.user, task):
        messages.error(request, 'Vous ne pouvez consulter que vos propres activités.')
        return redirect('tasks:list')
    return render(request, 'tasks/task_detail.html', {
        'task': task,
        'documents': task.documents.all(),
        'is_admin_view': request.user.is_admin(),
        'statuses': Task.STATUS_CHOICES,
    })


@login_required
def task_create(request):
    """
    Vue de création d'une tâche
    """
    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            if not request.user.is_admin():
                employee = _employee(request.user)
                if employee is None:
                    messages.error(request, 'Profil employé introuvable.')
                    return redirect('tasks:list')
                task.assigned_to = employee
            if not task.planned_date:
                task.planned_date = task.start_date or timezone.now().date()
            if not task.status:
                task.status = 'todo'
            task.save()
            for error in _store_documents(request, task):
                messages.warning(request, error)
            if request.user.is_admin() and task.assigned_to_id:
                messages.success(request, f'La tâche a été attribuée avec succès à {task.assigned_to.full_name}.')
            else:
                messages.success(request, f'Tâche {task.title} créée avec succès.')
            return redirect('tasks:detail', pk=task.pk)
    else:
        initial = {}
        planned = request.GET.get('planned_date')
        project_id = request.GET.get('project')
        if planned:
            initial['planned_date'] = planned
        if project_id and project_id.isdigit():
            initial['project'] = int(project_id)
        initial.setdefault('status', 'todo')
        initial.setdefault('priority', 'medium')
        form = TaskForm(initial=initial, user=request.user)

    return render(request, 'tasks/task_form.html', {
        'form': form,
        'title': 'Nouvelle tâche',
        'task': None,
        'is_admin_view': request.user.is_admin(),
    })


@login_required
def task_update(request, pk):
    """
    Vue de mise à jour d'une tâche
    """
    task = get_object_or_404(Task, pk=pk)
    if not _can_manage_task(request.user, task):
        messages.error(request, 'Vous ne pouvez modifier que vos propres activités.')
        return redirect('tasks:list')
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            if not request.user.is_admin():
                task.assigned_to = _employee(request.user)
            task.save()
            for error in _store_documents(request, task):
                messages.warning(request, error)
            messages.success(request, f'Tâche {task.title} mise à jour avec succès.')
            return redirect('tasks:detail', pk=task.pk)
    else:
        form = TaskForm(instance=task, user=request.user)

    return render(request, 'tasks/task_form.html', {
        'form': form,
        'title': 'Modifier la tâche',
        'task': task,
        'documents': task.documents.all(),
        'is_admin_view': request.user.is_admin(),
    })


@login_required
def task_delete(request, pk):
    """
    Vue de suppression d'une tâche
    """
    task = get_object_or_404(Task, pk=pk)
    if not _can_manage_task(request.user, task):
        messages.error(request, 'Vous ne pouvez supprimer que vos propres activités.')
        return redirect('tasks:list')

    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if request.method == 'POST':
        task.delete()
        messages.success(request, f'Tâche {task.title} supprimée avec succès.')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        if isinstance(next_url, str) and next_url.startswith('/') and not next_url.startswith('//'):
            return redirect(next_url)
        return redirect('tasks:list')

    return render(request, 'tasks/task_confirm_delete.html', {'task': task, 'next': next_url})


@login_required
def task_document(request, pk, document_id):
    document = get_object_or_404(TaskDocument.objects.select_related('task'), pk=document_id, task_id=pk)
    if not _can_manage_task(request.user, document.task):
        raise Http404
    if not document.file:
        raise Http404
    inline = request.GET.get('disposition') == 'inline'
    return FileResponse(
        document.file.open('rb'),
        as_attachment=not inline,
        filename=document.original_name,
        content_type='application/pdf',
    )


@login_required
@require_POST
def task_document_delete(request, pk, document_id):
    if not request.user.is_admin():
        messages.error(request, 'Seul le responsable peut retirer un document.')
        return redirect('tasks:detail', pk=pk)
    document = get_object_or_404(TaskDocument, pk=document_id, task_id=pk)
    if document.file:
        document.file.delete(save=False)
    document.delete()
    messages.success(request, 'Document retiré.')
    return redirect('tasks:update', pk=pk)


@login_required
@require_POST
def task_set_status(request, pk):
    task = get_object_or_404(Task, pk=pk)
    fallback = reverse_daily(request)
    if not _can_manage_task(request.user, task):
        messages.error(request, 'Vous ne pouvez modifier que vos propres activités.')
        return redirect(fallback)

    status = request.POST.get('status', '')
    allowed = {code for code, _label in Task.STATUS_CHOICES}
    if status not in allowed:
        messages.error(request, 'Statut inconnu.')
        return redirect(fallback)
    task.status = status
    task.save(update_fields=['status', 'updated_at'])
    if request.POST.get('silent') != '1':
        messages.success(request, f'Statut de « {task.title} » mis à jour.')
    return redirect(_safe_next(request, fallback))


def reverse_daily(request):
    from django.urls import reverse
    day = request.POST.get('date') or request.GET.get('date') or ''
    url = reverse('tasks:daily')
    if day:
        return f'{url}?date={day}'
    return url


FRENCH_DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
FRENCH_MONTHS = [
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]
BLOCK_ICONS = ['fa-magnifying-glass', 'fa-broom', 'fa-pen-ruler', 'fa-bullhorn', 'fa-palette', 'fa-laptop-code']
RIBBON_ICONS = ['fa-list-ul', 'fa-trash-can', 'fa-flag', 'fa-star', 'fa-folder-open', 'fa-check']


def _format_plan_date(day):
    return f"{FRENCH_DAYS[day.weekday()]} {day.day} {FRENCH_MONTHS[day.month - 1]} {day.year}"


def _parse_plan_day(raw):
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None


def _plan_sheet(employee, day, tasks):
    plan = DailyPlan.objects.filter(employee=employee, date=day).first() if employee else None
    grouped = {}
    order = []
    for task in tasks:
        label = (task.block_title or '').strip() or 'Activités'
        if label not in grouped:
            grouped[label] = []
            order.append(label)
        grouped[label].append(task)
    blocks = []
    for index, label in enumerate(order):
        blocks.append({
            'number': f'{index + 1:02d}',
            'title': label.upper(),
            'raw_title': label,
            'icon': BLOCK_ICONS[index % len(BLOCK_ICONS)],
            'ribbon': RIBBON_ICONS[index % len(RIBBON_ICONS)],
            'items': grouped[label],
        })
    first_name = employee.user.first_name if employee else ''
    last_name = (employee.user.last_name or '').upper() if employee else ''
    return {
        'employee': employee,
        'objective': plan.objective if plan else '',
        'blocks': blocks,
        'position': employee.get_position_display().upper() if employee else 'EMPLOYÉ',
        'first_name': first_name,
        'last_name': last_name,
        'signature': employee.full_name if employee else '',
    }


AVATAR_COLORS = ['#7c3aed', '#db2777', '#ea580c', '#0d9488', '#2563eb', '#16a34a', '#ca8a04', '#e11d48']


def _initials(employee):
    letters = ((employee.user.first_name or '')[:1] + (employee.user.last_name or '')[:1]).upper()
    return letters or (employee.user.username or '?')[:2].upper()


def _render_admin_todo(request, day, employees):
    from django.core.paginator import Paginator
    from django.db.models import Max
    from django.http import HttpResponse
    from decision_ai.analytics import tasks_on_date

    people = list(employees.select_related('user'))
    ids = [person.pk for person in people]
    day_tasks = list(tasks_on_date(day).filter(assigned_to_id__in=ids))
    by_employee = {}
    for task in day_tasks:
        by_employee.setdefault(task.assigned_to_id, []).append(task)
    last_updates = {
        row['assigned_to_id']: row['last']
        for row in Task.objects.filter(assigned_to_id__in=ids, planned_date=day).values('assigned_to_id').annotate(last=Max('updated_at'))
    }
    objectives = {
        plan.employee_id: plan.objective
        for plan in DailyPlan.objects.filter(employee_id__in=ids, date=day)
    }

    rows = []
    for person in people:
        tasks = by_employee.get(person.pk, [])
        countable = [task for task in tasks if task.status != 'cancelled']
        done = sum(1 for task in countable if task.status == 'completed')
        doing = sum(1 for task in countable if task.status in ('in_progress', 'review'))
        waiting = sum(1 for task in countable if task.status == 'todo')
        planned = len(countable)
        progress = round(done * 100 / planned) if planned else 0
        late = any(
            task.status not in Task.CLOSED_STATUSES and task.due_date and task.due_date < day
            for task in tasks
        ) or any(task.status == 'not_done' for task in tasks)
        if planned == 0:
            state_key, state_label = 'wait', 'En attente'
        elif late:
            state_key, state_label = 'late', 'En retard'
        else:
            state_key, state_label = 'ok', 'À jour'
        updated = last_updates.get(person.pk)
        if updated:
            local = timezone.localtime(updated)
            updated_label = local.strftime('%H:%M')
            updated_sub = "Aujourd'hui" if local.date() == day else local.strftime('%d/%m')
        else:
            updated_label, updated_sub = '—', ''
        person.initials = _initials(person)
        person.avatar_color = AVATAR_COLORS[person.pk % len(AVATAR_COLORS)]
        person.service_label = person.department or 'Non renseigné'
        person.planned = planned
        person.done = done
        person.doing = doing
        person.waiting = waiting
        person.progress = progress
        person.state_key = state_key
        person.state_label = state_label
        person.updated_label = updated_label
        person.updated_sub = updated_sub
        person.day_tasks = tasks
        person.objective = objectives.get(person.pk, '')
        rows.append(person)

    rows.sort(key=lambda row: (row.planned == 0, (row.full_name or '').lower()))

    filled = sum(1 for row in rows if row.planned)
    total = len(rows)
    stats = {
        'total': total,
        'filled': filled,
        'waiting_people': total - filled,
        'fill_rate': round(filled * 100 / total) if total else 0,
        'activities': sum(row.planned for row in rows),
        'done': sum(row.done for row in rows),
        'doing': sum(row.doing for row in rows),
        'waiting': sum(row.waiting for row in rows),
    }

    search = (request.GET.get('search') or '').strip()
    service = (request.GET.get('service') or '').strip()
    state = (request.GET.get('state') or '').strip()
    filtered = rows
    if search:
        needle = search.lower()
        filtered = [row for row in filtered if needle in row.full_name.lower() or needle in (row.email or '').lower()]
    if service:
        filtered = [row for row in filtered if row.department == service]
    if state:
        filtered = [row for row in filtered if row.state_key == state]

    if request.GET.get('export') == '1':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="todo-{day.isoformat()}.csv"'
        response.write('Employé;Service;Prévues;Terminées;En cours;Non commencées;Progression;Statut\n')
        for row in filtered:
            response.write(
                f'{row.full_name};{row.service_label};{row.planned};{row.done};{row.doing};{row.waiting};{row.progress}%;{row.state_label}\n'
            )
        return response

    paginator = Paginator(filtered, 8)
    page_obj = paginator.get_page(request.GET.get('page'))
    selected_id = request.GET.get('employee')
    selected = next((row for row in filtered if str(row.pk) == str(selected_id)), None)
    if selected is None and page_obj.object_list:
        selected = page_obj.object_list[0]
    services = sorted({row.department for row in rows if row.department})
    query = request.GET.copy()
    query.pop('page', None)
    query.pop('export', None)
    now = timezone.localtime()
    months = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
    days = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

    return render(request, 'tasks/todo_admin.html', {
        'day': day,
        'page_obj': page_obj,
        'rows': page_obj.object_list,
        'stats': stats,
        'selected': selected,
        'services': services,
        'search': search,
        'service': service,
        'state': state,
        'querystring': query.urlencode(),
        'today_label': f"{days[now.weekday()].capitalize()} {now.day} {months[now.month - 1]} {now.year}",
        'admin_initials': _initials_user(request.user),
    })


def _initials_user(user):
    letters = ((user.first_name or '')[:1] + (user.last_name or '')[:1]).upper()
    return letters or (user.username or 'AD')[:2].upper()


def _daily_redirect(day, employee=None):
    from django.urls import reverse
    url = f"{reverse('tasks:daily')}?date={day.isoformat()}"
    if employee is not None:
        url += f'&employee={employee.pk}'
    return redirect(url)


@login_required
def daily_todo(request):
    """Plan de travail du jour, même présentation pour l'employé et le responsable."""
    from decision_ai.analytics import tasks_on_date
    from employees.models import Employee

    day = _parse_plan_day(request.POST.get('date') or request.GET.get('date')) or timezone.now().date()
    actor = _employee(request.user)
    if actor is None and request.user.role == 'employee':
        from employees.models import Employee
        actor = Employee.objects.create(
            user=request.user,
            position='other',
            hire_date=day,
            status='active',
        )
    can_edit = actor is not None and not request.user.is_admin()

    if request.method == 'POST':
        if not can_edit:
            messages.error(request, 'Seul l\'employé peut modifier son plan de travail.')
            return redirect('tasks:daily')
        action = request.POST.get('action')
        if action == 'objective':
            objective = (request.POST.get('objective') or '').strip()[:220]
            DailyPlan.objects.update_or_create(
                employee=actor,
                date=day,
                defaults={'objective': objective},
            )
            messages.success(request, 'Objectif du jour enregistré.')
        elif action in ('add_block', 'add_item'):
            title = (request.POST.get('title') or '').strip()
            block_title = (request.POST.get('block_title') or '').strip()[:120]
            if action == 'add_block' and not block_title:
                messages.error(request, 'Indiquez le titre du bloc.')
            elif not title:
                messages.error(request, 'Indiquez la ligne à ajouter.')
            else:
                from projects.models import Project
                project = None
                raw_project = request.POST.get('project') or ''
                if raw_project.isdigit():
                    project = Project.objects.filter(pk=int(raw_project)).first()
                task = Task.objects.create(
                    title=title[:200],
                    block_title=block_title,
                    assigned_to=actor,
                    planned_date=day,
                    status='todo',
                    priority='medium',
                    project=project,
                )
                if project:
                    project.assigned_employees.add(actor)
                messages.success(request, 'Ligne ajoutée au plan.')
        return _daily_redirect(day)

    selected_employee = None
    employees = None
    missing_employees = []
    position = (request.GET.get('position') or '').strip()
    status = (request.GET.get('status') or '').strip()
    status_choices = ('todo', 'in_progress', 'review', 'completed', 'not_done')
    if request.user.is_admin():
        employees = Employee.objects.select_related('user').order_by('user__first_name', 'user__last_name')
        if position:
            employees = employees.filter(position=position)
        employee_id = request.GET.get('employee')
        if employee_id:
            selected_employee = employees.filter(pk=employee_id).first()
        task_qs = tasks_on_date(day, selected_employee).order_by('id')
        if status in status_choices:
            task_qs = task_qs.filter(status=status)
        if selected_employee:
            targets = [selected_employee]
        else:
            ids = set(task_qs.values_list('assigned_to_id', flat=True))
            ids.update(
                DailyPlan.objects.filter(date=day, employee__in=employees).values_list('employee_id', flat=True)
            )
            targets = list(employees.filter(pk__in=ids))
            if not status:
                filled = set(tasks_on_date(day).values_list('assigned_to_id', flat=True))
                filled.discard(None)
                missing_employees = employees.filter(status='active').exclude(pk__in=filled)
        sheets = [
            _plan_sheet(employee, day, task_qs.filter(assigned_to=employee))
            for employee in targets
        ]
    else:
        task_qs = tasks_on_date(day, actor).order_by('id') if actor else Task.objects.none()
        sheets = [_plan_sheet(actor, day, task_qs)] if actor else []

    my_projects = []
    if can_edit and actor:
        from projects.models import Project
        my_projects = Project.objects.filter(
            Q(assigned_employees=actor) | Q(tasks__assigned_to=actor)
        ).distinct().order_by('name')

    if request.user.is_admin() and request.GET.get('sheet') != '1':
        return _render_admin_todo(request, day, employees)

    return render(request, 'tasks/todo_daily.html', {
        'day': day,
        'prev_day': day - timedelta(days=1),
        'next_day': day + timedelta(days=1),
        'formatted_day': _format_plan_date(day),
        'sheets': sheets,
        'employees': employees,
        'selected_employee': selected_employee,
        'missing_employees': missing_employees,
        'position': position,
        'status_filter': status,
        'position_choices': Employee.POSITION_CHOICES,
        'can_edit': can_edit,
        'my_projects': my_projects,
    })


@login_required
def task_complete(request, pk):
    """
    Vue pour marquer une tâche comme terminée
    """
    task = get_object_or_404(Task, pk=pk)

    if not _can_manage_task(request.user, task):
        messages.error(request, 'Vous n\'avez pas le droit de modifier cette tâche.')
        return redirect('tasks:list')

    if request.method == 'POST':
        task.status = 'completed'
        task.save()
        messages.success(request, f'Tâche {task.title} marquée comme terminée.')
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        ):
            return redirect(next_url)
        return redirect('tasks:list')

    return redirect('tasks:list')
