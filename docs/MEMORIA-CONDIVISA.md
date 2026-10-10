# La memoria condivisa

Claude Code, l'assistente e gli altri programmi di intelligenza artificiale che usi (Codex, Gemini CLI, Cursor…)
leggono e scrivono nella stessa cartella. Così quello che hai deciso in una sessione lo trova la sessione dopo, anche
se l'hai aperta con un altro programma o su un altro PC.

## Dove sta

La sceglie la domanda di avvio numero 6. Di base `%USERPROFILE%\Jarvis-Memoria`. Può stare:
- in **OneDrive** (per esempio `%USERPROFILE%\OneDrive\Jarvis-Memoria`): la vedi da più PC;
- dentro un **vault di Obsidian** che hai già: le note diventano navigabili con i link `[[...]]`;
- in una cartella qualunque del disco.

Il percorso scelto è registrato in `%USERPROFILE%\.jarvis\percorsi.json`. Tutti i pezzi del programma leggono quel file.

## Com'è fatta

```
<memoria>\
├── Comune\Memoria.md          la porta d'ingresso: profilo, regole, elenco degli spazi
├── <spazio>\Stato.md          uno per spazio: FATTO, DA FARE, ERRORI, ultime sessioni, data e ora
├── Diario\AAAA-MM-GG.md       una riga per ogni sessione chiusa
├── Report\                    i resoconti dei lavori finiti
├── Sessioni\                  note di sessione
├── Claude-Code\progetti\<progetto>\memory\   la memoria automatica di Claude Code (giunzioni)
├── Claude-Code\piani\         i piani di Claude Code (giunzione da %USERPROFILE%\.claude\plans)
├── AGENTS.md                  ingresso per Codex, Cursor e altri harness
├── GEMINI.md                  ingresso per Gemini CLI
└── CLAUDE.md                  ingresso per Claude Code aperto in questa cartella
```

## Il collegamento: `strumenti\collega_memoria.py`

```powershell
cd $env:USERPROFILE\jarvis
.\.venv\Scripts\python.exe strumenti\collega_memoria.py              # guarda e racconta, non scrive
.\.venv\Scripts\python.exe strumenti\collega_memoria.py --applica    # crea struttura e collegamenti
```

Opzioni: `--memoria <cartella>`, `--spazi "Lavoro,Casa"`, `--harness "codex,gemini"`, `--con-sessioni`.

Cosa fa con `--applica`, sempre senza cancellare niente:
1. Crea le cartelle e i file di partenza che mancano (`Comune\Memoria.md`, `<spazio>\Stato.md`, file d'ingresso).
2. Per ogni `%USERPROFILE%\.claude\projects\<progetto>\memory` crea una **giunzione** verso
   `<memoria>\Claude-Code\progetti\<progetto>\memory`. La giunzione (`mklink /J`) non richiede l'amministratore.
   Se la cartella `memory` ha già dei file, li **unisce** alla memoria condivisa: un file con lo stesso nome e contenuto
   diverso si tiene con il suffisso `.da-<nome del PC>`. Poi rinomina l'originale in
   `memory.prima-del-collegamento-<data>` e solo dopo crea la giunzione. Ogni passo è stampato.
3. Fa lo stesso per la cache dei piani, `%USERPROFILE%\.claude\plans`.
4. Con `--harness codex` o `gemini` aggiunge una sezione «Memoria condivisa» a `%USERPROFILE%\.codex\AGENTS.md` o
   `%USERPROFILE%\.gemini\GEMINI.md`, con copia di sicurezza del file.
5. Con `--con-sessioni` copia anche le trascrizioni delle sessioni (`*.jsonl`) in `Claude-Code\sessioni\`: copia a senso
   unico, solo file nuovi o cambiati. È spenta di base perché le trascrizioni pesano e possono contenere testi privati.
6. Cerca segreti dentro la memoria e li elenca (percorso e riga, mai il valore).
7. Scrive `%USERPROFILE%\.jarvis\percorsi.json`.

Un progetto nuovo di Claude Code nasce con una cartella `memory` normale. Il gancio di fine sessione rilancia
`collega_memoria.py --applica --zitto`, quindi dalla sessione dopo anche quel progetto è nella memoria condivisa.

Le trascrizioni delle sessioni (`%USERPROFILE%\.claude\projects\<progetto>\*.jsonl`) restano dove sono: sono grandi,
cambiano a ogni messaggio e su OneDrive creerebbero conflitti. Lo stato che serve lo porta il gancio, qui sotto.

## Lo stato dei progetti si aggiorna da solo

Il gancio `%USERPROFILE%\.claude\hooks\stato_progetti.py` è installato su tre eventi di Claude Code: `Stop` (fine di
ogni risposta), `PreCompact` (prima di compattare il contesto) e `SessionEnd` (fine sessione). Legge solo la parte
nuova della trascrizione e aggiorna `<memoria>\<spazio>\Stato.md`:

| Sezione | Da dove viene |
|---|---|
| FATTO | file modificati (Edit/Write) e righe `FATTO: …` scritte da Claude nella risposta |
| DA FARE | righe `DA FARE: …`; un `FATTO: X` uguale a un `DA FARE: X` lo toglie |
| ERRORI | strumenti finiti in errore e righe `ERRORE: …` |
| Ultime sessioni | data e ora, cartella, ultima richiesta, evento |

Lo spazio si trova così: lo spazio la cui cartella contiene la cartella di lavoro; se nessuna, quello il cui nome compare
nel percorso; altrimenti «Generale». Il gancio toglie token e chiavi dai testi prima di scrivere, non blocca mai Claude
Code (esce sempre con 0) e scrive i suoi errori in `%USERPROFILE%\.jarvis\stato-ganci.log`.

Prova a mano, senza Claude Code:

```powershell
.\.venv\Scripts\python.exe $env:USERPROFILE\.claude\hooks\stato_progetti.py --prova <trascrizione.jsonl> --cwd <cartella>
```

## La skill `aggiorna-memoria`

Installata in `%USERPROFILE%\.claude\skills\aggiorna-memoria`. Due modalità:
- **progetto**: «a che punto siamo», «cosa abbiamo fatto», «errori», «handoff» su un progetto;
- **trasversale**: «aggiorna memoria», «pulizia memoria», «consolida la memoria» su tutti gli spazi.

Mai sovrascrivere alla cieca, mai cancellare senza un sì esplicito. Dettagli nel file `SKILL.md` della skill.

## Regole

- Una sola fonte per ogni fatto: si corregge la nota che c'è, non si aggiungono doppioni.
- Data e ora sempre, `AAAA-MM-GG HH:MM`.
- Nessun segreto nella memoria: stanno solo in `%USERPROFILE%\.env.jarvis`.
- Gli spazi non si mescolano.

## Cosa non è stato provato su un Windows vero

Le giunzioni (`mklink /J`) sono state scritte seguendo la documentazione di Windows ma provate solo con collegamenti
simbolici su un altro sistema. Se una giunzione non si crea (per esempio su un disco di rete o FAT32), lo script lo
dice con «ERRORE» e rimette a posto la cartella originale. In quel caso tieni la memoria su un disco NTFS locale o in
OneDrive.
