---
name: brain
description: Il cervello dei progetti di @@UTENTE@@, su questo PC Windows. All'apertura di una chat dice a che punto siamo, quali errori NON vanno ripetuti e cosa resta da fare, leggendo .claude/memoria/ della cartella in cui sei; alla chiusura salva errori, fatto, da fare e i fatti che una sessione futura rifarebbe da zero, riscrive (se c'è un vault Obsidian) la pagina «A che punto siamo» e controlla che le date dei documenti siano vere. Usa questa skill come PRIMA cosa aprendo una chat su un progetto e prima di ogni /clear o handoff, e ogni volta che l'utente dice «brain», «a che punto siamo», «cosa abbiamo fatto», «errori», «impianta», «troppi token», «consumo troppo», «salva», «aggiorna la memoria», «ricordati questo», «chiudiamo qui», «handoff» — e per tutto quello che riguarda il vault Obsidian, se c'è: note collegate, appunti, «scrivi una nota su X».
---

# Il brain dei progetti di @@UTENTE@@

## 🔴 La regola che viene prima di tutte: un progetto per volta

**Il brain di un progetto vive dentro quel progetto e non esce.** La memoria sta
in `<progetto>\.claude\memoria\`, la pagina di stato (se c'è un vault) nella cartella
di quel progetto, e nessuna delle due sa niente degli altri progetti.

Non è pignoleria: chi porta avanti cose che non c'entrano fra loro — il lavoro, la
casa, un hobby — sa che **una memoria che le mescola non è più memoria, è rumore**.

- **Non portare un fatto da un progetto all'altro.**
- **Non scrivere una pagina di stato fuori da una cartella di progetto**: una pagina
  che non appartiene a nessun progetto crea solo confusione.
- **Non spegnere né cancellare le skill di un altro progetto.**

## Prima di tutto: dove stai girando

| | |
|---|---|
| progetto | la cartella in cui hai aperto Claude Code (si risale finché si trova `CLAUDE.md` o `.claude\memoria\`) |
| memoria | `<progetto>\.claude\memoria\` — un file per fatto, `MEMORIA.md` è l'indice |
| vault Obsidian | facoltativo: `vault_dir` in `@@JARVIS_DIR_WIN@@\utente.json` (vedi `riferimenti\vault.md`) |
| strumenti | `@@HOME_WIN@@\.claude\skills\brain\strumenti\*.ps1` |

Gli strumenti di questa skill sono in PowerShell e non richiedono Python.

Se non hai un terminale (claude.ai, cellulare): salta a «Quando non c'è il disco», in fondo.

## Due comandi

```powershell
& "$env:USERPROFILE\.claude\skills\brain\strumenti\brain.ps1"
```

Apre: legge, decide, riferisce — stato, **tutti** gli errori da non ripetere, i
🔴 aperti, cosa è stato toccato negli ultimi tre giorni, se il vault è allineato
e quali documenti dichiarano una data falsa. Gira in un secondo perché non
attraversa gli archivi (`FATTURE\`, `BUSTE_PAGA\`, `CHIUSURE_CASSA\`…): quelli
sono dati, non stato del lavoro.

```powershell
& "$env:USERPROFILE\.claude\skills\brain\strumenti\salva.ps1" -Completato "..." -DaFare "..."
```

Chiude: aggiorna stato, errori, fatti, diario, **riscrive da sola la pagina nel
vault** e ricontrolla le date. Fa una copia di `MEMORIA.md` in
`.claude\memoria\.copie\` **prima** di toccarlo.

**Dopo aver riferito, non incollare il referto all'utente**: digli in due righe
dove siamo e cosa resta aperto, poi rispondi alla sua richiesta. E non
riscoprire quello che è già in memoria — apri il file del fatto.

## Gli errori da non ripetere — la sezione che vale di più

```powershell
& "…\salva.ps1" -Errore "che cosa è andato storto · perché non si vedeva · come si evita"
```

Finiscono in cima ad «A che punto siamo», **prima** di Fatto e Da fare, e il
referto le stampa **tutte**. È l'unica sezione che non viene mai accorciata, e
la ragione è aritmetica: rileggere quattro righe costa qualche centinaio di
token, **ricommettere l'errore costa una sessione intera** — più il danno,
quando l'errore ha cancellato file o mandato in onda codice rotto.

Ci va un errore quando:

- una strada sembrava giusta e **non lo era**, e niente lo diceva a voce alta
  (una variabile di prova che non arriva dove serve, e lo script gira per davvero);
- una verifica ha detto il **falso** (un numero stimato al posto di quello misurato:
  plausibile, e sbagliato del 21%);
- qualcosa è andato **a buon fine solo a metà, in silenzio**;
- si stava per **cancellare** roba credendola un doppione, e non lo era.

Scrivi **come si evita**, non solo che cosa è successo. «Attenzione ai
duplicati» non serve a nessuno; «prima di qualunque scrittura di massa si fa il
copia di sicurezza» sì.

⚠️ **Un errore corretto non si cancella dalla lista**: resta, ed è quello che
impedisce di rifarlo. Si toglie solo quando il codice che lo rendeva possibile
non esiste più.

## Lo stato: Fatto e Da fare

```powershell
& "…\salva.ps1" -Completato "bozza pronta","file riordinati"
& "…\salva.ps1" -DaFare "scrivere la relazione","🔴 il backup non parte"
# piu' voci = UN parametro con l'elenco: ripetere -Completato due volte e' un errore
# di PowerShell ("specificato piu' di una volta"). Per testi lunghi con apostrofi
# conviene un .ps1 di appoggio con gli elenchi in variabili @( ... ).
& "…\salva.ps1" -Tolto "scrivere la relazione"     # da fare -> fatto, quando è finita
& "…\salva.ps1" -Stato "una riga di contesto sopra i due elenchi"
```

`-Tolto` cerca per pezzo di testo e dice cosa ha spostato; se non trova nulla te
lo dice invece di far finta.

**Metti `🔴` davanti a quello che è un problema, non un compito.** «il backup notturno non parte» non è una cosa da fare venerdì: è un difetto aperto.
Nella pagina del vault i 🔴 finiscono in una sezione loro, «Quello che brucia».

Lo stato si **sovrascrive**: un elenco che accumula tutti gli stati vecchi non
dice più a che punto siamo. È questo che lo distingue dal diario (`-Log`).

⚠️ `-Stato` da solo **non** azzera Fatto e Da fare: gli elenchi si rileggono e si
riscrivono interi. Se la lettura fallisce, `salva.ps1` si ferma con
«NON riscrivo» invece di scrivere una sezione vuota — è successo una volta, 
e sono sparite 101 voci.

## I fatti: uno per file

```powershell
& "…\salva.ps1" -Fatto <slug-breve> `
   -Descrizione "una riga: serve a decidere se aprirlo, senza aprirlo" `
   -Tipo progetto `
   -Corpo "che cosa è vero" `
   -Perche "perché è così, e cosa si è scartato" `
   -Come "cosa farne la prossima volta" `
   -Collega altro-fatto,ancora-un-altro
```

`-Tipo`: `progetto` · `feedback` (come l'utente vuole che si lavori) ·
`riferimento` (percorsi, dashboard, chiavi) · `utente`.

**Merita di essere salvato:** un difetto che nessuno sospettava · una strada
provata che **non** funziona e perché — vale più di quella che funziona, perché
senza, la sessione dopo la riprova · una decisione e la sua ragione · un numero
che è costato fatica misurare, con lo strumento per rimisurarlo · un vincolo che
il codice non dice.

**Non merita:** quello che il repo già dice · quello che vale solo per questa
conversazione · il riassunto di cosa hai fatto. **Se una riga non cambia quello
che farà la sessione prossima, non ci va.**

Prima di scriverne uno nuovo, `salva.ps1 -Leggi`: se ce n'è già uno che lo copre
si aggiorna quello. Un fatto che si scopre sbagliato si corregge o si toglie —
una memoria che mente è peggio di una che manca.

## Il vault Obsidian (facoltativo)

Se hai collegato un vault, `salva.ps1` riscrive a ogni chiusura la pagina `A che punto siamo.md` nella cartella
del progetto: **non si corregge a mano**. Il dettaglio — dove si configura, cosa scrive, cosa non fare — sta in
**`riferimenti\vault.md`**. Senza vault non cambia niente: la memoria resta in `.claude\memoria\`.

⚠️ **Memoria e vault non sono la stessa cosa e non si copiano l'una nell'altra.**
La memoria (`.claude\memoria\`) serve al modello ed è telegrafica; il vault serve a te ed è più discorsivo.

## Le date

Ogni documento dichiara quando è stato aggiornato **con data e ora** (`AAAA-MM-GG HH:MM`), e il referto confronta quella
data con la modifica vera del file. **Un documento cambiato dopo la data che
dichiara è un documento di cui non ci si può fidare.**

```powershell
& "…\brain.ps1" -Timbra     # porta a oggi le date scadute
```

⚠️ Timbrare non rende vero il contenuto: **prima si legge e si corregge, poi si
timbra.** Una data fresca su un testo falso è peggio di una data vecchia, perché
toglie l'unico segnale che c'era. Ai documenti che non avevano mai una data ci
mette quella di **modifica vera**, non oggi.

## Quello che costa a ogni messaggio

**La regola madre: il giudizio al modello, l'esecuzione ripetibile al codice.**
Un modello sbaglia a caso e costa a ogni chiamata; uno script non sbaglia, è
istantaneo e costa zero. Corollario: **una CLI invece di un MCP** — un MCP carica
le definizioni di tutti i suoi metodi a ogni messaggio, una CLI costa zero finché
non la chiami e nel `CLAUDE.md` occupa una riga.

- **`CLAUDE.md` è un indice, non un manuale.** Riletto a ogni messaggio: radice
  sotto le 200 righe, uno per sottocartella, quello che è lungo va fuori con un
  rimando. Ci va solo quello che, se sbagliato, rompe qualcosa. ⚠️ Un `CLAUDE.md`
  che mente costa più di uno che manca: risolto un difetto lì descritto, la riga
  si aggiorna **nello stesso momento**.
- **`/clear` a ogni cambio di compito**, e modello ed effort si scelgono
  all'inizio. **`rewind` invece di `/compact`**: compattare costa moltissimo e
  decide da solo cosa buttare.
- **Contesto al 50% e al 95%**: al 50% si aggiorna la memoria (questa skill, modo
  chiusura) e si continua a lavorare nella stessa chat; al 95% c'è l'ultimo
  aggiornamento: si salva, si scrive il foglio di ripresa e si apre una chat
  pulita che riparte dal foglio. La casella che vale di più è **cosa è già
  stato provato e non funziona**. Su Windows il foglio si scrive a mano (non c'è
  `handoff.py`): stato, cosa è stato provato e non va, i file toccati, il
  prossimo passo.
- **I PDF non entrano interi**: 1.500-3.000 token a pagina. Se serve testo da un PDF, dillo
  invece di leggerne trenta.
- **I grafi si navigano, non si rileggono**: `codegraph query|impact|explore`,
  `graphify explain|path`. Prima si chiede al grafo *dove* sta la cosa, poi si
  legge **solo** quel file. ⚠️ Un grafo vecchio è peggio di nessun grafo: va
  riallineato dopo ogni spostamento di cartelle.
- **Prima di generare HTML, CSS o React, mostra un diagramma ASCII del layout e
  aspetta l'ok.** Venti righe di trattini si correggono per niente; trecento
  righe rigenerate perché un pulsante va spostato costano migliaia di token.
- **Le false scorciatoie**: screenshot di testo, prompt telegrafici «per
  risparmiare» (producono cicli di correzione), compressori di terze parti,
  rileggere un file appena scritto per controllare.

## Impiantare un progetto nuovo

Se `brain.ps1` dice «PROGETTO NUOVO», il metodo è questo, in quest'ordine:

1. `CLAUDE.md` in radice, **sotto le 200 righe**: dove-sta-cosa, le tre regole
   che rompono qualcosa, i comandi, i puntatori.
2. `.claude\memoria\MEMORIA.md` con le quattro sezioni («A che punto siamo»,
   con dentro Errori/Fatto/Da fare, «Cosa sappiamo già», «Diario»). La crea il
   primo `salva.ps1`.
3. Uno strumento deterministico al posto di ogni MCP, e `.gitignore`.
4. I grafi **solo sopra i 500 file**: sotto, costruirli e tenerli aggiornati
   costa più di quello che fanno risparmiare, e va **detto** invece di
   costruirli per abitudine.
5. Se usi un vault Obsidian e il progetto deve avere una pagina con un nome diverso da quello della cartella,
   aggiungilo a `$PROGETTI` in `strumenti\comune.ps1` (vedi `riferimenti\vault.md`).

## Prima di dire che è fatto

Rilancia `brain.ps1` e rileggi quello che vedrà la prossima sessione. **Se da
quel referto non capiresti a che punto sei, non è salvato bene** — e sei tu, che
hai il contesto in testa: a chi non ce l'ha sembrerà peggio.

⚠️ La memoria nativa di Claude Code (`~\.claude\projects\<slug>\memory\`) è
indicizzata sullo **slug della cartella da cui è partita la sessione**: aprendo
la chat altrove i fatti finiscono sotto il progetto sbagliato. Per questo la
memoria di riferimento è `.claude\memoria\`, dentro il progetto.

---

## Quando non c'è il disco — claude.ai, il cellulare, Cowork

Qui `.claude\memoria\`, il vault e gli `.ps1` non esistono. Tre regole, in ordine.

**1. Non fingere di aver letto la memoria.** Aprilo dicendo in **una riga** che
stai girando senza disco, e che quello che sai del progetto viene solo da questa
conversazione. Il danno peggiore che questa skill può fare è recitare uno stato
inventato: sul PC il referto è sempre vero, quindi l'utente si fida senza
rileggerlo. Se però l'utente incolla `MEMORIA.md` o `A che punto siamo.md`,
**quella è la memoria**: leggila e comportati come nel modo pieno, tranne che per
la scrittura.

**2. Se il PC è raggiungibile, scrivici davvero.** Se l'ambiente sa elencare le
altre sessioni dell'account e ce n'è una su questo progetto, **mandale il comando
da eseguire** invece di stampare istruzioni: l'utente dal cellulare non ha una
tastiera comoda.

**3. Altrimenti consegna il pezzo di memoria, pronto da posare** — non un
riassunto, **il file esatto**, così chi lo riceve deve solo salvarlo:

```
File da salvare: .claude\memoria\<slug-breve>.md

---
nome: <slug-breve>
descrizione: <una riga: serve a decidere se aprirlo, senza aprirlo>
tipo: progetto | feedback | riferimento | utente
aggiornato: AAAA-MM-GG HH:MM
---

<che cosa è vero>

**Perché:** <perché è così, e cosa si è scartato>

**Come si applica:** <cosa farne la prossima volta>

Vedi [[altro-fatto]]
```

**Quello che in modo cieco non si fa:** timbrare date (la data vera di modifica è
sul disco); riscrivere la pagina del vault a mano (la sovrascrive il primo
salvataggio vero, e nel frattempo mente); proporre di spostare memoria o vault «per semplificare»: `.claude\memoria\` sta dentro il progetto perché la memoria
nativa si indicizza sulla cartella di partenza. È una scelta già presa.
