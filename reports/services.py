from decision_ai.services import AIServiceError, DecisionAIService
from decision_ai.analytics import employee_report_payload


class ReportGenerator:
    """Prépare le rapport journalier à partir des activités enregistrées."""

    def generate_daily_report(self, user, day):
        payload = employee_report_payload(user, day)
        if payload['counts']['planned'] == 0:
            raise AIServiceError(
                "Données insuffisantes : aucune activité n'est enregistrée pour cette date. "
                "Le rapport n'a pas été généré."
            )
        return DecisionAIService().generate_employee_report(user, day)

    @staticmethod
    def task_lines(user, day, statuses):
        payload = employee_report_payload(user, day)
        titles = [
            task['title']
            for task in payload['tasks']
            if task['status_code'] in statuses
        ]
        return '\n'.join(titles)
