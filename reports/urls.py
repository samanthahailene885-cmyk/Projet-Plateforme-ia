from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_list, name='list'),
    path('create/', views.report_create, name='create'),
    path('generate/', views.report_generate, name='generate'),
    path('generer-jour/', views.generate_day_reports, name='generate_day'),
    path('save/', views.report_save, name='save'),
    path('importer-pdf/', views.report_upload, name='upload'),
    path('equipe/', views.team_report, name='team'),
    path('synthese/', views.team_synthesis, name='synthesis'),
    path('<int:pk>/pdf/', views.report_pdf, name='pdf'),
    path('<int:pk>/', views.report_detail, name='detail'),
]
