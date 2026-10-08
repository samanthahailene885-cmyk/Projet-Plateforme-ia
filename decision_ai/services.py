import logging

from django.conf import settings
from django.utils import timezone
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from decision_ai.analytics import (
    assistant_context,
    collect_alerts,
    day_stats,
    employee_report_payload,
    format_employee_payload,
    period_stats,
    project_delay_risks,
    recorded_answer,
    workload_rows,
)


logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Le service IA n'a pas produit de texte. Aucun contenu de remplacement n'est inventé."""


class NoSubmittedReportsError(AIServiceError):
    """Aucun rapport soumis : l'appel au modèle n'a pas lieu."""


def _api_error_parts(exc):
    body = getattr(exc, 'body', None) or {}
    error = body.get('error') if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {}
    return (
        type(exc).__name__,
        getattr(exc, 'status_code', None),
        error.get('code'),
        error.get('type'),
    )


def _log_api_error(exc):
    kind, status, code, error_type = _api_error_parts(exc)
    logger.warning(
        'Appel OpenAI refusé (%s, statut %s, code %s, type %s).',
        kind, status, code, error_type,
    )


def _activity_sentence(task):
    title = (task.get('title') or '').strip().rstrip('.')
    extras = []
    for key in ('description', 'comments'):
        value = (task.get(key) or '').strip().rstrip('.')
        if value and value.lower() not in title.lower():
            extras.append(value)
    sentence = title
    if extras:
        sentence = f"{sentence}. {'. '.join(extras)}"
    if sentence and sentence[-1] not in '.!?':
        sentence += '.'
    return sentence


def compose_employee_report(payload):
    """Une puce par activité enregistrée, sans chiffre ni rubrique inventés."""
    lines = []
    for task in payload['tasks']:
        sentence = _activity_sentence(task)
        if sentence:
            lines.append(f'■ {sentence}')
    return '\n\n'.join(lines)


def _quota_exhausted(exc):
    body = getattr(exc, 'body', None) or {}
    error = body.get('error') if isinstance(body, dict) else {}
    details = ''
    if isinstance(error, dict):
        details = f"{error.get('code') or ''} {error.get('type') or ''}"
    blob = f'{details} {exc}'
    return 'insufficient_quota' in blob or 'credit_balance_exhausted' in blob


REPORT_SYSTEM = (
    "Tu rédiges le rapport journalier d'un employé de l'agence RAC'IN. "
    "Tu utilises uniquement les activités fournies. "
    "Tu n'inventes aucune activité, aucun résultat, aucun chiffre et aucune difficulté. "
    "Chaque activité devient un seul paragraphe, séparé du suivant par une ligne vide. "
    "Le paragraphe reprend le travail indiqué, en une ou deux phrases, à partir du titre et de la remarque. "
    "Tu ne mets pas de titre de section, pas de date, pas de nom et pas de bilan chiffré. "
    "Tu commences chaque paragraphe par le caractère ■ suivi d'un espace. "
    "Tu écris en français."
)

REMARK_SYSTEM = (
    "Tu reformules une remarque en français professionnel. "
    "Tu conserves strictement le sens et les faits. "
    "Tu n'ajoutes aucune information. "
    "Tu renvoies uniquement la phrase reformulée, sans préambule."
)

SUMMARY_SYSTEM = (
    "Tu rédiges un résumé pour le responsable d'une agence de communication. "
    "Les chiffres fournis ont déjà été calculés : tu les reprends tels quels. "
    "Tu ne recalcules rien et tu n'inventes aucun employé, projet, activité ou nombre. "
    "Si aucune difficulté n'est listée, tu l'indiques. "
    "Tu restes factuel et tu ne juges pas la performance des employés. "
    "Réponds en français, de façon synthétique."
)

ALERT_SYSTEM = (
    "Tu expliques en français des alertes déjà produites par des règles. "
    "Tu ne crées pas de nouvelle alerte et tu n'inventes pas de fait. "
    "Tu ne juges pas la performance ou la productivité d'un employé. "
    "Tu proposes seulement de vérifier les éléments cités."
)

ASSISTANT_SYSTEM = (
    "Tu es l'assistant du responsable d'une agence de communication. "
    "Tu réponds uniquement à partir du contexte fourni. "
    "Les statistiques ont été calculées par le système : tu les recopies sans les additionner ni les recalculer. "
    "Tu n'inventes aucun employé, projet, activité ou chiffre. "
    "Si l'information n'est pas dans le contexte, tu le dis clairement. "
    "Tu ne juges pas la performance des employés. "
    "Tu réponds en français, de façon concise."
)

MONTHLY_SYSTEM = (
    "Tu rédiges un bilan mensuel factuel en français à partir des seuls chiffres fournis. "
    "Tu n'inventes aucune difficulté ni aucune réussite absente des données. "
    "Si une information manque, tu l'indiques."
)

TEAM_SYNTHESIS_SYSTEM = (
    "Tu rédiges UNE SEULE synthèse globale pour le responsable d'une agence de communication. "
    "Tu t'appuies uniquement sur les rapports journaliers soumis et les activités fournies. "
    "Tu ne produis pas un rapport séparé par employé et tu ne recopies pas les rapports à la suite. "
    "Tu n'inventes aucun employé, aucune activité, aucun projet, aucune difficulté, "
    "aucun métier, aucun nombre, aucune progression et aucune information absente. "
    "Tu n'ajoutes pas de civilité (M., Mme) si elle n'est pas déjà écrite dans les données. "
    "Les décomptes fournis ont été calculés par le système : tu peux les reprendre tels quels, "
    "sans les recalculer et sans en créer d'autres. "
    "Un rapport non soumis ne signifie pas une absence : tu peux seulement reprendre le nombre indiqué. "
    "Tu ne cites pas le nom d'un employé qui n'a pas de rapport dans les données. "
    "Si aucune difficulté n'est présente, écris qu'aucune difficulté n'a été signalée. "
    "N'écris pas qu'une activité est en cours si le décompte en cours est 0. "
    "N'écris pas qu'un projet concentre l'activité si aucun projet n'est fourni. "
    "Réponds en français, en quatre à six paragraphes continus, sans puces. "
    "Commence par le titre « Synthèse de la journée », puis le bilan des activités réalisées, "
    "puis les activités encore en cours s'il y en a, puis les difficultés réellement présentes, "
    "puis les projets réellement cités, puis une conclusion qui donne une vision globale de la journée."
)


class DecisionAIService:
    _quota_blocked = False

    def __init__(self):
        api_key = (getattr(settings, 'OPENAI_API_KEY', '') or '').strip()
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
        timeout = getattr(settings, 'OPENAI_TIMEOUT', 45)
        self.client = None
        self._setup_error = None
        if not api_key or api_key == 'your-openai-api-key':
            self._setup_error = (
                "Le service d'intelligence artificielle n'est pas configuré. "
                "Dans le fichier .env, remplacez OPENAI_API_KEY par une clé réelle "
                "(platform.openai.com), puis redémarrez l'application."
            )
            return
        try:
            self.client = OpenAI(api_key=api_key, timeout=timeout)
        except Exception:
            self.client = None
            self._setup_error = (
                "Le client OpenAI n'a pas pu démarrer. "
                "Vérifiez que le paquet openai est compatible avec les bibliothèques installées, "
                "puis redémarrez l'application."
            )

    def _complete(self, system, user_content, max_tokens=900):
        if not self.client:
            raise AIServiceError(
                self._setup_error
                or "Le service d'intelligence artificielle est indisponible."
            )
        if DecisionAIService._quota_blocked:
            raise AIServiceError(
                "Le compte OpenAI n'a plus de crédit. "
                "Ajoutez des crédits dans la facturation sur platform.openai.com, "
                "puis relancez la génération. Aucun texte n'a été inventé à la place."
            )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user_content},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            text = (response.choices[0].message.content or '').strip()
        except AIServiceError:
            raise
        except AuthenticationError as exc:
            _log_api_error(exc)
            raise AIServiceError(
                "La clé OPENAI_API_KEY a été refusée par le service. "
                "Vérifiez la clé dans le fichier .env, puis redémarrez l'application. "
                "Aucun texte n'a été inventé à la place."
            )
        except APITimeoutError as exc:
            _log_api_error(exc)
            raise AIServiceError(
                "Le service d'intelligence artificielle a mis trop de temps à répondre. "
                "Réessayez dans quelques instants. Aucun texte n'a été inventé."
            )
        except RateLimitError as exc:
            _log_api_error(exc)
            if _quota_exhausted(exc):
                DecisionAIService._quota_blocked = True
                raise AIServiceError(
                    "Le compte OpenAI n'a plus de crédit. "
                    "Ajoutez des crédits dans la facturation sur platform.openai.com, "
                    "puis relancez la génération. Aucun texte n'a été inventé à la place."
                )
            raise AIServiceError(
                "Le service d'intelligence artificielle est temporairement saturé. "
                "Réessayez dans quelques instants. Aucun texte n'a été inventé à la place."
            )
        except APIConnectionError as exc:
            _log_api_error(exc)
            raise AIServiceError(
                "Le service d'intelligence artificielle est temporairement indisponible. "
                "Réessayez dans quelques instants. Aucun texte n'a été inventé à la place."
            )
        except Exception as exc:
            _log_api_error(exc)
            raise AIServiceError(
                "Le service d'intelligence artificielle est temporairement indisponible. "
                "Réessayez dans quelques instants. Aucun texte n'a été inventé à la place."
            )
        if not text:
            raise AIServiceError(
                "Le service d'intelligence artificielle a renvoyé une réponse vide. "
                "Aucun texte de remplacement n'a été généré."
            )
        return text

    def _complete_or(self, system, user_content, fallback, max_tokens=900):
        """Utilise le modèle s'il répond, sinon le texte déjà calculé sur les données enregistrées."""
        try:
            return self._complete(system, user_content, max_tokens=max_tokens)
        except AIServiceError:
            return fallback

    def _get_current_date(self):
        return timezone.now().date().strftime('%d/%m/%Y')

    def generate_employee_report(self, user, day):
        payload = employee_report_payload(user, day)
        if payload['counts']['planned'] == 0:
            raise AIServiceError(
                "Données insuffisantes : aucune activité n'est enregistrée pour cette date. "
                "Le rapport n'a pas été généré."
            )
        if self.client and not DecisionAIService._quota_blocked:
            try:
                return self._complete(REPORT_SYSTEM, format_employee_payload(payload), max_tokens=900)
            except AIServiceError:
                pass
        from decision_ai.briefing import narrate_employee_day
        return narrate_employee_day(payload) or compose_employee_report(payload)

    def improve_remark(self, remark):
        remark = (remark or '').strip()
        if len(remark) < 3:
            raise AIServiceError("Saisissez une remarque avant de demander une reformulation.")
        return self._complete_or(
            REMARK_SYSTEM,
            f"Remarque d'origine :\n{remark}",
            remark,
            max_tokens=300,
        )

    def summarize_day(self, day):
        stats = day_stats(day)
        remarks = stats['remarks']
        if remarks:
            remark_lines = '\n'.join(
                f"- {item['employee']} / {item['task']} : {item['comment'][:400]}"
                for item in remarks[:20]
            )
        else:
            remark_lines = "Aucune remarque enregistrée pour cette date."
        if stats['planned'] == 0 and stats['reports'] == 0 and not remarks:
            raise AIServiceError(
                "Données insuffisantes : aucune activité ni rapport n'est enregistré pour cette date. "
                "Aucun résumé n'a été inventé."
            )
        content = (
            f"{_stats_block(stats)}\n\n"
            f"Remarques et difficultés saisies :\n{remark_lines}\n\n"
            "Produis un résumé avec : le volume d'activités (en reprenant les chiffres), "
            "les difficultés signalées, et les points qui méritent une vérification. "
            "N'ajoute aucun fait absent."
        )
        from decision_ai.briefing import agency_brief, difficulty_brief

        fallback = f"{agency_brief(day)}\n\n{difficulty_brief(day)}"
        return self._complete_or(SUMMARY_SYSTEM, content, fallback, max_tokens=800)

    def explain_alerts(self, alerts):
        if not alerts:
            raise AIServiceError(
                "Aucune situation à expliquer : les règles n'ont rien détecté dans les données enregistrées."
            )
        lines = []
        for alert in alerts[:25]:
            lines.append(
                f"- {alert['kind']} « {alert['subject']} » ({alert['project']}) : "
                f"{alert['reason']} Données : {alert['evidence']} "
                f"Vérification proposée : {alert['suggestion']}"
            )
        from decision_ai.briefing import alert_brief

        return self._complete_or(
            ALERT_SYSTEM,
            "Alertes déjà établies :\n" + '\n'.join(lines),
            alert_brief(alerts),
            max_tokens=800,
        )

    def answer_employee(self, question, facts):
        """Formule une réponse à partir des seuls faits de l'employé connecté."""
        question = (question or '').strip()
        if not question:
            raise AIServiceError('La question est vide.')
        return self._complete(
            (
                "Tu réponds à un employé à partir des seuls faits fournis. "
                "Tu ne cites aucun collègue, aucun chiffre et aucun projet absent de ces faits. "
                "Si les faits ne contiennent pas la réponse, dis-le."
            ),
            f"Question :\n{question}\n\nFaits enregistrés pour cet employé uniquement :\n{facts}",
            max_tokens=500,
        )

    def answer_question(self, question):
        question = (question or '').strip()
        if not question:
            raise AIServiceError("La question est vide.")
        today = timezone.now().date()
        context = f"Question du responsable :\n{question}\n\n{assistant_context(question, today)}"
        return self._complete_or(
            ASSISTANT_SYSTEM,
            context,
            recorded_answer(question, today),
            max_tokens=700,
        )

    def generate_intelligent_summary(self):
        today = timezone.now().date()
        return self.summarize_day(today)

    def detect_project_delays(self):
        return project_delay_risks()

    def analyze_workload(self):
        return workload_rows(timezone.now().date())

    def synthesize_submitted_reports(self, day):
        """Une synthèse d'équipe à partir des rapports soumis dans la base."""
        from reports.synthesis import collect_team_synthesis, compose_team_synthesis

        dossier = collect_team_synthesis(day)
        if dossier['analyzed'] == 0:
            raise NoSubmittedReportsError("Aucun rapport disponible pour cette date.")
        return compose_team_synthesis(dossier), dossier

    def generate_monthly_report(self):
        today = timezone.now().date()
        month_start = today.replace(day=1)
        stats = period_stats(month_start, today)
        alerts = collect_alerts(today)
        content = (
            f"Période : {stats['start']:%d/%m/%Y} au {stats['end']:%d/%m/%Y}\n"
            f"Activités prévues : {stats['planned']}\n"
            f"Activités passées au statut terminé : {stats['completed']}\n"
            f"En cours : {stats['in_progress']}\n"
            f"Non réalisées : {stats['not_done']}\n"
            f"Encore à faire : {stats['todo']}\n"
            f"Alertes ouvertes aujourd'hui : {len(alerts)}\n"
            "Rédige un bilan court. N'invente pas de difficulté si aucune alerte n'est comptée "
            "autrement que par ce nombre."
        )
        fallback = (
            f"Bilan du {stats['start']:%d/%m/%Y} au {stats['end']:%d/%m/%Y}. "
            f"Activités prévues : {stats['planned']}. "
            f"Passées au statut terminé : {stats['completed']}. "
            f"En cours : {stats['in_progress']}. "
            f"Non réalisées : {stats['not_done']}. "
            f"Encore à faire : {stats['todo']}. "
            f"Alertes ouvertes aujourd'hui : {len(alerts)}."
        )
        return self._complete_or(MONTHLY_SYSTEM, content, fallback, max_tokens=800)


def _stats_block(stats):
    return (
        f"Date : {stats['date']:%d/%m/%Y}\n"
        f"Activités prévues : {stats['planned']}\n"
        f"Terminées : {stats['completed']}\n"
        f"En cours : {stats['in_progress']}\n"
        f"À faire : {stats['todo']}\n"
        f"Non réalisées : {stats['not_done']}\n"
        f"Annulées : {stats['cancelled']}\n"
        f"Rapports enregistrés : {stats['reports']}\n"
        f"Employés actifs : {stats.get('active_employees', 'non demandé')}"
    )
