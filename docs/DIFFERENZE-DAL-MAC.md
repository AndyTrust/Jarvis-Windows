# Differenze da Jarvis per Mac

Questa distribuzione è allineata a Jarvis per Mac 0.6.0 (2026-10-09). Il codice comune è lo stesso; ogni comportamento
diverso sta dietro `sys.platform == "win32"`. Qui cosa è passato, cosa è stato sostituito e cosa resta solo sul Mac.

## Passato dal Mac nell'aggiornamento del 2026-10-10

| File | Cosa porta |
|---|---|
| `command-center/server.py` | lavori fermati con «■ Ferma» chiusi come scelta e non come errore; fusione a tre vie con le parti Windows (3 conflitti risolti tenendo `ferma_lavoro_in_corso` e i cicli di Windows) |
| `command-center/static/app.js.tpl` | «Ricomincia» pulisce anche le notifiche dei fili uniti; lo Stop non accende il bollino rosso |
| `command-center/static/index.html` | fusione a tre vie pulita |
| `command-center/attivita.py`, `static/ponte.js`, `static/stop-chat.js`, `static/dettato.js`, `static/mobile.css` | registro delle attività, ponte, Stop della chat, dettato stabile, grafica mobile |
| `command-center/static/dots.js` e `static/dots/*` | dieci personaggi nuovi con il mestiere (licenza MIT, attribuzione inclusa) |
| `strumenti/quaderno.py` | riprova la lettura quando OneDrive risponde «risorsa occupata» |
| `strumenti/report_pdf.py` | aggiornamenti del PDF dei report |
| agente `ricercatore-web` (modello) | profilo aggiornato |

## Nuovo solo in questa distribuzione

| File | Cosa fa |
|---|---|
| `CLAUDE.md`, `.claude/commands/inizia.md`, `INIZIA-QUI.md` | prima apertura in modalità piano con le domande di avvio |
| `INSTALLA.ps1 -DaRisposte` | installa dalle risposte approvate; scrive `installato.json` |
| `strumenti/collega_memoria.py` (riscritto) | memoria condivisa con giunzioni, unione senza perdite, file d'ingresso per gli harness |
| `claude-config/hooks/stato_avanzamento.py`, `conferma_salva.py` | stessi ganci del Mac: stato e diario aggiornati da soli |
| skill `aggiorna-memoria` neutra | percorsi da `percorsi.json`, comandi `python` e `%USERPROFILE%` |
| `CONTROLLA-PULIZIA.py` (rinforzato) | marcatori, segreti, IP pubblici, mail, telefoni, percorsi personali |
| attività «Jarvis Giro notturno» | al posto del lavoro launchd del Mac alle 06:40 |

## Sostituzioni per Windows

| Sul Mac | Su Windows |
|---|---|
| launchd (`~/Library/LaunchAgents/com.jarvis.*`) | Utilità di pianificazione: «Jarvis Avvio», «Jarvis Battito», «Jarvis Giro notturno» |
| osascript, finestre del Terminale `.command` | script PowerShell in `avvio\`, processi senza finestra (`senza_finestre.py`, `pythonw.exe`) |
| collegamenti simbolici | giunzioni `mklink /J` (senza amministratore) |
| `python3` | il Python di `.venv` (`.venv\Scripts\python.exe`) |
| `os.kill(pid, 0)`, `pgrep`, `lsof` | `strumenti/processi.py` e la tabella dei processi di Windows |
| `fcntl` | lucchetti a file |
| voce macOS | Talk to Jarvis con Whisper e Kokoro, Shift destro |
| `Brewfile` | winget (Python, eSpeak NG, Git) |

## Solo sul Mac (non portato, e perché)

| Cosa | Motivo |
|---|---|
| `strumenti/mac.py`, `Brewfile`, `launchd/`, `routine_salva.py`, `routine_orari.py` | specifici di macOS |
| `chat_ponte.py`, `incarichi_ponte.py`, `attivita_ponte.py`, `fonte_vps.py` attivo | ponti fra Mac e server dell'autore |
| ponte del telefono, `strumenti/latenza/*`, `costruisci_grafo_regole.py` | lato server del telefono: sta nel repository del telefono |
| agenti personali dell'autore (ricerca finanziaria, notifiche sul telefono) | dati e scopi personali |
| strumenti di posta dell'autore, strumenti dei suoi siti e dei suoi database | dati personali e infrastruttura privata |
| `vps/`, `docker/`, backup del server | infrastruttura privata |
| memoria, vault, riunioni, sessioni, registri delle attività | dati personali |
| uno strumento del gestionale dell'autore (era nel repository del 2026-10-05) | dati di un'azienda precisa: tolto dalla distribuzione |

## Neutralizzazione del 2026-10-10

Il repository del 2026-10-05 conteneva ancora nomi di cartelle, servizi e risorse dell'autore che il controllo di allora
non cercava (nomi di risorse, cartelle locali, l'indirizzo del server per l'assistenza). Sono stati sostituiti con
nomi generici (`<nome-progetto>`, `database`, `.jarvis-locale`…) in modo coerente in tutto il codice. L'assistenza a
distanza ora parte vuota: chi offre assistenza compila `assistenza-tunnel.json` e `assistenza-chiave-pubblica.txt`.
