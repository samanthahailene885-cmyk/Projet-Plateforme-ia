from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import AISummary, AIChat
from .services import DecisionAIService


@login_required
def ai_assistant(request):
    """
    Vue de l'assistant IA avec interface de chat
    """
    # Récupérer l'historique des conversations
    chat_history = AIChat.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    context = {
        'chat_history': chat_history,
    }
    return render(request, 'decision_ai/assistant.html', context)


@login_required
def ai_chat(request):
    """
    Vue API pour le chat avec l'IA
    """
    if request.method == 'POST':
        question = request.POST.get('question', '')
        
        if not question:
            return JsonResponse({'error': 'Question vide'}, status=400)
        
        # Utiliser le service IA pour répondre
        service = DecisionAIService()
        answer = service.answer_question(question)
        
        # Sauvegarder la conversation
        AIChat.objects.create(
            user=request.user,
            question=question,
            answer=answer
        )
        
        return JsonResponse({
            'question': question,
            'answer': answer
        })
    
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@login_required
def generate_summary(request):
    """
    Vue pour générer un résumé intelligent
    """
    if not request.user.is_admin():
        messages.error(request, 'Vous n\'avez pas les droits pour effectuer cette action.')
        return redirect('tasks:list')
    
    service = DecisionAIService()
    summary_content = service.generate_intelligent_summary()
    
    # Sauvegarder le résumé
    AISummary.objects.create(
        generated_by=request.user,
        title=f"Résumé intelligent - {service._get_current_date()}",
        content=summary_content,
        summary_type='daily'
    )
    
    messages.success(request, 'Résumé intelligent généré avec succès.')
    return redirect('decision_ai:summaries')


@login_required
def summaries_list(request):
    """
    Vue de la liste des résumés IA
    """
    if not request.user.is_admin():
        messages.error(request, 'Vous n\'avez pas les droits pour accéder à cette page.')
        return redirect('tasks:list')
    
    summaries = AISummary.objects.select_related('generated_by').all()
    
    context = {
        'summaries': summaries,
    }
    return render(request, 'decision_ai/summaries.html', context)


@login_required
def delay_detection(request):
    """
    Vue pour la détection des retards de projets
    """
    if not request.user.is_admin():
        messages.error(request, 'Vous n\'avez pas les droits pour accéder à cette page.')
        return redirect('tasks:list')
    
    service = DecisionAIService()
    at_risk_projects = service.detect_project_delays()
    
    context = {
        'at_risk_projects': at_risk_projects,
    }
    return render(request, 'decision_ai/delay_detection.html', context)


@login_required
def workload_analysis(request):
    """
    Vue pour l'analyse de la charge de travail
    """
    if not request.user.is_admin():
        messages.error(request, 'Vous n\'avez pas les droits pour accéder à cette page.')
        return redirect('tasks:list')
    
    service = DecisionAIService()
    workload_analysis = service.analyze_workload()
    
    context = {
        'workload_analysis': workload_analysis,
    }
    return render(request, 'decision_ai/workload_analysis.html', context)


@login_required
def monthly_report(request):
    """
    Vue pour générer un rapport mensuel
    """
    if not request.user.is_admin():
        messages.error(request, 'Vous n\'avez pas les droits pour effectuer cette action.')
        return redirect('tasks:list')
    
    service = DecisionAIService()
    report_content = service.generate_monthly_report()
    
    # Sauvegarder le rapport
    AISummary.objects.create(
        generated_by=request.user,
        title=f"Rapport mensuel - {service._get_current_date()}",
        content=report_content,
        summary_type='monthly'
    )
    
    messages.success(request, 'Rapport mensuel généré avec succès.')
    return redirect('decision_ai:summaries')
