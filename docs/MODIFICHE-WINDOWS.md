# Come funziona su Windows (e i limiti noti)

Questo Jarvis è scritto per **Windows**: ogni pezzo che dipende dal sistema operativo (processi, voce, finestre, percorsi) usa
gli strumenti di Windows e non presuppone nient'altro sul PC oltre a Python e Claude Code.

## Come sono fatti i pezzi che dipendono dal sistema

| Cosa | Come funziona su Windows |
|---|---|
| Ascolto e voce | `talk_to_jarvis_windows.py`: Shift destro → Whisper locale → Claude → voce Sara (Kokoro) |
| Volto sul desktop | l'**orb** `jarvis_orb_windows.py` (finestra a strati con logo e stati) |
| Elenco dei processi | lettura con CIM/PowerShell (con cache di 3 s), in `server.py` |
| «Questo processo è vivo?» | elenco processi (su Windows `os.kill(pid, 0)` **termina** il processo!) |
| Fermare una missione | `taskkill /T /F` |
| `PATH` | il PATH vero di Windows + `~\.local\bin` |
| Python per le missioni | ambiente `.venv` della cartella di Jarvis con `claude-agent-sdk` |
| Codifica dei file | UTF-8 esplicito ovunque (accenti ed emoji) |
| Interruttori Voce e Orb | accendono e spengono i processi veri e mostrano lo stato reale |
| Finestra del pannello | `--app` a schermo intero; sotto i 1100 px il pannello destro non ruba una riga di griglia |
| Catena vocale | Whisper → Claude → Kokoro, tutto locale |
| Assistenza a distanza | tunnel ssh dentro WSL (`wsl.exe -e sh -s`, script su stdin, chiusura dei processi Linux esplicita e verificata), tmate dentro WSL come riserva, blocco del registro con `msvcrt`; si accende con il tasto «Attiva assistenza», vedi `docs/ASSISTENZA.md` |

## Caratteristiche di questa versione

- **Lavagna** con gruppi (Memoria, Agenti dell'utente, e uno per ogni progetto che aggiungi) e **sinapsi** che accende tutto
  il percorso, blu all'andata e verde al ritorno; il gancio riconosce l'agente anche dai percorsi Windows (`agents\<nome>.md`)
  e chiude gli agenti rimasti attivi.
- **Battuta del lunedì** una volta a settimana, mai ripetuta, con registro (`battute-lunedi.md`); si spegne con
  `"battuta_lunedi": false` in `utente.json`.
- **Memoria per utente** con il tuo profilo (lavoro, vita privata, tono, uso) e **memoria per progetto** (skill `brain`).
- **Installatore** ripetibile con verifica, e **modelli personali** (niente nomi o percorsi scritti a mano nel codice).

## Limiti noti

- Un agente **nuovo** si invoca per nome solo dalla sessione di Claude Code successiva alla sua creazione.
- Serve **Claude Code** con il login fatto: senza, chat, missioni e agenti non rispondono (il pannello lo dice: «login mancante»).
- Il primo ascolto scarica il modello Whisper «small» (~500 MB); la voce Kokoro è scaricata dall'installatore (~350 MB).
- `sentinella.py` usa `fcntl` (solo Unix): su Windows non si importa e la **sentinella** (pulizia automatica dei processi fantasma e rapporto
  di controllo) è di fatto spenta: la scheda Stato mostra «nessuna anomalia» senza aver controllato. Da portare.
