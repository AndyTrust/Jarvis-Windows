# salva.ps1 — CHIUSURA: stato, errori, fatti, diario, e la pagina nel vault.
#
#   .\salva.ps1 -Errore "che cosa e' andato storto · perche' non si vedeva · come si evita"
#   .\salva.ps1 -Completato "bozza pronta" -DaFare "scrivere la relazione"
#   .\salva.ps1 -Tolto "scrivere la relazione"       da fare -> fatto
#   .\salva.ps1 -Stato "una riga di contesto sopra i due elenchi"
#   .\salva.ps1 -Fatto <slug> -Descrizione "..." -Corpo "..." -Perche "..." -Come "..."
#   .\salva.ps1 -Leggi                              cosa c'e' dentro adesso
#
# La pagina «A che punto siamo» nel vault si riscrive a OGNI salvataggio: non e'
# un flag da ricordare, e' parte della chiusura.

param(
  [string]$Cartella,
  [string]$Stato,
  [string[]]$Completato = @(),
  [string[]]$DaFare = @(),
  [string[]]$Tolto = @(),
  [string[]]$Errore = @(),
  [string]$Fatto,
  [string]$Descrizione = '',
  [ValidateSet('progetto','feedback','riferimento','utente')][string]$Tipo = 'progetto',
  [string]$Corpo = '',
  [string]$Perche = '',
  [string]$Come = '',
  [string]$Collega = '',
  [string]$Log,
  [switch]$Leggi,
  [switch]$SoloVault
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
. (Join-Path $PSScriptRoot 'comune.ps1')

$p = Trova-Progetto $Cartella

$TESTA = @"
# Memoria — $($p.Nome)

*Ultima modifica: $ORA*

Un file per fatto. Questo e' l'indice: si legge da solo, i file si aprono solo
quando servono. Lo legge /brain all'apertura di una chat.

## A che punto siamo

_(ancora niente)_

## Cosa sappiamo già

## Diario
"@

function Slug {
  param([string]$s)
  $x = ($s.ToLower().Trim() -replace '[^a-z0-9]+','-') -replace '-+','-'
  return $x.Trim('-').Substring(0, [Math]::Min(60, $x.Trim('-').Length))
}

# -- La pagina del progetto dentro il vault -----------------------------------
# Ogni progetto e' autonomo: la pagina sta dentro la cartella del progetto nel vault e parla solo di lui.
function Scrivi-PaginaVault {
  param($Prog, [string]$Testo)
  # Nessun vault configurato (o non trovato): niente da scrivere, la memoria resta in .claude\memoria\.
  if (-not $Prog.VaultRadice) { return }
  if (-not $Prog.VaultDir) {
    Write-Output "·   il progetto $($Prog.Nome) non ha una cartella nel vault: salto la pagina (vedi comune.ps1)."
    return
  }

  $sez    = Get-Sezione $Testo '## A che punto siamo'
  $err    = Get-Voci $sez '### Errori da non ripetere'
  $fatti  = Get-Voci $sez '### Fatto'
  $aperti = Get-Voci $sez '### Da fare'
  $pre    = Get-Preambolo $sez
  $pre    = ($pre -replace '(?m)^_\d{4}-\d{2}-\d{2}_\s*$','').Trim()
  $diario = Get-Sezione $Testo '## Diario'

  $rossi   = @($aperti | Where-Object { $_.Contains($ROSSO) })
  $normali = @($aperti | Where-Object { -not $_.Contains($ROSSO) })

  $b = New-Object System.Text.StringBuilder
  [void]$b.AppendLine('---')
  [void]$b.AppendLine('titolo: A che punto siamo')
  [void]$b.AppendLine('tag: [stato, brain]')
  [void]$b.AppendLine("aggiornato: $ORA")
  [void]$b.AppendLine('---')
  [void]$b.AppendLine('')
  [void]$b.AppendLine("# A che punto siamo — $($Prog.Nome)")
  [void]$b.AppendLine('')
  [void]$b.AppendLine("> Riscritta da ``/brain`` a ogni chiusura di sessione, leggendo")
  [void]$b.AppendLine('> `.claude/memoria/MEMORIA.md` nella cartella del progetto.')
  [void]$b.AppendLine('> **Non correggerla a mano**: la prossima chiusura la sovrascrive.')
  [void]$b.AppendLine('')
  if ($pre) { [void]$b.AppendLine($pre); [void]$b.AppendLine('') }

  if ($rossi.Count -gt 0) {
    [void]$b.AppendLine("## $ROSSO Quello che brucia")
    [void]$b.AppendLine('')
    foreach ($x in $rossi) { [void]$b.AppendLine("- " + ($x -replace [regex]::Escape($ROSSO), '').Trim()) }
    [void]$b.AppendLine('')
  }
  if ($normali.Count -gt 0) {
    [void]$b.AppendLine("## Da fare ($($normali.Count))")
    [void]$b.AppendLine('')
    foreach ($x in $normali) { [void]$b.AppendLine("- " + $x) }
    [void]$b.AppendLine('')
  }
  if ($fatti.Count -gt 0) {
    [void]$b.AppendLine("## Fatto ($($fatti.Count))")
    [void]$b.AppendLine('')
    foreach ($x in $fatti) { [void]$b.AppendLine("- " + $x) }
    [void]$b.AppendLine('')
  }
  if ($err.Count -gt 0) {
    [void]$b.AppendLine("## Errori da non ripetere ($($err.Count))")
    [void]$b.AppendLine('')
    [void]$b.AppendLine('Non si cancellano quando l''errore e'' corretto: sono loro che impediscono di rifarlo.')
    [void]$b.AppendLine('')
    foreach ($x in $err) { [void]$b.AppendLine("- " + $x) }
    [void]$b.AppendLine('')
  }
  if ($diario) {
    $righe = @($diario -split "`r?`n" | Where-Object { $_.Trim().StartsWith('- ') })
    if ($righe.Count -gt 0) {
      [void]$b.AppendLine('## Ultime righe di diario')
      [void]$b.AppendLine('')
      $q = $righe
      if ($righe.Count -gt 12) { $q = $righe[($righe.Count-12)..($righe.Count-1)] }
      foreach ($x in $q) { [void]$b.AppendLine($x.Trim()) }
      [void]$b.AppendLine('')
    }
  }
  [void]$b.AppendLine('---')
  [void]$b.AppendLine('')
  [void]$b.AppendLine("Il dettaglio non sta qui: sta nei fatti in ``.claude/memoria/`` dentro il progetto.")
  [void]$b.AppendLine('Questa pagina serve a te, quella memoria serve al modello — e non si copiano l''una nell''altra.')

  Scrivi-Testo $Prog.PaginaVault ($b.ToString())
  Write-Output "OK  vault: $($Prog.PaginaVault)"
  Write-Output ("    $($rossi.Count) che bruciano · $($normali.Count) da fare · $($fatti.Count) fatte · $($err.Count) errori")
}

# ---------- LEGGI ----------
if ($Leggi) {
  if (Test-Path -LiteralPath $p.File) { Write-Output (Leggi-Testo $p.File) }
  else { Write-Output '(memoria vuota)' }
  return
}

$testo = Leggi-Testo $p.File
if (-not $testo) { $testo = $TESTA }

# ---------- SOLO LA PAGINA DEL VAULT ----------
if ($SoloVault) { Scrivi-PaginaVault $p $testo; return }

$qualcosa = $Stato -or $Completato.Count -or $DaFare.Count -or $Tolto.Count -or `
            $Errore.Count -or $Fatto -or $Log
if (-not $qualcosa) {
  Write-Output 'Serve almeno -Stato, -Completato, -DaFare, -Tolto, -Errore, -Fatto o -Log.'
  Write-Output '(-SoloVault riscrive solo la pagina del vault, senza toccare la memoria.)'
  exit 1
}

$copia = Salva-Copia $p.File
if ($copia) { Write-Output "·   copia di sicurezza: .claude\memoria\.copie\$(Split-Path $copia -Leaf)" }

# ---------- UN FATTO: file suo + riga nell'indice ----------
if ($Fatto) {
  $s = Slug $Fatto
  $c = $Corpo.Trim()
  if (-not $c) { $c = '_(da scrivere)_' }
  if ($Perche) { $c += "`n`n**Perche':** " + $Perche.Trim() }
  if ($Come)   { $c += "`n`n**Come si applica:** " + $Come.Trim() }
  if ($Collega) {
    # Si separa su virgole E spazi: PowerShell legge «-Collega a,b» come un array
    # e lo consegna a un [string] gia' unito da uno spazio, quindi tagliare solo
    # sulla virgola produce un unico [[a b]] che non punta a niente.
    $link = @($Collega -split '[,\s]+' | Where-Object { $_.Trim() } | ForEach-Object { "[[" + $_.Trim() + "]]" })
    $c += "`n`nVedi " + ($link -join ' · ')
  }
  $desc = $Descrizione
  if (-not $desc) { $desc = $Fatto }
  $testoFatto = "---`nnome: $s`ndescrizione: $desc`ntipo: $Tipo`naggiornato: $ORA`n---`n`n$c`n"
  Scrivi-Testo (Join-Path $p.Memoria "$s.md") $testoFatto

  $vecchie = @((Get-Sezione $testo '## Cosa sappiamo già') -split "`r?`n" |
               Where-Object { $_.Trim() -and -not $_.Trim().StartsWith("- [$s]") })
  $riga = "- [$s]($s.md) — $desc"
  $testo = Set-Sezione $testo '## Cosa sappiamo già' ((@($vecchie) + @($riga)) -join "`n")
  Write-Output "OK  fatto salvato: .claude\memoria\$s.md"
}

# ---------- LO STATO: errori, fatto, da fare ----------
if ($Errore.Count -or $Completato.Count -or $DaFare.Count -or $Tolto.Count -or $Stato) {
  $sez = Get-Sezione $testo '## A che punto siamo'
  if ($null -eq $sez) { $sez = '' }
  $err    = @(Get-Voci $sez '### Errori da non ripetere')
  $fatti  = @(Get-Voci $sez '### Fatto')
  $aperti = @(Get-Voci $sez '### Da fare')
  $pre    = Get-Preambolo $sez

  # 🔴 La guardia, primo pezzo: la lettura e' fallita del tutto.
  # Il 6/09/2026 un salvataggio col solo --stato ha azzerato Fatto (76 voci) e
  # Da fare (25) stampando «0 fatte · 0 da fare», che sembrava un conteggio delle
  # novita' e invece era il referto di una cancellazione.
  if ($sez -match '(?m)^\s*###\s' -and ($err.Count + $fatti.Count + $aperti.Count) -eq 0) {
    Write-Output '!! MEMORIA.md ha i sottotitoli ma non ne ho letto nessuna voce: NON riscrivo.'
    Write-Output '   Guarda a mano .claude\memoria\MEMORIA.md prima di rilanciare.'
    exit 2
  }
  # Quante voci c'erano PRIMA. Si contano sul testo, non sul risultato della
  # lettura: se la lettura sbaglia, il suo conteggio sbaglia con lei.
  $vocePrima = @([regex]::Matches($sez, '(?m)^\s*-\s')).Count

  foreach ($x in $Errore) {
    $e = $x.Trim()
    if (-not $e.StartsWith($ROSSO)) { $e = "$ROSSO $e" }
    if ($err -notcontains $e) { $err += $e }
  }
  foreach ($x in $Tolto) {
    $simili = @($aperti | Where-Object { $_.ToLower().Contains($x.ToLower()) })
    if ($simili.Count -eq 0) {
      Write-Output "!! «$x» non e' in «Da fare»: non lo sposto."
      continue
    }
    foreach ($v in $simili) {
      $aperti = @($aperti | Where-Object { $_ -ne $v })
      if ($fatti -notcontains $v) { $fatti += $v }
      Write-Output "->  «$v» da fare -> fatto"
    }
  }
  foreach ($x in $Completato) { if ($fatti -notcontains $x) { $fatti += $x } }
  foreach ($x in $DaFare) {
    # se era segnata fatta torna aperta: non puo' stare in tutti e due gli elenchi
    $fatti = @($fatti | Where-Object { $_ -ne $x })
    if ($aperti -notcontains $x) { $aperti += $x }
  }

  $blocchi = New-Object System.Collections.ArrayList
  [void]$blocchi.Add("_${OGGI}_")
  if ($Stato) {
    [void]$blocchi.Add($Stato.Trim())
  } else {
    $vecchioPre = ($pre -replace '(?m)^_\d{4}-\d{2}-\d{2}_\s*$','').Trim()
    if ($vecchioPre) { [void]$blocchi.Add($vecchioPre) }
  }
  if ($err.Count)    { [void]$blocchi.Add("### Errori da non ripetere`n" + (($err    | ForEach-Object { "- $_" }) -join "`n")) }
  if ($fatti.Count)  { [void]$blocchi.Add("### Fatto`n"                  + (($fatti  | ForEach-Object { "- $_" }) -join "`n")) }
  if ($aperti.Count) { [void]$blocchi.Add("### Da fare`n"                + (($aperti | ForEach-Object { "- $_" }) -join "`n")) }

  # 🔴 La guardia, secondo pezzo: si contano le voci PRIMA e DOPO sul testo.
  # E' l'unico controllo che regge anche quando la lettura fallisce in un modo
  # che non avevo previsto — il 9/09/2026 Get-Voci restituiva un array dentro un
  # array, e ogni sezione si e' riscritta su una riga sola: nessun errore,
  # nessuna eccezione, 91 voci diventate 3. Aggiungere righe e' sempre lecito;
  # averne meno di prima non lo e' mai, perche' qui dentro non si cancella.
  $nuovaSez  = ($blocchi.ToArray()) -join "`n`n"
  $voceDopo  = @([regex]::Matches($nuovaSez, '(?m)^\s*-\s')).Count
  if ($voceDopo -lt $vocePrima) {
    Write-Output "!! prima c'erano $vocePrima voci, dopo ne resterebbero ${voceDopo}: NON riscrivo."
    Write-Output '   MEMORIA.md e'' intatto. E'' un difetto di lettura, non un dato mancante.'
    exit 3
  }
  $testo = Set-Sezione $testo '## A che punto siamo' $nuovaSez
  Write-Output "OK  stato: $($err.Count) errori · $($fatti.Count) fatte · $($aperti.Count) da fare  ($vocePrima -> $voceDopo voci)"
}

# ---------- IL DIARIO: solo in fondo ----------
if ($Log) {
  $d = Get-Sezione $testo '## Diario'
  if ($null -eq $d) { $d = '' }
  $testo = Set-Sezione $testo '## Diario' (($d + "`n- $ORA · " + $Log.Trim()).Trim())
  Write-Output 'OK  riga di diario aggiunta'
}

Scrivi-Testo $p.File ($testo.TrimEnd() + "`n")

# ---------- LA DATA DICHIARATA IN CIMA ----------
[void](Timbra-File $p.File $ORA)

# ---------- LA PAGINA DEL VAULT: sempre, non su richiesta ----------
Scrivi-PaginaVault $p (Leggi-Testo $p.File)

# ---------- LE DATE ----------
$v = @(Get-DateScadute $p.Disco | Where-Object { $_.Tipo -eq 'scaduta' })
if ($v.Count -gt 0) {
  Write-Output ''
  Write-Output "!! $($v.Count) documenti con la data scaduta:"
  foreach ($x in $v) { Write-Output ("   " + $x.Rel) }
  Write-Output '   brain.ps1 -Timbra li porta a oggi — ma prima guarda se il contenuto e'' ancora'
  Write-Output '   vero: una data fresca su un testo falso toglie l''unico segnale che c''era.'
}
