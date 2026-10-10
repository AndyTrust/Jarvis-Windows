# brain.ps1 — APERTURA: guarda, decide, riferisce. Zero token per il modello.
#
#   .\brain.ps1                    il referto (progetto = cartella corrente)
#   .\brain.ps1 -Cartella "C:\..." un altro progetto
#   .\brain.ps1 -Tutto             non accorcia gli elenchi
#   .\brain.ps1 -Timbra            porta a oggi le date scadute
#
# Non chiede niente: guarda la cartella, la memoria, le date dei file, e sceglie
# da se' se il progetto e' nuovo, se e' a posto, o se qualcosa e' scaduto.

param(
  [string]$Cartella,
  [switch]$Tutto,
  [switch]$Timbra,
  [switch]$Hook
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
. (Join-Path $PSScriptRoot 'comune.ps1')

$p = Trova-Progetto $Cartella
$haMemoria = Test-Path -LiteralPath $p.File
$haClaude  = Test-Path -LiteralPath $p.ClaudeMd

# ---------- TIMBRO ----------
if ($Timbra) {
  $v = Get-DateScadute $p.Disco
  if ($v.Count -eq 0) { Write-Output 'OK  nessuna data scaduta'; return }
  foreach ($x in $v) {
    $quando = $null
    if ($x.Tipo -eq 'senza') { $quando = (Get-Item -LiteralPath $x.Piena).LastWriteTime.ToString('yyyy-MM-dd HH:mm') }
    if (Timbra-File $x.Piena $quando) {
      $dice = '(nessuna)'
      if ($x.Dichiarata) { $dice = $x.Dichiarata.ToString('yyyy-MM-dd') }
      $nuova = $ORA
      if ($x.Tipo -eq 'senza') { $nuova = $quando }
      Write-Output ("  -> {0,-44} {1} -> {2}" -f $x.Rel, $dice, $nuova)
    }
  }
  return
}

# ---------- PROGETTO NUOVO ----------
if (-not $haMemoria -and -not $haClaude) {
  Write-Output ''
  Write-Output ("+- {0}" -f $p.Nome)
  Write-Output '|  PROGETTO NUOVO - niente CLAUDE.md, niente .claude\memoria\'
  Write-Output '+-'
  Write-Output ''
  Write-Output 'Impianto (leggi la sezione «Impiantare un progetto nuovo» in SKILL.md):'
  Write-Output '  1. CLAUDE.md a indice, sotto le 200 righe'
  Write-Output '  2. .claude\memoria\MEMORIA.md con le quattro sezioni'
  Write-Output '  3. .gitignore, e uno strumento al posto di ogni MCP'
  Write-Output ''
  Write-Output "ATTENZIONE: se questa non e' la cartella del progetto, il referto non vale niente."
  return
}

$testo = Leggi-Testo $p.File
$stato = Get-Sezione $testo '## A che punto siamo'
$err   = Get-Voci $stato '### Errori da non ripetere'
$fatti = Get-Voci $stato '### Fatto'
$aperti= Get-Voci $stato '### Da fare'
$preamb= Get-Preambolo $stato
$sapere= Get-Sezione $testo '## Cosa sappiamo già'
$nFatti = 0
if (Test-Path -LiteralPath $p.Memoria) {
  $nFatti = @(Get-ChildItem -LiteralPath $p.Memoria -Filter '*.md' -File | Where-Object { $_.Name -ne 'MEMORIA.md' }).Count
}

$eta = '(mai)'
if ($haMemoria) {
  $g = ((Get-Date).Date - (Get-Item -LiteralPath $p.File).LastWriteTime.Date).Days
  if ($g -eq 0) { $eta = 'toccata oggi' } elseif ($g -eq 1) { $eta = 'toccata ieri' } else { $eta = "ferma da $g giorni" }
}

Write-Output ''
Write-Output ("+- {0}  ·  {1}" -f $p.Nome, $OGGI)
Write-Output ("|  memoria: {0} fatti · MEMORIA.md {1}" -f $nFatti, $eta)
Write-Output '+-'

if ($preamb) {
  Write-Output ''
  foreach ($l in ($preamb -split "`r?`n")) { Write-Output $l }
}

# --- Gli errori: si stampano TUTTI. E' l'unica sezione che non si accorcia ---
# Rileggerli costa qualche centinaio di token; ricommettere l'errore costa una
# sessione intera, piu' il danno quando ha cancellato file o mandato in onda
# codice rotto.
if ($err.Count -gt 0) {
  Write-Output ''
  Write-Output ("== ERRORI DA NON RIPETERE ({0}) ==" -f $err.Count)
  foreach ($e in $err) { Write-Output ("- " + $e) }
}

if ($aperti.Count -gt 0) {
  $rossi  = @($aperti | Where-Object { $_.Contains($ROSSO) })
  $normali= @($aperti | Where-Object { -not $_.Contains($ROSSO) })
  Write-Output ''
  Write-Output ("== DA FARE ({0}, di cui {1} col pallino rosso) ==" -f $aperti.Count, $rossi.Count)
  foreach ($x in $rossi) { Write-Output ("- " + $x) }
  $q = $normali
  if (-not $Tutto -and $normali.Count -gt 8) { $q = $normali[0..7] }
  foreach ($x in $q) { Write-Output ("- " + $x) }
  if (-not $Tutto -and $normali.Count -gt 8) {
    Write-Output ("  ... e altre {0} non rosse (-Tutto per vederle)" -f ($normali.Count - 8))
  }
}

if ($fatti.Count -gt 0) {
  Write-Output ''
  Write-Output ("== FATTO ({0}) - le ultime ==" -f $fatti.Count)
  $q = $fatti
  if (-not $Tutto -and $fatti.Count -gt 6) { $q = $fatti[($fatti.Count-6)..($fatti.Count-1)] }
  foreach ($x in $q) { Write-Output ("- " + $x) }
}

# --- Cosa e' cambiato da ieri: si guarda il disco, non la memoria ---
$tuttiFile = Get-FileProgetto $p.Disco
$limite = (Get-Date).AddDays(-3)
$recenti = @($tuttiFile |
  Where-Object { $_.LastWriteTime -gt $limite -and -not $_.Name.StartsWith('.') } |
  Sort-Object LastWriteTime -Descending)
if ($recenti.Count -gt 0) {
  Write-Output ''
  Write-Output ("== TOCCATI NEGLI ULTIMI 3 GIORNI ({0}) ==" -f $recenti.Count)
  foreach ($f in ($recenti | Select-Object -First 10)) {
    Write-Output ("  {0}  {1}" -f $f.LastWriteTime.ToString('dd/MM HH:mm'), $f.FullName.Substring($p.Disco.Length).TrimStart('\'))
  }
}

# --- Il vault Obsidian (facoltativo): c'e' la pagina di QUESTO progetto, ed e' fresca? ---
if ($p.VaultRadice) {
  Write-Output ''
  if (-not $p.VaultDir) {
    Write-Output ("·  {0} non ha una cartella nel vault: se la vuoi, creala con lo stesso nome del progetto (o mappala in strumenti\comune.ps1)." -f $p.Nome)
  } elseif (-not (Test-Path -LiteralPath $p.PaginaVault)) {
    Write-Output '·  il vault non ha ancora «A che punto siamo» per questo progetto: la scrive salva.ps1'
  } else {
    $g = ((Get-Date).Date - (Get-Item -LiteralPath $p.PaginaVault).LastWriteTime.Date).Days
    $quando = "$g giorni fa"
    if ($g -eq 0) { $quando = 'oggi' } elseif ($g -eq 1) { $quando = 'ieri' }
    $verdetto = 'allineata'
    if ($g -gt 1) { $verdetto = "vecchia: rilancia salva.ps1 a fine sessione" }
    Write-Output ("vault: «A che punto siamo» aggiornata {0} - {1}" -f $quando, $verdetto)
  }
}

# --- Le date: un documento cambiato dopo la data che dichiara non e' affidabile ---
$v = Get-DateScadute $p.Disco $tuttiFile
$vec = @($v | Where-Object { $_.Tipo -eq 'scaduta' })
$sen = @($v | Where-Object { $_.Tipo -eq 'senza' })
if ($vec.Count -gt 0) {
  Write-Output ''
  Write-Output ("!! {0} documenti cambiati DOPO la data che dichiarano:" -f $vec.Count)
  foreach ($x in $vec) {
    Write-Output ("   {0,-44} dice {1}, toccato {2}" -f $x.Rel, $x.Dichiarata.ToString('yyyy-MM-dd'), $x.Modificata.ToString('yyyy-MM-dd'))
  }
  Write-Output "   Guarda se il contenuto e' ancora vero, POI -Timbra. Timbrare una bugia la peggiora."
}
if ($sen.Count -gt 0) {
  Write-Output ''
  Write-Output ("·  {0} documenti non dichiarano nessuna data (-Timbra ci mette quella di modifica vera)" -f $sen.Count)
  foreach ($x in ($sen | Select-Object -First 5)) { Write-Output ("   " + $x.Rel) }
}

if (-not $haMemoria) {
  Write-Output ''
  Write-Output "!! C'e' il CLAUDE.md ma non la memoria. A fine sessione:"
  Write-Output '   .\salva.ps1 -Stato "..." -DaFare "..."'
}
