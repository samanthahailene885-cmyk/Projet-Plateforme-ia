from django.conf import settings
from tasks.models import Task
from django.utils import timezone


class ReportGenerator:
    """
    Service pour générer des rapports avec l'IA
    """

    def __init__(self):
        self.client = None
        # Ne pas initialiser OpenAI si la bibliothèque a des problèmes de compatibilité
        # Le système utilisera le mode fallback par défaut
    
    def generate_daily_report(self, user):
        """
        Génère un rapport quotidien pour un employé
        """
        # Utiliser directement le mode fallback (génération basique)
        return self._generate_fallback_report(user)
    
    def _prepare_report_context(self, user, completed_tasks, in_progress_tasks):
        """
        Prépare le contexte pour la génération du rapport
        """
        context = f"Employé: {user.first_name} {user.last_name}\n"
        context += f"Date: {timezone.now().date().strftime('%d/%m/%Y')}\n\n"

        if completed_tasks:
            context += "Tâches terminées aujourd'hui:\n"
            for task in completed_tasks:
                project_name = task.project.name if task.project else "projet non assigné"
                context += f"- {task.title} (Projet: {project_name})\n"
                if task.description:
                    context += f"  Description: {task.description}\n"
        else:
            context += "Aucune tâche terminée aujourd'hui.\n"

        context += "\n"

        if in_progress_tasks:
            context += "Tâches en cours:\n"
            for task in in_progress_tasks:
                project_name = task.project.name if task.project else "projet non assigné"
                context += f"- {task.title} (Projet: {project_name}, Priorité: {task.get_priority_display()})\n"
                if task.description:
                    context += f"  Description: {task.description}\n"
        else:
            context += "Aucune tâche en cours.\n"

        context += "\nInstructions: Rédige un rapport narratif professionnel et élégant en français. Utilise un style narratif comme 'Aujourd'hui, Madame/Monsieur X a réalisé...' ou 'L'équipe a travaillé sur...'. Sois précis, professionnel et engageant. Évite les listes à puces, préfère des phrases complètes et fluides."

        return context
    
    def _generate_fallback_report(self, user, completed_tasks=None, in_progress_tasks=None):
        """
        Génère un rapport de secours si l'IA n'est pas disponible
        """
        # Vérifier si l'utilisateur a un profil Employee, sinon le créer
        try:
            employee = user.employee_profile
        except:
            # Créer automatiquement un profil Employee si l'utilisateur a le rôle employee
            if user.role == 'employee':
                from employees.models import Employee
                employee = Employee.objects.create(
                    user=user,
                    position='other',
                    hire_date=timezone.now().date(),
                    status='active'
                )
            else:
                # Pour les admins sans profil, créer un profil temporaire
                from employees.models import Employee
                employee = Employee.objects.create(
                    user=user,
                    position='project_manager',
                    hire_date=timezone.now().date(),
                    status='active'
                )

        if completed_tasks is None:
            today = timezone.now().date()
            completed_tasks = Task.objects.filter(
                assigned_to=employee,
                status='completed',
                updated_at__date=today
            )

        if in_progress_tasks is None:
            in_progress_tasks = Task.objects.filter(
                assigned_to=employee,
                status='in_progress'
            )

        # Générer un rapport narratif basique
        report = f"Aujourd'hui, {user.first_name} {user.last_name} a travaillé sur les tâches suivantes:\n\n"

        if completed_tasks:
            report += "Tâches terminées:\n"
            for task in completed_tasks:
                project_name = task.project.name if task.project else "projet non assigné"
                report += f"- {task.title} pour le projet {project_name}\n"
        else:
            report += "Aucune tâche n'a été terminée aujourd'hui.\n"

        report += "\n"

        if in_progress_tasks:
            report += "Tâches en cours:\n"
            for task in in_progress_tasks:
                project_name = task.project.name if task.project else "projet non assigné"
                report += f"- {task.title} pour le projet {project_name}\n"
        else:
            report += "Aucune tâche n'est en cours.\n"

        return report
