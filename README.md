# Plateforme Intelligente d'Aide à la Décision

## Description
Plateforme web professionnelle pour la gestion d'une agence de communication avec intégration d'intelligence artificielle pour l'aide à la décision.

## Technologies
- Backend: Django (Python)
- Base de données: PostgreSQL
- Frontend: HTML5, CSS3, Bootstrap 5, JavaScript, Chart.js
- IA: OpenAI API

## Installation

1. Créer un environnement virtuel:
```bash
python -m venv venv
venv\Scripts\activate
```

2. Installer les dépendances:
```bash
pip install -r requirements.txt
```

3. Configurer la base de données PostgreSQL:
```bash
CREATE DATABASE plateforme_db;
```

4. Configurer les variables d'environnement:
```bash
cp .env.example .env
# Éditer .env avec vos configurations
```

5. Exécuter les migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

6. Créer un superutilisateur:
```bash
python manage.py createsuperuser
```

7. Lancer le serveur:
```bash
python manage.py runserver
```

## Structure du projet
```
plateforme_web/
├── manage.py
├── requirements.txt
├── .env
├── core/                  # Configuration principale
├── authentication/        # Module d'authentification
├── employees/             # Gestion des employés
├── projects/              # Gestion des projets
├── tasks/                 # Gestion des tâches
├── todo/                  # Todo List
├── reports/               # Rapports quotidiens
├── permissions/           # Gestion des permissions
├── attendance/            # Gestion de la présence
├── dashboard/             # Tableau de bord
├── decision_ai/           # Module IA
├── notifications/        # Notifications
├── static/                # Fichiers statiques
└── templates/             # Templates HTML
```

## Modules
1. Authentification
2. Gestion des employés
3. Gestion des projets
4. Gestion des tâches
5. Todo List
6. Rapport quotidien
7. Gestion des permissions
8. Présence
9. Tableau de bord
10. DecisionAI (Module IA)
