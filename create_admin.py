import os
from datetime import date

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from authentication.models import User
from employees.models import Employee

TEAM = [
    ('nouzou', 'nabihouddine', 'Zaina', 'Zaina', 'other', '', date(2026, 7, 21)),
    ('awa.traore', 'Employe-2026', 'Awa', 'Traoré', 'designer', 'Direction Generale', date(2026, 10, 8)),
    ('mamadou.kone', 'Employe-2026', 'Mamadou', 'Koné', 'developer', 'Direction Generale', date(2026, 10, 8)),
    ('fatou.diarra', 'Employe-2026', 'Fatou', 'Diarra', 'communication', 'Direction Generale', date(2026, 10, 8)),
    ('ibrahim.bah', 'Employe-2026', 'Ibrahim', 'Bah', 'marketing', 'Direction Generale', date(2026, 10, 8)),
]


def ensure_team():
    """Crée les employés de la démonstration s'ils n'existent pas encore."""
    for username, password, first, last, position, department, hired in TEAM:
        user = User.objects.filter(username=username).first()
        if user is None:
            user = User.objects.create_user(
                username=username,
                email=f'{username}@racin.africa',
                password=password,
                first_name=first,
                last_name=last,
                role='employee',
            )
        else:
            changed = []
            if user.role != 'employee':
                user.role = 'employee'
                changed.append('role')
            if not user.is_active:
                user.is_active = True
                changed.append('is_active')
            if not user.first_name:
                user.first_name = first
                changed.append('first_name')
            if not user.last_name:
                user.last_name = last
                changed.append('last_name')
            if os.environ.get('RENDER') == 'true' and username == 'nouzou':
                user.first_name = 'Zaina'
                user.last_name = 'Zaina'
                user.set_password(password)
                changed = ['first_name', 'last_name', 'role', 'is_active', 'password']
            if changed:
                user.save()
        profile = Employee.objects.filter(user=user).first()
        if profile is None:
            Employee.objects.create(
                user=user,
                position=position,
                department=department,
                hire_date=hired,
                status='active',
            )
        elif profile.status != 'active':
            profile.status = 'active'
            profile.save(update_fields=['status', 'updated_at'])

# Vérifier si l'utilisateur admin existe déjà
try:
    admin_user = User.objects.get(username='admin')
    # Mettre à jour le rôle en admin
    admin_user.role = 'admin'
    admin_user.is_active = True
    if os.environ.get('RENDER') == 'true':
        admin_user.set_password('admin123')
    admin_user.save()
    print("Utilisateur 'admin' existe déjà, rôle mis à jour en admin!")
    print("Username: admin")
    print("Password: (inchangé)")
except User.DoesNotExist:
    # Créer un nouvel utilisateur admin
    admin_user = User.objects.create_user(
        username='admin',
        email='admin@company.com',
        password='admin123',
        first_name='Admin',
        last_name='Principal',
        role='admin'
    )
    print("Compte admin créé avec succès!")
    print("Username: admin")
    print("Password: admin123")

ensure_team()
