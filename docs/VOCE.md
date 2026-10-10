# La voce di Jarvis: filtro rumore, la tua voce, Whisper e Kokoro «Sara»

*Scritta il 2026-09-30.* Come togliere il rumore di sottofondo e regolare quanto Jarvis è pronto a rispondere. Sul PC Windows la voce si accende con il tasto **Shift destro**: un tocco per parlare, un tocco per mandare.

## Cosa fa ogni pezzo

| Pezzo | Compito | Dove si regola (`app/strumenti/talk_to_jarvis_windows.py`, in alto) |
|---|---|---|
| **Filtro rumore** | toglie i bassi sotto 80 Hz (ventole, vibrazioni) e il rumore costante (ronzio, condizionatore) prima di Whisper | `PROPORZIONE_RUMORE` (0-1) e `SOGLIA_VOCE` |
| **Whisper** (`faster-whisper`) | trasforma la voce in testo, in italiano | `MODELLO_WHISPER` (di partenza `small`) |
| **Kokoro, voce «Sara»** | legge le risposte ad alta voce, in locale | modelli in `strumenti\kokoro` |

## 1. Installare il filtro rumore

`INSTALLA.ps1` lo installa da solo: mette `scipy` e `noisereduce` nell'ambiente `.venv` e li controlla con un import. Per controllare a mano:

```powershell
.\.venv\Scripts\python.exe -c "import scipy, noisereduce; print('filtro ok')"
```

Se manca, `pip install scipy noisereduce` nello stesso ambiente. Senza il filtro Jarvis funziona lo stesso ma scrive nel registro «filtro rumore non applicato».

## 2. Far riconoscere la tua voce

Kokoro ha voci fisse: la voce di Sara non si clona. Quello che si regola è **come Jarvis ti capisce**:
- Parla vicino al microfono, in una stanza non troppo rumorosa: il filtro toglie il rumore costante, non le altre persone che parlano.
- Whisper capisce meglio i nomi propri che gli si danno: se sbaglia sempre lo stesso nome, si aggiunge nella frase guida della trascrizione.
- Se Jarvis ignora frasi vere con «solo rumore di fondo», abbassa `SOGLIA_VOCE` (di partenza 0,005): dipende dal microfono. Se trascrive rumore come parole, alzala.

## 3. La reattività: Whisper e Kokoro

Il tempo fra quando smetti di parlare e quando Jarvis risponde è la somma di tre attese.

| Attesa | Cosa la allunga | Cosa fare |
|---|---|---|
| Trascrizione | il modello di Whisper è grande | `MODELLO_WHISPER = "base"` è più veloce e sbaglia di più; `"medium"` è più preciso e più lento. Provalo con le tue frasi |
| Filtro | `noisereduce` lavora sull'audio intero | `PROPORZIONE_RUMORE` più bassa (0,6) è più svelta e pulisce meno |
| Lettura | Sara legge frasi lunghe | le risposte lunghe si accorciano da sole (`LIMITE_CARATTERI_VOCE`, 800) |

Dopo ogni modifica riavvia la voce con il collegamento **Talk to Jarvis** sul Desktop.

## Se qualcosa non va

- **Nessun suono in uscita:** controlla che eSpeak NG sia installato (`INSTALLA.ps1` lo fa) e i modelli in `strumenti\kokoro`.
- **Non sente il microfono:** Impostazioni di Windows → Privacy → Microfono, deve poterlo usare Python.
- **Controllo generale:** `VERIFICA.ps1`.
