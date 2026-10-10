# Disinstallare

Ogni passo si può fare da solo. La memoria condivisa è tua: questa guida non la cancella.

```powershell
# 1. ferma il pannello e le attività pianificate
Get-NetTCPConnection -LocalPort 7777 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess }
Unregister-ScheduledTask -TaskName "Jarvis Avvio" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "Jarvis Battito" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "Jarvis Giro notturno" -Confirm:$false -ErrorAction SilentlyContinue

# 2. i collegamenti sul Desktop
$d = [Environment]::GetFolderPath("Desktop")
"Jarvis Command Center","Jarvis Orb","Talk to Jarvis","Aggiorna Jarvis" | ForEach-Object { Remove-Item (Join-Path $d "$_.lnk") -ErrorAction SilentlyContinue }
```

3. **I ganci di Claude Code.** In `%USERPROFILE%\.claude` c'è la copia `settings.json.bak-jarvis-<data>` fatta prima
   della prima installazione: puoi rimetterla al posto di `settings.json`. Oppure apri `settings.json` e togli le voci
   che nominano `jarvis_avvio.py`, `jarvis_status.py`, `guardia_comandi.py`, `connessioni_guardia.py`,
   `stato_avanzamento.py`, `conferma_salva.py`. Poi togli quei file da `%USERPROFILE%\.claude\hooks\` e la sezione «Chi usa questo PC» da
   `%USERPROFILE%\.claude\CLAUDE.md`. Le skill stanno in `%USERPROFILE%\.claude\skills\`.

4. **Le giunzioni della memoria.** Ogni `%USERPROFILE%\.claude\projects\<progetto>\memory` collegato è una giunzione.
   Togliere una giunzione non cancella i file a cui punta:

   ```powershell
   Get-ChildItem "$env:USERPROFILE\.claude\projects\*\memory" -Attributes ReparsePoint | ForEach-Object {
       $dest = $_.FullName; $_.Delete()                               # toglie solo il collegamento
       New-Item -ItemType Directory $dest | Out-Null                  # rimette una cartella normale vuota
   }
   ```

   Se vuoi riportare le note nella cartella del progetto, copiale da `<memoria>\Claude\projects\<progetto>\memory`.
   Le cartelle `memory.prima-del-collegamento-<data>` sono gli originali di prima: puoi rimetterle al posto di `memory`.
   Stessa cosa per `%USERPROFILE%\.claude\plans`.

5. **Il programma.** Cancella `%USERPROFILE%\jarvis` (contiene anche il tuo profilo e la memoria personale: copiali prima
   se ti servono) e `%USERPROFILE%\.jarvis`.

6. **I programmi installati da winget** (Python, eSpeak NG, Git) restano: toglili da Impostazioni → App se non ti
   servono. Claude Code si toglie come dice la guida ufficiale (https://code.claude.com/docs/en/setup, sezione
   «Uninstall Claude Code»).

La memoria condivisa resta dove l'avevi messa. Cancellala solo se sei sicuro.
