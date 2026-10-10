# Memoria condivisa (Windows)

Una sola memoria, letta e scritta da Claude Code, dall'assistente e dagli altri programmi (Codex, Gemini CLI, Cursor).
La crea e la collega `strumenti\collega_memoria.py`, che l'installazione lancia da sola. Gli stessi nomi valgono sul Mac.

## Dove sta e com'è fatta

Il percorso è in `%USERPROFILE%\.jarvis\percorsi.json` (chiave `memoria`). Di base è `%USERPROFILE%\Jarvis-Memoria`;
alle domande di avvio puoi scegliere una cartella in OneDrive o un vault di Obsidian che hai già.

```
<memoria>\
  Comune\Memoria.md         porta d'ingresso: profilo, regole, dove sta cosa
  <spazio>\Stato.md         uno per spazio, scritto dai ganci (più <spazio>.md, Decisioni.md, Report\)
  Diario\AAAA-MM-GG.md      il diario del giorno: Fatto, Da fare, Errori da non ripetere, con l'ora
  Report\  Sessioni\        report e una riga per ogni evento di sessione
  Claude\projects\          l'auto-memoria di Claude Code dei tuoi progetti (giunzioni)
  Claude\piani\             i piani di Claude Code (giunzione)
  AGENTS.md  GEMINI.md  CLAUDE.md   file d'ingresso per gli altri programmi
```

Le cartelle degli spazi non esistono all'inizio: le crea `crea_progetto.py` quando nasce un progetto.

## Cosa si collega e cosa no

| Cosa | Nella memoria condivisa? | Come |
|---|---|---|
| `%USERPROFILE%\.claude\projects\*\memory` | sì | giunzione (`mklink /J`, non serve l'amministratore) verso `<memoria>\Claude\projects\<progetto>\memory` |
| `%USERPROFILE%\.claude\plans` | sì | giunzione verso `<memoria>\Claude\piani` |
| `%USERPROFILE%\.claude\projects\*\*.jsonl` (le chat) | no | grandi, scritte mentre lavori, possono contenere quello che incolli: nella memoria va il riassunto |
| `settings.json`, `.credentials.json`, `.claude.json` | no | impostazioni e accessi di questo PC |

Se una cartella `memory` ha già dei file, prima si UNISCONO alla memoria condivisa. Un file con lo stesso nome e
contenuto diverso si tiene con il suffisso `.da-<nome del PC>`. L'originale resta, rinominato in
`memory.prima-del-collegamento-<data>`, e solo dopo nasce la giunzione. Niente si cancella.

## Si aggiorna da sola

Il gancio `%USERPROFILE%\.claude\hooks\stato_avanzamento.py` fa il giro meccanico per lo spazio della cartella in cui
lavori: rifà la parte automatica di `<spazio>\Stato.md` (FATTO, DA FARE ed ERRORI dalla memoria del progetto, diari
degli agenti, errori ripetuti, file toccati, ultimo commit) e aggiunge al diario del giorno solo le voci nuove. Se non
c'è niente di nuovo resta muto.

| Quando | Chi lo fa partire |
|---|---|
| fine di ogni risposta, compattazione, fine sessione | ganci `Stop`, `PreCompact`, `SessionEnd` di Claude Code |
| conferme («ok», «perfetto», «va bene», «chiuso», «fatto», «salva») | gancio `UserPromptSubmit` `conferma_salva.py`: lancia il giro e chiede all'assistente il salvataggio con giudizio di `aggiorna-memoria` |
| ogni commit e ogni push di un progetto | ganci git `post-commit` e `pre-push` (`strumenti\ganci_git.py`, messi da `crea_progetto.py` e dal giro ogni 30 minuti, senza toccare i tuoi) |
| azioni nel Command Center (agente nato, cambiato, tolto; file caricati) | il Command Center, che scrive in `MEMORIA.md` del progetto e rifà Stato e diario |
| `/aggiorna` | la skill `aggiorna-memoria` |
| ogni 15 minuti, anche a pannello spento | attività «Jarvis Battito» (`sincro\ogni30.py`) |

A mano: `PY %USERPROFILE%\.claude\hooks\stato_avanzamento.py --giro --evento <nome> --cwd <cartella>`.

## Pulizia di quello che Claude Code salva da solo

`strumenti\pulisci_claude.py` gira ogni giorno alle 06:20 (attività «Jarvis Pulizia») e dentro `/aggiorna`:

| Cosa | Regola |
|---|---|
| `projects\*\memory` | mai cancellata: si unisce alla memoria condivisa (`collega_memoria.py --solo-progetti`) |
| `projects\*\*.jsonl` più vecchie di 30 giorni (`--giorni-chat`) | riassunto nel diario del giorno, archivio compresso in `%USERPROFILE%\.jarvis\archivio-chat\`, solo dopo esce da `.claude`; archivi tenuti 180 giorni |
| `shell-snapshots`, `session-env`, `debug`, `paste-cache`, `cache\pdf-testo`, `file-history`, `todos` | tolti oltre la soglia (da 3 a 30 giorni) |
| sessioni aperte, file delle ultime 24 ore, `settings.json`, `agents`, `skills`, `hooks`, `commands`, `plugins` | mai toccati |

`--prova` dice cosa farebbe senza toccare niente. Su Windows lo script non interroga i processi delle sessioni (lì
`os.kill(pid, 0)` chiuderebbe il processo): protegge le chat con il margine delle 24 ore.

## Disinstallare

Vedi `docs\DISINSTALLARE.md`: le giunzioni si tolgono con `rmdir <giunzione>` (toglie solo il collegamento) e la
cartella `memory.prima-del-collegamento-<data>` torna al suo nome.
