# Come funziona

```
  tu ──► Claude Code (terminale)            tu ──► Command Center (browser, 127.0.0.1:7777)
            │  ganci: avvio, lavagna,                 │  chat, stato, squadra, missioni,
            │  guardie, stato dei progetti            │  scadenze, memoria, voce, lavagna
            ▼                                         ▼
     %USERPROFILE%\.claude  ◄──────────────►  %USERPROFILE%\jarvis (programma + profilo)
            │                                         │
            └──────────►  memoria condivisa  ◄────────┘
                          Comune\  <spazio>\Stato.md  Diario\  Report\  Sessioni\
                          Claude-Code\progetti\*\memory  (giunzioni)
                                   ▲
                     Codex, Gemini CLI, Cursor (AGENTS.md, GEMINI.md)
```

## Le parti

| Parte | Dove | Cosa fa |
|---|---|---|
| Command Center | `jarvis\command-center\server.py` | il pannello nel browser; usa solo la libreria standard di Python |
| Missioni | `command-center\missione.py` | un orchestratore che lancia più agenti in parallelo con `claude-agent-sdk` |
| Lavagna | `command-center\static\` e `.claude\hooks\jarvis_status.py` | mostra in tempo reale chi lavora e su cosa |
| Voce | `strumenti\talk_to_jarvis_windows.py`, `strumenti\kokoro\` | Shift destro: microfono → Whisper → Claude Code → voce |
| Orb | `strumenti\jarvis_orb_windows.py` | il cerchio sul desktop: riposo, ascolto, penso, parlo |
| Registro dei lavori | `strumenti\lavori.py`, `portiere.py` | chi lavora su cosa, chiavi per le risorse condivise |
| Battito | `sincro\ogni30.py` | ogni 15 minuti controlla memoria e sentinelle |
| Quaderno degli agenti | `strumenti\quaderno.py`, `giro_apprendimento.py` | ogni agente annota quello che impara |
| Riunioni | `strumenti\riunione.py`, skill `riunione-agenti` | il punto giornaliero di un gruppo di agenti |
| Report | `strumenti\report_pdf.py` | trasforma un resoconto in PDF |
| Memoria condivisa | `strumenti\collega_memoria.py`, gancio `stato_progetti.py` | vedi `MEMORIA-CONDIVISA.md` |

## I ganci di Claude Code

| Evento | Script | Cosa fa |
|---|---|---|
| SessionStart | `hooks\jarvis_avvio.py` | presenta l'assistente con il tuo nome e il suo, il profilo, la memoria, gli stati degli spazi |
| UserPromptSubmit, Stop, SubagentStop, Pre/PostToolUse | `jarvis\.claude\hooks\jarvis_status.py` | alimenta la lavagna |
| PreToolUse (Bash, PowerShell) | `hooks\guardia_comandi.py` | blocca i comandi irreversibili prima che partano |
| PreToolUse (Bash, PowerShell, MCP) | `hooks\connessioni_guardia.py` | controlla le connessioni verso l'esterno |
| Stop, PreCompact, SessionEnd | `hooks\stato_progetti.py` | aggiorna `<spazio>\Stato.md`, il diario, i collegamenti |

L'installatore li aggiunge a `%USERPROFILE%\.claude\settings.json` riconoscendoli dal nome dello script: i ganci che
avevi già restano, e rilanciando non si raddoppiano. Prima di scrivere fa una copia `settings.json.bak-jarvis-<data>`.
I ganci usano il Python dell'ambiente `.venv` (mai `python3`, che su Windows spesso non esiste).

## Il nome tuo e quello dell'assistente

Nessun nome è scritto nel codice. Stanno in `%USERPROFILE%\jarvis\utente.json` (`nome`, `nome_assistente`) e nel
`CLAUDE.md` personale. Il gancio di avvio li legge a ogni sessione. Per cambiarli modifica quei due file.
