# Installazione: tutte le opzioni

La strada consigliata è quella di `INIZIA-QUI.md`: Claude Code in modalità piano, `/inizia`, approvazione, poi
`INSTALLA.ps1 -DaRisposte`. Qui ci sono i dettagli per chi vuole capire o fare a mano.

## Tre modi di lanciare l'installatore

```powershell
# 1. con le risposte raccolte da Claude Code (%USERPROFILE%\.jarvis\risposte-avvio.json)
powershell -ExecutionPolicy Bypass -File .\INSTALLA.ps1 -DaRisposte

# 2. con le domande in PowerShell
powershell -ExecutionPolicy Bypass -File .\INSTALLA.ps1

# 3. senza domande, con i predefiniti o con i parametri
powershell -ExecutionPolicy Bypass -File .\INSTALLA.ps1 -Silenzioso -NomeUtente "Marta" -NomeAssistente "Friday"
```

## Parametri

| Parametro | Cosa fa | Predefinito |
|---|---|---|
| `-DaRisposte` | legge `%USERPROFILE%\.jarvis\risposte-avvio.json` e non chiede niente | — |
| `-FileRisposte <file>` | un altro file di risposte | — |
| `-NomeUtente`, `-NomeAssistente` | come ti chiama, come si chiama | nome dell'account; Jarvis |
| `-Lingua`, `-FusoOrario` | lingua e fuso | italiano; quello di Windows |
| `-Ruolo`, `-VitaPrivata`, `-Personalita`, `-Uso` | il profilo | testi neutri |
| `-Memoria <cartella>` | la memoria condivisa | `%USERPROFILE%\Jarvis-Memoria` (o quella già scelta) |
| `-NonToccare "<testo>"` | cosa l'assistente non tocca mai | chiede prima fuori dagli spazi |
| `-Destinazione <cartella>`, `-Porta <n>` | dove installare, porta del pannello | `%USERPROFILE%\jarvis`, 7777 |
| `-Silenzioso` | nessuna domanda | — |
| `-SenzaModelliVoce` | non scarica Kokoro (circa 350 MB) | — |
| `-SenzaClaudeConfig` | non tocca `%USERPROFILE%\.claude` | — |
| `-SenzaCollegamenti`, `-SenzaCompiti`, `-SenzaAvvio`, `-SenzaPrerequisiti` | salta Desktop, attività pianificate, avvio, winget | — |
| `-RifaiFilePersonali` | riscrive i file personali dai modelli (perdi le modifiche) | — |
| `-ConAssistenza` | prepara l'assistenza a distanza (WSL, openssh, tmate) | — |

## Il file delle risposte

Modello: `modelli-personali\risposte-avvio.esempio.json`. Campi:

| Campo | Esempio |
|---|---|
| `utente.nome`, `assistente.nome` | «Mario», «Jarvis» |
| `lingua`, `tono`, `fuso_orario` | «italiano», «diretto e sintetico», «Europe/Rome» |
| `lavoro.ruolo`, `lavoro.uso`, `vita_privata` | testi liberi |
| `avvio`, `primo_progetto`, `creazione` | «zero» o «primo»; `{"nome": "<nome-progetto>", "cartella": "..."}` o `null`; «piano» o «automatica» (si parte sempre senza progetti precaricati) |
| `memoria.cartella`, `memoria.tipo` | percorso; `nuova`, `onedrive` o `obsidian` |
| `harness` | `["claude-code", "codex", "gemini", "cursor"]` |
| `voce.attiva`, `telefono.attivo`, `vps.usa` | sì o no |
| `posta.attiva`, `posta.caselle` | solo indirizzo e tipo, **mai password** |
| `non_toccare` | elenco di cartelle o azioni |
| `installazione.cartella`, `installazione.porta` | `%USERPROFILE%\\jarvis`, 7777 |

Se il file contiene qualcosa che sembra una password, un token o una chiave, l'installatore si ferma e lo dice.

## Cosa resta sul PC dopo l'installazione

| Dove | Cosa |
|---|---|
| `%USERPROFILE%\jarvis` | il programma e i tuoi file personali (`utente.json`, `CLAUDE.md`, configurazione, agenti, memoria personale) |
| `%USERPROFILE%\.jarvis` | `risposte-avvio.json`, `percorsi.json`, `installato.json`, stato dei ganci |
| `%USERPROFILE%\.claude` | skill, ganci (`hooks\`), sezione in `CLAUDE.md`, ganci uniti in `settings.json` (copia `settings.json.bak-jarvis-<data>`) |
| la memoria condivisa | vedi `docs\MEMORIA-CONDIVISA.md` |
| Desktop | quattro collegamenti |
| Utilità di pianificazione | «Jarvis Avvio» (all'accesso), «Jarvis Battito» (ogni 15 minuti), «Jarvis Giro notturno» (06:40) |

`installato.json` è il segno che la prima apertura è fatta: il `CLAUDE.md` del repository non rifà le domande.
Per rifarle: `/inizia`.
