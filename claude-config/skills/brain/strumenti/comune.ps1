# comune.ps1 — quello che brain.ps1 e salva.ps1 usano tutti e due.
# Windows, PowerShell 5.1. Niente Python: serve solo PowerShell.

$ErrorActionPreference = 'Stop'
$OGGI = (Get-Date).ToString('yyyy-MM-dd')
# Ogni aggiornamento porta data E ORA.
$ORA = (Get-Date).ToString('yyyy-MM-dd HH:mm')

# -- Il vault Obsidian (facoltativo) -------------------------------------------
# Se usi Obsidian, scrivi in utente.json (nella cartella di Jarvis) "vault_dir": il percorso del vault,
# cioe' la cartella che contiene .obsidian\. Se e' vuoto o non esiste, il vault semplicemente non si usa:
# la memoria in .claude\memoria\ funziona lo stesso. Si puo' anche impostare la variabile JARVIS_VAULT.
$JARVIS_CASA = $env:JARVIS_DIR
if (-not $JARVIS_CASA) { $JARVIS_CASA = Join-Path $env:USERPROFILE 'jarvis' }
$VAULT_RADICE = $env:JARVIS_VAULT
if (-not $VAULT_RADICE) {
  try {
    $u = Get-Content -LiteralPath (Join-Path $JARVIS_CASA 'utente.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($u.vault_dir) { $VAULT_RADICE = [string]$u.vault_dir }
  } catch {}
}
if ($VAULT_RADICE -and -not (Test-Path -LiteralPath $VAULT_RADICE)) { $VAULT_RADICE = $null }

# -- La mappa progetto -> cartella nel vault (facoltativa) ---------------------
# Se un progetto ha nel vault una cartella con un nome diverso da quello del disco, mettila qui:
#   'Mio Progetto' = @{ Disco = 'C:\Users\tu\Documenti\Mio Progetto'; Vault = 'Mio Progetto (note)' }
# Senza voce, la cartella del vault e' quella con lo stesso nome del progetto, se esiste.
$PROGETTI = @{}

$DOC   = @('CLAUDE.md','LEGGIMI.md','MEMORIA.md','ARCHITETTURA.md','README.md')

# Le cartelle che non si attraversano: dati e archivi grossi, non stato del lavoro.
# Attraversarli (specie su OneDrive) fa impiegare minuti a un referto che deve costare secondi.
$SALTA_DIR = @('.git','node_modules','__pycache__','.venv','.codegraph','graphify-out',
           'dist','build','vendor','.copie','.agents','.vscode','.obsidian')
$SALTA = $SALTA_DIR   # nome vecchio, tenuto per non rompere chi lo usa
$DATA_RX = [regex]'(?im)^[*_\s]*(aggiornat[ao]|data|ultima modifica)[*_\s]*:\s*"?(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?'

# Il pallino rosso si costruisce dal numero, non si scrive nel sorgente: e' una
# coppia surrogata, e basta salvare il file con la codifica sbagliata perche' il
# confronto smetta di funzionare in silenzio — l'elenco dice «0 rossi» mentre ne
# ha dodici, che e' esattamente il tipo di guasto che non si vede.
$ROSSO = [char]::ConvertFromUtf32(0x1F534)

# -- File: sempre UTF-8 senza BOM, o gli accenti e i pallini rossi si rompono --
function Leggi-Testo {
  param([string]$File)
  if (Test-Path -LiteralPath $File) { return [System.IO.File]::ReadAllText($File, [System.Text.Encoding]::UTF8) }
  return ''
}

function Scrivi-Testo {
  param([string]$File, [string]$Testo)
  $dir = Split-Path -Path $File -Parent
  if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  $enc = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($File, $Testo, $enc)
}

# -- Trova il progetto: si risale finche' si incontra il marcatore -------------
function Trova-Progetto {
  param([string]$Cartella)
  if (-not $Cartella) { $Cartella = (Get-Location).Path }
  if (-not (Test-Path -LiteralPath $Cartella)) { throw "$Cartella non esiste" }
  $p = (Resolve-Path -LiteralPath $Cartella).Path
  $c = $p
  while ($true) {
    if ((Test-Path -LiteralPath (Join-Path $c '.claude\memoria')) -or
        (Test-Path -LiteralPath (Join-Path $c 'CLAUDE.md'))) { break }
    $su = Split-Path -Path $c -Parent
    if (-not $su -or $su -eq $c) { $c = $p; break }
    $c = $su
  }

  $nome = Split-Path -Path $c -Leaf
  $vdir = $null
  foreach ($k in $PROGETTI.Keys) {
    $d = $PROGETTI[$k].Disco.TrimEnd('\')
    if ($d -ieq $c.TrimEnd('\')) { $nome = $k; $vdir = $PROGETTI[$k].Vault; break }
  }
  if (-not $vdir -and $VAULT_RADICE) {
    # non mappato: si prova la cartella del vault con lo stesso nome del progetto
    if (Test-Path -LiteralPath (Join-Path $VAULT_RADICE $nome)) { $vdir = $nome }
  }

  $vaultPieno = $null
  $pagina = $null
  if ($vdir -and $VAULT_RADICE) {
    $vaultPieno = Join-Path $VAULT_RADICE $vdir
    $pagina = Join-Path $vaultPieno 'A che punto siamo.md'
  }

  return [pscustomobject]@{
    Nome         = $nome
    Disco        = $c
    Memoria      = (Join-Path $c '.claude\memoria')
    File         = (Join-Path $c '.claude\memoria\MEMORIA.md')
    ClaudeMd     = (Join-Path $c 'CLAUDE.md')
    VaultRadice  = $VAULT_RADICE
    VaultDir     = $vaultPieno
    PaginaVault  = $pagina
    Mappato      = [bool]$PROGETTI.ContainsKey($nome)
  }
}

# -- Le sezioni di MEMORIA.md -------------------------------------------------
function Get-Sezione {
  param([string]$Testo, [string]$Titolo)   # Titolo tipo '## A che punto siamo'
  $righe = @($Testo -split "`r?`n")
  $i = -1
  for ($k = 0; $k -lt $righe.Count; $k++) {
    if ($righe[$k].Trim().ToLower() -eq $Titolo.ToLower()) { $i = $k; break }
  }
  if ($i -lt 0) { return $null }
  $j = $righe.Count
  for ($k = $i + 1; $k -lt $righe.Count; $k++) {
    if ($righe[$k] -like '## *') { $j = $k; break }
  }
  if ($j -le ($i + 1)) { return '' }
  return (($righe[($i + 1)..($j - 1)]) -join "`n").Trim()
}

function Set-Sezione {
  param([string]$Testo, [string]$Titolo, [string]$Nuovo)
  $righe = @($Testo -split "`r?`n")
  $i = -1
  for ($k = 0; $k -lt $righe.Count; $k++) {
    if ($righe[$k].Trim().ToLower() -eq $Titolo.ToLower()) { $i = $k; break }
  }
  if ($i -lt 0) { return ($Testo.TrimEnd() + "`n`n" + $Titolo + "`n`n" + $Nuovo + "`n") }
  $j = $righe.Count
  for ($k = $i + 1; $k -lt $righe.Count; $k++) {
    if ($righe[$k] -like '## *') { $j = $k; break }
  }
  $pre  = @($righe[0..$i])
  $post = @()
  if ($j -lt $righe.Count) { $post = @($righe[$j..($righe.Count - 1)]) }
  return (($pre + @('') + @($Nuovo -split "`r?`n") + @('') + $post) -join "`n")
}

function Get-Voci {
  param([string]$Sezione, [string]$Sotto)  # Sotto tipo '### Fatto'
  $dentro = $false
  $out = New-Object System.Collections.ArrayList
  foreach ($l in ($Sezione -split "`r?`n")) {
    $t = $l.Trim()
    if ($t.ToLower().StartsWith($Sotto.ToLower())) { $dentro = $true; continue }
    if ($dentro -and $t.StartsWith('### ')) { $dentro = $false }
    if ($dentro -and $t.StartsWith('- ')) { [void]$out.Add($t.Substring(2).Trim()) }
  }
  # 🔴 Niente `return ,@(...)`: la virgola incarta l'array in un altro array, e
  # chi chiama con @(Get-Voci ...) si ritrova UNA voce che contiene tutte le
  # altre. Non da' errore: l'elenco si riscrive su una riga sola, unito da spazi,
  # e il conteggio dice «2 fatte» dove ce n'erano 61. Si restituisce piatto, e si
  # conta prima e dopo (vedi la guardia in salva.ps1).
  return [string[]]$out.ToArray()
}

function Get-Preambolo {
  param([string]$Sezione)
  if (-not $Sezione) { return '' }
  $i = $Sezione.IndexOf('###')
  if ($i -lt 0) { return $Sezione.Trim() }
  return $Sezione.Substring(0, $i).Trim()
}

# -- La copia di sicurezza: MEMORIA.md non e' sotto git e non ha altri backup --
# Il 6/09/2026 un salvataggio ha cancellato Fatto (76 voci) e Da fare (25) senza
# dirlo. La copia costa un file, e compra il diritto di sbagliare.
function Salva-Copia {
  param([string]$File)
  if (-not (Test-Path -LiteralPath $File)) { return $null }
  $dir = Join-Path (Split-Path -Path $File -Parent) '.copie'
  if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  $dest = Join-Path $dir ('MEMORIA-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.md')
  Copy-Item -LiteralPath $File -Destination $dest -Force
  $vecchie = @(Get-ChildItem -LiteralPath $dir -Filter 'MEMORIA-*.md' | Sort-Object Name -Descending)
  if ($vecchie.Count -gt 12) { $vecchie[12..($vecchie.Count - 1)] | Remove-Item -Force }
  return $dest
}

# -- Una sola passeggiata sul disco, con le cartelle grosse potate -------------
# Il referto la fa una volta e la riusa: camminare due volte su OneDrive
# raddoppia l'unica cosa lenta che c'e' qui dentro.
function Get-FileProgetto {
  param([string]$Base, [int]$Profondita = 4)
  $out  = New-Object System.Collections.ArrayList
  $coda = New-Object System.Collections.Queue
  $coda.Enqueue(@{ Dir = $Base; Liv = 0 })
  while ($coda.Count -gt 0) {
    $n = $coda.Dequeue()
    try { $figli = @(Get-ChildItem -LiteralPath $n.Dir -Force -ErrorAction Stop) } catch { continue }
    foreach ($f in $figli) {
      if ($f.PSIsContainer) {
        if ($n.Liv -ge $Profondita) { continue }
        if ($SALTA_DIR -contains $f.Name) { continue }
        $coda.Enqueue(@{ Dir = $f.FullName; Liv = $n.Liv + 1 })
      } else {
        [void]$out.Add($f)
      }
    }
  }
  return $out.ToArray()
}

# -- Le date dichiarate contro le date vere -----------------------------------
function Get-DateScadute {
  param([string]$Base, $File)
  if (-not $File) { $File = Get-FileProgetto $Base }
  $out = New-Object System.Collections.ArrayList
  foreach ($f in $File) {
    if ($DOC -notcontains $f.Name) { continue }
    $rel = $f.FullName.Substring($Base.Length).TrimStart('\')
    $t = Leggi-Testo $f.FullName
    $m = $DATA_RX.Match($t)
    if (-not $m.Success) {
      [void]$out.Add([pscustomobject]@{ Rel=$rel; Piena=$f.FullName; Dichiarata=$null; Modificata=$f.LastWriteTime.Date; Tipo='senza' })
      continue
    }
    $dich = [datetime]::ParseExact($m.Groups[2].Value, 'yyyy-MM-dd', $null)
    if (($f.LastWriteTime.Date - $dich).Days -gt 1) {
      [void]$out.Add([pscustomobject]@{ Rel=$rel; Piena=$f.FullName; Dichiarata=$dich; Modificata=$f.LastWriteTime.Date; Tipo='scaduta' })
    }
  }
  return $out.ToArray()
}

function Timbra-File {
  param([string]$File, [string]$Quando)
  $t = Leggi-Testo $File
  if (-not $t) { return $false }
  $aveva = $DATA_RX.IsMatch($t)
  if (-not $Quando) {
    # Se non ne aveva mai avuta una, ci va la data di MODIFICA vera, non oggi:
    # scrivere «oggi» su un file fermo da tre settimane e' una bugia in piu'.
    if ($aveva) { $Quando = $ORA }
    else { $Quando = (Get-Item -LiteralPath $File).LastWriteTime.ToString('yyyy-MM-dd HH:mm') }
  }
  if ($aveva) {
    $m = $DATA_RX.Match($t)
    # si sostituisce data e, se c'era, anche l'ora: «2026-09-09» o «2026-09-09 12:55»
    $lung = 10
    if ($m.Groups[3].Success) { $lung = $m.Groups[3].Index + $m.Groups[3].Length - $m.Groups[2].Index }
    $nuovo = $t.Remove($m.Groups[2].Index, $lung).Insert($m.Groups[2].Index, $Quando)
  } elseif ($t.StartsWith('---')) {
    $nuovo = ([regex]'^---\r?\n').Replace($t, "---`naggiornato: $Quando`n", 1)
  } else {
    $righe = @($t -split "`r?`n")
    $i = -1
    for ($k = 0; $k -lt $righe.Count; $k++) { if ($righe[$k].TrimStart().StartsWith('#')) { $i = $k; break } }
    if ($i -lt 0) { return $false }
    $nuovo = ((@($righe[0..$i]) + @('', "*Ultima modifica: $Quando*") + @($righe[($i+1)..($righe.Count-1)])) -join "`n")
  }
  if ($nuovo -ne $t) {
    # Timbrare con la data di modifica VERA e poi lasciare che la scrittura porti
    # l'mtime a oggi rende il file «scaduto» un secondo dopo (visto il 9/09/2026:
    # sei documenti timbrati e subito segnalati). Se la data messa non e' oggi,
    # l'mtime si rimette dov'era: il contenuto non e' cambiato, solo l'etichetta.
    $lw = (Get-Item -LiteralPath $File).LastWriteTime
    Scrivi-Testo $File $nuovo
    if (-not $Quando.StartsWith($OGGI)) { (Get-Item -LiteralPath $File).LastWriteTime = $lw }
    return $true
  }
  return $false
}
