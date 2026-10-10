# Assistenza a distanza a pagamento

Il riquadro «Assistenza a distanza» nella pagina **Stato** del Command Center fa entrare un tecnico nel terminale di
questo PC e, se c'è TightVNC, anche sullo **schermo** (vede e usa monitor, mouse e tastiera), solo quando lo chiede il
cliente e solo per il tempo pagato. Questo PC è **solo cliente**: verifica i codici
di ricarica, non li crea. La chiave privata e lo strumento che genera i codici stanno solo dal tecnico.

## Per il cliente: tre passi

1. **Aggiorna Jarvis.** Doppio clic su «Aggiorna Jarvis» sul Desktop (oppure `AGGIORNA-JARVIS.cmd` nella cartella del clone).
2. **Attiva assistenza.** Apri il pannello, pagina Stato, e premi **«Attiva assistenza»**. Una volta sola. Se manca
   qualcosa si apre una finestra che lo installa da sola. Può chiedere i permessi di amministratore o un riavvio:
   dopo il riavvio riparte da sola.
3. **Quando serve aiuto.** Incolla il codice che ti ha mandato il tecnico e premi «Ricarica». Spunta il consenso e premi
   «Chiedi assistenza». Compare una richiesta che comincia con `jarvis-tunnel:`. Premi «Copia» e mandala al tecnico
   (WhatsApp va bene). Un solo consenso vale per schermo e terminale. Quando il tecnico guarda lo schermo il riquadro
   dice «Schermo condiviso attivo». Per chiudere tutto in ogni momento: **STOP**.

Il pagamento avviene fuori dal pannello, come d'accordo con il tecnico. Il codice di ricarica arriva dopo.

## Cosa fa «Attiva assistenza»

- **Crea `command-center\assistenza.json`** se manca, con `"abilitata": true` e la sezione `"tunnel"` presa da
  `command-center\assistenza-tunnel.json` (solo dati pubblici: indirizzo del server del tecnico, sua chiave host, chiave
  pubblica del tecnico, fascia di porte). Se il file c'è già **aggiunge solo quello che manca**: i valori del cliente
  restano. Accende `"abilitata"`, perché è quello che il cliente ha chiesto premendo il tasto. Un file rotto non si
  tocca: il pannello dice di correggerlo o cancellarlo.
- **Se manca qualcosa** (WSL, Ubuntu, openssh, tmate) apre una finestra PowerShell con `strumenti\ASSISTENZA.ps1 -SoloPrepara`:
  1. WSL con Ubuntu (`wsl --install -d Ubuntu --no-launch`), con i permessi di amministratore chiesti da solo; se Windows
     vuole un riavvio lo dice e al prossimo accesso riparte da sola;
  2. Ubuntu mai aperta: la prepara senza chiedere utente e password (`ubuntu.exe install --root`);
  3. dentro Ubuntu: `openssh-client openssh-server tmux tmate procps`. Il server ssh **di sistema** resta spento e bloccato
     (`/etc/ssh/sshd_not_to_be_run`, servizio disabilitato): il pannello ne avvia uno suo solo durante l'assistenza;
  4. **schermo condiviso**: se manca, installa TightVNC Server con winget (`GlavSoft.TightVNC`, licenza GPLv2, scaricato
     dal cliente: Jarvis non lo contiene), solo la parte Server, **senza servizio** e **senza eccezione nel firewall**
     (Windows chiede i permessi una volta). Controlla che ci sia `ssh.exe` di Windows (OpenSSH Client, incluso in Windows
     10/11) e che un eventuale servizio TightVNC sia spento;
  5. accende l'assistenza in `assistenza.json` (come sopra).

Senza dati di pagamento in `assistenza.json` il riquadro non mostra ordini, coordinate o IBAN: dice solo di chiedere il
codice al tecnico.

## Come funziona il collegamento (tunnel dentro WSL)

Tutto gira **dentro WSL**, lanciato dal pannello con `wsl.exe`. Lo script che fa il lavoro arriva a Linux su stdin
(`wsl.exe -e sh -s`): niente percorsi Windows da tradurre, niente virgolette da far passare.

1. Per ogni sessione si creano due chiavi nuove (`ssh-keygen -t ed25519`) in `~/.jarvis-assistenza-cliente/sessione`
   (casa Linux, permessi 700): la chiave host del server ssh locale e la chiave del cliente.
2. Parte un `sshd` **solo su 127.0.0.1**, porta a caso, senza password, che accetta **solo** la chiave pubblica del tecnico
   (`restrict,pty`: niente inoltri). Se c'è tmux, il tecnico entra in una sessione tmux che il cliente può guardare in sola
   lettura (il comando compare nel riquadro).
3. Parte `ssh -N -R 127.0.0.1:PORTA:127.0.0.1:<porta locale>` verso l'utente `assistenza` del server del tecnico, con la
   chiave host del server fissata (`StrictHostKeyChecking=yes`). Il collegamento parte da qui, in uscita: nessuna porta
   aperta verso l'esterno.
4. Il riquadro mostra la **richiesta** `jarvis-tunnel:1:PORTA:UTENTE:CHIAVEHOST:CHIAVECLIENTE` da mandare al tecnico. Il
   tecnico la incolla dal suo lato: apre la chiave del cliente sul server, legata a quella sola porta, e si collega.

**I processi dentro WSL non muoiono con Windows.** Per questo la chiusura è esplicita: ogni processo scrive il suo pid nella
cartella della sessione; alla chiusura si controlla che il pid sia davvero nostro (la riga di comando contiene la cartella
della sessione), si ferma lui con tutti i figli (le connessioni del tecnico sono figli di sshd), si aspetta, si usa KILL se
serve e si **verifica** che siano morti. Poi si chiude tmux e si cancellano le chiavi. Se la verifica non riesce (WSL che non
risponde) il registro lo segna e il primo STOP dopo ci riprova.

La sessione si chiude per: **STOP** del cliente, **credito finito**, **tetto di 8 ore**, **tunnel caduto** (chiuso dal
tecnico o rete persa), **Linux che non risponde**, modulo spento. Se il tunnel **non si stabilisce entro 15 minuti**, o il
cliente ferma prima che si stabilisca, il primo blocco (15 minuti) **torna a credito**: il servizio non è partito. Finché il
tunnel non si è stabilito non si scalano altri blocchi.

Finché la sessione dura, il pannello tiene aperti i due `wsl.exe` che fanno girare sshd e ssh in primo piano: tengono viva la
distribuzione e dal lato Windows si vede subito se uno è uscito.

**tmate resta la riserva**: se in `assistenza.json` manca la sezione tunnel, o in Ubuntu manca openssh, si usa tmate
(terminale condiviso verso tmate.io) come prima, e il riquadro mostra la riga `ssh ...` di tmate.

## Lo schermo condiviso (TightVNC)

Funziona su Windows **Home e Pro** (l'RDP integrato no: su Home non c'è). Cliente e tecnico vedono **lo stesso schermo**:
TightVNC gira in modo applicazione e condivide il desktop vero, con la sua icona vicino all'orologio.

1. All'avvio della sessione il pannello sceglie una porta locale a caso e scrive in `HKCU\Software\TightVNC\Server`:
   `LoopbackOnly=1` (ascolta **solo su 127.0.0.1**), autenticazione VNC, e una **password nuova di 8 caratteri** (il massimo
   del VNC), nel formato del VNC. Poi avvia `tvnserver.exe -run` e controlla con `netstat` che ascolti solo su 127.0.0.1:
   se ascoltasse anche fuori, lo ferma subito e resta il solo terminale.
2. Il tunnel dello schermo lo apre **`ssh.exe` di Windows** (dentro WSL2 il 127.0.0.1 di Windows non si vede): stessa chiave
   di sessione del terminale (copiata da WSL in `%LOCALAPPDATA%\jarvis-assistenza\schermo\sessione`), stesso server, chiave
   host fissata, `-R 127.0.0.1:PORTA_SCHERMO:127.0.0.1:<porta del VNC>`. PORTA_SCHERMO è accanto a quella del terminale.
   Il terminale resta dentro WSL com'era.
3. La richiesta diventa `jarvis-tunnel:2:PORTA:PORTA_SCHERMO:UTENTE:CHIAVEHOST:CHIAVECLIENTE:SEGRETO`. SEGRETO è la password del
   VNC **cifrata con la chiave pubblica del tecnico** (X25519 + SHA-256 + etichetta HMAC): chi legge la richiesta su WhatsApp non
   la può usare, il tecnico la legge con la sua chiave privata. Il server del tecnico apre la chiave del cliente con **due**
   porte (terminale e schermo) e nessun'altra.
4. **Un solo STOP chiude tutto.** Alla chiusura (STOP, credito finito, 8 ore, terminale caduto) il pannello ferma TightVNC e il
   tunnel dello schermo, **verifica** che siano morti e che la porta non risponda, **toglie la password** dal registro e
   cancella la chiave copiata. Se cade il terminale si chiude anche lo schermo. Se cade solo il tunnel dello schermo, si riapre;
   se il cliente chiude TightVNC dall'icona, lo schermo si chiude e resta il terminale.

Senza TightVNC (o con `"schermo": false` in `assistenza.json`) la richiesta resta `jarvis-tunnel:1:…` e si usa il solo
terminale, senza errori. Limiti: TightVNC in modo applicazione non vede le finestre di Windows che chiedono i permessi di
amministratore (il desktop sicuro) e non funziona alla schermata di accesso.

## Conteggio

Regola del 2026-10-02: **50 € l'ora = 12,50 € ogni 15 minuti**, sempre anticipati, a blocchi da 15. All'avvio si scala **solo il
primo blocco da 15 minuti** (servono almeno 15 minuti di credito). Poi, 60 secondi prima che il blocco finisca, se c'è credito si
scala il blocco dopo; se non c'è, la sessione si chiude alla fine del blocco già pagato. Nessuna ora anticipata. La ricarica minima
è 15 minuti (12,50 €), anche il primo codice. Tetto di 8 ore per sessione. I minuti del blocco in corso non si restituiscono
(salvo il tunnel mai stabilito, sopra). Primo blocco, ricarica minima e scatto sono fissi nel codice (`REGOLA_BLOCCHI` in
`strumenti/assistenza.py`): un `assistenza.json` scritto prima, con 60 dentro, non conta più e non va modificato a mano. Durante la sessione in cima a tutte le pagine resta il banner rosso
«Assistenza attiva» con il cronometro e il tasto «Ferma».

## I pezzi

| File (in `%USERPROFILE%\jarvis`) | Cosa fa |
|---|---|
| `strumenti\assistenza.py` | il modulo del pannello: codici (Ed25519, Python puro), credito, tunnel dentro WSL, schermo (TightVNC + ssh.exe), tmate, attivazione |
| `strumenti\ASSISTENZA.ps1` | installa e controlla (WSL, Ubuntu, openssh, tmux, tmate), accende l'assistenza |
| `strumenti\prepara_assistenza_windows.ps1` | rimando a `ASSISTENZA.ps1`, lo usa `INSTALLA.ps1 -ConAssistenza` |
| `command-center\assistenza-tunnel.json` | i valori **pubblici** del collegamento (nessun segreto) |
| `command-center\assistenza-chiave-pubblica.txt` | la chiave **pubblica** che verifica i codici di ricarica |
| `command-center\assistenza.esempio.json` | il modello delle condizioni (tariffa, scatti) e dei dati di pagamento |
| `command-center\assistenza.json` | la configurazione del PC. **Solo sul PC**, mai in git |
| `command-center\assistenza-registro.json` e `assistenza.log` | credito, codici usati, sessioni. **Solo sul PC** |

`INSTALLA.ps1` e `AGGIORNA.ps1` non toccano mai `assistenza.json`, il registro e il log.

## Se qualcosa non va

In PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\jarvis\strumenti\ASSISTENZA.ps1" -SoloControlla
```

Non installa niente. Stampa un **RIEPILOGO** di poche righe (`ok` / `MANCA`): si copia e si manda al tecnico. Controlla WSL,
Ubuntu, openssh e tmate dentro Ubuntu, TightVNC e `ssh.exe` di Windows (e se TightVNC è in ascolto, solo su 127.0.0.1),
`assistenza.json`, se il server del tecnico si raggiunge e cosa dice il pannello.

Altri comandi con lo stesso file: `-Ferma` chiude subito una sessione (anche i processi rimasti dentro Linux), `-Stato` dice
se c'è una sessione aperta e copia di nuovo la richiesta, `-Distro NOME` sceglie un'altra distribuzione. Esce con 0 se è tutto
pronto, 1 se manca qualcosa, 3010 se serve riavviare.

Problemi noti: virtualizzazione spenta nel BIOS (`0x80370102`), WSL non abilitato (`0x8007019e`), rete aziendale che blocca la
porta del server del tecnico (il riepilogo lo dice).

## Il pagamento dentro il pannello (facoltativo, per il tecnico)

Se in `assistenza.json` ci sono le sezioni `"tecnico"` e `"pagamento"` compilate (vedi `assistenza.esempio.json`), il riquadro
permette anche di scegliere le ore e mostra coordinate del bonifico, email e WhatsApp, solo dopo la scelta delle ore. Senza,
non compare niente di tutto questo.

## Come si prova

Su macOS o Linux, senza WSL:

```
python3 app/strumenti/prova_assistenza.py
```

Usa un `wsl.exe` finto (`ASSISTENZA_WSL`, `ASSISTENZA_MODO=wsl`) che lancia lo script del tunnel sulla macchina stessa, e
ssh, sshd, ssh-keygen e tmate finti: prova il tasto, la creazione di `assistenza.json` senza sovrascrivere, apertura e chiusura
del tunnel, 8 ore, tunnel caduto, rimborso, Linux che non risponde, la riserva tmate e il riquadro senza dati di pagamento.

```
python3 app/strumenti/prova_assistenza_schermo.py
```

Lo schermo con un TightVNC, un `ssh.exe` e un `netstat` finti: richiesta versione 2, password che il tecnico decifra ed è
uguale a quella del VNC, mai in chiaro nei file, ascolto solo su 127.0.0.1, percorso intero dalla porta dello schermo al VNC,
«Schermo condiviso attivo», STOP (anche da un altro processo), terminale caduto, 8 ore, VNC chiuso dal cliente, VNC che ascolta
fuori (rifiutato), PC senza TightVNC (solo terminale). Il registro di Windows, `tasklist`/`taskkill` e TightVNC veri si
provano solo su Windows: `ASSISTENZA.ps1 -SoloControlla` dice se TightVNC c'è e se ascolta solo su 127.0.0.1.

Con il pannello acceso (anche la copia di prova, `CC_PORTA=7778 CC_PROVA=1`):

```
CC_PORTA=7778 python app/command-center/prova_assistenza_pannello.py
```

Prova il tasto vero (`POST /api/assistenza/attiva`) e il riquadro senza dati di pagamento; alla fine rimette `assistenza.json`
com'era. Su Windows, se manca qualcosa, il tasto apre davvero la finestra di installazione.

| Variabile | A cosa serve |
|---|---|
| `ASSISTENZA_DIR` | cartella di `assistenza.json` e del registro |
| `ASSISTENZA_MODO` | `wsl` o `nativo` |
| `ASSISTENZA_WSL` | percorso di un `wsl.exe` (finto nelle prove) |
| `ASSISTENZA_WSL_DISTRO` | distribuzione WSL (anche `"wsl_distro"` in `assistenza.json`) |
| `ASSISTENZA_SSH`, `ASSISTENZA_SSHD`, `ASSISTENZA_SSH_KEYGEN`, `ASSISTENZA_TMUX` | i programmi del tunnel come li vede Linux |
| `ASSISTENZA_TUNNEL_DIR` | cartella Linux delle chiavi di sessione |
| `ASSISTENZA_TMATE`, `ASSISTENZA_SOCKET` | un tmate da lanciare direttamente e il suo socket |
| `ASSISTENZA_CHIAVE_PUBBLICA` | chiave pubblica di prova per i codici |
| `ASSISTENZA_PREPARA` | fuori da Windows: programma da lanciare al posto di `ASSISTENZA.ps1` |
| `ASSISTENZA_VNC`, `ASSISTENZA_SSH_WIN`, `ASSISTENZA_NETSTAT` | TightVNC, `ssh.exe` di Windows e netstat (finti nelle prove; con `ASSISTENZA_VNC` le impostazioni vanno in un JSON invece che nel registro) |
| `ASSISTENZA_SCHERMO_DIR` | cartella Windows della chiave copiata per lo schermo |
