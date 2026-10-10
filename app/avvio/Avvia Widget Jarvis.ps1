# Avvia l'orb di Jarvis (il cerchio sul desktop: logo + stemma, animato, trascinabile).
$cartella = Split-Path -Parent $PSScriptRoot
$py = Join-Path $cartella ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $py)) { $py = Join-Path $cartella ".venv\Scripts\python.exe" }
$env:PYTHONUTF8 = "1"
Start-Process -FilePath $py -ArgumentList "strumenti\jarvis_orb_windows.py" -WorkingDirectory $cartella -WindowStyle Hidden
