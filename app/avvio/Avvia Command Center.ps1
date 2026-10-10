# Apre il Command Center di Jarvis come app (finestra propria, a schermo intero, senza barra degli indirizzi).
# Se il server non gira lo avvia in background. Non ha percorsi scritti a mano: parte da dove sta questo file.
param([int]$Porta = 0)

$ErrorActionPreference = "Stop"
$cartella = Split-Path -Parent $PSScriptRoot                      # ...\jarvis
$cc = Join-Path $cartella "command-center"
$py = Join-Path $cartella ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Manca l'ambiente Python ($py). Rilancia INSTALLA.ps1." }

if ($Porta -eq 0) {
    $Porta = 7777
    $cfg = Join-Path $cc "configurazione.json"
    if (Test-Path $cfg) { try { $Porta = [int]((Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json).porta) } catch {} }
}

New-Item -ItemType Directory -Force -Path (Join-Path $cc "lavori") | Out-Null
$inAscolto = Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue
if (-not $inAscolto) {
    $env:PYTHONUTF8 = "1"
    $env:CC_PORTA = "$Porta"
    Start-Process -FilePath $py -ArgumentList "server.py" -WorkingDirectory $cc `
        -RedirectStandardOutput (Join-Path $cc "lavori\server.log") `
        -RedirectStandardError (Join-Path $cc "lavori\server-err.log") `
        -WindowStyle Hidden
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        if (Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue) { break }
    }
}

# Si apre come app: Chrome (o Edge) in modalità app, massimizzata.
$browser = @(
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($browser) {
    Start-Process -FilePath $browser -ArgumentList "--app=http://127.0.0.1:$Porta/#home", "--start-maximized"
} else {
    Start-Process "http://127.0.0.1:$Porta/"
}
