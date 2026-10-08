from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    path('', views.task_list, name='list'),
    path('todo/', views.daily_todo, name='daily'),
    path('create/', views.task_create, name='create'),
    path('difficultes/', views.difficulty_list, name='difficulties'),
    path('difficultes/signaler/', views.difficulty_create, name='difficulty_create'),
    path('difficultes/<int:pk>/resoudre/', views.difficulty_resolve, name='difficulty_resolve'),
    path('<int:pk>/', views.task_detail, name='detail'),
    path('<int:pk>/update/', views.task_update, name='update'),
    path('<int:pk>/delete/', views.task_delete, name='delete'),
path('<int:pk>/documents/<int:document_id>/', views.task_document, name='document'),
    path('<int:pk>/documents/<int:document_id>/delete/', views.task_document_delete, name='document_delete'),
    path('<int:pk>/resultat/', views.task_result_upload, name='result_upload'),
    path('<int:pk>/resultat/fichier/', views.task_result, name='result'),
    path('<int:pk>/complete/', views.task_complete, name='complete'),
    path('<int:pk>/status/', views.task_set_status, name='set_status'),
]
