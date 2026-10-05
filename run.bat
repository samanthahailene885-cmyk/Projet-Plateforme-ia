@echo off
echo Lancement de la plateforme RAC'IN...
echo.

cd /d "%~dp0maquette"

where npm >nul 2>&1
if errorlevel 1 (
  echo Node.js est introuvable. Installez-le, puis relancez run.bat.
  pause
  exit /b 1
)

if not exist node_modules (
  echo Installation des composants, patientez...
  call npm install
  if errorlevel 1 (
    echo L'installation a echoue.
    pause
    exit /b 1
  )
)

netstat -ano | findstr ":5173" | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo La plateforme est deja lancee.
  echo Ouverture de http://127.0.0.1:5173
  start "" http://127.0.0.1:5173/
  pause
  exit /b 0
)

echo.
echo La plateforme s'ouvre sur http://127.0.0.1:5173
echo Appuyez sur CTRL+C pour arreter.
echo.

call npm run dev -- --open

pause
