from django.urls import path

from . import work_api

urlpatterns = [
    path('session/', work_api.session_view, name='work_session'),
    path('connexion/', work_api.login_view, name='work_login'),
    path('deconnexion/', work_api.logout_view, name='work_logout'),
    path('basculer/', work_api.switch_view, name='work_switch'),
    path('employes/', work_api.employees_view, name='work_employees'),
    path('projets/', work_api.projects_view, name='work_projects'),
    path('projets/<int:pk>/', work_api.project_detail_view, name='work_project'),
    path('taches/', work_api.tasks_view, name='work_tasks'),
    path('taches/<int:pk>/', work_api.task_detail_view, name='work_task'),
    path('taches/<int:pk>/statut/', work_api.task_status_view, name='work_task_status'),
    path('taches/<int:pk>/resultat/', work_api.task_result_view, name='work_task_result'),
    path('taches/<int:pk>/fichier/', work_api.task_result_file_view, name='work_task_file'),
    path('taches/<int:pk>/documents/<int:document_id>/', work_api.task_document_view, name='work_task_document'),
    path('todos/', work_api.todos_view, name='work_todos'),
    path('rapports/', work_api.reports_view, name='work_reports'),
    path('rapports/<int:pk>/fichier/', work_api.report_file_view, name='work_report_file'),
    path('permissions/', work_api.permissions_view, name='work_permissions'),
    path('permissions/<int:pk>/', work_api.permission_decide_view, name='work_permission'),
    path('difficultes/', work_api.difficulties_view, name='work_difficulties'),
    path('alertes/', work_api.alerts_view, name='work_alerts'),
    path('notifications/', work_api.notifications_view, name='work_notifications'),
    path('messages/', work_api.messages_view, name='work_messages'),
    path('documents/', work_api.documents_view, name='work_documents'),
    path('demonstration/', work_api.demonstration_view, name='work_demonstration'),
]
