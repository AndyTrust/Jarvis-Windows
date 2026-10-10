# Problemi comuni su Windows

## «L'esecuzione di script è disabilitata nel sistema» (ExecutionPolicy)

Windows blocca gli script PowerShell scaricati. Due strade:
- lancia sempre con `powershell -ExecutionPolicy Bypass -File .\INSTALLA.ps1` (vale solo per quel comando);
- oppure, una volta sola per il tuo utente: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Se hai scaricato lo ZIP, i file portano il segno «scaricato da internet»: `Get-ChildItem -Recurse | Unblock-File`
nella cartella del repository.

## Antivirus e SmartScreen

- SmartScreen può fermare un `.ps1` o un collegamento appena creato: «Ulteriori informazioni» → «Esegui comunque»,
  solo se il file viene da questo repository.
- Alcuni antivirus segnalano `pynput` (legge la tastiera per il tasto Shift destro) o i processi Python senza finestra
  (`pythonw.exe`). Non sono virus: aggiungi un'eccezione per la cartella `%USERPROFILE%\jarvis` se serve.
- L'antivirus può rallentare molto `pip install`: è normale, aspetta.

## `claude` non viene riconosciuto

Chiudi e riapri il terminale dopo l'installazione. Se non basta, la cartella `%USERPROFILE%\.local\bin` non è nel PATH:
Impostazioni → Sistema → Informazioni → Impostazioni di sistema avanzate → Variabili d'ambiente → Path → Nuovo.
La guida ufficiale ha una sezione apposta («Fix your PATH», https://code.claude.com/docs/en/troubleshoot-install).

## `python` apre il Microsoft Store

È il segnaposto di Windows, non un Python vero. L'installatore lo riconosce e installa Python 3.12 con winget. Per
toglierlo: Impostazioni → App → Impostazioni app avanzate → Alias di esecuzione delle app → spegni «python.exe» e
«python3.exe».

## Percorsi lunghi

Windows limita i percorsi a 260 caratteri, e le librerie Python a volte li superano. Per toglierlo (serve
l'amministratore, una volta sola):

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
git config --global core.longpaths true
```

Poi riavvia. In alternativa installa in una cartella corta (`-Destinazione C:\jarvis`).

## Proxy aziendale

Se il PC esce su internet da un proxy:

```powershell
$env:HTTPS_PROXY = "http://proxy.azienda.example:8080"
$env:HTTP_PROXY  = $env:HTTPS_PROXY
git config --global http.proxy $env:HTTPS_PROXY
```

`pip`, `git`, `winget` e Claude Code leggono queste variabili. Per renderle fisse: Variabili d'ambiente dell'utente.
Un proxy che ispeziona HTTPS richiede il certificato aziendale: chiedilo al tuo reparto informatico.

## Le giunzioni della memoria non si creano

`mklink /J` funziona su dischi NTFS locali. Non funziona su dischi di rete, chiavette FAT32 o exFAT. Tieni la memoria
condivisa su un disco locale o in OneDrive. Lo script lo dice con una riga «ERRORE» e rimette a posto la cartella.

## OneDrive e file «solo online»

Con «File su richiesta» attivo, una nota può essere solo nella nuvola e aprirsi lentamente la prima volta. Per la
memoria condivisa: tasto destro sulla cartella → «Mantieni sempre su questo dispositivo».

## La voce non parla o non sente

Vedi `docs\VOCE.md`. In breve: `VERIFICA.ps1` controlla modelli e librerie; il microfono va permesso in Impostazioni →
Privacy e sicurezza → Microfono → «Consenti alle app desktop».
