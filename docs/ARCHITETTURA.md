# Architettura

```
                    ┌────────────────────────── Claude Code (il cervello) ──────────────────────────┐
  tu ──────────────►│  chat / missioni / agenti (esecutore, ricercatore-web, agenti dei progetti)  │
                    └───────▲──────────────────────────────┬──────────────────────────┬────────────┘
                            │ SessionStart                  │ ganci (hook)             │ SDK
        ~/.claude/hooks/jarvis_avvio.py                      ▼                          ▼
        (carica CLAUDE.md, profilo e memoria    .claude/hooks/jarvis_status.py   command-center/missione.py
         dell'utente, battuta del lunedì)        scrive backtalk/.jarvis_status   (orchestratore + esperti in parallelo)
                                                         │  (la lavagna in tempo reale)
                                                         ▼
   Orb (desktop) ◄────────────────────────  COMMAND CENTER  command-center/server.py  http://127.0.0.1:7777
   Talk to Jarvis (Shift destro)             ├─ pagine: Chat · Stato · Squadra · Missioni · Scadenze · Memoria · Voce · Lavagna
   Whisper → Claude → voce Sara              ├─ raccoglitori (ogni pochi secondi): stato, agenti, memoria, comunicazioni…
                                             └─ flusso in tempo reale (SSE) verso la pagina
```

## Le parti

| Parte | Dove | Cosa fa |
|---|---|---|
| **Command Center** | `command-center/server.py`, `static/` | Il pannello. Solo libreria standard di Python. Legge `configurazione.json`, `spazi.json`, `pannello.json`. |
| **Missioni** | `command-center/missione.py` | Un processo con `claude-agent-sdk`: un orchestratore lancia in parallelo gli esperti dei progetti. `conferme.py` decide cosa chiede il tuo sì (l'irreversibile). |
| **Spazi e agenti** | `command-center/spazi.py`, `spazi.json` | Spazio → progetti → agenti. Gli agenti sono i file `<progetto>/.claude/agents/*.md`. |
| **Lavagna in tempo reale** | `.claude/hooks/jarvis_status.py` → `backtalk/.jarvis_status` | I ganci di Claude Code scrivono chi lavora e chi ha lanciato chi. Il pannello lo legge e accende i fili. |
| **Voce** | `strumenti/talk_to_jarvis_windows.py`, `strumenti/kokoro/` | Shift destro accende/spegne il microfono → Whisper locale → Claude → voce Sara (Kokoro), tutto sul PC. |
| **Orb** | `strumenti/jarvis_orb_windows.py` | Il cerchio sul desktop: riposo, ascolto, penso, parlo, lavoro. Menu con tasto destro. |
| **Battito** | `sincro/ogni30.py`, `controlla.py` | Ogni 15 minuti controlla che la memoria dei progetti sia aggiornata e ne tiene copia. |
| **Registro lavori** | `strumenti/lavori.py`, `portiere.py`, `agenti.py`, `sentinella.py` | Chi tiene quali risorse, sessioni aperte, pulizia dei processi fantasma. |
| **Memoria** | `.claude/memoria-<utente>/` | Memoria persistente di chi usa il PC: il profilo, un indice `MEMORIA.md` e un file per fatto. |
| **Skill «brain»** | `~/.claude/skills/brain/` | La memoria di ogni progetto: a inizio sessione dice a che punto siamo e quali errori non ripetere, a fine sessione salva. |

## I file personali (creati da `modelli-personali/`)

`utente.json` (nome, lavoro, vita privata, personalità, uso, cartella della memoria) · `CLAUDE.md` (come si comporta Jarvis) ·
`command-center/configurazione.json` · `spazi.json` · `pannello.json` (la lavagna) · `.claude/agents/*.md` ·
`.claude/memoria-<utente>/`. Sono creati **solo se mancano** e non entrano mai in git.

## Come funziona il collegamento a Claude Code

`INSTALLA.ps1` lancia `claude-config/installa_claude.py`, che aggiunge a `~/.claude/settings.json` (dopo una copia di
sicurezza) sette ganci, riconosciuti dal nome dello script così che lo si possa rilanciare senza duplicati:

| Evento | Script | Serve a |
|---|---|---|
| `SessionStart` | `~/.claude/hooks/jarvis_avvio.py` | carica identità, profilo e memoria dell'utente; il lunedì l'ordine della battuta |
| `UserPromptSubmit`, `Stop`, `SubagentStop` | `jarvis_status.py` | la lavagna sa quando Jarvis lavora e quando smette |
| `PreToolUse` / `PostToolUse` su `Agent` | `jarvis_status.py` | la lavagna sa quale agente è stato lanciato e quando ha finito |
| `PostToolUse` (tutti) | `jarvis_status.py` | «cosa sta facendo adesso» |

## Regole di separazione della memoria

1. La memoria di un utente non si carica mai in un'altra installazione né si copia nella memoria di un altro.
2. Ogni progetto ha la sua memoria dentro la sua cartella (`.claude/memoria/`): i fatti non passano da un progetto all'altro.
3. Lavoro e vita privata sono due terreni distinti: si incrociano solo se lo chiede l'utente.
