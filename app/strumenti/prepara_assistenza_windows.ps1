# prepara_assistenza_windows.ps1 - ora e' un rimando: il comando unico e' ASSISTENZA.ps1 (stessa cartella).
#   -SoloControlla  controlla e basta       -Distro NOME  distribuzione WSL da usare
param([switch]$SoloControlla, [string]$Distro = "", [string]$Destinazione = "")
$qui = Split-Path -Parent $MyInvocation.MyCommand.Path
$a = @()
if ($SoloControlla) { $a += "-SoloControlla" } else { $a += "-SoloPrepara" }
if ($Distro) { $a += @("-Distro", $Distro) }
& (Join-Path $qui "ASSISTENZA.ps1") @a
exit $LASTEXITCODE
