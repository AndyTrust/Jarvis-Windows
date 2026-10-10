# Aggiorna Jarvis all'ultima versione senza toccare le cose tue.
#   powershell -ExecutionPolicy Bypass -File .\AGGIORNA.ps1 -Controlla     dice cosa cambierebbe, non scrive
#   powershell -ExecutionPolicy Bypass -File .\AGGIORNA.ps1                scarica il codice nuovo e lo installa
#
# Cosa cambia: il codice (app/), la grafica e la documentazione. Cosa NON si tocca mai: utente.json, CLAUDE.md,
# configurazione.json, spazi.json, pannello.json, gli agenti in .claude\agents, la memoria, la posta, i report,
# e l'assistenza a distanza (command-center\assistenza.json, assistenza-registro.json, assistenza.log).
# Quei file li crea INSTALLA.ps1 solo se mancano e stanno nel .gitignore della cartella installata.
# Prima di aggiornare fa una copia del codice attuale in %USERPROFILE%\jarvis-copia-AAAAMMGG-HHMM (per tornare indietro).
param([switch]$Controlla)
$ErrorActionPreference = 'Stop'
$qui = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $qui
if (-not (Test-Path (Join-Path $qui '.git'))) { throw 'Questa cartella non e'' un clone git: scarica Jarvis con git clone per poterlo aggiornare.' }
git fetch --quiet origin
$locale = (git rev-parse HEAD).Trim()
$remoto = (git rev-parse '@{u}').Trim()
$installata = Join-Path $env:USERPROFILE 'jarvis'
$segno = Join-Path $installata 'VERSIONE.installata'
$inst = ''
if (Test-Path $segno) { $inst = (Get-Content $segno -Raw).Trim() }
# due cose diverse: il clone (git) e la copia installata in %USERPROFILE%\jarvis. Un "git pull" a mano aggiorna solo il clone.
if ($locale -eq $remoto -and $inst -eq $locale) { Write-Host 'Jarvis e'' gia'' all''ultima versione.'; exit 0 }
if ($locale -ne $remoto) {
    Write-Host "Aggiornamento disponibile: $($locale.Substring(0,8)) -> $($remoto.Substring(0,8))"
    git diff --stat 'HEAD..@{u}'
} else {
    $vecchia = if ($inst) { $inst.Substring(0,[Math]::Min(8,$inst.Length)) } else { 'sconosciuta' }
    Write-Host "Il clone e' aggiornato ($($locale.Substring(0,8))) ma la copia installata no (versione $vecchia): la riallineo."
}
Write-Host 'Le tue impostazioni, i tuoi agenti, la memoria e i documenti: NON toccati.'
if ($Controlla) { exit 0 }
$dest = Join-Path $env:USERPROFILE ("jarvis-copia-" + (Get-Date -Format 'yyyyMMdd-HHmm'))
if (Test-Path $installata) {
    robocopy $installata $dest /E /XD .venv __pycache__ node_modules /XF *.pyc /NFL /NDL /NJH /NJS | Out-Null
    Write-Host "Copia del codice attuale: $dest"
}
if ($locale -ne $remoto) {
    # 05/10/2026: i file su disco erano già identici a GitHub (portati a mano) ma git li vedeva «modificati» e
    # l'avanti veloce si rifiutava: in quel caso basta riallineare l'indice, nessun file cambia
    git diff --quiet '@{u}' --
    if ($LASTEXITCODE -eq 0) { git reset --quiet '@{u}' } else { git merge --ff-only '@{u}' }
    if ($LASTEXITCODE -ne 0) { Write-Host "git non ha potuto scaricare l'aggiornamento (file modificati qui o rami divergenti): mi fermo, niente e' stato installato."; exit 1 }
}
# 05/10/2026: INSTALLA.ps1 riaccende il pannello PRIMA che qui si segni la versione installata. Il pannello nuovo legge
# VERSIONE.in-corso (la versione che si sta installando) e non rimostra «Aggiornamento disponibile» per l'aggiornamento
# appena fatto. Se l'installazione fallisce il segno si toglie e l'avviso torna.
$inCorso = Join-Path $installata 'VERSIONE.in-corso'
Set-Content -Path $inCorso -Value (git rev-parse HEAD).Trim() -Encoding ascii
& (Join-Path $qui 'INSTALLA.ps1') -Silenzioso
if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
    Set-Content -Path $segno -Value (git rev-parse HEAD).Trim() -Encoding ascii
    Remove-Item $inCorso -ErrorAction SilentlyContinue
    Write-Host 'Fatto. Apri una nuova sessione di Claude Code e ricarica il pannello.'
} else {
    Remove-Item $inCorso -ErrorAction SilentlyContinue
    Write-Host "L'installazione ha dato errore ($LASTEXITCODE): la versione installata non e' stata segnata."
}
