from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_list, name='list'),
    path('create/', views.report_create, name='create'),
    path('generate/', views.report_generate, name='generate'),
    path('<int:pk>/', views.report_detail, name='detail'),
]
