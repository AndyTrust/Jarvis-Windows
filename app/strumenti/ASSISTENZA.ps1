# ASSISTENZA.ps1 - prepara l'assistenza a distanza su Windows. Lo lancia il tasto 'Attiva assistenza' del pannello.
#
#   powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\jarvis\strumenti\ASSISTENZA.ps1"
#
# Cosa fa, in ordine (si puo' rilanciare quando vuoi: quello che c'e' gia' non lo rifa):
#   1. controlla WSL (il Linux di Windows) e, se manca, lo installa con Ubuntu (chiede i permessi di
#      amministratore da solo; se Windows chiede di riavviare, lo dice e riparte al riavvio);
#   2. se Ubuntu e' installata ma non e' mai stata aperta, la prepara senza chiederti utente e password;
#   3. installa dentro Ubuntu openssh (client e server, per il collegamento sicuro), tmux e tmate (riserva).
#      Il server ssh di sistema resta SPENTO: il pannello ne avvia uno suo solo durante l'assistenza;
#   4. accende l'assistenza in command-center\assistenza.json (lo crea se manca; se c'e' aggiunge solo quello
#      che manca e non cambia i tuoi valori);
#   (prima del 4) SCHERMO CONDIVISO (2026-10-02): installa TightVNC Server (GPLv2) con winget, se manca, SENZA servizio
#      e SENZA eccezione nel firewall (Windows chiede i permessi una volta). Il pannello lo avvia solo durante
#      l'assistenza, in ascolto solo su 127.0.0.1, con una password nuova per ogni sessione, e lo ferma alla fine.
#      Serve anche ssh.exe di Windows (OpenSSH Client, incluso in Windows 10/11). Funziona su Home e Pro.
# Poi si continua nel pannello, pagina Stato: incolla il codice, spunta il consenso, 'Chiedi assistenza'.
# Nessuna porta si apre verso l'esterno su questo PC: il collegamento parte sempre da qui, in uscita.
#
#   ... -SoloControlla   controlla e basta: stampa in poche righe cosa manca (da incollare a chi ti assiste)
#   ... -SoloPrepara     come senza opzioni (lo usano il pannello e INSTALLA.ps1)
#   ... -Ferma           chiude subito una sessione di assistenza aperta (STOP)
#   ... -Stato           dice se c'e' una sessione aperta
#   ... -Distro NOME     usa questa distribuzione WSL (di partenza: Ubuntu, o quella che c'e')
# Esce con 0 se e' tutto pronto, 1 se manca qualcosa (il motivo e' scritto), 3010 se serve riavviare.
param(
    [switch]$Ferma,
    [switch]$Stato,
    [switch]$SoloControlla,
    [switch]$SoloPrepara,
    [switch]$Si,                                      # vecchia opzione: non serve piu', resta accettata
    [switch]$Elevato,
    [string]$Distro = ""
)
$ErrorActionPreference = "Continue"
$env:WSL_UTF8 = "1"                                   # wsl.exe scrive in UTF-8 invece che in UTF-16
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$Socket = "/tmp/jarvis-assistenza.sock"               # tmate: percorso DENTRO Linux, lo stesso del pannello
$Cartella = Join-Path $env:LOCALAPPDATA "jarvis-assistenza"
$FilePid = Join-Path $Cartella "custode.pid"
New-Item -ItemType Directory -Force -Path $Cartella | Out-Null
$Radice = Split-Path -Parent $PSScriptRoot            # la cartella di Jarvis (strumenti\..)
$Modulo = Join-Path $PSScriptRoot "assistenza.py"
$Pacchetti = "openssh-client openssh-server tmux tmate procps"
$Riepilogo = @()

function Titolo($t) { Write-Host ""; Write-Host $t -ForegroundColor Cyan }
function Ok($t) { Write-Host ("    ok     " + $t) -ForegroundColor Green; $script:Riepilogo += ("ok     " + $t) }
function Manca($t) { Write-Host ("    manca  " + $t) -ForegroundColor Yellow; $script:Riepilogo += ("MANCA  " + $t) }
function Info($t) { Write-Host ("           " + $t) -ForegroundColor Gray }
function Fine($codice) { Write-Host ""; exit $codice }

function MostraRiepilogo([int]$codice) {
    Write-Host ""
    Write-Host "---- RIEPILOGO (copialo e mandalo a chi ti assiste se qualcosa non va) ----" -ForegroundColor White
    Write-Host ("Assistenza Windows " + (Get-Date -Format "yyyy-MM-dd HH:mm") + " - " + [Environment]::OSVersion.VersionString)
    foreach ($r in $script:Riepilogo) { Write-Host $r }
    Write-Host "----------------------------------------------------------------------------" -ForegroundColor White
    Fine $codice
}

function EAmministratore {
    $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# il Python di Jarvis (quello del pannello), oppure quello di sistema
function PythonJarvis {
    $v = Join-Path $Radice ".venv\Scripts\python.exe"
    if (Test-Path $v) { return ,@($v) }
    if (Get-Command py.exe -ErrorAction SilentlyContinue) { return ,@("py.exe", "-3") }
    if (Get-Command python.exe -ErrorAction SilentlyContinue) { return ,@("python.exe") }
    return ,@()
}

function Modulo([string[]]$Argomenti) {
    $py = @(PythonJarvis)
    if ($py.Count -eq 0 -or -not (Test-Path $Modulo)) { return [pscustomobject]@{ Codice = 99; Testo = "Python o strumenti\assistenza.py non trovati" } }
    $env:PYTHONUTF8 = "1"
    $exe = $py[0]; $resto = @(); if ($py.Count -gt 1) { $resto = $py[1..($py.Count - 1)] }
    $out = & $exe @resto $Modulo @Argomenti 2>&1 | Out-String
    return [pscustomobject]@{ Codice = $LASTEXITCODE; Testo = $out.Trim() }
}

# wsl.exe: testo pulito (tolti i byte nulli dell'UTF-16 delle versioni vecchie) e codice di uscita
function Wsl([string[]]$Argomenti) {
    $out = & wsl.exe @Argomenti 2>&1 | Out-String
    $codice = $LASTEXITCODE
    $testo = ($out -replace "`0", "").Trim()
    return [pscustomobject]@{ Codice = $codice; Testo = $testo }
}

# come Wsl, ma con un tempo massimo (rete assente, apt bloccato): dopo $Secondi si ferma e lo dice
function WslTempo([int]$Secondi, [string[]]$Argomenti) {
    $job = Start-Job -ScriptBlock {
        param($a)
        $env:WSL_UTF8 = "1"
        $o = & wsl.exe @a 2>&1 | Out-String
        [pscustomobject]@{ Codice = $LASTEXITCODE; Testo = ($o -replace "`0", "").Trim() }
    } -ArgumentList (,$Argomenti)
    if (Wait-Job $job -Timeout $Secondi) {
        $r = Receive-Job $job
        Remove-Job $job -Force
        return $r
    }
    Stop-Job $job; Remove-Job $job -Force
    return [pscustomobject]@{ Codice = 124; Testo = "tempo scaduto dopo $Secondi secondi" }
}

function DistroInstallate {
    $r = Wsl @("-l", "-q")
    if ($r.Codice -ne 0) { return @() }
    # solo i nomi veri (niente spazi: le frasi di errore di WSL non sono distribuzioni), senza quelle interne di Docker
    return @($r.Testo -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -match "^[A-Za-z0-9._-]+$" -and $_ -notlike "docker-desktop*" })
}

function ScegliDistro($elenco) {
    if ($Distro -and ($elenco -contains $Distro)) { return $Distro }
    if ($Distro) { return "" }
    $u = $elenco | Where-Object { $_ -like "Ubuntu*" } | Select-Object -First 1
    if ($u) { return $u }
    return ($elenco | Select-Object -First 1)
}

function ServeRiavvio([string]$testo, [int]$codice) {
    return ($codice -eq 3010) -or ($testo -match "riavvi|reboot|restart|3010")
}

function ProgrammaRipresa {
    # al prossimo accesso a Windows il comando riparte da solo (una volta)
    try {
        $riga = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -File "' + $PSCommandPath + '" -SoloPrepara'
        New-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce" -Force | Out-Null
        New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce" -Name "JarvisAssistenza" -Value $riga -PropertyType String -Force | Out-Null
        Info "Al prossimo accesso a Windows questo comando riparte da solo."
    } catch { Info "Dopo il riavvio premi di nuovo 'Attiva assistenza' nel pannello." }
}

function RilanciaComeAmministratore {
    Info "Servono i permessi di amministratore: Windows te li chiede adesso (rispondi Si)."
    $a = "-NoProfile -ExecutionPolicy Bypass -NoExit -File `"$PSCommandPath`" -Elevato -SoloPrepara"
    if ($Distro) { $a += " -Distro `"$Distro`"" }
    try {
        Start-Process powershell.exe -Verb RunAs -ArgumentList $a
        Write-Host ""
        Write-Host "Ho aperto una finestra come amministratore: continua li'." -ForegroundColor Yellow
        Fine 0
    } catch {
        Write-Host "Non ho i permessi di amministratore. Apri PowerShell con il tasto destro > Esegui come amministratore e rilancia il comando." -ForegroundColor Red
        Fine 1
    }
}

function MessaggioErroreWsl([string]$testo) {
    if ($testo -match "0x80370102|virtualiz|virtualizz") {
        return "La virtualizzazione e' spenta nel BIOS del PC: va accesa (voce 'Virtualization' / 'SVM' / 'Intel VT-x') e poi si rilancia il comando."
    }
    if ($testo -match "0x8007019e|0x80070003") {
        return "WSL non e' abilitato in Windows: il comando lo abilita da amministratore."
    }
    return ""
}

function FermaCustode {
    if (Test-Path $FilePid) {
        try {
            $pidVecchio = [int](Get-Content $FilePid -Raw)
            Stop-Process -Id $pidVecchio -Force -ErrorAction SilentlyContinue
        } catch { }
        Remove-Item $FilePid -Force -ErrorAction SilentlyContinue
    }
}

function TrovaVnc {
    foreach ($r in @($env:ProgramFiles, $env:ProgramW6432, ${env:ProgramFiles(x86)})) {
        if ($r -and (Test-Path (Join-Path $r "TightVNC\tvnserver.exe"))) { return (Join-Path $r "TightVNC\tvnserver.exe") }
    }
    return $null
}

# ------------------------------------------------------------------ STOP e STATO (non installano niente)
if ($Ferma -or $Stato) {
    if ($Ferma) {
        # prima la via del pannello: chiude la sessione nel registro e ferma i processi dentro Linux, controllando
        $m = Modulo @("stop")
        $elenco = DistroInstallate
        $d = ScegliDistro $elenco
        if ($d) {
            # resti di tmate (vecchie sessioni) e, se il pannello non ha potuto, i processi del tunnel
            [void](Wsl @("-d", $d, "-u", "root", "-e", "tmate", "-S", $Socket, "kill-server"))
            [void](Wsl @("-d", $d, "-u", "root", "-e", "pkill", "-f", "jarvis-assistenza-cliente/sessione/(sshd_config|cliente)"))
            [void](Wsl @("-d", $d, "-e", "tmux", "-L", "jarvis-assistenza", "kill-server"))
        }
        # schermo condiviso: se il pannello non ha potuto, TightVNC si chiude e la password di sessione si toglie
        $vncF = TrovaVnc
        if ($vncF -and (Get-Process -Name tvnserver -ErrorAction SilentlyContinue)) { & $vncF -controlapp -shutdown 2>$null | Out-Null }
        Remove-ItemProperty -Path "HKCU:\Software\TightVNC\Server" -Name Password -ErrorAction SilentlyContinue
        FermaCustode
        Write-Host "Assistenza chiusa: il tecnico non puo' piu' entrare." -ForegroundColor Green
        Fine 0
    }
    $m = Modulo @("stato")
    try { $s = $m.Testo | ConvertFrom-Json } catch { $s = $null }
    if (-not $s) { Write-Host ("Non riesco a leggere lo stato: " + $m.Testo) -ForegroundColor Yellow; Fine 1 }
    if (-not $s.abilitata) { Write-Host "Assistenza spenta: premi 'Attiva assistenza' nel pannello." -ForegroundColor Yellow; Fine 0 }
    if ($s.attiva) {
        $riga = if ($s.attiva.richiesta) { $s.attiva.richiesta } else { $s.attiva.ssh }
        Write-Host ("Sessione APERTA dalle " + $s.attiva.ora_inizio + " (" + $s.attiva.modo + "). Da mandare al tecnico:") -ForegroundColor Green
        Write-Host ""; Write-Host ("    " + $riga) -ForegroundColor White
        try { Set-Clipboard -Value $riga; Info "Copiata negli appunti." } catch { }
    } else { Write-Host ("Nessuna sessione aperta. Credito: " + $s.credito_min + " minuti.") -ForegroundColor Yellow }
    Fine 0
}

# ------------------------------------------------------------------ 1. WSL
Titolo "[1] WSL (il Linux di Windows)"
$haWslExe = [bool](Get-Command wsl.exe -ErrorAction SilentlyContinue)
$ws = $null
if ($haWslExe) { $ws = Wsl @("--status") }
$wslPronto = $haWslExe -and $ws -and $ws.Codice -eq 0 -and -not ($ws.Testo -match "--install|non .* installato|not installed")
if ($wslPronto) {
    Ok "WSL risponde"
} else {
    Manca "WSL non e' installato (o non risponde)"
    if ($ws -and $ws.Testo) { Info ($ws.Testo.Split("`n")[0]) }
    if ($SoloControlla) { MostraRiepilogo 1 }
    if (-not (EAmministratore)) { RilanciaComeAmministratore }
    Info "Installo WSL con Ubuntu: wsl --install -d Ubuntu --no-launch (puo' volerci qualche minuto e internet)"
    $inst = WslTempo 1500 @("--install", "-d", "Ubuntu", "--no-launch")
    if ($inst.Testo) { Info ($inst.Testo -replace "`r?`n", "`n           ") }
    if (ServeRiavvio $inst.Testo $inst.Codice) {
        Write-Host ""
        Write-Host "  SERVE RIAVVIARE IL PC per finire l'installazione di WSL." -ForegroundColor Yellow
        ProgrammaRipresa
        Write-Host "  Salva il lavoro, riavvia Windows: al ritorno questo comando riparte da solo." -ForegroundColor Yellow
        Fine 3010
    }
    $m = MessaggioErroreWsl $inst.Testo
    if ($m) { Write-Host ("  " + $m) -ForegroundColor Red; Fine 1 }
    $ws = Wsl @("--status")
    if ($ws.Codice -ne 0) {
        Write-Host "  WSL non risponde ancora. Riavvia il PC: al ritorno il comando riparte da solo." -ForegroundColor Yellow
        ProgrammaRipresa
        Fine 3010
    }
    Ok "WSL installato"
}

# ------------------------------------------------------------------ 2. Ubuntu
Titolo "[2] Ubuntu dentro WSL"
$elenco = DistroInstallate
$d = ScegliDistro $elenco
if (-not $d) {
    if ($Distro -and $elenco.Count -gt 0) {
        Manca ("la distribuzione '" + $Distro + "' (ci sono: " + ($elenco -join ", ") + ")")
        MostraRiepilogo 1
    }
    Manca "nessuna distribuzione Linux registrata in WSL"
    if ($SoloControlla) { MostraRiepilogo 1 }
    # Ubuntu puo' essere gia' scaricata ma mai aperta (non registrata): la si prepara SENZA chiedere utente e password
    $lanciatore = Get-Command "ubuntu*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $lanciatore) {
        Info "Scarico Ubuntu: wsl --install -d Ubuntu --no-launch"
        $inst = WslTempo 1200 @("--install", "-d", "Ubuntu", "--no-launch")
        if ($inst.Testo) { Info ($inst.Testo -replace "`r?`n", "`n           ") }
        if (ServeRiavvio $inst.Testo $inst.Codice) {
            Write-Host "  SERVE RIAVVIARE IL PC." -ForegroundColor Yellow; ProgrammaRipresa; Fine 3010
        }
        $m = MessaggioErroreWsl $inst.Testo
        if ($m) { Write-Host ("  " + $m) -ForegroundColor Red; Fine 1 }
        $lanciatore = Get-Command "ubuntu*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if ($lanciatore) {
        Info ("Preparo Ubuntu (senza utente e senza password): " + $lanciatore.Name + " install --root")
        $p = Start-Process -FilePath $lanciatore.Source -ArgumentList @("install", "--root") -PassThru -WindowStyle Hidden
        if (-not $p.WaitForExit(900000)) { try { $p.Kill() } catch { }; Write-Host "  Ubuntu non ha finito in 15 minuti: rilancia il comando." -ForegroundColor Red; Fine 1 }
    }
    $elenco = DistroInstallate
    $d = ScegliDistro $elenco
    if (-not $d) {
        Write-Host "  Ubuntu non risulta ancora registrata. Apri 'Ubuntu' dal menu Start una volta, crea utente e password, poi premi di nuovo 'Attiva assistenza'." -ForegroundColor Yellow
        Fine 1
    }
}
# la distribuzione si avvia davvero?
$prova = Wsl @("-d", $d, "-u", "root", "-e", "echo", "pronta")
if ($prova.Codice -ne 0 -or $prova.Testo -notmatch "pronta") {
    $m = MessaggioErroreWsl $prova.Testo
    if ($m) { Manca $m } else {
        Manca ("la distribuzione '" + $d + "' non parte")
        Info ($prova.Testo.Split("`n")[0])
        Info "Prova: wsl --update (da amministratore), poi riavvia il PC e premi di nuovo 'Attiva assistenza'."
    }
    MostraRiepilogo 1
}
Ok ("distribuzione pronta: " + $d)

# ------------------------------------------------------------------ 3. programmi dentro Ubuntu
Titolo "[3] Programmi dentro Ubuntu (openssh, tmux, tmate)"
function Mancanti {
    $r = Wsl @("-d", $d, "-u", "root", "-e", "sh", "-c", "for p in ssh ssh-keygen /usr/sbin/sshd tmux tmate ps; do command -v `$p >/dev/null 2>&1 || echo `$p; done")
    return @($r.Testo -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}
$mancano = Mancanti
if ($mancano.Count -gt 0 -and -not $SoloControlla) {
    Info ("Installo (tocca solo il Linux dentro WSL, non Windows): apt-get install " + $Pacchetti)
    # policy-rc.d: durante l'installazione il server ssh di sistema non parte. Dopo resta spento e bloccato:
    # il pannello avvia un suo sshd solo su 127.0.0.1 e solo durante l'assistenza.
    $sh = "printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && chmod +x /usr/sbin/policy-rc.d; " +
          "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $Pacchetti; rc=`$?; " +
          "rm -f /usr/sbin/policy-rc.d; exit `$rc"
    $i = WslTempo 900 @("-d", $d, "-u", "root", "-e", "sh", "-c", $sh)
    $mancano = Mancanti
    if ($mancano.Count -gt 0 -and $i.Testo) { Info (($i.Testo.Split("`n") | Select-Object -Last 3) -join " | ") }
}
# il server ssh di sistema: sempre spento e bloccato (anche se c'era gia')
if (-not $SoloControlla) { [void](Wsl @("-d", $d, "-u", "root", "-e", "sh", "-c", "[ -d /etc/ssh ] && touch /etc/ssh/sshd_not_to_be_run; command -v systemctl >/dev/null 2>&1 && { systemctl disable ssh.service ssh.socket; systemctl stop ssh.service ssh.socket; systemctl mask ssh.service ssh.socket; } >/dev/null 2>&1; true")) }
$openssh = -not ($mancano | Where-Object { $_ -in @("ssh", "ssh-keygen", "/usr/sbin/sshd", "ps") })
if ($openssh) { Ok "openssh dentro Ubuntu (collegamento sicuro verso il tecnico)" } else { Manca ("openssh dentro Ubuntu: " + (($mancano | Where-Object { $_ -ne "tmate" -and $_ -ne "tmux" }) -join ", ")) }
if ($mancano -contains "tmate") { Manca "tmate (la riserva)" } else { Ok "tmate (la riserva)" }
if ($mancano -contains "tmux") { Info "tmux manca: il tecnico lavora lo stesso, ma non potrai guardare la sua sessione" }

# ------------------------------------------------------------------ 5. schermo condiviso (TightVNC + ssh.exe di Windows)
function SezioneSchermo {
    Titolo "[4] Schermo condiviso (il tecnico vede e usa lo schermo, solo durante l'assistenza)"
    $vnc = TrovaVnc
    if (-not $vnc -and -not $SoloControlla) {
        if (Get-Command winget.exe -ErrorAction SilentlyContinue) {
            Info "Installo TightVNC Server con winget (senza servizio e senza aprire il firewall). Windows chiede i permessi: rispondi Si."
            $opz = "/quiet /norestart ADDLOCAL=Server SERVER_REGISTER_AS_SERVICE=0 SERVER_ADD_FIREWALL_EXCEPTION=0 SERVER_ALLOW_SAS=0 " +
                   "SET_ACCEPTRFBCONNECTIONS=1 VALUE_OF_ACCEPTRFBCONNECTIONS=0 SET_LOOPBACKONLY=1 VALUE_OF_LOOPBACKONLY=1 " +
                   "SET_ALLOWLOOPBACK=1 VALUE_OF_ALLOWLOOPBACK=1 SET_ACCEPTHTTPCONNECTIONS=1 VALUE_OF_ACCEPTHTTPCONNECTIONS=0"
            & winget.exe install --id GlavSoft.TightVNC --exact --silent --accept-package-agreements --accept-source-agreements --override $opz 2>&1 |
                Select-Object -Last 3 | ForEach-Object { Info ([string]$_) }
            $vnc = TrovaVnc
        } else { Info "winget non c'e' (App Installer di Microsoft Store): TightVNC va installato a mano da tightvnc.com, solo la parte Server." }
    }
    if ($vnc) { Ok ("TightVNC Server installato: " + $vnc) } else { Manca "TightVNC Server (per lo schermo condiviso; il terminale funziona lo stesso)" }
    $sshWin = Join-Path $env:SystemRoot "System32\OpenSSH\ssh.exe"
    if (Test-Path $sshWin) { Ok "ssh di Windows (OpenSSH Client)" }
    else { Manca "ssh di Windows (Impostazioni > App > Funzionalita' facoltative > Client OpenSSH)" }
    # un TightVNC registrato come SERVIZIO ascolterebbe sempre: non deve esserci
    $serv = Get-Service -Name tvnserver -ErrorAction SilentlyContinue
    if ($serv) {
        if ($serv.Status -eq "Running" -and -not $SoloControlla -and (EAmministratore)) {
            Stop-Service tvnserver -Force -ErrorAction SilentlyContinue; Set-Service tvnserver -StartupType Disabled -ErrorAction SilentlyContinue
            Info "Il servizio TightVNC era acceso: fermato e disattivato (il pannello usa solo il modo applicazione)."
        }
        $serv = Get-Service -Name tvnserver -ErrorAction SilentlyContinue
        if ($serv.Status -eq "Running") { Manca "servizio TightVNC acceso: va fermato (da amministratore: Stop-Service tvnserver; Set-Service tvnserver -StartupType Disabled)" }
        else { Ok "servizio TightVNC spento (si usa solo durante l'assistenza)" }
    }
    # in ascolto adesso? Fuori da una sessione e' normale che non lo sia; se lo e', solo su 127.0.0.1
    $proc = @(Get-Process -Name tvnserver -ErrorAction SilentlyContinue)
    if ($proc.Count -eq 0) { Info "TightVNC non e' in ascolto adesso (normale: parte solo durante l'assistenza)" }
    else {
        $asc = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $proc.Id -contains $_.OwningProcess })
        $fuori = @($asc | Where-Object { $_.LocalAddress -notin @("127.0.0.1", "::1") })
        if ($fuori.Count -gt 0) { Manca ("TightVNC ascolta anche fuori da questo PC (" + (($fuori | ForEach-Object { $_.LocalAddress + ":" + $_.LocalPort }) -join ", ") + "): premi STOP o chiudilo dall'icona") }
        elseif ($asc.Count -gt 0) { Ok ("TightVNC in ascolto solo su 127.0.0.1 (porta " + (($asc | ForEach-Object { $_.LocalPort }) -join ", ") + ")") }
        else { Info "TightVNC acceso ma senza porte in ascolto" }
    }
}
SezioneSchermo

# ------------------------------------------------------------------ 4. assistenza.json e controllo del pannello
Titolo "[5] Assistenza nel pannello"
if (-not $SoloControlla) {
    $a = Modulo @("attiva", "--distro", $d)
    if ($a.Codice -eq 0) { Ok "assistenza accesa in command-center\assistenza.json" } else { Manca ("assistenza.json: " + $a.Testo) }
}
$conf = Join-Path $Radice "command-center\assistenza.json"
$tunnel = $null
if (Test-Path $conf) {
    try {
        $c = Get-Content $conf -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($c.abilitata -eq $true) { Ok "assistenza.json: abilitata" } else { Manca "assistenza.json: spenta (premi 'Attiva assistenza')" }
        if ($c.tunnel -and $c.tunnel.host) { $tunnel = $c.tunnel; Ok ("assistenza.json: collegamento verso " + $c.tunnel.host + ":" + $c.tunnel.porta) } else { Manca "assistenza.json: manca la sezione tunnel" }
    } catch { Manca "assistenza.json non e' leggibile" }
} else { Manca "assistenza.json (premi 'Attiva assistenza')" }
if ($tunnel) {
    try {
        $t = New-Object Net.Sockets.TcpClient
        $iar = $t.BeginConnect([string]$tunnel.host, [int]$tunnel.porta, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne(5000) -and $t.Connected) { Ok "il server del tecnico si raggiunge (porta aperta in uscita)" }
        else { Manca "il server del tecnico non si raggiunge: rete o firewall aziendale" }
        $t.Close()
    } catch { Manca "il server del tecnico non si raggiunge: rete o firewall aziendale" }
}
$m = Modulo @("manca")
if ($m.Codice -eq 0) { Ok "il pannello dice: pronto" }
elseif ($m.Codice -eq 99) { Info $m.Testo }
else { Manca ("il pannello dice: " + (($m.Testo -split "`r?`n") -join "; ")) }

$tuttoOk = -not ($Riepilogo | Where-Object { $_ -like "MANCA*" })
if ($tuttoOk) {
    Write-Host ""
    Write-Host "PRONTO. Ora nel pannello (pagina Stato): incolla il codice, spunta il consenso, 'Chiedi assistenza'." -ForegroundColor Green
    if ($SoloControlla) { MostraRiepilogo 0 }
    Fine 0
}
MostraRiepilogo 1
