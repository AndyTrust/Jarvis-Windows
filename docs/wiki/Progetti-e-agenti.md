# Progetti e agenti (Windows)

L'assistente parte vuoto. Dopo l'installazione non ci sono progetti, spazi, capogruppo o specialisti. Ci sono solo
l'assistente, i due aiutanti di casa (`esecutore`, `ricercatore-web`), i ganci, le skill e il Command Center con le
pagine vuote («Nessun progetto ancora: di' a <assistente> di crearne uno»). Progetti e agenti nascono dalle tue
richieste, uno alla volta. Gli stessi comandi e gli stessi file valgono sul Mac.

Qui sotto `J` è la cartella dell'assistente (di base `%USERPROFILE%\jarvis`) e `PY` è il suo interprete
(`J\.venv\Scripts\python.exe`). Gli script usano solo la libreria standard, quindi va bene anche `python`.

## Una sola fonte

| Cosa | Dove |
|---|---|
| Elenco di spazi e progetti | `J\command-center\spazi.json` |
| Schede degli agenti | `<cartella del progetto>\.claude\agents\<nome>.md` |
| Diari degli agenti | `<cartella del progetto>\.claude\memoria\agenti\<nome>.md` |
| File che carichi | `<cartella del progetto>\File\`, elencati in `<cartella del progetto>\Indice-file.md` |
| Memoria del progetto | `<cartella del progetto>\.claude\memoria\MEMORIA.md` (Fatto, Da fare, Errori da non ripetere) |
| Stato dello spazio | `<memoria>\<spazio>\Stato.md` (con `<spazio>.md`, `Decisioni.md`, `Report\`) |
| Diario del giorno | `<memoria>\Diario\AAAA-MM-GG.md` |

Tutto il resto si rilegge da qui: lavagna, menu agenti, pagina «Progetti», Missioni, riunioni, giro notturno e
`Stato.md`. Il Command Center guarda questi file ogni 2 secondi. Un progetto o un agente creato dalla riga di comando
o dalla chat compare sulla lavagna e nel menu da solo, senza ricaricare: nelle prove è comparso tra 0,4 e 2,1 secondi.
`<memoria>` è la chiave `memoria` di `%USERPROFILE%\.jarvis\percorsi.json` (di base `%USERPROFILE%\Jarvis-Memoria`).
I progetti nuovi nascono nella chiave `progetti` (di base `%USERPROFILE%\Progetti`).

## Come nasce un progetto

Lo dici a parole («apri il progetto Sito Vetrina», «mi segui anche il ricettario?») o scrivi `/nuovo-progetto <nome>`
in Claude Code. La skill `nuovo-progetto` controlla che non esista, la prima volta ti mostra il piano e poi lo crea:

```powershell
PY J\strumenti\crea_progetto.py "Sito Vetrina" --descrizione "sito di presentazione" --prova   # cosa farebbe
PY J\strumenti\crea_progetto.py "Sito Vetrina" --descrizione "sito di presentazione"
PY J\strumenti\crea_progetto.py "Ricettario" --spazio "Cucina" --cartella "D:\Lavori\Ricette"   # cartella che c'è già
PY J\strumenti\crea_progetto.py --elenco
```

Crea solo quello che manca. Rilanciarlo non rifà niente, e ogni file cambiato ha prima una copia `.bak-AAAAMMGG-HHMMSS`.
- la voce in `spazi.json` (uno spazio nuovo con il nome del progetto, se non scrivi `--spazio`);
- `<memoria>\<spazio>\` con `<spazio>.md`, `Stato.md`, `Decisioni.md` e `Report\`;
- la cartella del progetto con `File\`, `Indice-file.md`, `.claude\memoria\MEMORIA.md` e `.claude\memoria\agenti\`;
- il capogruppo `.claude\agents\<id>-ceo.md`, dal modello unico, con il suo diario;
- se la cartella è un repository git, i ganci `post-commit` e `pre-push` che salvano lo stato a ogni commit e push.
  Un gancio tuo resta: il blocco di Jarvis va in testa e non cambia l'esito.

Se in `%USERPROFILE%\.jarvis\risposte-avvio.json` c'è `"creazione": "automatica"`, l'assistente crea senza mostrarti
prima il piano. Dal Command Center lo stesso lavoro lo fanno «＋ Nuovo progetto» (pagina Progetti) e «＋ Nuovo gruppo»
(lavagna): passano dallo stesso script.

## Come nasce un agente

Ogni progetto ha sempre un capogruppo. Gli specialisti li crea lui, uno alla volta, quando serve una competenza. Puoi
crearli anche tu: «mi serve qualcuno che scriva i testi», `/nuovo-agente "Sito Vetrina" copywriter`, oppure
«＋ Specialista» nella pagina del progetto.

```powershell
PY J\strumenti\crea_agente.py "Sito Vetrina" copywriter --missione "scrive i testi delle pagine partendo dai file in File/" `
   --modello sonnet --strumenti "Read, Grep, Glob" --limiti "non pubblica niente" --prova
```

Lo script controlla le regole:
- nessun agente senza una missione chiara (almeno 25 caratteri, diversa dal ruolo);
- haiku esegue comandi già scritti, sonnet ricerca, scrive e verifica (predefinito), opus solo per programmare
  (serve `--programma` o una missione che parla di codice);
- un progetto senza capogruppo si rifiuta: prima `crea_progetto.py`.

La scheda contiene missione, modello, strumenti, limiti, memoria e il diario obbligatorio. L'agente lo legge all'avvio
(`quaderno.py leggi <nome>`) e prima di chiudere scrive le tre sezioni fisse con data e ora:
`quaderno.py scrivi <nome> --fatto "…" --da_fare "…" --errore "…"`. I diari finiscono da soli nello `Stato.md` dello
spazio. Lo stesso errore scritto in due giorni diversi compare come «⚠ ERRORI RIPETUTI (da segnalare al proprietario)».

## I file del progetto

Carichi i file dalla pagina del progetto («Carica file», fino a 50 MB l'uno) oppure li copi a mano in
`<cartella>\File\`. `Indice-file.md` si riscrive da solo con nome, data di arrivo, tipo e peso. Lo aggiorna il Command
Center entro 2 secondi e, a pannello spento, l'attività «Jarvis Battito». Il capogruppo lo legge all'inizio di ogni lavoro.

## Le azioni finiscono da sole nella memoria

Quando un agente nasce, cambia o viene tolto, e quando arrivano o spariscono file, il Command Center scrive una riga
con data e ora in `MEMORIA.md` del progetto (sezione Fatto). Rifà poi `Stato.md` dello spazio e il diario del giorno.
Non c'è niente da copiare a mano.

## Cambiare, togliere, spostare, archiviare

| Cosa | Riga di comando | Command Center |
|---|---|---|
| Missione, modello, strumenti, limiti | `crea_agente.py "<progetto>" <nome> --modifica --missione "…" --modello …` | pagina Progetti, scheda dell'agente, «Salva la scheda» |
| Nome di un agente | `crea_agente.py "<progetto>" <nome> --rinomina <nuovo>` | campo «Nome» della scheda |
| Diario | `quaderno.py scrivi <nome> …` | pagina Progetti o scheda dell'agente sulla lavagna, «Salva il diario» |
| Togliere uno specialista | `crea_agente.py "<progetto>" <nome> --togli` (va in `.claude\agents\_archivio\`) | «Togli» |
| Nome del progetto | `crea_progetto.py --rinomina <id> "<nome>"` | «Rinomina» |
| Spostare la cartella | `crea_progetto.py --sposta <id> <cartella nuova>` | «Sposta» |
| Archiviare | `crea_progetto.py --archivia <id>` (esce da `spazi.json`, i file restano) | «Archivia» |
| Riprendere | `crea_progetto.py --ripristina <id>` | — |

Il capogruppo non si toglie: si archivia il progetto. Un progetto archiviato esce anche dalla lavagna.
Cancellare davvero una cartella resta una scelta tua, a mano.

## Riunioni e giro notturno

Ogni progetto con capogruppo è un gruppo della riunione giornaliera (`PY J\strumenti\riunione.py <id> prepara`), con
capogruppo, specialisti, `Stato.md` e indice dei file come fonti. Il giro notturno dei diari
(`strumenti\giro_apprendimento.py`, attività «Jarvis Giro notturno» alle 06:40) lavora sugli stessi progetti. Senza
progetti non fanno niente e non danno errori.
