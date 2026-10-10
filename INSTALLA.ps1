# INSTALLA.ps1 — installa Jarvis per Windows su questo PC, da zero e senza configurazioni a mano.
#
#   powershell -ExecutionPolicy Bypass -File .\INSTALLA.ps1
#
# Fa tutto da solo e si può rilanciare quando vuoi (aggiorna il codice, NON tocca i tuoi file personali):
#   prerequisiti (Python, eSpeak NG) -> copia di Jarvis -> ambiente Python e librerie -> voce (Kokoro) ->
#   file personali dai modelli (solo se mancano) -> collegamento a Claude Code -> collegamenti sul Desktop ->
#   avvio automatico -> (con -ConAssistenza: WSL, openssh e tmate per l'assistenza a distanza) -> avvio e verifica.
# Le uniche cose "tue" sono i file personali che crea da modelli: configurazione.json, spazi.json, pannello.json,
# utente.json, CLAUDE.md, gli agenti e la memoria iniziale con il tuo profilo. Cambiali quando vuoi.
# Ti fa poche domande (nome, lavoro, vita privata, personalità, come vuoi usare Jarvis): tutte facoltative,
# invio = valore predefinito. Con -Silenzioso non chiede niente; le risposte si possono dare con i parametri.
# Con -DaRisposte (2026-10-10) legge le risposte che Claude Code ha raccolto con le DOMANDE DI AVVIO
# (%USERPROFILE%\.jarvis\risposte-avvio.json, vedi CLAUDE.md e modelli-personali\risposte-avvio.esempio.json)
# e non chiede niente. Alla fine scrive %USERPROFILE%\.jarvis\installato.json.
param(
    [string]$NomeUtente = "",                       # come Jarvis ti chiama (se vuoto te lo chiede)
    [string]$Ruolo = "",                            # che lavoro fai / di cosa ti occupi
    [string]$VitaPrivata = "",                      # interessi, famiglia, cose private da seguire
    [string]$Personalita = "",                      # il tono di Jarvis (es. "diretto e sintetico", "caldo e ironico")
    [string]$Uso = "",                              # per cosa vuoi usare Jarvis (lavoro, vita privata, entrambi...)
    [string]$Destinazione = "",                     # dove installare (predefinito: %USERPROFILE%\jarvis)
    [int]$Porta = 7777,
    [switch]$Silenzioso,                            # niente domande: usa i predefiniti
    [switch]$SenzaModelliVoce,                      # non scarica la voce Kokoro (~350 MB)
    [switch]$SenzaClaudeConfig,                     # non tocca ~/.claude
    [switch]$SenzaCollegamenti,                     # niente collegamenti sul Desktop
    [switch]$SenzaCompiti,                          # niente attività pianificate
    [switch]$SenzaAvvio,                            # non avvia il pannello alla fine
    [switch]$SenzaPrerequisiti,                     # non installa nulla con winget (solo controlla)
    [switch]$RifaiFilePersonali,                    # riscrive anche i file personali dai modelli (perde le tue modifiche!)
    [switch]$ConAssistenza,                         # prepara e accende l'assistenza a distanza: WSL, openssh e tmate dentro WSL
    [switch]$DaRisposte,                            # legge %USERPROFILE%\.jarvis\risposte-avvio.json e non chiede niente
    [string]$FileRisposte = "",                     # un altro file di risposte (di base quello sopra)
    [string]$NomeAssistente = "",                   # come si chiama l'assistente (di base Jarvis)
    [string]$Memoria = "",                          # la memoria condivisa (di base %USERPROFILE%\Jarvis-Memoria)
    [string]$Lingua = "",                           # lingua delle risposte (di base italiano)
    [string]$FusoOrario = "",                       # es. Europe/Rome (di base quello di Windows)
    [string]$NonToccare = "",                       # cartelle o cose che l'assistente non deve mai toccare
    [string]$PrimoProgetto = ""                     # facoltativo: il primo progetto da creare subito (si parte da zero)
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Radice = $PSScriptRoot
$utf8 = New-Object System.Text.UTF8Encoding($false)
$utf8bom = New-Object System.Text.UTF8Encoding($true)
$Avvisi = New-Object System.Collections.ArrayList
$Log = Join-Path $Radice "installazione.log"

function Scrivi($t, $colore = "Gray") { Write-Host $t -ForegroundColor $colore; Add-Content -Path $Log -Value ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $t) -Encoding UTF8 }
function Passo($n, $t) { Scrivi ""; Scrivi ("[$n] $t") "Cyan" }
function Ok($t) { Scrivi ("    ok  " + $t) "Green" }
function Avviso($t) { Scrivi ("    !!  " + $t) "Yellow"; [void]$Avvisi.Add($t) }
function Leggi([string]$p) { return [IO.File]::ReadAllText($p, [Text.Encoding]::UTF8) }
function Salva([string]$p, [string]$t) {
    $dir = Split-Path -Parent $p
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $enc = $utf8
    if ($p -like "*.ps1") { $enc = $utf8bom }        # PowerShell 5.1 vuole il BOM per le lettere accentate
    [IO.File]::WriteAllText($p, $t, $enc)
}

Set-Content -Path $Log -Value ("Installazione di Jarvis per Windows - {0}" -f (Get-Date)) -Encoding UTF8
Scrivi "==============================================================" "White"
Scrivi "  JARVIS PER WINDOWS - installazione" "White"
Scrivi "==============================================================" "White"

try {
    # ------------------------------------------------------------------ 0. controlli di base
    Passo 0 "Controlli di base"
    if ($env:OS -ne "Windows_NT") { throw "Questo installatore è per Windows." }
    if ($PSVersionTable.PSVersion.Major -lt 5) { throw "Serve PowerShell 5 o più recente." }
    Ok ("Windows, PowerShell " + $PSVersionTable.PSVersion)
    if (-not (Test-Path (Join-Path $Radice "app\command-center\server.py"))) { throw "Non trovo app\command-center\server.py: lancia INSTALLA.ps1 dalla cartella del repository." }

    # risposte delle DOMANDE DI AVVIO (raccolte da Claude Code in modalità piano, approvate dall'utente)
    $Spazi = @(); $Harness = @()
    if ($DaRisposte -or $FileRisposte) {
        if (-not $FileRisposte) { $FileRisposte = Join-Path $env:USERPROFILE ".jarvis\risposte-avvio.json" }
        if (-not (Test-Path $FileRisposte)) { throw "Non trovo $FileRisposte. Apri Claude Code nella cartella del repository e scrivi /inizia: le domande di avvio lo creano." }
        $grezzo = [IO.File]::ReadAllText($FileRisposte, [Text.Encoding]::UTF8)
        # niente segreti nelle risposte: password, token e chiavi si mettono dopo in %USERPROFILE%\.env.jarvis
        if ($grezzo -match '(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_|xox[baprs]-|AIza[0-9A-Za-z_-]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|"(password|token|api_?key|secret)"\s*:\s*"[^"]+")') {
            throw "Nel file delle risposte c'è qualcosa che sembra un segreto (password, token o chiave). Toglilo: i segreti vanno solo in %USERPROFILE%\.env.jarvis."
        }
        $R = $grezzo | ConvertFrom-Json
        function DaR($valore, $campo) { if ($valore) { return $valore }; if ($campo) { return ([string]$campo).Trim() }; return "" }
        $NomeUtente     = DaR $NomeUtente $R.utente.nome
        $NomeAssistente = DaR $NomeAssistente $R.assistente.nome
        $Ruolo          = DaR $Ruolo $R.lavoro.ruolo
        $Uso            = DaR $Uso $R.lavoro.uso
        $VitaPrivata    = DaR $VitaPrivata $R.vita_privata
        $Personalita    = DaR $Personalita $R.tono
        $Lingua         = DaR $Lingua $R.lingua
        $FusoOrario     = DaR $FusoOrario $R.fuso_orario
        $Memoria        = DaR $Memoria $R.memoria.cartella
        $Destinazione   = DaR $Destinazione $R.installazione.cartella
        if ($R.installazione.porta) { $Porta = [int]$R.installazione.porta }
        if ($R.voce -and ($R.voce.attiva -eq $false)) { $SenzaModelliVoce = [switch]$true }
        if (-not $NonToccare -and $R.non_toccare) { $NonToccare = (@($R.non_toccare) | Where-Object { $_ }) -join "; " }
        # si parte da zero (2026-10-10): niente elenco di spazi, al massimo il primo progetto da creare subito
        if (-not $PrimoProgetto -and $R.primo_progetto -and $R.primo_progetto.nome) { $PrimoProgetto = ([string]$R.primo_progetto.nome).Trim() }
        if ($R.harness) { $Harness = @($R.harness | Where-Object { $_ }) }
        $Silenzioso = [switch]$true
        Ok "Risposte di avvio lette da $FileRisposte"
    }
    if ($Destinazione) { $Destinazione = [Environment]::ExpandEnvironmentVariables($Destinazione) }
    if ($Memoria) { $Memoria = [Environment]::ExpandEnvironmentVariables($Memoria) }
    # rilanciando (AGGIORNA.ps1 usa -Silenzioso) memoria e nome dell'assistente restano quelli scelti la prima volta
    if (-not $Memoria) {
        $pjf = Join-Path $env:USERPROFILE ".jarvis\percorsi.json"
        if (Test-Path $pjf) { try { $m0 = [string]((Get-Content $pjf -Raw -Encoding UTF8 | ConvertFrom-Json).memoria); if ($m0.Trim()) { $Memoria = $m0.Trim() } } catch {} }
    }
    if (-not $NomeAssistente) {
        $dest0 = $Destinazione; if (-not $dest0) { $dest0 = Join-Path $env:USERPROFILE "jarvis" }
        $uj0 = Join-Path $dest0 "utente.json"
        if (Test-Path $uj0) { try { $a0 = [string]((Get-Content $uj0 -Raw -Encoding UTF8 | ConvertFrom-Json).nome_assistente); if ($a0.Trim()) { $NomeAssistente = $a0.Trim() } } catch {} }
    }
    if (-not $NomeAssistente) { $NomeAssistente = "Jarvis" }
    if (-not $Lingua) { $Lingua = "italiano" }
    if (-not $FusoOrario) { $FusoOrario = [TimeZoneInfo]::Local.Id }
    if (-not $Memoria) { $Memoria = Join-Path $env:USERPROFILE "Jarvis-Memoria" }
    if (-not $NonToccare) { $NonToccare = "nessuna indicazione: chiedi prima di toccare cartelle fuori dai progetti" }
    if (-not $Destinazione) { $Destinazione = Join-Path $env:USERPROFILE "jarvis" }
    $Destinazione = [IO.Path]::GetFullPath($Destinazione)
    Ok "Cartella di installazione: $Destinazione"

    # nomi personali
    # rilanciando (aggiornamento) il nome e' quello gia' salvato in utente.json, non quello dell'account Windows
    if (-not $NomeUtente) {
        $ujEsistente = Join-Path $Destinazione "utente.json"
        if (Test-Path $ujEsistente) {
            try { $n0 = [string]((Get-Content $ujEsistente -Raw -Encoding UTF8 | ConvertFrom-Json).nome); if ($n0.Trim()) { $NomeUtente = $n0.Trim() } } catch {}
        }
    }
    if (-not $NomeUtente) {
        $predef = (Get-Culture).TextInfo.ToTitleCase(($env:USERNAME -split "[ ._-]")[0].ToLower())
        if ($Silenzioso) { $NomeUtente = $predef }
        else {
            $r = Read-Host "Come ti deve chiamare Jarvis? (invio = $predef)"
            if ($r.Trim()) { $NomeUtente = $r.Trim() } else { $NomeUtente = $predef }
        }
    }
    # il profilo: tutto facoltativo, invio = valore predefinito (si cambia dopo in utente.json e CLAUDE.md)
    function Chiedi([string]$valore, [string]$domanda, [string]$predefinito) {
        if ($valore) { return $valore.Trim() }
        if ($Silenzioso) { return $predefinito }
        $r = Read-Host $domanda
        if ($r -and $r.Trim()) { return $r.Trim() }
        return $predefinito
    }
    $Ruolo = Chiedi $Ruolo "Che lavoro fai, di cosa ti occupi? (invio = lo dirai a Jarvis strada facendo)" "non ancora specificato: chiedilo con naturalezza quando serve"
    $VitaPrivata = Chiedi $VitaPrivata "Nella vita privata cosa vuoi che Jarvis segua? Interessi, famiglia, casa... (invio = niente per ora)" "non ancora specificata: chiedila con discrezione quando serve"
    $Personalita = Chiedi $Personalita "Che tono vuoi da Jarvis? Es. diretto e sintetico, caldo e ironico, formale (invio = cordiale e diretto)" "cordiale, diretto e sintetico, con un filo di ironia"
    $Uso = Chiedi $Uso "Per cosa vuoi usarlo? Lavoro, vita privata, entrambi, con quali priorità (invio = entrambi)" "sia il lavoro sia la vita privata, con la stessa attenzione"
    # lo "slug" serve per i nomi di cartella: minuscolo, senza accenti, solo lettere, numeri e trattini
    $norm = $NomeUtente.Normalize([Text.NormalizationForm]::FormD)
    $sb = New-Object Text.StringBuilder
    foreach ($ch in $norm.ToCharArray()) { if ([Globalization.CharUnicodeInfo]::GetUnicodeCategory($ch) -ne "NonSpacingMark") { [void]$sb.Append($ch) } }
    $Slug = ($sb.ToString().ToLower() -replace "[^a-z0-9]+", "-").Trim("-")
    if (-not $Slug) { $Slug = "utente" }
    Ok "Utente: $NomeUtente  (cartella memoria: memoria-$Slug)"

    # ------------------------------------------------------------------ 1. prerequisiti
    Passo 1 "Prerequisiti"
    function Trova-Python {
        $c = @()
        foreach ($n in @("python", "python3")) { $g = Get-Command $n -ErrorAction SilentlyContinue; if ($g) { $c += $g.Source } }
        $c += @(Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:LOCALAPPDATA\Python\pythoncore-*\python.exe", "C:\Program Files\Python3*\python.exe" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
        foreach ($p in $c) {
            if ($p -like "*\WindowsApps\*") { continue }      # il segnaposto del Microsoft Store non è un Python vero
            try {
                $v = & $p -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
                if ($LASTEXITCODE -eq 0 -and [version]$v -ge [version]"3.10") { return $p }
            } catch {}
        }
        return $null
    }
    $PyBase = Trova-Python
    if (-not $PyBase -and -not $SenzaPrerequisiti) {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Scrivi "    Python 3.10 o più non trovato: lo installo con winget (Python 3.12)..."
            winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements | Out-Null
            $PyBase = Trova-Python
        }
    }
    if (-not $PyBase) { throw "Non trovo Python 3.10 o più recente. Installalo da https://www.python.org/downloads/ (spunta 'Add to PATH') e rilancia." }
    Ok ("Python: " + (& $PyBase --version) + "  ($PyBase)")

    if (-not (Test-Path "C:\Program Files\eSpeak NG\espeak-ng.exe")) {
        if (-not $SenzaPrerequisiti -and (Get-Command winget -ErrorAction SilentlyContinue)) {
            Scrivi "    eSpeak NG (serve alla voce italiana) non trovato: lo installo con winget..."
            try { winget install -e --id eSpeak-NG.eSpeak-NG --silent --accept-package-agreements --accept-source-agreements | Out-Null } catch {}
        }
        if (Test-Path "C:\Program Files\eSpeak NG\espeak-ng.exe") { Ok "eSpeak NG installato" }
        else { Avviso "eSpeak NG non installato: la voce potrebbe usare la copia inclusa nelle librerie Python; se non parla, installa eSpeak NG." }
    } else { Ok "eSpeak NG presente" }

    $claudeExe = $null
    $g = Get-Command claude -ErrorAction SilentlyContinue
    if ($g) { $claudeExe = $g.Source } elseif (Test-Path (Join-Path $env:USERPROFILE ".local\bin\claude.exe")) { $claudeExe = Join-Path $env:USERPROFILE ".local\bin\claude.exe" }
    if ($claudeExe) { Ok "Claude Code: $claudeExe" }
    else { Avviso "Claude Code non trovato. Installalo (https://claude.com/claude-code) e fai il login con 'claude': senza, chat, missioni e agenti non rispondono." }

    $browser = @("$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe", "C:\Program Files\Google\Chrome\Application\chrome.exe", "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "C:\Program Files\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($browser) { Ok "Browser per l'app: $browser" } else { Avviso "Né Chrome né Edge trovati: il pannello si aprirà nel browser predefinito (http://127.0.0.1:$Porta)." }

    # ------------------------------------------------------------------ 2. copia dei file
    Passo 2 "Copia di Jarvis in $Destinazione"
    New-Item -ItemType Directory -Force -Path $Destinazione | Out-Null
    $Fwd = $Destinazione.Replace("\", "/")
    $Home_ = $env:USERPROFILE
    $tok = [ordered]@{
        JARVIS_DIR     = $Fwd
        JARVIS_DIR_WIN = $Destinazione
        HOME           = $Home_.Replace("\", "/")
        HOME_WIN       = $Home_
        UTENTE         = $NomeUtente
        NOME_ASSISTENTE = $NomeAssistente
        LINGUA         = $Lingua
        FUSO_ORARIO    = $FusoOrario
        MEMORIA_CONDIVISA = $Memoria
        NON_TOCCARE    = $NonToccare
        UTENTE_SLUG    = $Slug
        RUOLO_LAVORO   = $Ruolo
        VITA_PRIVATA   = $VitaPrivata
        PERSONALITA    = $Personalita
        USO            = $Uso
        PORTA          = "$Porta"
        DATA           = (Get-Date -Format "yyyy-MM-dd")
    }
    function Render([string]$t, [bool]$json) {
        foreach ($k in $tok.Keys) {
            $v = [string]$tok[$k]
            if ($json -and $k -ne "PORTA") { $v = $v.Replace("\", "\\").Replace('"', '\"') }
            $t = $t.Replace("@@$k@@", $v)
        }
        return $t
    }
    $app = Join-Path $Radice "app"
    $n = 0; $r = 0
    Get-ChildItem $app -Recurse -File -Force | Where-Object { $_.FullName -notmatch "[\\/]__pycache__[\\/]" } | ForEach-Object {   # -Force: anche app\.claude\hooks (cartella che comincia col punto)
        $rel = $_.FullName.Substring($app.Length).TrimStart("\")
        if ($_.Name -like "*.tpl") {
            $dest = Join-Path $Destinazione ($rel -replace "\.tpl$", "")
            Salva $dest (Render (Leggi $_.FullName) ($dest -like "*.json")); $r++
        } else {
            $dest = Join-Path $Destinazione $rel
            $dir = Split-Path -Parent $dest
            if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
            Copy-Item $_.FullName $dest -Force; $n++
        }
    }
    Ok "$n file copiati, $r resi con i tuoi dati"

    # ------------------------------------------------------------------ 3. file personali (solo se mancano)
    Passo 3 "File personali (creati dai modelli solo se non esistono già)"
    $mod = Join-Path $Radice "modelli-personali"
    $piano = @(
        @("configurazione.base.json.tpl",      "command-center\configurazione.json"),
        @("spazi.base.json.tpl",               "command-center\spazi.json"),
        @("pannello.base.json.tpl",            "command-center\pannello.json"),
        @("utente.json.tpl",                   "utente.json"),
        @("CLAUDE.md.tpl",                     "CLAUDE.md"),
        @("agents\esecutore.md.tpl",           ".claude\agents\esecutore.md"),
        @("agents\ricercatore-web.md.tpl",     ".claude\agents\ricercatore-web.md"),
        @("agents\LEGGIMI.md.tpl",             ".claude\agents\LEGGIMI.md"),
        @("memoria\MEMORIA.md.tpl",            ".claude\memoria-$Slug\MEMORIA.md"),
        @("memoria\battute-lunedi.md.tpl",     ".claude\memoria-$Slug\battute-lunedi.md")
    )
    foreach ($p in $piano) {
        $src = Join-Path $mod $p[0]; $dest = Join-Path $Destinazione $p[1]
        if ((Test-Path $dest) -and -not $RifaiFilePersonali) { Scrivi ("    =   già c'è: " + $p[1] + " (non lo tocco)"); continue }
        Salva $dest (Render (Leggi $src) ($dest -like "*.json"))
        Ok ("creato " + $p[1])
    }
    foreach ($d in @("report-missioni", "command-center\lavori", "command-center\missioni", "sincro\copie")) { New-Item -ItemType Directory -Force -Path (Join-Path $Destinazione $d) | Out-Null }
    # .gitignore della cartella installata: i dati personali non finiscono mai in git
    $gi = Join-Path $Destinazione ".gitignore"
    if (-not (Test-Path $gi)) {
        Salva $gi (@("# dati personali e di lavoro: mai in git", ".venv/", "utente.json", "CLAUDE.md", "Scadenze personali.md", "report-missioni/",
            ".claude/memoria*/", ".claude/agents/", "backtalk/.jarvis_status*", "sincro/copie/", "sincro/ultimo.json", "command-center/configurazione.json", "command-center/spazi.json",
            "command-center/pannello.json", "command-center/lavori/", "command-center/missioni/", "command-center/missioni_archivio/", "command-center/catena-stato.json",
            "command-center/assistenza.json", "command-center/assistenza-registro.json", "command-center/assistenza-registro.json.*", "command-center/assistenza.log",
            "strumenti/kokoro/*.onnx", "strumenti/kokoro/*.bin", "strumenti/*.log", "__pycache__/", "installazione.log",
            "command-center/vault-sezioni.json", "vault-esportazione-*.json", "*.vault", "*password*.csv", "*Password*.csv") -join "`n")
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $Destinazione "backtalk") | Out-Null      # qui vive il file della lavagna in tempo reale
    Copy-Item (Join-Path $Radice "requirements.txt") (Join-Path $Destinazione "requirements.txt") -Force
    # la copia installata non ha il .git: CLONE.txt dice al pannello da quale clone si aggiorna (avviso «Aggiornamento disponibile»)
    Set-Content -Path (Join-Path $Destinazione "CLONE.txt") -Value $Radice -Encoding ascii

    # ------------------------------------------------------------------ 4. ambiente Python
    Passo 4 "Ambiente Python e librerie (può richiedere qualche minuto)"
    $Venv = Join-Path $Destinazione ".venv"
    $PyVenv = Join-Path $Venv "Scripts\python.exe"
    if (-not (Test-Path $PyVenv)) { & $PyBase -m venv $Venv; if ($LASTEXITCODE -ne 0) { throw "Non riesco a creare l'ambiente Python." } }
    & $PyVenv -m pip install --quiet --upgrade pip 2>&1 | Out-Null
    & $PyVenv -m pip install --quiet -r (Join-Path $Destinazione "requirements.txt") 2>&1 | ForEach-Object { Add-Content $Log $_ }
    if ($LASTEXITCODE -ne 0) { throw "L'installazione delle librerie è fallita (vedi installazione.log)." }
    $prova = & $PyVenv -c "import claude_agent_sdk, faster_whisper, kokoro_onnx, sounddevice, pynput, PIL, soundfile, numpy, scipy, noisereduce; print('ok')" 2>&1
    if ("$prova" -notmatch "ok") { throw "Le librerie non si importano: $prova" }
    Ok "Librerie installate e verificate"

    # ------------------------------------------------------------------ 5. voce
    Passo 5 "Voce italiana (Kokoro Sara, in locale)"
    $kok = Join-Path $Destinazione "strumenti\kokoro"
    $modelli = @(
        @{ n = "kokoro-v1.0.onnx"; u = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"; b = 325532387; h = "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5" },
        @{ n = "voices-v1.0.bin";  u = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin";  b = 28214398;  h = "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d" }
    )
    if ($SenzaModelliVoce) { Avviso "Voce non scaricata (-SenzaModelliVoce): Talk to Jarvis non parlerà finché non scarichi i modelli." }
    else {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        foreach ($m in $modelli) {
            $f = Join-Path $kok $m.n
            if ((Test-Path $f) -and ((Get-Item $f).Length -eq $m.b)) { Ok ($m.n + " già presente"); continue }
            Scrivi ("    scarico " + $m.n + " (" + [math]::Round($m.b / 1MB) + " MB)...")
            $tmp = "$f.parte"
            Invoke-WebRequest -Uri $m.u -OutFile $tmp -UseBasicParsing
            if ((Get-Item $tmp).Length -ne $m.b) { Remove-Item $tmp -Force; throw ("Download incompleto di " + $m.n) }
            $hash = (Get-FileHash $tmp -Algorithm SHA256).Hash.ToLower()
            if ($hash -ne $m.h) { Avviso ($m.n + ": l'impronta non coincide con quella attesa (potrebbe essere una versione nuova del modello)") }
            Move-Item $tmp $f -Force
            Ok ($m.n + " scaricato")
        }
    }

    # ------------------------------------------------------------------ 6. Claude Code
    Passo 6 "Collegamento a Claude Code"
    if ($SenzaClaudeConfig) { Scrivi "    saltato (-SenzaClaudeConfig)" }
    else {
        $cc = Join-Path $env:USERPROFILE ".claude"
        New-Item -ItemType Directory -Force -Path (Join-Path $cc "hooks") | Out-Null
        $cfg = Join-Path $Radice "claude-config"
        Salva (Join-Path $cc "hooks\jarvis_avvio.py") (Render (Leggi (Join-Path $cfg "hooks\jarvis_avvio.py.tpl")) $false)
        Ok "gancio di avvio: ~\.claude\hooks\jarvis_avvio.py"
        if (Test-Path (Join-Path $cfg "skills\brain")) {
            $sk = Join-Path $cc "skills\brain"
            Get-ChildItem (Join-Path $cfg "skills\brain") -Recurse -File | ForEach-Object {
                $rel = $_.FullName.Substring((Join-Path $cfg "skills\brain").Length).TrimStart("\")
                $dest = Join-Path $sk ($rel -replace "\.tpl$", "")
                if ($_.Name -like "*.tpl") { Salva $dest (Render (Leggi $_.FullName) $false) }
                else { $d = Split-Path -Parent $dest; New-Item -ItemType Directory -Force -Path $d | Out-Null; Copy-Item $_.FullName $dest -Force }
            }
            Ok "skill «brain» (memoria dei tuoi progetti)"
        }
        # 2026-10-05: le altre skill del repo (aggiorna-memoria, brainstorming, riunione-agenti, systematic-debugging,
        # verification-before-completion, writing-plans, writing-skills) e i ganci di sicurezza (guardia dei comandi per
        # Git Bash, guardia delle connessioni) e, dal 2026-10-10, la skill nuovo-progetto. Sono codice: si riscrivono a
        # ogni aggiornamento.
        Get-ChildItem (Join-Path $cfg "skills") -Directory | Where-Object { $_.Name -ne "brain" } | ForEach-Object {
            $sk = Join-Path $cc ("skills\" + $_.Name)
            $radiceSk = $_.FullName
            Get-ChildItem $radiceSk -Recurse -File | ForEach-Object {
                $dest = Join-Path $sk ($_.FullName.Substring($radiceSk.Length).TrimStart("\") -replace "\.tpl$", "")
                if ($_.Name -like "*.tpl") { Salva $dest (Render (Leggi $_.FullName) $false) }
                else { $d = Split-Path -Parent $dest; New-Item -ItemType Directory -Force -Path $d | Out-Null; Copy-Item $_.FullName $dest -Force }
            }
        }
        Ok "skill di lavoro (aggiorna-memoria, nuovo-progetto, brainstorming, riunione-agenti, debugging, verifiche, piani, skill)"
        foreach ($g in @("guardia_comandi.py", "connessioni_guardia.py", "stato_avanzamento.py", "conferma_salva.py")) {
            $src = Join-Path $cfg ("hooks\" + $g)
            if (Test-Path $src) { Copy-Item $src (Join-Path $cc ("hooks\" + $g)) -Force }
        }
        Ok "ganci: guardia_comandi.py, connessioni_guardia.py, stato_avanzamento.py e conferma_salva.py (stato e diario aggiornati da soli)"
        # 2026-10-10: i comandi /nuovo-progetto e /nuovo-agente valgono in ogni cartella (si riscrivono a ogni aggiornamento)
        $cmdSrc = Join-Path $cfg "commands"
        if (Test-Path $cmdSrc) {
            Get-ChildItem $cmdSrc -File -Filter *.md | ForEach-Object { Salva (Join-Path $cc ("commands\" + ($_.Name -replace "\.tpl$", ""))) (Render (Leggi $_.FullName) $false) }
            Ok "comandi di Claude Code: /nuovo-progetto e /nuovo-agente"
        }
        $md = Join-Path $env:TEMP "jarvis-claude-md.txt"
        Salva $md (Render (Leggi (Join-Path $cfg "CLAUDE-globale.md.tpl")) $false)
        & $PyVenv (Join-Path $cfg "installa_claude.py") --jarvis $Destinazione --claude-md $md --python $PyVenv
        if ($LASTEXITCODE -ne 0) { Avviso "I ganci di Claude Code non sono stati installati (vedi sopra): la lavagna non mostrerà il lavoro in tempo reale." } else { Ok "ganci installati (copia di sicurezza di settings.json fatta)" }
        # la memoria: dove stanno su questo PC la memoria di Claude Code, quella di Jarvis e un eventuale vault condiviso
        $cm = Join-Path $Destinazione "strumenti\collega_memoria.py"
        if (Test-Path $cm) {
            $argCm = @($cm, "--applica", "--memoria", $Memoria)
            if ($Spazi.Count -gt 0) { $argCm += @("--spazi", ($Spazi -join ",")) }
            if ($Harness.Count -gt 0) { $argCm += @("--harness", ($Harness -join ",")) }
            & $PyVenv @argCm
            if ($LASTEXITCODE -ne 0) { Avviso "Il collegamento della memoria non è riuscito: rilancia strumenti\collega_memoria.py --applica" } else { Ok "memoria condivisa collegata in $Memoria (elenco in ~\.jarvis\percorsi.json)" }
        }
        # si parte da zero: nessun progetto. Se nelle risposte c'è il primo progetto, nasce adesso (crea_progetto.py è
        # idempotente: rilanciando l'installazione non si raddoppia niente)
        if ($PrimoProgetto) {
            & $PyVenv (Join-Path $Destinazione "strumenti\crea_progetto.py") $PrimoProgetto --memoria $Memoria
            if ($LASTEXITCODE -ne 0) { Avviso "Il primo progetto non è stato creato: chiedilo a $NomeAssistente o usa /nuovo-progetto" } else { Ok "primo progetto creato: $PrimoProgetto (con il suo capogruppo)" }
        }
    }

    # ------------------------------------------------------------------ 7. collegamenti sul Desktop
    Passo 7 "Collegamenti sul Desktop"
    if ($SenzaCollegamenti) { Scrivi "    saltato (-SenzaCollegamenti)" }
    else {
        $ico = Join-Path $Destinazione "strumenti\jarvis.ico"
        & $PyVenv -c "from PIL import Image; im=Image.open(r'$Destinazione\command-center\static\icona-64.png').convert('RGBA'); im.save(r'$ico', sizes=[(16,16),(32,32),(48,48),(64,64)])" 2>$null
        $desk = [Environment]::GetFolderPath("Desktop")
        $sh = New-Object -ComObject WScript.Shell
        $ps = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
        foreach ($c in @(
                @("Jarvis Command Center", "Avvia Command Center.ps1"),
                @("Jarvis Orb", "Avvia Widget Jarvis.ps1"),
                @("Talk to Jarvis", "Talk to Jarvis.ps1"))) {
            $l = $sh.CreateShortcut((Join-Path $desk ($c[0] + ".lnk")))
            $l.TargetPath = $ps
            $l.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"" + (Join-Path $Destinazione ("avvio\" + $c[1])) + "`""
            $l.WorkingDirectory = $Destinazione
            if (Test-Path $ico) { $l.IconLocation = $ico }
            $l.Save()
            Ok ("collegamento: " + $c[0])
        }
        # il collegamento di aggiornamento: finestra visibile e aperta alla fine, così si vede cosa è cambiato.
        # Lancia AGGIORNA.ps1 del clone da cui si è installato (fa git fetch, copia di sicurezza, riallinea, non tocca i file personali).
        $agg = Join-Path $Radice "AGGIORNA.ps1"
        if (Test-Path $agg) {
            $l = $sh.CreateShortcut((Join-Path $desk "Aggiorna Jarvis.lnk"))
            $l.TargetPath = $ps
            $l.Arguments = "-NoProfile -ExecutionPolicy Bypass -NoExit -File `"$agg`""
            $l.WorkingDirectory = $Radice
            $l.Description = "Scarica e installa l'ultima versione di Jarvis senza toccare i tuoi dati"
            if (Test-Path $ico) { $l.IconLocation = $ico }
            $l.Save()
            Ok "collegamento: Aggiorna Jarvis"
        }
    }

    # ------------------------------------------------------------------ 8. avvio automatico
    Passo 8 "Avvio automatico all'accesso e battito della memoria"
    if ($SenzaCompiti) { Scrivi "    saltato (-SenzaCompiti)" }
    else {
        try {
            $impost = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
            $a1 = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ("-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"" + (Join-Path $Destinazione "avvio\Avvio automatico Jarvis.ps1") + "`"")
            Register-ScheduledTask -TaskName "Jarvis Avvio" -Action $a1 -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) -Settings $impost -Force | Out-Null
            $a2 = New-ScheduledTaskAction -Execute (Join-Path $Venv "Scripts\pythonw.exe") -Argument "sincro\ogni30.py --zitto" -WorkingDirectory $Destinazione
            $t2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15)
            Register-ScheduledTask -TaskName "Jarvis Battito" -Action $a2 -Trigger $t2 -Settings $impost -Force | Out-Null
            # 2026-10-10: il giro notturno dei quaderni degli agenti (sul Mac era launchd com.jarvis.giro-apprendimento alle 06:40)
            $a3 = New-ScheduledTaskAction -Execute (Join-Path $Venv "Scripts\pythonw.exe") -Argument "strumenti\giro_apprendimento.py" -WorkingDirectory $Destinazione
            Register-ScheduledTask -TaskName "Jarvis Giro notturno" -Action $a3 -Trigger (New-ScheduledTaskTrigger -Daily -At "06:40") -Settings $impost -Force | Out-Null
            # 2026-10-10: la pulizia di ~\.claude (memorie unite alla memoria condivisa, trascrizioni vecchie archiviate)
            $a4 = New-ScheduledTaskAction -Execute (Join-Path $Venv "Scripts\pythonw.exe") -Argument "strumenti\pulisci_claude.py --applica --quiet" -WorkingDirectory $Destinazione
            Register-ScheduledTask -TaskName "Jarvis Pulizia" -Action $a4 -Trigger (New-ScheduledTaskTrigger -Daily -At "06:20") -Settings $impost -Force | Out-Null
            Ok "attività «Jarvis Avvio» (all'accesso), «Jarvis Battito» (ogni 15 minuti), «Jarvis Pulizia» (06:20) e «Jarvis Giro notturno» (06:40)"
        } catch { Avviso ("Attività pianificate non create: " + $_.Exception.Message) }
    }

    # ------------------------------------------------------------------ 8b. assistenza a distanza (facoltativa)
    if ($ConAssistenza) {
        Passo "8b" "Assistenza a distanza: WSL, openssh e tmate (docs\ASSISTENZA.md)"
        $pa = Join-Path $Destinazione "strumenti\prepara_assistenza_windows.ps1"
        & $pa -Destinazione $Destinazione
        if ($LASTEXITCODE -eq 0) { Ok "assistenza a distanza pronta e accesa (command-center\assistenza.json)" }
        else { Avviso "Assistenza a distanza non ancora pronta: vedi il riepilogo sopra. Basta premere «Attiva assistenza» nel pannello (pagina Stato)." }
    }

    # ------------------------------------------------------------------ 9. avvio e verifica
    Passo 9 "Avvio e verifica"
    if ($SenzaAvvio) { Scrivi "    avvio saltato (-SenzaAvvio)" }
    else {
        $env:PYTHONUTF8 = "1"
        $env:CC_PORTA = "$Porta"
        $ccDir = Join-Path $Destinazione "command-center"
        # un aggiornamento deve riavviare il pannello: se resta acceso quello vecchio, il codice nuovo non si vede (01/10/2026)
        $vecchio = Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($vecchio) {
            $proc = Get-Process -Id $vecchio.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -match 'python') {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                for ($i = 0; $i -lt 20 -and (Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue); $i++) { Start-Sleep -Milliseconds 250 }
                Scrivi "    Command Center vecchio fermato: riparte con il codice nuovo"
            }
        }
        if (-not (Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue)) {
            Start-Process -FilePath $PyVenv -ArgumentList "server.py" -WorkingDirectory $ccDir -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $ccDir "lavori\server.log") -RedirectStandardError (Join-Path $ccDir "lavori\server-err.log")
        }
        $su = $false
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Milliseconds 500
            try { if ((Invoke-WebRequest "http://127.0.0.1:$Porta/" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) { $su = $true; break } } catch {}
        }
        if ($su) { Ok "Command Center attivo su http://127.0.0.1:$Porta" } else { Avviso "Il Command Center non risponde: guarda command-center\lavori\server-err.log" }
    }
    $ver = Join-Path $Radice "VERIFICA.ps1"
    if (Test-Path $ver) { & $ver -Destinazione $Destinazione -Porta $Porta -SenzaServer:$SenzaAvvio }

    # il segno che la prima apertura è fatta: CLAUDE.md del repository non rifà le domande di avvio
    $ij = Join-Path $env:USERPROFILE ".jarvis\installato.json"
    $verRepo = ""; $fv = Join-Path $Radice "VERSIONE"; if (Test-Path $fv) { $verRepo = (Get-Content $fv -Raw).Trim() }
    Salva $ij ((@{ versione = $verRepo; data = (Get-Date -Format "yyyy-MM-dd HH:mm"); cartella = $Destinazione; memoria = $Memoria;
        utente = $NomeUtente; assistente = $NomeAssistente; avvisi = $Avvisi.Count; da_risposte = [bool]($DaRisposte -or $FileRisposte) } | ConvertTo-Json) + "`n")
    Ok "scritto $ij"

    Scrivi ""
    Scrivi "==============================================================" "White"
    if ($Avvisi.Count -eq 0) { Scrivi "  INSTALLAZIONE COMPLETATA, senza avvisi." "Green" }
    elseif ($Avvisi.Count -eq 1) { Scrivi "  INSTALLAZIONE COMPLETATA con 1 avviso (sopra, in giallo)." "Yellow" }
    else { Scrivi ("  INSTALLAZIONE COMPLETATA con " + $Avvisi.Count + " avvisi (sopra, in giallo).") "Yellow" }
    Scrivi "==============================================================" "White"
    Scrivi ""
    Scrivi "Da fare per personalizzare (tutto facoltativo, vedi docs\PERSONALIZZAZIONE.md):"
    Scrivi "  - $Destinazione\utente.json e CLAUDE.md: come $NomeAssistente ti chiama, il tuo profilo e come si comporta"
    Scrivi "  - $Memoria\<spazio>\Stato.md: lo stato dei progetti, aggiornato da solo a ogni risposta di Claude Code"
    Scrivi "  - $Destinazione\command-center\configurazione.json: siti da tenere d'occhio, comandi rapidi, porta"
    Scrivi "  - i progetti: si parte da zero. Di' a $NomeAssistente «crea il progetto ...» o scrivi /nuovo-progetto <nome> in Claude Code"
    Scrivi "  - apri una NUOVA sessione di Claude Code perché i ganci partano"
    Scrivi "Per aprire il pannello: doppio clic su «Jarvis Command Center» sul Desktop."
    exit 0
}
catch {
    Scrivi ""
    Scrivi ("ERRORE: " + $_.Exception.Message) "Red"
    Scrivi "Il dettaglio è in $Log. Puoi rilanciare INSTALLA.ps1: riparte da dove serve e non perde i tuoi file." "Red"
    exit 1
}
