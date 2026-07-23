from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.attendance_list, name='list'),
    path('create/', views.attendance_create, name='create'),
    path('<int:pk>/', views.attendance_detail, name='detail'),
    path('<int:pk>/update/', views.attendance_update, name='update'),
    path('<int:pk>/delete/', views.attendance_delete, name='delete'),
]
