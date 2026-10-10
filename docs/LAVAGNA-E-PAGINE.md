# Le pagine del pannello e le regole della lavagna

Il pannello (`http://127.0.0.1:7777`) ha **8 schede**, sempre in questo ordine. Ognuna ha una **spia** (verde ok, gialla
attenzione, rossa guasto, blu al lavoro, grigia non pronta). A destra dell'intestazione: «live» (aggiornamenti in tempo
reale), lo stato della voce, «tutto regolare» e l'ora. Il pannello si apre **a schermo intero** e si adatta anche a finestre
strette (sotto i 1100 px il pannello destro scompare fuori dalla Lavagna, e l'area principale usa tutta l'altezza).

| Scheda | Cosa mostra |
|---|---|
| **Chat** | La chat con Jarvis («Ciao <nome>, su cosa lavoriamo oggi?»): modo *lavoro* (lavora davvero, l'irreversibile chiede il sì) o *lettura*. Suggerimenti e comandi `/memoria`, `/brain`, `/lavori`, `/verifica`. |
| **Stato** | «Cosa succede» (ultimi fatti), la voce, la salute del pannello (ogni raccoglitore con il suo ultimo giro), la sentinella, gli **Interruttori** (Voce — Shift destro; Orb di Jarvis), i comandi rapidi, la chat a voce. |
| **Squadra** | Chi lavora adesso, chiavi e cose da guardare, i lavori con il loro esito. |
| **Missioni** | Affidi un obiettivo a uno spazio e ai suoi progetti: un orchestratore lancia gli esperti in parallelo, in *lettura* o *lavoro*. Ogni missione ha registro, agenti, «Invia» e «Chiudi missione». |
| **Scadenze** | Le scadenze personali (`Scadenze personali.md`) e «da ricordare». |
| **Memoria** | Note della memoria, sessioni, diario di oggi, la **sincronia** (ultimo giro del battito, un semaforo per progetto) e gli sviluppi aperti. |
| **Voce** | Come ascolta, pensa e parla Jarvis: Whisper (locale) → Claude → Kokoro Sara (locale). |
| **Lavagna** | Il disegno di chi risponde a chi, con la sinapsi in tempo reale. Vedi sotto. |

Nella colonna di sinistra: i motori (Claude Code), «Nuova chat con Jarvis», la ricerca degli agenti e **i gruppi** (uno per spazio),
con gli agenti trascinabili nella Lavagna. **Non c'è nessun piè di pagina.**

## La lavagna: come deve essere fatta

```
<Nome utente>  (nota)
     │
     ▼
<assistente> — orchestratore, risponde a <utente>   (nota)
     (all'inizio basta così: si parte da zero)
     └──► 📁 <nome-progetto>  (nota, nasce con il progetto) ──► <id>-ceo ──► specialisti
          (ogni progetto creato compare da solo, con il suo capogruppo e la sua squadra)
```

Regole:

1. **Una nota con lo stesso nome di uno spazio è il suo gruppo.** Tasto destro → scheda del gruppo, che mostra i progetti, gli
   agenti e i link `Memoria:` e `Report:` dello spazio (i percorsi veri di dove registra).
2. **Gli agenti sono schede vere** (avatar, modello), non note. La chiave è `progetto:agente` (per esempio `jarvis:esecutore`).
3. **I fili sono i «comunica con»**: quello che colleghi nella lavagna diventa il campo `comunica:` nel profilo dell'agente, e viceversa.
   La barra dice «Profili: allineati» quando coincidono; «Aggiorna ultime modifiche» lancia una missione che li riallinea.
4. Il flusso è **dall'alto in basso**: utente → Jarvis → gruppi → agenti. Le risposte risalgono lungo gli stessi fili.
5. Gli agenti passano all'esecutore solo ciò che va **eseguito** (mai messaggi a nome tuo senza il tuo sì) e alla memoria (diario e `Stato.md`) ciò che va **ricordato**.

## La sinapsi (la richiesta che si vede correre)

Quando Jarvis lancia un agente, **si accende il percorso vero** sulla lavagna, tratto per tratto (anche passando dai gruppi):

| Fase | Filo | Freccia | Bolla |
|---|---|---|---|
| **Richiesta** (andata) | **blu**, tratteggiato e animato nel verso della comunicazione | blu, verso chi riceve | «Jarvis → Esecutore: <cosa>» |
| **Risposta** (ritorno) | **verde**, animato al contrario | verde, verso chi aveva chiesto | — |
| **Errore** | **rosso** | rossa | «errore …» |

La scheda di chi lavora si illumina, il gruppo mostra «1 al lavoro». Se fra due schede non c'è un filo diretto si accende il
percorso più corto sui fili veri; solo se non esiste nessun percorso si disegna un filo temporaneo tratteggiato.

Come nasce: i ganci di Claude Code (`jarvis_status.py`) scrivono in `backtalk/.jarvis_status` ogni agente lanciato (con `nodo` =
il suo nome, ricavato dal tipo o dal percorso `agents\<nome>.md` citato nel prompt) e quando finisce. Se un agente resta «attivo»
dopo la fine del turno (chiamata fallita), lo `Stop` lo chiude, così la sinapsi non resta accesa.

## Testi e formattazione

- Tutto il pannello è **in italiano**, frasi corte. Nomi e colori per spazio: Memoria verde acqua, Agenti dell'utente viola;
  ai gruppi che aggiungi assegni tu il colore.
- Il nome dell'utente compare nel saluto della chat, nella lavagna, negli agenti e nel gancio di avvio: si cambiano in
  `utente.json` e nei file personali (vedi PERSONALIZZAZIONE.md).
- Le battute del lunedì sono **pulite**, una sola volta a settimana, mai ripetute; ogni dato ha sempre la sua fonte.

## Lavagna e menu laterale: come sono collegati

Aggiornato il 02/10/2026. Fonte di verità degli agenti: il profilo `.claude/agents/<nome>.md` di ogni progetto.
Fonte di verità della disposizione: `command-center/pannello.json` (la disposizione precedente resta in
`pannello.json.prev`). Fonte degli spazi e dei progetti: `command-center/spazi.json`.

```
 pagina (app.js)                         server (server.py)                       disco
 ---------------                         ------------------                       -----
 trascina/toglie scheda  --POST /api/pannello (con «versione»)-->  scrivi_pannello()  --> pannello.json
        ^                                      |  409 se la versione è vecchia
        |                                      v
 SSE /api/flusso  <------- tocca("pannello") / tocca("spazi") -----  ogni scrittura
   «pannello» -> riallineaPannelloDalServer() (rilegge e ridisegna se la versione sul disco è più nuova)
   «spazi»    -> caricaSpazi() (menu, archiviati, lavagna)
```

## Regole della lavagna

- **Tolto non ritorna.** Togliere una scheda dalla lavagna scrive la sua chiave in `lavagne.<id>.tolti`
  (`progetto:agente`, oppure `nota:<testo>`). «Tutta la catena», «Ordina», «Apri gruppo» e «Allinea» saltano
  le schede in `tolti`. Si rimettono solo trascinandole dalla colonna di sinistra, o con «Ripristina» (agente o gruppo).
- **Selezione multipla.** Maiusc+clic o Ctrl+clic aggiungono una scheda alla scelta; Maiusc+trascinamento sul foglio
  vuoto disegna un riquadro di selezione; Ctrl+A le sceglie tutte; le frecce le spostano (con Maiusc di 50 punti);
  trascinarne una sposta tutto il gruppo scelto.
- **Gruppi.** La ✕ su un gruppo-spazio chiama `togli_gruppo` per ogni suo progetto: i profili vanno in
  `<progetto>/_archivio-AAAAMMGG-HHMMSS/`, la voce esce da `spazi.json` ed entra in `gruppi-archiviati.json`.
  Cartella e memoria non si toccano. La cartella di Jarvis stesso (e quello che sta dentro) non si archivia mai.
- **Archiviati.** «Ripristina» rimette tutto. «Elimina» toglie dall'elenco: i profili non si cancellano dal disco
  (gruppo: resta `_archivio-…`; agente: va in `.claude/agents/_archivio/_eliminati/`).
- **Nuovo gruppo.** Si sceglie una cartella già sul PC; nasce solo il capogruppo. Poi parte `avvia_gruppo`: il capogruppo
  legge l'indice della cartella (`indice_cartella`, niente documenti interi) e propone i sotto-agenti nei Lavori.
  «Crea i sotto-agenti proposti» li crea sotto di lui (nome valido, modello ammesso, niente doppioni, al massimo 8).
  Poi si modificano a mano.
- **Pulizia.** `ripulisci_lavagna` toglie schede, fili, bolle e «aspetto» di agenti o gruppi che non esistono più,
  e le note doppie di Jarvis.
- **Attività.** Ogni comunicazione vista finisce in `command-center/attivita-agenti.jsonl` (solo aggiunte, rotazione a 2 MB).
  La scheda di un agente mostra il pannello «Attività» (`/api/agente-attivita?agente=progetto:nome`).

## Prova

Con il server acceso (meglio una copia di prova, vedi l'intestazione di `server.py`), dalla cartella del Command Center:

```
CC_PORTA=7778 python prova_lavagna.py     26 controlli: salvataggio, tempo reale, tolto-resta-tolto,
                                          ciclo gruppo, ciclo agente, proposta, guardia su Jarvis
CC_PORTA=7778 python prova_attivita.py    10 controlli sul registro attività per agente
```

Lavorano in una cartella temporanea e rimettono tutto com'era.
