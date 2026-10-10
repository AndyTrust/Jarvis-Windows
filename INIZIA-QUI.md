# Inizia qui: Jarvis su Windows con Claude Code

Questa guida porta da un PC Windows 10 o 11 vuoto a Jarvis installato. Il lavoro lo fa Claude Code: tu rispondi a
qualche domanda e approvi il piano. Tempo: 20-40 minuti, quasi tutto di download.

## Cosa serve

| Cosa | Perché | Obbligatorio |
|---|---|---|
| Windows 10 versione 1809 o più recente, oppure Windows 11 | requisito di Claude Code | sì |
| 4 GB di RAM, processore x64 o ARM64 | requisito di Claude Code | sì |
| Un abbonamento Claude Pro, Max, Team o Enterprise, oppure un account Console | Claude Code non funziona con il piano gratuito | sì |
| Git for Windows | scaricare il repository; dà a Claude Code la shell Bash | consigliato |
| Python 3.10 o più recente | il programma è in Python (INSTALLA.ps1 lo installa da solo se manca) | sì, automatico |
| Circa 2 GB liberi | librerie Python, voce (circa 400 MB) | sì |
| Microfono e casse | solo per la voce | no |

Fonte dei requisiti e dei comandi di Claude Code: pagina ufficiale «Advanced setup»,
https://code.claude.com/docs/en/setup, letta il 2026-10-10. Se un comando qui sotto non va più, vale quella pagina.

## Passo 1. Apri PowerShell

Menu Start, scrivi «PowerShell», apri «Windows PowerShell». Non serve aprirlo come amministratore.
La riga deve cominciare con `PS C:\Users\...>`.

## Passo 2. Installa Git for Windows e Claude Code

```powershell
winget install -e --id Git.Git
irm https://claude.ai/install.ps1 | iex
```

Il secondo comando è l'installatore ufficiale di Claude Code (non mostra l'avanzamento mentre scarica). In alternativa:
`winget install Anthropic.ClaudeCode` (con winget gli aggiornamenti li lanci tu: `winget upgrade Anthropic.ClaudeCode`).
Dal Prompt dei comandi (CMD) il comando ufficiale è
`curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd`.

Chiudi PowerShell, riaprilo e controlla:

```powershell
claude --version
git --version
```

Se `claude` non viene riconosciuto, la cartella non è ancora nel PATH: vedi `docs\PROBLEMI-WINDOWS.md`.

## Passo 3. Scarica Jarvis

```powershell
cd $env:USERPROFILE
git clone <indirizzo del repository> Jarvis-Windows
cd Jarvis-Windows
```

Senza Git: scarica lo ZIP dalla pagina del repository, estrailo in `%USERPROFILE%\Jarvis-Windows`, poi
tasto destro su un file `.ps1` → Proprietà → «Annulla blocco» (oppure `Get-ChildItem -Recurse | Unblock-File`).

## Passo 4. Apri Claude Code in modalità piano

```powershell
claude --permission-mode plan
```

Al primo avvio Claude Code ti chiede di accedere con il browser. Poi scrivi:

```
/inizia
```

Claude legge `CLAUDE.md` del repository, vede che Jarvis non è installato e ti fa le **domande di avvio**, una alla
volta: come vuoi essere chiamato e come vuoi chiamare l'assistente, lingua e tono, fuso orario, che lavoro fai e se vuoi
partire da zero o creare subito il primo progetto, dove tenere la memoria condivisa, quali altri programmi di intelligenza artificiale usi, voce, telefono,
server remoto, posta, cosa non deve toccare mai. Ogni domanda ha un valore predefinito: se non sai, rispondi «invio».

**Non scrivere password o chiavi nelle risposte.** Vanno dopo in `%USERPROFILE%\.env.jarvis`.

## Passo 5. Approva il piano

Claude ti mostra il piano: il file delle risposte, cosa installerà, cosa non toccherà, come si torna indietro.
Se va bene, rispondi «sì». Solo allora Claude esce dalla modalità piano, scrive
`%USERPROFILE%\.jarvis\risposte-avvio.json` e lancia:

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALLA.ps1 -DaRisposte
```

Puoi lanciarlo anche tu a mano. Senza `-DaRisposte` l'installatore fa le domande da solo; con `-Silenzioso` non chiede
niente e usa i predefiniti.

## Passo 6. Controlla

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFICA.ps1
```

Sul Desktop trovi «Jarvis Command Center», «Jarvis Orb», «Talk to Jarvis» e «Aggiorna Jarvis». Apri una **nuova**
sessione di Claude Code: i ganci partono da lì.

## Passo 7. Il primo progetto

Si parte da zero: nessun progetto, spazio o agente precaricato. Il Command Center mostra «Nessun progetto ancora».
Quando ti serve, dillo all'assistente («apri il progetto Negozio», «mi serve qualcuno che segua le fatture») oppure
scrivi in Claude Code `/nuovo-progetto <nome>` e `/nuovo-agente <progetto> <ruolo>`. Nasce il progetto con la sua
cartella (`File\` per i tuoi file), la memoria, lo `Stato.md` e il capogruppo `<id>-ceo`, che poi crea gli specialisti
uno alla volta. Lo stesso si fa dalla pagina «Progetti» del Command Center. Guida: `docs\wiki\Progetti-e-agenti.md`.

## Dove andare dopo

- `docs\COME-FUNZIONA.md`: le parti del programma e come si parlano.
- `docs\wiki\Progetti-e-agenti.md`: come nascono, cambiano e si archiviano progetti e agenti.
- `docs\wiki\Memoria-condivisa.md`: la memoria comune a Claude Code, all'assistente e agli altri programmi, e come si
  aggiorna da sola.
- `docs\wiki\Vault.md`: il Vault, dove tenere password, carte e PIN (parte vuoto, lo crei con email e password).
- `docs\VOCE.md`, `docs\VPS-FACOLTATIVA.md`, `docs\AGGIORNARE.md`, `docs\DISINSTALLARE.md`, `docs\PROBLEMI-WINDOWS.md`.
