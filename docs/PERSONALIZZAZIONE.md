# Personalizzare Jarvis

L'installatore crea tutto già funzionante e ti fa poche domande per costruire il tuo profilo. Qui c'è quello che **puoi cambiare a
piacere**, dove sta e come. I file personali stanno nella cartella installata (`%USERPROFILE%\jarvis`) e **non vengono mai
sovrascritti** rilanciando `INSTALLA.ps1` (a meno di `-RifaiFilePersonali`, che li rifà dai modelli e perde le tue modifiche).

| Cosa | File | Come |
|---|---|---|
| Come Jarvis ti chiama e chi sei | `utente.json` | `nome`, `ruolo` (il tuo lavoro), `vita_privata`, `personalita` (il tono), `uso` (come lo usi), `battuta_lunedi` (`false` per spegnerla), `memoria_dir`, `vault_dir` (facoltativo, vedi sotto). Vale dalla prossima sessione di Claude Code. |
| Come si comporta (tono, regole) | `CLAUDE.md` | È il primo file che Jarvis legge. Scrivi in italiano semplice; ogni regola deve spiegare il *perché*. |
| Il tuo profilo esteso | `.claude/memoria-<nome>/MEMORIA.md` | Lavoro, vita privata, preferenze: aggiornalo quando cambia qualcosa, o chiedi a Jarvis di farlo. |
| Porta, siti da tenere d'occhio, comandi rapidi, modo chat | `command-center/configurazione.json` | Riavvia il pannello (o rilancia «Jarvis Avvio»). |
| I tuoi progetti e i loro agenti | `command-center/spazi.json` | Vedi sotto. |
| La lavagna (posizioni e fili) | `command-center/pannello.json` | Si modifica **dalla lavagna** (trascina, collega, «Nuova nota»); non serve toccare il file. |
| Gli agenti | `.claude/agents/*.md` | Si modificano dalla scheda dell'agente nel pannello o a mano (frontmatter + istruzioni). |
| La memoria | `.claude/memoria-<nome>/` e la memoria condivisa | La riempiono l'assistente e i ganci. Puoi leggerla e correggerla a mano. |

## Lavoro e vita privata

Jarvis li tratta come due terreni distinti e non porta un fatto dall'uno all'altro se non glielo chiedi. Un buon modo di usarlo:

- **Lavoro:** un progetto per cartella, ciascuno con la sua memoria (`/brain` a inizio sessione, salvataggio a fine).
- **Vita privata:** promemoria, scadenze personali (`Scadenze personali.md`), cose da ricordare: stanno nella tua memoria personale.
- Se vuoi un tono diverso nei due ambiti, scrivilo in `CLAUDE.md` («al lavoro sii formale, nel privato più leggero»).

## Aggiungere un progetto con i suoi agenti

Si parte da zero. Un progetto nasce quando lo chiedi all'assistente, con `/nuovo-progetto <nome>` in Claude Code o con
«＋ Nuovo progetto» nella pagina Progetti del Command Center: `strumenti\crea_progetto.py` crea la voce in `spazi.json`,
la cartella con `File\`, la memoria, `Stato.md` e il capogruppo `<id>-ceo`. Gli specialisti li crea il capogruppo con
`strumenti\crea_agente.py`, uno alla volta. Un agente nuovo si invoca per nome dalla sessione di Claude Code successiva
(lavagna e Missioni lo vedono subito). Guida completa: `docs\wiki\Progetti-e-agenti.md`.

## Obsidian (facoltativo)

Se usi Obsidian, scrivi in `utente.json` il percorso del tuo vault in `vault_dir` (la cartella che contiene `.obsidian`): la skill
`brain` riscriverà a ogni chiusura la pagina «A che punto siamo» di ogni progetto, se il vault ha una cartella con il suo nome.
Il dettaglio è in `~/.claude/skills/brain/riferimenti/vault.md`. Senza vault non cambia nulla.

## Voce

- Shift destro accende/spegne il microfono. Se non parla, controlla che in `strumenti\kokoro\` ci siano `kokoro-v1.0.onnx` e
  `voices-v1.0.bin` (rilancia `INSTALLA.ps1` senza `-SenzaModelliVoce`) e che eSpeak NG sia installato.
- Il modello Whisper («small») si scarica da solo al primo ascolto.

## Come parlano gli agenti

Ogni agente ha due manopole indipendenti, da 0 a 3, più un tono libero: **serietà** (leggero, pacato, professionale,
rigoroso) e **umorismo** (nessuno, misurato, vivace, sfacciato). Si cambiano dalla scheda dell'agente sulla lavagna, o quando
lo crei. Il Command Center le scrive nel profilo (`serieta:`, `umorismo:`, `tono:`) e in un blocco «Come parli» dentro il
testo, così l'agente le sente davvero. Per dare un valore di partenza a tutti gli agenti che non ce l'hanno:
`python strumenti\imposta_come_parla.py` (mostra) e poi `--applica` (scrive). Rilanciarlo non cambia niente.

## Pulire ~/.claude

`python strumenti\pulisci_claude.py` mostra le chat di Claude Code più vecchie di 7 giorni, i testi dei PDF e gli incollati
vecchi; con `--applica` li toglie (mai l'auto-memoria, mai le chat toccate nelle ultime 24 ore). Non parte da solo: prima
salva in memoria quello che ti serve.

## Cambiare nome o spostare l'installazione

- Nome e profilo: `utente.json`, `CLAUDE.md` e `.claude/memoria-<nome>/MEMORIA.md` (e il testo del saluto nella lavagna, che è una
  nota che puoi rinominare).
- Spostare: rilancia `INSTALLA.ps1 -Destinazione D:\nuovo` (copia il tuo `pannello.json`, `spazi.json` e `configurazione.json` prima se vuoi tenerli).

## Disinstallare

Cancella la cartella installata, le attività «Jarvis Avvio» e «Jarvis Battito» (Utilità di pianificazione), i tre collegamenti sul
Desktop e i sette ganci di Claude Code in `~/.claude/settings.json` (cerca `jarvis_avvio.py` e `jarvis_status.py`; l'installatore
ha lasciato una copia `settings.json.bak-jarvis-…`).
