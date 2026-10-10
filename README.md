# Jarvis per Windows

Un assistente personale per Windows 10 e 11, costruito sopra Claude Code: un pannello di controllo nel browser
(Command Center), una lavagna di agenti che lavorano insieme, la voce in locale, l'orb sul desktop e una **memoria
condivisa** fra Claude Code, l'assistente e gli altri programmi di intelligenza artificiale che usi.

Il repository è neutro: non contiene nomi, dati o segreti di nessuno. Al primo avvio Claude Code ti chiede come vuoi
essere chiamato, come vuoi chiamare l'assistente (di base «Jarvis») e dove tenere la memoria. Si parte da zero: nessun
progetto, spazio o agente precaricato. Quando nomini un progetto l'assistente lo crea (cartella, memoria, `Stato.md`,
capogruppo) e il capogruppo crea gli specialisti che servono, uno alla volta: l'assistente si programma da solo sulle
tue richieste. Guida: [docs/wiki/Progetti-e-agenti.md](docs/wiki/Progetti-e-agenti.md).

Versione 0.6.0 (allineata a Jarvis per Mac 0.6.0 del 2026-10-09). Distribuzione gratuita, licenza GPL-3.0.

## Per cominciare

Leggi **[INIZIA-QUI.md](INIZIA-QUI.md)**. In breve:

```powershell
winget install -e --id Git.Git
irm https://claude.ai/install.ps1 | iex          # installatore ufficiale di Claude Code
git clone <indirizzo del repository> Jarvis-Windows
cd Jarvis-Windows
claude --permission-mode plan                     # poi scrivi: /inizia
```

Claude Code fa le domande di avvio una per volta in modalità piano, ti mostra il piano e, solo dopo il tuo sì, lancia
`INSTALLA.ps1 -DaRisposte`. Chi preferisce fare da sé può lanciare `INSTALLA.ps1` direttamente: fa le stesse domande in
PowerShell.

## Cosa serve

- Windows 10 1809 o più recente, oppure Windows 11; 4 GB di RAM; circa 2 GB liberi.
- Un abbonamento Claude Pro, Max, Team o Enterprise, oppure un account Console (Claude Code non va con il piano gratuito).
- Python 3.10 o più recente (l'installatore mette Python 3.12 con winget se manca), Git for Windows consigliato.
- Facoltativi: microfono e casse per la voce, un telefono Android, un server remoto (VPS).

## Cosa fa l'installazione

| Passo | Cosa fa |
|---|---|
| Domande di avvio | nome tuo e dell'assistente, lingua, tono, fuso, lavoro, da zero o primo progetto, memoria, harness, voce, cosa non toccare |
| Prerequisiti | Python 3.12 e eSpeak NG con winget se mancano; controlla Claude Code e il browser |
| Programma | copia il codice in `%USERPROFILE%\jarvis`, ambiente `.venv` con le librerie verificate da un import |
| Voce | scarica i modelli di Kokoro (circa 350 MB) e ne controlla dimensione e impronta |
| File personali | `utente.json`, `CLAUDE.md`, configurazione, `spazi.json` vuoto, i due aiutanti di casa, memoria iniziale: solo se mancano |
| Claude Code | skill (fra cui `aggiorna-memoria` e `nuovo-progetto`), comandi `/nuovo-progetto` e `/nuovo-agente`, ganci di sicurezza e ganci della memoria automatica, uniti a `settings.json` con copia di sicurezza |
| Memoria condivisa | struttura `Comune\ Diario\ Report\ Sessioni\ Claude\`, giunzioni dalle cartelle `memory` di Claude Code, file d'ingresso per gli altri harness |
| Desktop e avvio | collegamenti «Jarvis Command Center», «Jarvis Orb», «Talk to Jarvis», «Aggiorna Jarvis»; attività pianificate (avvio, battito, pulizia, giro notturno) |
| Verifica | avvia il pannello e lancia `VERIFICA.ps1` |

Si può rilanciare quando vuoi: aggiorna il codice e non tocca i tuoi file personali.

## Documentazione

| Documento | Di cosa parla |
|---|---|
| [INIZIA-QUI.md](INIZIA-QUI.md) | installazione passo per passo con Claude Code |
| [docs/INSTALLAZIONE.md](docs/INSTALLAZIONE.md) | tutte le opzioni di `INSTALLA.ps1` e il file delle risposte |
| [docs/COME-FUNZIONA.md](docs/COME-FUNZIONA.md) | le parti del programma e come si parlano |
| [docs/wiki/Progetti-e-agenti.md](docs/wiki/Progetti-e-agenti.md) | come nascono, cambiano e si archiviano progetti e agenti |
| [docs/wiki/Memoria-condivisa.md](docs/wiki/Memoria-condivisa.md) | la memoria comune, le giunzioni, stato e diario aggiornati da soli, la pulizia di `.claude` |
| [docs/wiki/Vault.md](docs/wiki/Vault.md) | il Vault: password, carte e PIN cifrati sul PC (DPAPI), recupero con 24 parole, importazione da Chrome |
| [docs/VOCE.md](docs/VOCE.md) | Whisper, Kokoro, filtro del rumore |
| [docs/VPS-FACOLTATIVA.md](docs/VPS-FACOLTATIVA.md) | il server remoto facoltativo e il link di affiliazione |
| [docs/AGGIORNARE.md](docs/AGGIORNARE.md) | aggiornare senza perdere niente |
| [docs/DISINSTALLARE.md](docs/DISINSTALLARE.md) | togliere tutto, passo per passo |
| [docs/PROBLEMI-WINDOWS.md](docs/PROBLEMI-WINDOWS.md) | ExecutionPolicy, antivirus e SmartScreen, percorsi lunghi, proxy |
| [docs/DIFFERENZE-DAL-MAC.md](docs/DIFFERENZE-DAL-MAC.md) | cosa c'è e cosa manca rispetto a Jarvis per Mac |
| [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md), [docs/LAVAGNA-E-PAGINE.md](docs/LAVAGNA-E-PAGINE.md), [docs/PERSONALIZZAZIONE.md](docs/PERSONALIZZAZIONE.md), [docs/ASSISTENZA.md](docs/ASSISTENZA.md) | approfondimenti |

## Server remoto (facoltativo)

Jarvis funziona tutto sul tuo PC. Un server remoto serve solo se vuoi l'assistente acceso anche a PC spento. Se ne vuoi
uno, questo è un **link di affiliazione**: https://www.hostinger.com/it/prezzi?REFERRALCODE=ITALOMARZIANO. Chi compra da lì riconosce una commissione
all'autore del progetto. Puoi scegliere qualunque altro fornitore. Dettagli in [docs/VPS-FACOLTATIVA.md](docs/VPS-FACOLTATIVA.md).

## Segreti e dati personali

- Password, token e chiavi stanno solo in `%USERPROFILE%\.env.jarvis`, sul tuo PC. Mai nel repository, mai nella memoria
  condivisa. `collega_memoria.py` controlla che nella memoria non ce ne siano; `INSTALLA.ps1 -DaRisposte` si ferma se il
  file delle risposte ne contiene uno.
- Il tuo profilo, la memoria, le risposte di avvio e i registri sono nel `.gitignore`.
- Password dei siti, carte e PIN: il **Vault** del Command Center (voce «Vault»). Parte vuoto, i dati stanno in
  `%APPDATA%\Jarvis\vault\`, la chiave del dispositivo è protetta da DPAPI di Windows. Gli agenti non lo usano sul
  browser in Windows (solo Mac e server Linux). Guida: [docs/wiki/Vault.md](docs/wiki/Vault.md).
- Prima di pubblicare una modifica: `python CONTROLLA-PULIZIA.py` deve dire «0 nomi di file e 0 righe».

## Licenza

Il codice di questo progetto è distribuito con licenza **GNU GPL versione 3** (file [LICENSE](LICENSE)). Puoi usarlo,
studiarlo, modificarlo e ridistribuirlo. Chi modifica e ridistribuisce deve restare sotto GPL-3.0 e dare il codice
sorgente a chi riceve il programma. La GPL non vieta di vendere copie o servizi: obbliga a passare le stesse libertà.
Le parti di terzi incluse o scaricate (Kokoro, Whisper, librerie Python, immagini, skill) hanno le loro licenze:
elenco e compatibilità in [NOTICE.md](NOTICE.md).
