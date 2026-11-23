@echo off
setlocal
cd /d "%~dp0"
echo Iniciando Jardines de la Costa ERP en la red local, puerto 5000
".venv\Scripts\python.exe" -m waitress --listen=0.0.0.0:5000 wsgi:app
