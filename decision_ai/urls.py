from django.urls import path
from . import views

app_name = 'decision_ai'

urlpatterns = [
    path('assistant/', views.ai_assistant, name='assistant'),
    path('chat/', views.ai_chat, name='chat'),
    path('summaries/', views.summaries_list, name='summaries'),
    path('generate-summary/', views.generate_summary, name='generate_summary'),
    path('delay-detection/', views.delay_detection, name='delay_detection'),
    path('workload-analysis/', views.workload_analysis, name='workload_analysis'),
    path('monthly-report/', views.monthly_report, name='monthly_report'),
]
