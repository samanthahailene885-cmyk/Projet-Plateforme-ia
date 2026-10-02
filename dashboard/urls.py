from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('recherche/', views.dashboard_search, name='search'),
    path('employee/', views.employee_home, name='employee_home'),
]
