# Novità della lavagna e del Command Center (02/10/2026)

Riepilogo delle modifiche portate nel template. I dettagli su come funziona la lavagna sono in
LAVAGNA-E-PAGINE.md.

## Lavagna

- Una scheda tolta resta tolta. La sua chiave va nel campo «tolti» della lavagna. Ordina, Tutta la catena,
  Apri gruppo e Allinea non la rimettono. Torna solo trascinandola dal menu o con Ripristina.
- Selezione multipla: Maiusc o Ctrl più clic, riquadro con Maiusc più trascinamento, Ctrl+A per tutto,
  frecce per spostare, trascinamento di gruppo.
- Tempo reale: quando il pannello cambia sul disco, la pagina lo rilegge e ridisegna da sola.
- Prima di ogni salvataggio il server tiene la disposizione precedente in pannello.json.prev.
- Ripulisci lavagna toglie schede, fili, bolle e colori di agenti o gruppi che non esistono più. Si può
  ripetere: la seconda volta non toglie niente.
- Allinea segnala anche un «Comunica con» che punta a un agente inesistente.

## Gruppi e agenti

- Togli gruppo dal menu e dalla lavagna. Il server rifiuta di archiviare la cartella di Jarvis o una
  cartella che sta dentro. Gli spazi di sistema non si tolgono.
- Gli archiviati (gruppi e agenti) hanno anche Elimina. Toglie la voce dall'elenco, ma i profili restano
  sul disco: il gruppo in _archivio-..., l'agente in .claude/agents/_archivio/_eliminati/.
- Nuovo gruppo da una cartella del PC: nasce il capogruppo, che legge solo l'indice della cartella e propone
  i sotto-agenti. Il bottone «Crea i sotto-agenti proposti» li crea sotto di lui, con controlli fissi su
  nome, modello e doppioni, al massimo 8.
- Corretto il riconoscimento del progetto di un file su Windows (percorsi con barra rovesciata).

## Attività per agente

- Ogni comunicazione vista (richiesta, risposta, errore) si aggiunge a attivita-agenti.jsonl. Il file
  ruota a 2 MB.
- Nuovo endpoint /api/agente-attivita?agente=progetto:nome con righe, contatori e avvisi.
- La scheda dell'agente ha il pannello Attività. Il menu mostra un contatore per agente. Le schede sulla
  lavagna mostrano l'ultima comunicazione. Un clic su una riga accende il filo sulla lavagna.
- Il pannello tiene le ultime 200 comunicazioni.

## Registro condiviso (facoltativo, spento di default)

- Nuova chiave «registro_condiviso» in configurazione.json: una cartella, per esempio sincronizzata con
  un altro computer. Se la chiave manca o la cartella non esiste, non si scrive nulla.
- Se c'è, il server aggiunge gli eventi in <cartella>/attivita-<NOME-PC>.jsonl, una riga JSON per evento,
  solo in aggiunta e solo nel file del proprio PC.
- Nel file condiviso vanno solo le richieste fra agenti. Le chat dell'utente con Jarvis, la sentinella e le
  ricerche in memoria restano nello storico locale.

Esempio:

    "registro_condiviso": "~/Sincronizzata/registro"

## Prove

- prova_lavagna.py: 26 controlli.
- prova_attivita.py: 10 controlli.
- Tutte e due leggono la porta da CC_PORTA e usano i file accanto a sé. Vanno lanciate contro una copia
  di prova del Command Center.
