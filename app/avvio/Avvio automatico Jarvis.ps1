# Avvio di Jarvis all'accesso: Command Center (senza aprire finestre), orb fluttuante, primo battito.
# Lo registra INSTALLA.ps1 nell'Utilità di pianificazione ("Jarvis Avvio"); si può lanciare anche a mano.
$cartella = Split-Path -Parent $PSScriptRoot
$cc = Join-Path $cartella "command-center"
$py = Join-Path $cartella ".venv\Scripts\python.exe"
$pyw = Join-Path $cartella ".venv\Scripts\pythonw.exe"
$env:PYTHONUTF8 = "1"

$porta = 7777
$cfg = Join-Path $cc "configurazione.json"
if (Test-Path $cfg) { try { $porta = [int]((Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json).porta) } catch {} }
$env:CC_PORTA = "$porta"

if (-not (Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue)) {
    New-Item -ItemType Directory -Force -Path (Join-Path $cc "lavori") | Out-Null
    Start-Process -FilePath $py -ArgumentList "server.py" -WorkingDirectory $cc -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $cc "lavori\server.log") -RedirectStandardError (Join-Path $cc "lavori\server-err.log")
    Start-Sleep -Seconds 4
}
Start-Process -FilePath $pyw -ArgumentList "strumenti\jarvis_orb_windows.py" -WorkingDirectory $cartella -WindowStyle Hidden
Start-Process -FilePath $pyw -ArgumentList "sincro\ogni30.py", "--zitto" -WorkingDirectory $cartella -WindowStyle Hidden
