# Aggiornare

```powershell
cd $env:USERPROFILE\Jarvis-Windows
powershell -ExecutionPolicy Bypass -File .\AGGIORNA.ps1 -Controlla    # dice cosa cambierebbe
powershell -ExecutionPolicy Bypass -File .\AGGIORNA.ps1               # scarica e installa
```

Oppure il collegamento «Aggiorna Jarvis» sul Desktop, oppure «Aggiorna ora» nel pannello quando compare il riquadro
«Aggiornamento disponibile».

Cosa fa: `git fetch`, copia del codice attuale in `%USERPROFILE%\jarvis-copia-AAAAMMGG-HHMM`, avanti veloce del clone,
poi `INSTALLA.ps1 -Silenzioso`. Rilanciato così l'installatore tiene la memoria condivisa e il nome dell'assistente che
avevi scelto (li rilegge da `%USERPROFILE%\.jarvis\percorsi.json` e da `utente.json`).

Cosa non tocca mai: `utente.json`, `CLAUDE.md` personale, `configurazione.json`, `spazi.json`, `pannello.json`, gli
agenti, la memoria personale e quella condivisa, i report, l'assistenza.

## Tornare indietro

La copia `%USERPROFILE%\jarvis-copia-<data>` è il codice di prima. Per tornarci: chiudi il pannello, copia il contenuto
di quella cartella sopra `%USERPROFILE%\jarvis` (i tuoi file personali non sono nella copia, quindi restano i tuoi).

## Senza Git

Chi ha scaricato lo ZIP: scarica lo ZIP nuovo, estrailo sopra la cartella vecchia del repository (non sopra
`%USERPROFILE%\jarvis`), sblocca i file (`Get-ChildItem -Recurse | Unblock-File`) e rilancia `INSTALLA.ps1 -Silenzioso`.
