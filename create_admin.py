import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from authentication.models import User

# Vérifier si l'utilisateur admin existe déjà
try:
    admin_user = User.objects.get(username='admin')
    # Mettre à jour le rôle en admin
    admin_user.role = 'admin'
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
