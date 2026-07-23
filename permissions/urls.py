from django.urls import path
from . import views

app_name = 'permissions'

urlpatterns = [
    path('', views.permission_list, name='list'),
    path('create/', views.permission_create, name='create'),
    path('<int:pk>/', views.permission_detail, name='detail'),
    path('<int:pk>/approve/', views.permission_approve, name='approve'),
]
