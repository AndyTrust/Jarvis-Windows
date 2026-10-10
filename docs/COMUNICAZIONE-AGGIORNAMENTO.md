Come far aggiornare chi ha già installato Jarvis

Questo testo si può inviare così com'è a chi ha già Jarvis installato. Non contiene dati di nessuno.

Messaggio da inviare (aggiornamento del 2026-10-02: assistenza a distanza con un tasto)

  Ciao, c'è una versione nuova di Jarvis. Porta l'assistenza a distanza con un tasto solo.
  L'aggiornamento non tocca la tua memoria, i tuoi agenti, le tue impostazioni e i tuoi documenti.

  1. Aggiorna. Fai doppio clic su "Aggiorna Jarvis" sul Desktop. Alla fine ricarica il pannello (F5).
  2. Attiva. Nel pannello, pagina Stato, premi "Attiva assistenza". Basta una volta.
     Se si apre una finestra, lasciala finire. Se chiede i permessi, rispondi Sì. Se chiede di riavviare, riavvia.
  3. Quando ti serve aiuto. Incolla il codice che ti mando e premi "Ricarica". Spunta il consenso.
     Premi "Chiedi assistenza". Premi "Copia" e mandami la richiesta su WhatsApp.
     Puoi fermare tutto quando vuoi con STOP.

  Quanto costa: 50 euro l'ora, cioè 12,50 euro ogni 15 minuti, sempre anticipati.
  All'inizio si scalano solo i primi 15 minuti. Poi un blocco da 15 alla volta, finché c'è credito.
  Se il collegamento non parte entro 15 minuti, i 15 minuti tornano a credito. Si può ricaricare anche solo 15 minuti.

  Se qualcosa non va, mandami quello che stampa questo comando in PowerShell:
    powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\jarvis\strumenti\ASSISTENZA.ps1" -SoloControlla

Se il collegamento "Aggiorna Jarvis" non c'è sul Desktop

  1. Apri la cartella dove avevi scaricato Jarvis-Privato-Windows (il clone da cui hai installato).
  2. Fai doppio clic su AGGIORNA-JARVIS.cmd.
  Se il doppio clic non si apre: in PowerShell, nella cartella del clone, esegui
    git pull
    powershell -ExecutionPolicy Bypass -File .\AGGIORNA.ps1

Cosa fa l'aggiornamento

- Controlla se c'è una versione nuova (git fetch) e mostra cosa cambia.
- Copia il codice attuale in %USERPROFILE%\jarvis-copia-AAAAMMGG-HHMM, per tornare indietro se serve.
- Scarica il codice nuovo e lo installa con INSTALLA.ps1 in modalità silenziosa.
- Non cambia mai: utente.json, CLAUDE.md, configurazione.json, spazi.json, pannello.json, gli agenti in .claude\agents, la memoria,
  la posta, i report e i dati dell'assistenza a distanza. Quei file li crea l'installatore solo se mancano.
- Segna la versione installata in VERSIONE.installata.

Solo controllare, senza installare

    powershell -ExecutionPolicy Bypass -File .\AGGIORNA.ps1 -Controlla

Se qualcosa non va

- "Questa cartella non è un clone git": Jarvis era stato scaricato come zip. Si scarica di nuovo con git clone e si lancia INSTALLA.ps1 una volta: da lì in poi vale l'aggiornamento.
- Il repository è privato: serve l'accesso al proprio account GitHub (gh auth login oppure le credenziali che chiede git).
- Per tornare alla versione di prima: la cartella jarvis-copia-... contiene il codice com'era.
- L'assistenza non parte: il comando -SoloControlla qui sopra stampa un riepilogo di poche righe da mandare al tecnico (docs\ASSISTENZA.md).

Per chi mantiene il repository

1. Le modifiche al codice base si fanno nel clone, si passa CONTROLLA-PULIZIA.py (deve dare 0), poi commit e push su main.
2. Si scrive una riga in docs\NOVITA-LAVAGNA.md (o in un nuovo file docs\NOVITA-...) con cosa è cambiato.
3. Si invia agli utenti il messaggio qui sopra. Chi aggiorna riceve da solo anche i collegamenti nuovi.
