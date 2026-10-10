# Jarvis per Windows — istruzioni per Claude Code

Questo file lo legge Claude Code quando lo apri nella cartella del repository scaricato. Il repository è neutro: non
contiene nomi, dati o segreti di nessuno. Tutto quello che riguarda la persona che lo installa nasce dalle DOMANDE DI
AVVIO qui sotto e resta sul suo PC.

## Prima apertura

Controlla se esiste `%USERPROFILE%\.jarvis\installato.json` (in PowerShell: `Test-Path "$env:USERPROFILE\.jarvis\installato.json"`).

- **Esiste:** Jarvis è già installato. Leggilo, saluta la persona con il nome che c'è scritto e chiedi su cosa
  lavorare. Per aggiornare: `AGGIORNA.ps1`. Per rifare le domande: `/inizia`.
- **Non esiste:** è la prima apertura. Fai così, in quest'ordine:
  1. **Entra in MODALITÀ PIANO** prima di tutto. Se hai lo strumento per farlo, usalo; altrimenti chiedi alla persona di
     premere `Shift+Tab` finché in basso compare «plan mode», oppure di riaprire con `claude --permission-mode plan`.
     In modalità piano non modifichi niente: leggi, chiedi e prepari il piano.
  2. **Fai le DOMANDE DI AVVIO, una per volta.** Aspetta la risposta prima di passare alla successiva. Ogni domanda ha
     un valore predefinito: se la persona risponde «invio», «vai» o «non so», usi quello e lo dici.
  3. **Scrivi il PIANO di installazione** (sezione «Il piano» qui sotto) e chiedi l'approvazione.
  4. **Solo dopo il sì:** esci dalla modalità piano, scrivi `%USERPROFILE%\.jarvis\risposte-avvio.json` e lancia
     `powershell -ExecutionPolicy Bypass -File .\INSTALLA.ps1 -DaRisposte`. Leggi l'uscita, poi lancia `VERIFICA.ps1` e
     riferisci cosa è andato e cosa no, con le righe vere dell'uscita.

Il comando `/inizia` (`.claude/commands/inizia.md`) fa partire la stessa procedura quando vuoi.

## Le domande di avvio

Una per volta, in questo ordine. Tra parentesi il valore predefinito e il campo del file delle risposte.

1. **Come vuoi che ti chiami?** E **come vuoi chiamare l'assistente?** (nome dell'account Windows; «Jarvis»)
   → `utente.nome`, `assistente.nome`. Da qui in poi chiami la persona con quel nome.
2. **In che lingua e con che tono vuoi le risposte?** Esempi: diretto e sintetico, caldo e ironico, formale.
   (italiano; cordiale, diretto, con un filo di ironia) → `lingua`, `tono`
3. **Fuso orario.** (quello di Windows, es. Europe/Rome) → `fuso_orario`
4. **Che lavoro fai e per cosa userai l'assistente?** Lavoro, vita privata o tutti e due. → `lavoro.ruolo`, `lavoro.uso`,
   `vita_privata`
5. **Vuoi partire da zero o creare subito il primo progetto?** Da zero (predefinito): nessun progetto, spazio o agente;
   nascono quando li nomini. Se il primo: chiedi solo il nome e, se c'è già, la cartella (verifica con `Get-ChildItem`).
   Non chiedere altri progetti. Poi: quando nominerai un progetto nuovo, prima ti mostro il piano (predefinito) o lo
   creo subito? → `avvio` («zero» o «primo»), `primo_progetto` ({"nome", "cartella"} o null), `creazione` («piano» o
   «automatica»)
6. **Dove tengo la memoria condivisa?** È la cartella che Claude Code, l'assistente e gli altri programmi leggono e
   scrivono insieme. Proponi: `%USERPROFILE%\Jarvis-Memoria` (predefinita), una cartella in OneDrive se c'è (così la
   vedi da più PC), oppure un vault di Obsidian che la persona ha già. Guarda tu se esistono `%USERPROFILE%\OneDrive*`
   o cartelle con `.obsidian` dentro e proponile per nome. → `memoria.cartella`, `memoria.tipo`
7. **Usi anche altri programmi di intelligenza artificiale?** Claude Code, Codex, Gemini CLI, Cursor, altri. Servono
   per scrivere il file d'ingresso giusto nella memoria condivisa (AGENTS.md, GEMINI.md). (solo Claude Code) → `harness`
8. **Voce, telefono, server remoto, posta.** Quattro sì o no, uno per volta:
   - voce in locale (Kokoro + Whisper, circa 400 MB da scaricare) (sì) → `voce.attiva`
   - telefono Android collegato (no) → `telefono.attivo`
   - un server remoto (VPS) per tenere l'assistente acceso quando il PC è spento (no). È **facoltativo**. Se la persona
     ne vuole uno, dai il link di `docs/affiliazione.txt` e di' chiaramente che è un **link di affiliazione**: chi lo
     usa riconosce una commissione all'autore del progetto. Si può scegliere qualunque altro fornitore. → `vps.usa`
   - posta: quali caselle leggere, solo indirizzo e tipo (no). **Mai password qui.** → `posta.attiva`, `posta.caselle`
9. **C'è qualcosa che non devo toccare mai?** Cartelle, programmi, file, azioni. (niente in particolare: chiedo prima
   di toccare cartelle fuori dagli spazi) → `non_toccare`
10. **Dove installo il programma e su che porta?** (`%USERPROFILE%\jarvis`, porta 7777) → `installazione.cartella`,
    `installazione.porta`

Regole delle domande:
- **Niente segreti** nelle risposte: password, token, chiavi API non si chiedono e non si scrivono nel file. Se la
  persona ne incolla uno, non lo ripeti, non lo salvi, e le dici che andrà in `%USERPROFILE%\.env.jarvis` dopo
  l'installazione. `INSTALLA.ps1 -DaRisposte` si ferma se trova qualcosa che sembra un segreto.
- Una domanda e ti fermi. Non riempire tu le risposte che la persona non ha dato, a parte i predefiniti dichiarati.
- Il formato del file è in `modelli-personali\risposte-avvio.esempio.json`.

## Il piano

Prima di toccare qualunque cosa mostra:
- il contenuto di `risposte-avvio.json` che scriverai (senza segreti);
- cosa installerà `INSTALLA.ps1` (Python 3.12 e eSpeak NG con winget se mancano, librerie Python, voce se scelta,
  file personali dai modelli, skill e ganci di Claude Code con copia di sicurezza di `settings.json`, memoria condivisa
  con le giunzioni, collegamenti sul Desktop, attività pianificate «Jarvis Avvio», «Jarvis Battito», «Jarvis Pulizia» e
  «Jarvis Giro notturno»; nessun progetto, salvo il primo se l'ha chiesto);
- cosa NON toccherà (le cartelle di `non_toccare`, i ganci già presenti in `settings.json`, i dati nelle cartelle
  `memory` di Claude Code: vengono uniti, mai cancellati);
- come si torna indietro (`docs\DISINSTALLARE.md`).

Poi chiedi: «Approvi il piano?». Senza un sì chiaro non esci dalla modalità piano.

## Dopo l'installazione

- Il profilo vive in `%USERPROFILE%\jarvis\utente.json` e in `%USERPROFILE%\jarvis\CLAUDE.md`. Nessun nome è scritto
  nel codice: il nome della persona e quello dell'assistente si leggono da lì.
- La memoria condivisa è quella di `%USERPROFILE%\.jarvis\percorsi.json`: `Comune\Memoria.md` (porta d'ingresso),
  `<spazio>\Stato.md`, `Diario\AAAA-MM-GG.md`, `Report\`, `Sessioni\`, `Claude\projects\`. Si aggiorna da sola:
  il gancio `stato_avanzamento.py` (Stato.md e diario del giorno, a fine risposta, compattazione e fine sessione), il
  gancio `conferma_salva.py` (alle conferme «ok», «perfetto», «chiuso»… chiede il salvataggio di `aggiorna-memoria`)
  e i ganci git dei progetti a ogni commit e push. Il FATTO / DA FARE / ERRORI viene dalla memoria del progetto
  (`.claude/memoria/MEMORIA.md`, scritta da `aggiorna-memoria`) e dai diari degli agenti. Guida: `docs\wiki\Memoria-condivisa.md`.
- Le skill `aggiorna-memoria` e `nuovo-progetto` sono installate in `%USERPROFILE%\.claude\skills\`.

## Progetti e agenti: l'assistente si programma da solo

L'assistente parte **senza progetti, spazi, capogruppo né specialisti**. Nascono dalle richieste del proprietario.
La fonte unica è `command-center\spazi.json` + le schede in `<cartella del progetto>\.claude\agents\` + le cartelle.
Lavagna, menu agenti, pagine del Command Center e `Stato.md` si rileggono da lì da soli (in uno o due secondi).

- **Il proprietario nomina un progetto che non c'è** («apri il progetto X», «iniziamo …», «seguimi anche Y») o fa una
  richiesta che non rientra in nessuno spazio: usa la skill `nuovo-progetto`. Controlla con
  `python strumenti\crea_progetto.py --elenco`; se manca, proponi in poche righe cosa crei (uscita di `--prova`),
  la prima volta in modalità piano, poi in automatico se in `%USERPROFILE%\.jarvis\risposte-avvio.json` c'è
  `"creazione": "automatica"`; crea con `strumenti\crea_progetto.py` e verifica.
- **Ogni progetto ha un capogruppo** (`<id>-ceo`). Gli specialisti li crea il capogruppo, uno alla volta, con
  `strumenti\crea_agente.py` quando serve una competenza («mi serve qualcuno che faccia Y»). Nessun agente senza
  missione chiara. haiku esegue, sonnet ricerca, scrive e verifica, opus solo programmazione.
- **Ogni agente ha il suo diario** (`<cartella>\.claude\memoria\agenti\<nome>.md`: Fatto, Da fare, Errori commessi da
  non ripetere): quando lanci un agente metti nel compito l'uscita di `python strumenti\quaderno.py leggi <nome>`;
  quando torna, salva le sue righe con `quaderno.py raccogli <nome> --da <file>`.
- I file del proprietario per un progetto stanno in `<cartella>\File\`; `Indice-file.md` si aggiorna da solo.
- Comandi: `/nuovo-progetto <nome>`, `/nuovo-agente <progetto> <ruolo>`. Guida: `docs\wiki\Progetti-e-agenti.md`.

## Regole per chi lavora su questo repository

- Il repository resta neutro: prima di ogni commit `python CONTROLLA-PULIZIA.py` deve dire 0.
- Segreti mai nel repository né nella memoria condivisa: stanno solo in `%USERPROFILE%\.env.jarvis`.
- Il Vault (`app\command-center\vault_cc.py`, pagina #vault, guida `docs\wiki\Vault.md`) tiene password, carte e PIN
  del proprietario, cifrati in `%APPDATA%\Jarvis\vault\`. Non leggere i suoi file e non chiedere valori in chat. Su
  Windows gli agenti non lo usano sul browser; le carte non si usano mai.
- Prove, non ipotesi: dai per fatto solo quello che hai controllato con un comando o un file.
- Conferma prima dell'irreversibile: cancellare, pubblicare, scrivere fuori dalle cartelle concordate.
