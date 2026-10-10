@echo off
rem Doppio clic per aggiornare Jarvis all'ultima versione. Non tocca i tuoi dati (memoria, agenti, impostazioni, posta).
rem Va tenuto nella cartella del clone di Jarvis-Privato-Windows, accanto ad AGGIORNA.ps1.
cd /d "%~dp0"
if not exist ".git" (
  echo Questa cartella non e' un clone git di Jarvis. Scarica Jarvis con git clone e rilancia da li'.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0AGGIORNA.ps1"
echo.
pause
