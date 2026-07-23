from django.conf import settings
from openai import OpenAI
from django.utils import timezone
from datetime import timedelta
from projects.models import Project
from tasks.models import Task
from employees.models import Employee
from attendance.models import Attendance
from reports.models import DailyReport


class DecisionAIService:
    """
    Service principal pour les fonctionnalités IA d'aide à la décision
    """
    
    def __init__(self):
        try:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        except Exception as e:
            print(f"Erreur lors de l'initialisation du client OpenAI: {e}")
            self.client = None
    
    def _get_current_date(self):
        """Retourne la date actuelle formatée"""
        return timezone.now().date().strftime('%d/%m/%Y')
    
    def generate_intelligent_summary(self):
        """
        Génère un résumé intelligent des tâches, rapports et projets
        """
        if not self.client:
            return self._generate_fallback_summary()
        
        # Récupérer les données
        context = self._prepare_summary_context()
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un assistant expert en gestion de projet pour une agence de communication. Génère un résumé professionnel et structuré de l'activité de l'agence."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"Erreur lors de la génération du résumé: {e}")
            return self._generate_fallback_summary()
    
    def _prepare_summary_context(self):
        """
        Prépare le contexte pour la génération du résumé
        """
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # Projets
        active_projects = Project.objects.filter(status='in_progress')
        completed_projects = Project.objects.filter(status='completed', updated_at__gte=week_ago)
        
        # Tâches
        completed_tasks = Task.objects.filter(status='completed', updated_at__gte=week_ago)
        in_progress_tasks = Task.objects.filter(status='in_progress')
        
        # Rapports
        recent_reports = DailyReport.objects.filter(date__gte=week_ago)
        
        context = f"Résumé de l'activité de l'agence (semaine du {week_ago.strftime('%d/%m/%Y')} au {today.strftime('%d/%m/%Y')})\n\n"
        
        context += f"Projets actifs: {active_projects.count()}\n"
        for project in active_projects[:5]:
            context += f"- {project.name} (Progression: {project.progress}%)\n"
        
        context += f"\nProjets terminés cette semaine: {completed_projects.count()}\n"
        
        context += f"\nTâches terminées cette semaine: {completed_tasks.count()}\n"
        context += f"Tâches en cours: {in_progress_tasks.count()}\n"
        
        context += f"\nRapports envoyés cette semaine: {recent_reports.count()}\n"
        
        context += "\nGénère un résumé professionnel mettant en évidence les points clés, les réussites et les points d'attention."
        
        return context
    
    def _generate_fallback_summary(self):
        """
        Génère un résumé de secours
        """
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        active_projects = Project.objects.filter(status='in_progress')
        completed_tasks = Task.objects.filter(status='completed', updated_at__gte=week_ago)
        in_progress_tasks = Task.objects.filter(status='in_progress')
        
        summary = f"Résumé de l'activité - {today.strftime('%d/%m/%Y')}\n\n"
        summary += f"Projets actifs: {active_projects.count()}\n"
        summary += f"Tâches terminées cette semaine: {completed_tasks.count()}\n"
        summary += f"Tâches en cours: {in_progress_tasks.count()}\n"
        
        return summary
    
    def answer_question(self, question):
        """
        Répond à une question de l'utilisateur basée sur les données de la base
        """
        if not self.client:
            return self._answer_question_fallback(question)
        
        context = self._prepare_qa_context(question)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un assistant IA pour une agence de communication. Réponds uniquement aux questions basées sur les données fournies. Sois précis et professionnel."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                max_tokens=500,
                temperature=0.5
            )
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"Erreur lors de la réponse: {e}")
            return self._answer_question_fallback(question)
    
    def _prepare_qa_context(self, question):
        """
        Prépare le contexte pour répondre à une question
        """
        today = timezone.now().date()
        
        # Récupérer les données pertinentes
        employees = Employee.objects.select_related('user').all()
        projects = Project.objects.all()
        tasks = Task.objects.select_related('project', 'assigned_to__user').all()
        today_attendance = Attendance.objects.filter(date=today)
        today_reports = DailyReport.objects.filter(date=today)
        
        context = f"Question: {question}\n\n"
        context += "Données disponibles:\n\n"
        
        context += f"Employés ({employees.count()}):\n"
        for emp in employees:
            context += f"- {emp.full_name} ({emp.get_position_display})\n"
        
        context += f"\nProjets ({projects.count()}):\n"
        for proj in projects:
            context += f"- {proj.name} (Statut: {proj.get_status_display()}, Progression: {proj.progress}%)\n"
        
        context += f"\nPrésence aujourd'hui:\n"
        context += f"- Présents: {today_attendance.filter(status='present').count()}\n"
        context += f"- Absents: {today_attendance.filter(status='absent').count()}\n"
        context += f"- Retards: {today_attendance.filter(status='late').count()}\n"
        
        context += f"\nRapports envoyés aujourd'hui: {today_reports.count()}\n"
        
        context += "\nRéponds à la question en utilisant uniquement ces données."
        
        return context
    
    def _answer_question_fallback(self, question):
        """
        Réponse de secours pour les questions
        """
        question_lower = question.lower()
        
        if 'absent' in question_lower:
            today = timezone.now().date()
            absent_count = Attendance.objects.filter(date=today, status='absent').count()
            return f"Il y a {absent_count} employé(s) absent(s) aujourd'hui."
        
        elif 'retard' in question_lower or 'projet' in question_lower:
            overdue_projects = Project.objects.filter(end_date__lt=timezone.now().date(), status__in=['in_progress', 'planning'])
            if overdue_projects:
                return f"Projets en retard: {', '.join([p.name for p in overdue_projects])}"
            return "Aucun projet en retard."
        
        elif 'rapport' in question_lower:
            today = timezone.now().date()
            reports_count = DailyReport.objects.filter(date=today).count()
            return f"{reports_count} rapport(s) envoyé(s) aujourd'hui."
        
        else:
            return "Désolé, je ne peux pas répondre à cette question sans l'API OpenAI."
    
    def detect_project_delays(self):
        """
        Détecte les projets à risque de retard
        """
        today = timezone.now().date()
        at_risk_projects = []
        
        projects = Project.objects.filter(status__in=['planning', 'in_progress'])
        
        for project in projects:
            # Projets dont la date de fin est proche
            days_remaining = project.days_remaining
            if days_remaining is not None and days_remaining <= 7:
                at_risk_projects.append({
                    'project': project,
                    'risk_level': 'high' if days_remaining <= 3 else 'medium',
                    'days_remaining': days_remaining,
                    'reason': 'Date limite proche'
                })
            
            # Projets avec progression insuffisante
            if project.progress < 50 and project.days_remaining < 14:
                at_risk_projects.append({
                    'project': project,
                    'risk_level': 'high',
                    'days_remaining': project.days_remaining,
                    'reason': 'Progression insuffisante'
                })
        
        return at_risk_projects
    
    def analyze_workload(self):
        """
        Analyse la charge de travail des employés
        """
        employees = Employee.objects.select_related('user').prefetch_related('assigned_tasks').all()
        
        workload_analysis = []
        
        for employee in employees:
            active_tasks = employee.assigned_tasks.filter(status='in_progress')
            high_priority_tasks = active_tasks.filter(priority__in=['high', 'urgent'])
            
            workload_level = 'normal'
            if active_tasks.count() > 10:
                workload_level = 'overloaded'
            elif active_tasks.count() < 2:
                workload_level = 'underloaded'
            
            workload_analysis.append({
                'employee': employee,
                'total_tasks': active_tasks.count(),
                'high_priority_tasks': high_priority_tasks.count(),
                'workload_level': workload_level,
                'recommendation': self._get_workload_recommendation(workload_level, active_tasks.count())
            })
        
        return workload_analysis
    
    def _get_workload_recommendation(self, workload_level, task_count):
        """
        Génère des recommandations basées sur la charge de travail
        """
        if workload_level == 'overloaded':
            return "Considérer la réaffectation de certaines tâches ou l'embauche temporaire."
        elif workload_level == 'underloaded':
            return "Peut accepter de nouvelles responsabilités ou aider d'autres équipes."
        else:
            return "Charge de travail équilibrée."
    
    def generate_monthly_report(self):
        """
        Génère un rapport mensuel avec l'IA
        """
        if not self.client:
            return self._generate_fallback_monthly_report()
        
        context = self._prepare_monthly_context()
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un expert en gestion d'entreprise. Génère un rapport mensuel professionnel avec statistiques, points forts, difficultés et recommandations."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"Erreur lors de la génération du rapport mensuel: {e}")
            return self._generate_fallback_monthly_report()
    
    def _prepare_monthly_context(self):
        """
        Prépare le contexte pour le rapport mensuel
        """
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        # Statistiques du mois
        completed_projects = Project.objects.filter(status='completed', updated_at__gte=month_start)
        completed_tasks = Task.objects.filter(status='completed', updated_at__gte=month_start)
        reports_sent = DailyReport.objects.filter(date__gte=month_start)
        
        context = f"Rapport mensuel - {today.strftime('%B %Y')}\n\n"
        context += f"Projets terminés ce mois: {completed_projects.count()}\n"
        context += f"Tâches terminées ce mois: {completed_tasks.count()}\n"
        context += f"Rapports envoyés ce mois: {reports_sent.count()}\n"
        
        context += "\nGénère un rapport mensuel structuré avec:\n"
        context += "- Résumé du mois\n"
        context += "- Statistiques principales\n"
        context += "- Points forts\n"
        context += "- Difficultés rencontrées\n"
        context += "- Recommandations pour améliorer la gestion\n"
        
        return context
    
    def _generate_fallback_monthly_report(self):
        """
        Génère un rapport mensuel de secours
        """
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        completed_projects = Project.objects.filter(status='completed', updated_at__gte=month_start)
        completed_tasks = Task.objects.filter(status='completed', updated_at__gte=month_start)
        
        report = f"Rapport mensuel - {today.strftime('%B %Y')}\n\n"
        report += f"Projets terminés: {completed_projects.count()}\n"
        report += f"Tâches terminées: {completed_tasks.count()}\n"
        report += "\nRecommandations: Continuer à suivre la progression des projets et optimiser la répartition des tâches."
        
        return report
