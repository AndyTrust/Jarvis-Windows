# Avvia l'ascolto vocale di Jarvis (Whisper locale + voce Sara): Shift destro accende/spegne il microfono.
# Senza finestra di terminale: i log vanno in strumenti\talk-to-jarvis.log e talk-to-jarvis-err.log.
$cartella = Split-Path -Parent $PSScriptRoot
$py = Join-Path $cartella ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $py)) { $py = Join-Path $cartella ".venv\Scripts\python.exe" }
$espeak = "C:\Program Files\eSpeak NG"
if (Test-Path $espeak) { $env:PATH = "$espeak;" + $env:PATH }
$env:PYTHONUTF8 = "1"
Start-Process -FilePath $py -ArgumentList "strumenti\talk_to_jarvis_windows.py" -WorkingDirectory $cartella -WindowStyle Hidden
