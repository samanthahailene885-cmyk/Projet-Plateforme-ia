@echo off
echo Lancement du projet Django...
echo.

cd /d "%~dp0"

echo Activation de l'environnement virtuel...
call venv\Scripts\activate.bat

echo.
echo Demarrage du serveur de developpement...
echo Le serveur sera accessible sur http://127.0.0.1:8000
echo Appuyez sur CTRL+C pour arreter le serveur.
echo.

python manage.py runserver

pause
