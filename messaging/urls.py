from django.urls import path

from . import views

app_name = 'messaging'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('fichier/<int:pk>/', views.message_file, name='file'),
]
