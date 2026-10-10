# imposta-affiliazione.ps1 — mette il link di affiliazione della VPS facoltativa in tutti i documenti.
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\imposta-affiliazione.ps1          sostituisce e dice dove
#   powershell -ExecutionPolicy Bypass -File .\scripts\imposta-affiliazione.ps1 -Prova   dice cosa cambierebbe
#
# Fonte unica: docs\affiliazione.txt (prima riga che non comincia con «#»). Nei documenti sostituisce il segnaposto
# {{LINK_AFFILIAZIONE_VPS}} e il link applicato la volta prima (docs\affiliazione-applicata.txt).
# Stessa logica di scripts\imposta_affiliazione.py.
param([switch]$Prova)
$ErrorActionPreference = "Stop"
$Radice = Split-Path -Parent $PSScriptRoot
$Segnaposto = "{{LINK_AFFILIAZIONE_VPS}}"
$Fonte = Join-Path $Radice "docs\affiliazione.txt"
$Applicata = Join-Path $Radice "docs\affiliazione-applicata.txt"
$utf8 = New-Object System.Text.UTF8Encoding($false)

$righe = @([IO.File]::ReadAllLines($Fonte, [Text.Encoding]::UTF8) | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith("#") })
if ($righe.Count -eq 0 -or -not $righe[0].StartsWith("https://")) { Write-Host "$Fonte : manca il link (una riga che comincia con https://)" -ForegroundColor Red; exit 1 }
$nuovo = $righe[0]
$vecchio = ""
if (Test-Path $Applicata) { $vecchio = ([IO.File]::ReadAllText($Applicata, [Text.Encoding]::UTF8)).Trim() }

$file = @()
foreach ($f in @("README.md", "INIZIA-QUI.md", "CLAUDE.md")) { $p = Join-Path $Radice $f; if (Test-Path $p) { $file += Get-Item $p } }
$file += @(Get-ChildItem (Join-Path $Radice "docs") -Filter *.md -File -ErrorAction SilentlyContinue)
$file += @(Get-ChildItem (Join-Path $Radice ".claude\commands") -Filter *.md -File -ErrorAction SilentlyContinue)

$cambiati = 0
foreach ($f in ($file | Sort-Object FullName)) {
    $t = [IO.File]::ReadAllText($f.FullName, [Text.Encoding]::UTF8)
    $n = $t.Replace($Segnaposto, $nuovo)
    if ($vecchio -and $vecchio -ne $nuovo) { $n = $n.Replace($vecchio, $nuovo) }
    if ($n -ne $t) {
        $cambiati++
        $rel = $f.FullName.Substring($Radice.Length + 1)
        if ($Prova) { Write-Host "cambierebbe: $rel" } else { [IO.File]::WriteAllText($f.FullName, $n, $utf8); Write-Host "aggiornato: $rel" }
    }
}
if (-not $Prova) { [IO.File]::WriteAllText($Applicata, $nuovo + "`n", $utf8) }
$esito = "aggiornati"; if ($Prova) { $esito = "da aggiornare" }
Write-Host "$cambiati documenti $esito; link: $nuovo"
