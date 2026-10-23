import json
import logging
import re
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

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

_THINKING = re.compile(r'<think>.*?</think>', re.IGNORECASE | re.DOTALL)


class AIServiceError(Exception):
    """Le service IA n'a pas produit de texte. Aucun contenu de remplacement n'est inventé."""


class NoSubmittedReportsError(AIServiceError):
    """Aucun rapport soumis : l'appel au modèle n'a pas lieu."""


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

SYNTHESIS_SYSTEM = (
    "Tu rédiges la synthèse des rapports journaliers pour le responsable de RAC'IN Africa. "
    "Tu regroupes les travaux par métier, au lieu de résumer chaque employé séparément. "
    "Tu t'appuies uniquement sur les rapports, les notes et les faits fournis. "
    "Tu n'inventes aucune activité, aucun employé, aucun projet, aucun retard, "
    "aucune difficulté et aucun chiffre. "
    "Tu ne présentes pas une réflexion ou une préparation comme un livrable terminé. "
    "Tu n'attribues aucun pourcentage et tu ne juges pas les employés. "
    "Si aucune difficulté n'est écrite, tu l'indiques explicitement. "
    "Un rapport non soumis n'est pas une absence. "
    "Tu suis exactement ce plan, avec ces titres, dans cet ordre : "
    "Résumé général ; "
    "2. Activités réalisées ; "
    "3. Activités en cours ; "
    "4. Difficultés signalées ; "
    "5. Points nécessitant l'attention du responsable ; "
    "6. Conclusion et recommandations. "
    "Le résumé général est un paragraphe. "
    "Les activités réalisées sont des puces par métier réellement présent "
    "(Graphisme, Community management, Développement web, Communication et marketing). "
    "Les activités en cours forment un paragraphe. "
    "Les difficultés forment un ou deux paragraphes. "
    "Les points d'attention sont des puces tirées des faits. "
    "La conclusion est un paragraphe de recommandations, séparé des faits. "
    "Tu écris en français."
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
    "Réponds en français avec les titres Résumé général, "
    "2. Activités réalisées, 3. Activités en cours, 4. Difficultés signalées, "
    "5. Points nécessitant l'attention du responsable, "
    "6. Conclusion et recommandations."
)


class DecisionAIService:
    def __init__(self):
        self.base_url = (getattr(settings, 'OLLAMA_BASE_URL', '') or '').strip().rstrip('/')
        self.model = (getattr(settings, 'OLLAMA_MODEL', '') or '').strip()
        timeout = getattr(settings, 'OLLAMA_TIMEOUT', 60)
        self.timeout = timeout if isinstance(timeout, (int, float)) and timeout > 0 else 60
        self.hosted_url = (getattr(settings, 'AI_BASE_URL', '') or '').strip().rstrip('/')
        self.hosted_model = (getattr(settings, 'AI_MODEL', '') or '').strip()
        self.hosted_key = (getattr(settings, 'AI_API_KEY', '') or '').strip()
        hosted_timeout = getattr(settings, 'AI_TIMEOUT', 80)
        self.hosted_timeout = hosted_timeout if isinstance(hosted_timeout, (int, float)) and hosted_timeout > 0 else 80

    def _uses_local_model(self):
        return bool(self.base_url and self.model)

    def _complete(self, system, user_content, max_tokens=900):
        """Demande une formulation au modèle. N'invente rien s'il ne répond pas."""
        if self._uses_local_model():
            return self._complete_local(system, user_content, max_tokens)
        if self.hosted_url and self.hosted_model:
            return self._complete_hosted(system, user_content, max_tokens)
        raise AIServiceError(
            "Le modèle local n'est pas configuré. "
            "Indiquez OLLAMA_BASE_URL et OLLAMA_MODEL, puis redémarrez l'application. "
            "Aucun texte n'a été inventé."
        )

    def _complete_local(self, system, user_content, max_tokens):
        payload = json.dumps({
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user_content},
            ],
            'stream': False,
            'options': {
                'temperature': 0.2,
                'num_predict': max_tokens,
            },
        }).encode('utf-8')
        request = urllib.request.Request(
            f'{self.base_url}/api/chat',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode('utf-8')
        except urllib.error.HTTPError as exc:
            logger.warning('Ollama a répondu HTTP %s.', exc.code)
            raise AIServiceError(
                "Le modèle local n'a pas pu répondre. "
                "Vérifiez qu'Ollama est démarré et que le modèle indiqué est installé. "
                "Aucun texte n'a été inventé."
            )
        except (urllib.error.URLError, TimeoutError, OSError):
            logger.warning('Ollama est injoignable.')
            raise AIServiceError(
                "Le modèle local est indisponible. "
                "Démarrez Ollama sur cet ordinateur, puis réessayez. "
                "Aucun texte n'a été inventé."
            )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise AIServiceError(
                "Le modèle local a renvoyé une réponse illisible. Aucun texte n'a été inventé."
            )
        message = data.get('message') if isinstance(data, dict) else None
        text = (message.get('content') or '').strip() if isinstance(message, dict) else ''
        text = _visible_answer(text)
        if not text:
            raise AIServiceError(
                "Le modèle local a renvoyé une réponse vide. "
                "Aucun texte de remplacement n'a été généré."
            )
        return text

    def _hosted_endpoint(self):
        url = self.hosted_url
        if url.endswith('/chat/completions') or url.endswith('/openai'):
            return url
        return f'{url}/chat/completions'

    def _complete_hosted(self, system, user_content, max_tokens):
        payload = json.dumps({
            'model': self.hosted_model,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user_content},
            ],
            'temperature': 0.2,
            'max_tokens': max_tokens,
            'stream': False,
        }).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        if self.hosted_key:
            headers['Authorization'] = f'Bearer {self.hosted_key}'
        request = urllib.request.Request(
            self._hosted_endpoint(),
            data=payload,
            headers=headers,
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=self.hosted_timeout) as response:
                raw = response.read().decode('utf-8')
        except Exception:
            logger.warning('Le modèle hébergé n’a pas répondu à temps.')
            raise AIServiceError(
                "Le modèle hébergé n'a pas pu répondre. Aucun texte n'a été inventé."
            )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise AIServiceError(
                "Le modèle hébergé a renvoyé une réponse illisible. Aucun texte n'a été inventé."
            )
        choices = data.get('choices') if isinstance(data, dict) else None
        message = choices[0].get('message') if isinstance(choices, list) and choices else None
        text = (message.get('content') or '').strip() if isinstance(message, dict) else ''
        text = _visible_answer(text)
        if not text:
            raise AIServiceError(
                "Le modèle hébergé a renvoyé une réponse vide. "
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
        from reports.synthesis import (
            collect_team_synthesis,
            compose_team_synthesis,
            synthesis_has_expected_shape,
            synthesis_prompt,
        )

        dossier = collect_team_synthesis(day)
        if dossier['analyzed'] == 0:
            raise NoSubmittedReportsError("Aucun rapport disponible pour cette date.")
        fallback = compose_team_synthesis(dossier)
        previous_timeout = self.timeout
        previous_hosted = self.hosted_timeout
        if self._uses_local_model():
            self.timeout = min(previous_timeout, 20)
        else:
            # Render coupe la requête au bout d'une trentaine de secondes.
            self.hosted_timeout = min(self.hosted_timeout, 18)
        try:
            text = self._complete(SYNTHESIS_SYSTEM, synthesis_prompt(dossier), max_tokens=1600)
            if not (text or '').strip():
                raise AIServiceError("Le modèle n'a renvoyé aucun texte.")
            if not synthesis_has_expected_shape(text):
                raise AIServiceError("Le modèle n'a pas suivi le plan de synthèse.")
            dossier['generative'] = True
        except AIServiceError as exc:
            text = fallback
            dossier['generative'] = False
            dossier['ai_error'] = str(exc)
        finally:
            self.timeout = previous_timeout
            self.hosted_timeout = previous_hosted
        return text, dossier

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


def _visible_answer(text):
    return _THINKING.sub('', text or '').strip()


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
