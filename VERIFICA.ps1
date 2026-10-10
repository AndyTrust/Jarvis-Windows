# VERIFICA.ps1 — controlla che Jarvis sia installato e collegato bene. Si può lanciare quando vuoi.
#   powershell -ExecutionPolicy Bypass -File .\VERIFICA.ps1 [-Destinazione C:\percorso] [-Porta 7777]
# Esce con codice 0 se non ci sono errori (gli avvisi non contano), altrimenti con il numero di errori.
param(
    [string]$Destinazione = "",
    [int]$Porta = 7777,
    [switch]$SenzaServer
)
$ErrorActionPreference = "Continue"
if (-not $Destinazione) { $Destinazione = Join-Path $env:USERPROFILE "jarvis" }
$err = 0; $avv = 0
function OK($t) { Write-Host ("    ok   " + $t) -ForegroundColor Green }
function KO($t) { Write-Host ("    ERRORE  " + $t) -ForegroundColor Red; $script:err++ }
function AV($t) { Write-Host ("    avviso  " + $t) -ForegroundColor Yellow; $script:avv++ }
function Sez($t) { Write-Host ""; Write-Host $t -ForegroundColor Cyan }

Write-Host "Verifica di Jarvis in $Destinazione" -ForegroundColor White
$py = Join-Path $Destinazione ".venv\Scripts\python.exe"

Sez "File e ambiente"
foreach ($f in @("command-center\server.py", "command-center\missione.py", "command-center\static\index.html", "command-center\static\app.js",
        "command-center\configurazione.json", "command-center\spazi.json", "command-center\pannello.json", "utente.json", "CLAUDE.md",
        "strumenti\jarvis_orb_windows.py", "strumenti\talk_to_jarvis_windows.py", ".claude\hooks\jarvis_status.py",
        ".claude\agents\esecutore.md")) {
    if (Test-Path (Join-Path $Destinazione $f)) { OK $f } else { KO "manca $f" }
}
if (Test-Path $py) {
    $r = & $py -c "import claude_agent_sdk, faster_whisper, kokoro_onnx, sounddevice, pynput, PIL, soundfile, numpy; print('ok')" 2>&1
    if ("$r" -match "ok") { OK "librerie Python (Claude SDK, Whisper, Kokoro, audio, orb)" } else { KO "librerie Python: $r" }
} else { KO "manca l'ambiente Python ($py)" }

Sez "Segnaposto non sostituiti"
$resti = @()
Get-ChildItem $Destinazione -Recurse -File -Include *.py, *.js, *.json, *.md, *.ps1, *.html -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "\\(\.venv|missioni|missioni_archivio|copie|lavori)\\" } | ForEach-Object {
        try { if ([IO.File]::ReadAllText($_.FullName) -match "@@(JARVIS_DIR|JARVIS_DIR_WIN|HOME|HOME_WIN|UTENTE|UTENTE_SLUG|RUOLO_LAVORO|VITA_PRIVATA|PERSONALITA|USO|PORTA|DATA|NOME_ASSISTENTE|LINGUA|FUSO_ORARIO|MEMORIA_CONDIVISA|NON_TOCCARE)@@") { $resti += $_.FullName.Substring($Destinazione.Length + 1) } } catch {}
    }
if ($resti.Count -eq 0) { OK "nessun @@SEGNAPOSTO@@ rimasto nei file installati" } else { KO ("segnaposto rimasti in: " + ($resti -join ", ")) }

Sez "Memoria condivisa e stato dei progetti"
$perc = Join-Path $env:USERPROFILE ".jarvis\percorsi.json"
if (Test-Path $perc) {
    try {
        $pj = Get-Content $perc -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($pj.memoria -and (Test-Path $pj.memoria)) { OK ("memoria condivisa: " + $pj.memoria) } else { KO "la memoria condivisa di percorsi.json non esiste" }
        foreach ($c in @($pj.collegamenti)) { if ($c -and $c.stato -ne "collegata") { AV ("collegamento " + $c.locale + ": " + $c.stato) } }
    } catch { KO "percorsi.json non è leggibile" }
} else { AV "manca ~\.jarvis\percorsi.json: rilancia strumenti\collega_memoria.py --applica" }
$set = Join-Path $env:USERPROFILE ".claude\settings.json"
if ((Test-Path $set) -and ((Get-Content $set -Raw) -match "stato_progetti\.py")) { OK "gancio dello stato dei progetti (Stop, PreCompact, SessionEnd)" } else { AV "gancio stato_progetti.py non installato in ~\.claude\settings.json" }
if (Test-Path (Join-Path $env:USERPROFILE ".jarvis\installato.json")) { OK "installato.json presente (prima apertura completata)" }

Sez "Voce"
$kok = Join-Path $Destinazione "strumenti\kokoro"
foreach ($f in @("kokoro-v1.0.onnx", "voices-v1.0.bin")) {
    if (Test-Path (Join-Path $kok $f)) { OK "modello $f" } else { AV "manca il modello $f (Talk to Jarvis non parlerà: rilancia INSTALLA.ps1 senza -SenzaModelliVoce)" }
}

Sez "Command Center"
if ($SenzaServer) { AV "server non controllato (-SenzaServer)" }
else {
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$Porta/" -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { OK "il pannello risponde su http://127.0.0.1:$Porta" } else { KO "il pannello risponde $($r.StatusCode)" }
        $pagina = $r.Content
        foreach ($s in @("Chat", "Stato", "Squadra", "Missioni", "Scadenze", "Memoria", "Voce", "Lavagna")) {
            if ($pagina -match [regex]::Escape($s)) { } else { KO "nella pagina manca la scheda «$s»" }
        }
        OK "le 8 schede ci sono (Chat, Stato, Squadra, Missioni, Scadenze, Memoria, Voce, Lavagna)"
        foreach ($a in @("app.js", "app.css", "sw.js")) {
            try { $x = Invoke-WebRequest "http://127.0.0.1:$Porta/static/$a" -UseBasicParsing -TimeoutSec 5; if ($x.StatusCode -eq 200) { } } catch { KO "non si carica static/$a" }
        }
        OK "app.js, app.css e sw.js si caricano"
    } catch { KO "il pannello non risponde su porta $Porta (guarda command-center\lavori\server-err.log)" }
    $errLog = Join-Path $Destinazione "command-center\lavori\server-err.log"
    if ((Test-Path $errLog) -and ((Get-Item $errLog).Length -gt 0)) { AV ("server-err.log non è vuoto: " + ((Get-Content $errLog -Tail 3) -join " | ")) }
}

Sez "Claude Code"
$g = Get-Command claude -ErrorAction SilentlyContinue
if ($g -or (Test-Path (Join-Path $env:USERPROFILE ".local\bin\claude.exe"))) { OK "Claude Code installato" } else { AV "Claude Code non trovato" }
$sett = Join-Path $env:USERPROFILE ".claude\settings.json"
if (Test-Path $sett) {
    $t = [IO.File]::ReadAllText($sett)
    foreach ($e in @("jarvis_avvio.py", "jarvis_status.py")) { if ($t -match [regex]::Escape($e)) { OK "gancio $e in settings.json" } else { AV "gancio $e non presente in ~/.claude/settings.json" } }
} else { AV "~/.claude/settings.json non esiste" }
$hook = Join-Path $env:USERPROFILE ".claude\hooks\jarvis_avvio.py"
if ((Test-Path $hook) -and (Test-Path $py)) {
    $env:JARVIS_DIR = $Destinazione
    $env:JARVIS_AVVIO_PROVA = "1"          # la prova non scrive segni (battuta del lunedì)
    $o = & $py $hook 2>&1 | Select-Object -First 1
    Remove-Item Env:JARVIS_AVVIO_PROVA -ErrorAction SilentlyContinue
    if ("$o" -match "^# JARVIS DI") { OK "il gancio di avvio parte: $o".Substring(0, [Math]::Min(90, ("ok   il gancio di avvio parte: $o").Length)) } else { KO "il gancio di avvio non parte correttamente: $o" }
    Remove-Item Env:JARVIS_DIR -ErrorAction SilentlyContinue
}

Sez "Collegamenti e avvio automatico"
$desk = [Environment]::GetFolderPath("Desktop")
foreach ($c in @("Jarvis Command Center", "Jarvis Orb", "Talk to Jarvis")) { if (Test-Path (Join-Path $desk "$c.lnk")) { OK "collegamento $c" } else { AV "manca il collegamento «$c» sul Desktop" } }
foreach ($t in @("Jarvis Avvio", "Jarvis Battito")) { if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) { OK "attività pianificata $t" } else { AV "manca l'attività «$t»" } }

Write-Host ""
if ($err -eq 0) { Write-Host ("Verifica finita: nessun errore, $avv avvisi.") -ForegroundColor Green } else { Write-Host ("Verifica finita: $err errori, $avv avvisi.") -ForegroundColor Red }
exit $err
