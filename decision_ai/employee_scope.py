"""Réponses de l'assistant employé, limitées à ses propres enregistrements."""
import unicodedata
from datetime import timedelta

from projects.models import Project
from tasks.models import DailyPlan, Task


def _fold(value):
    normalized = unicodedata.normalize('NFKD', value or '')
    return ''.join(char for char in normalized if not unicodedata.combining(char)).lower()


def _lines(tasks):
    if not tasks:
        return 'Aucune.'
    rows = []
    for task in tasks:
        project = task.project.name if task.project_id else 'Sans projet'
        due = task.due_date.strftime('%d/%m/%Y') if task.due_date else 'sans échéance'
        rows.append(f'- {task.title} | projet : {project} | échéance : {due} | statut : {task.get_status_display()}')
    return '\n'.join(rows)


def employee_facts(employee, day):
    tasks = Task.objects.filter(assigned_to=employee).exclude(status='cancelled').select_related('project')
    projects = Project.objects.filter(assigned_employees=employee).exclude(status='cancelled').order_by('name')
    plan = DailyPlan.objects.filter(employee=employee, date=day).first()
    today_items = tasks.filter(planned_date=day)
    return {
        'tasks': tasks,
        'in_progress': tasks.filter(status__in=('in_progress', 'review')),
        'today': today_items,
        'deadlines': tasks.exclude(status__in=Task.CLOSED_STATUSES).exclude(due_date__isnull=True).order_by('due_date'),
        'projects': projects,
        'objective': plan.objective if plan else '',
        'week_done': tasks.filter(
            status='completed',
            completed_at__date__gte=day - timedelta(days=6),
            completed_at__date__lte=day,
        ),
    }


def answer_from_records(employee, question, day):
    """Réponse factuelle. None si la question demande une formulation libre."""
    folded = _fold(question)
    facts = employee_facts(employee, day)
    if 'semaine' in folded:
        return f"Activités terminées sur les 7 derniers jours :\n{_lines(facts['week_done'])}"
    if 'en cours' in folded:
        return f"Tâches en cours :\n{_lines(facts['in_progress'])}"
    if 'aujourd' in folded or 'todo' in folded:
        objective = f"\nObjectif enregistré : {facts['objective']}" if facts['objective'] else ''
        return f"Activités du {day:%d/%m/%Y} :\n{_lines(facts['today'])}{objective}"
    if 'delai' in folded or 'echeance' in folded:
        return f"Prochains délais :\n{_lines(list(facts['deadlines'][:8]))}"
    if 'projet' in folded:
        if not facts['projects']:
            return 'Aucun projet ne vous est attribué.'
        return 'Projets qui vous sont attribués :\n' + '\n'.join(f'- {project.name}' for project in facts['projects'])
    return None


def facts_for_model(employee, day):
    facts = employee_facts(employee, day)
    return (
        f"Employé : {employee.full_name}\n"
        f"Date : {day:%d/%m/%Y}\n"
        f"Tâches en cours :\n{_lines(facts['in_progress'])}\n"
        f"Activités du jour :\n{_lines(facts['today'])}\n"
        f"Prochains délais :\n{_lines(list(facts['deadlines'][:8]))}\n"
        f"Projets :\n" + ('\n'.join(f'- {project.name}' for project in facts['projects']) or 'Aucun.')
    )
