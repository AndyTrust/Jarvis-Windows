#!/usr/bin/env python3
"""Talk to Jarvis, per Windows: tieni premuto Shift destro per parlare, rilascia per
inviare la richiesta (se durante la pressione tocchi un altro tasto, e' una
maiuscola: l'audio si scarta, cosi' Shift+lettera resta libero).

Motore locale per Windows:

  microfono (sounddevice) -> trascrizione locale (faster-whisper, italiano)
  -> Claude Code in modo lavoro (claude -p ... --dangerously-skip-permissions)
  -> voce italiana Sara (strumenti/kokoro/parla.py, Kokoro).

Uso: python3 strumenti/talk_to_jarvis_windows.py
"""
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parents[1] / "command-center")); import senza_finestre  # noqa: E402,F401  (Windows: niente finestre di terminale)
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import winsound
from pathlib import Path

import numpy as np
import sounddevice as sd
from pynput import keyboard

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI / "kokoro"))

# Stato condiviso col widget (strumenti/jarvis_widget_windows.py): stessa idea del
# "volto" sul Mac (state/state), qui un solo file JSON con stato + testo + livello
# audio vero (0-1), cosi' la bolla del widget disegna una forma d'onda vera, non finta.
STATO_FILE = QUI / "stato_voce.json"


def scrivi_stato(stato, testo="", livello=0.0):
    try:
        STATO_FILE.write_text(
            json.dumps({"stato": stato, "testo": testo, "livello": round(float(livello), 3), "ts": time.time()}),
            encoding="utf-8")
    except OSError:
        pass


def carica_env_jarvis():
    """Le credenziali (token di Claude Code, ecc.) stanno in ~/.env.jarvis,
    fuori da ogni repository (vedi README.md). Non sovrascrive variabili
    gia' impostate nell'ambiente."""
    f = Path.home() / ".env.jarvis"
    if not f.exists():
        return
    for riga in f.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        chiave, valore = riga.split("=", 1)
        chiave, valore = chiave.strip(), valore.strip().strip('"').strip("'")
        os.environ.setdefault(chiave, valore)


carica_env_jarvis()

TARGET = keyboard.Key.shift_r
FREQUENZA = 16000
MODELLO_WHISPER = "small"
LIMITE_CARATTERI_VOCE = 800
PROPORZIONE_RUMORE = 0.85  # 0-1: quanto rumore togliere; più alto pulisce di più ma può "metallizzare" la voce
SOGLIA_VOCE = 0.005        # RMS sotto cui, dopo il filtro, c'è solo rumore: da tarare sul microfono vero

_registrando = False
_frammenti = []
_stream = None
_press_t = None
_chord = False
_lock = threading.Lock()
_whisper = None
_livello_corrente = 0.0
_thread_livello = None


def log(msg):
    print(f"[talk-to-jarvis] {msg}", flush=True)


def modello_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        log("carico il modello Whisper (la prima volta scarica ~500MB)...")
        _whisper = WhisperModel(MODELLO_WHISPER, device="cpu", compute_type="int8")
    return _whisper


def filtra_rumore(audio):
    """Filtro del rumore ambientale prima di Whisper: taglia i bassi sotto 80 Hz (ventole,
    vibrazioni) e toglie il rumore costante (ronzio, condizionatore) con noisereduce.
    Se il filtro non c'è o fallisce, si trascrive l'audio com'è."""
    try:
        import noisereduce as nr
        from scipy.signal import butter, sosfilt
        audio = sosfilt(butter(4, 80, btype="highpass", fs=FREQUENZA, output="sos"), audio)
        return nr.reduce_noise(y=audio, sr=FREQUENZA, stationary=True,
                               prop_decrease=PROPORZIONE_RUMORE).astype(np.float32)
    except Exception as e:
        log(f"filtro rumore non applicato: {e}")
        return audio


def callback_audio(indata, frames, tempo, stato):
    global _livello_corrente
    if _registrando:
        _frammenti.append(indata.copy())
        # RMS del blocco appena arrivato, con un minimo di guadagno: il microfono
        # a riposo e' quasi silenzioso, senza *6 la barra non si vedrebbe muovere
        _livello_corrente = min(1.0, float(np.sqrt(np.mean(indata ** 2))) * 6)


def _scrivi_livello_in_ciclo():
    """Mentre si registra, scrive il livello vero ~10 volte al secondo: la bolla
    del widget disegna una forma d'onda vera, non un'animazione finta."""
    while _registrando:
        scrivi_stato("ascolto", "", _livello_corrente)
        time.sleep(0.08)


def inizia_registrazione():
    global _stream, _frammenti, _thread_livello
    _frammenti = []
    _stream = sd.InputStream(samplerate=FREQUENZA, channels=1, dtype="float32", callback=callback_audio)
    _stream.start()
    scrivi_stato("ascolto", "", 0.0)
    _thread_livello = threading.Thread(target=_scrivi_livello_in_ciclo, daemon=True)
    _thread_livello.start()
    log("ascolto... (rilascia Shift destro per inviare)")


def ferma_e_elabora():
    global _stream
    if _stream is not None:
        _stream.stop()
        _stream.close()
        _stream = None
    if not _frammenti:
        log("nessun audio registrato")
        scrivi_stato("inattivo")
        return
    audio = np.concatenate(_frammenti, axis=0).flatten()
    durata = len(audio) / FREQUENZA
    if durata < 0.4:
        log("registrazione troppo breve, ignorata")
        scrivi_stato("inattivo")
        return
    scrivi_stato("penso", "trascrivo...")
    log(f"trascrivo ({durata:.1f}s)...")
    audio = filtra_rumore(audio)
    if float(np.sqrt(np.mean(audio ** 2))) < SOGLIA_VOCE:
        log("solo rumore di fondo, ignorato")
        scrivi_stato("inattivo")
        return
    try:
        # vad_filter: Whisper non vede i tratti senza voce, dove inventa frasi dal rumore
        segmenti, _ = modello_whisper().transcribe(audio, language="it", vad_filter=True,
                                                   condition_on_previous_text=False)
        testo = " ".join(s.text.strip() for s in segmenti).strip()
    except Exception as e:
        log(f"errore nella trascrizione: {e}")
        scrivi_stato("inattivo")
        return
    if not testo:
        log("non ho capito nulla")
        scrivi_stato("inattivo")
        return
    log(f"tu: {testo}")
    scrivi_stato("penso", testo)
    chiedi_a_claude(testo)


# --- Una sola conversazione, quella della voce: la chat del Command Center la legge da chat.jsonl
# e ci scrive dentro (backtalk/.esterno_in). Claude Code la ricorda con un session-id proprio.
CHAT_JSONL = QUI.parent / "backtalk" / "chat.jsonl"
ESTERNO_IN = QUI.parent / "backtalk" / ".esterno_in"
SESSIONE_FILE = QUI / "sessione_voce.json"
_turno_lock = threading.Lock()  # un turno alla volta: voce e messaggi scritti non si accavallano


def registra_chat(chi, testo):
    """Aggiunge una battuta a backtalk/chat.jsonl (chi = 'utente' o 'jarvis'); formato letto da /api/chat/storia."""
    try:
        CHAT_JSONL.parent.mkdir(parents=True, exist_ok=True)
        with open(CHAT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "chi": chi, "testo": testo},
                               ensure_ascii=False) + "\n")
    except OSError as e:
        log(f"chat non registrata: {e}")


def sessione_voce():
    """(id, esiste_gia): la conversazione di Claude Code che la voce continua a ogni turno."""
    import uuid
    try:
        return json.loads(SESSIONE_FILE.read_text(encoding="utf-8"))["id"], True
    except Exception:
        nuovo = str(uuid.uuid4())
        SESSIONE_FILE.write_text(json.dumps({"id": nuovo}), encoding="utf-8")
        return nuovo, False


def leggi_messaggi_scritti():
    """Messaggi scritti nella chat del Command Center (backtalk/.esterno_in): li prende e svuota il file."""
    try:
        testo = ESTERNO_IN.read_text(encoding="utf-8-sig")
        if not testo.strip():
            return []
        ESTERNO_IN.write_text("", encoding="utf-8")
    except OSError:
        return []
    return [r.strip() for r in testo.splitlines() if r.strip()]


def ciclo_messaggi_scritti():
    while True:
        for msg in leggi_messaggi_scritti():
            log(f"scritto in chat: {msg}")
            scrivi_stato("penso", msg)
            chiedi_a_claude(msg)
        time.sleep(1.0)


AVVISI_S = (8, 40, 90)  # se la risposta tarda, Jarvis lo dice a voce: subito e poi ogni tanto
FRASI_AVVISO = ("Ricevuto, ci sto lavorando.", "Ci sto ancora lavorando, ti avviso appena ho finito.",
                "Il lavoro è lungo, sono ancora al lavoro.")


def _tienimi_aggiornato(fine):
    """Mentre Claude lavora, a voce: ricevuto dopo 8 secondi, poi aggiornamenti. Tace appena arriva la risposta."""
    passato = 0
    for attesa, frase in zip(AVVISI_S, FRASI_AVVISO):
        if fine.wait(attesa - passato):
            return
        passato = attesa
        log(f"avviso a voce: {frase}")
        parla(frase)


def chiedi_a_claude(testo):
    with _turno_lock:
        _chiedi_a_claude(testo)


def _chiedi_a_claude(testo):
    # CLAUDE_CODE_OAUTH_TOKEN e ANTHROPIC_API_KEY insieme mandano in conflitto
    # l'autenticazione (401 "API key is invalid", verificato il 28/09/2026):
    # il primo e' quello giusto per la CLI, il secondo si toglie dall'ambiente del figlio.
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    registra_chat("utente", testo)
    sid, esiste = sessione_voce()
    fine = threading.Event()
    threading.Thread(target=_tienimi_aggiornato, args=(fine,), daemon=True).start()
    try:
        r = subprocess.run(
            ["claude", "-p", testo, "--dangerously-skip-permissions",  # modo lavoro (30/09: tolto il piano)
             "--resume" if esiste else "--session-id", sid,
             "--append-system-prompt", "Risposta a voce: massimo 2 frasi brevi, niente elenchi, vai dritto al punto."],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
            cwd=str(QUI.parent), env=env,
        )
        risposta = (r.stdout or r.stderr or "").strip()
        if r.returncode != 0 and esiste and "session" in (r.stderr or "").lower():
            SESSIONE_FILE.unlink(missing_ok=True)  # sessione sparita: la prossima volta ne parte una nuova
    except Exception as e:
        risposta = f"Errore chiamando Claude Code: {e}"
    finally:
        fine.set()
    # il blocco «Stato di avanzamento» e' per la chat scritta: a voce non si legge e non va nella conversazione vocale
    import re
    corpo = re.split(r"\*{0,2}\s*Stato di avanzamento", risposta, maxsplit=1)[0].strip()
    if not corpo:  # la risposta era solo il blocco: a voce basta «cosa è stato fatto»
        m = re.search(r"Cosa è stato fatto:?\**\s*(.+)", risposta)
        corpo = m.group(1).strip() if m else ""
    risposta = corpo or risposta
    if not risposta:
        risposta = "Non ho ricevuto risposta."
    log(f"jarvis: {risposta}")
    registra_chat("jarvis", risposta)
    scrivi_stato("parlo", risposta)
    parla(risposta)
    scrivi_stato("inattivo")


def parla(testo):
    try:
        from parla import parla as sintetizza, per_voce  # strumenti/kokoro/parla.py
    except Exception as e:
        log(f"Kokoro non disponibile: {e}")
        return
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        dest = f.name
    try:
        frase = per_voce(testo)[:LIMITE_CARATTERI_VOCE]
        try:  # voce primaria: Edge TTS italiano (serve internet)
            from parla_edge import parla as sintetizza_edge
            sintetizza_edge(frase, dest)
            log("voce: Edge TTS")
        except Exception as e:  # rete assente o Edge giu': ripiego su Kokoro Sara (offline)
            log(f"Edge TTS non disponibile ({e}), uso Kokoro")
            sintetizza(frase, dest)
        _riproduci_con_livello(dest, testo)
    except Exception as e:
        log(f"errore nella voce: {e}")
    finally:
        Path(dest).unlink(missing_ok=True)


def _riproduci_con_livello(percorso_wav, testo):
    """Riproduce il wav di Kokoro e, mentre suona, scrive il livello vero a blocchi
    di ~80ms: la bolla del widget disegna la forma d'onda della voce, non una finta."""
    try:
        import soundfile as sf
        dati, sr = sf.read(percorso_wav, dtype="float32")
    except Exception:
        winsound.PlaySound(percorso_wav, winsound.SND_FILENAME)  # fallback senza livello
        return
    sd.play(dati, sr)
    passo = max(1, int(sr * 0.08))
    for i in range(0, len(dati), passo):
        blocco = dati[i:i + passo]
        livello = min(1.0, float(np.sqrt(np.mean(blocco ** 2))) * 4) if len(blocco) else 0.0
        scrivi_stato("parlo", testo, livello)
        time.sleep(0.08)
    sd.wait()


def annulla_registrazione(motivo="Shift destro era usato con un altro tasto"):
    """Shift destro usato per una maiuscola (o con un altro tasto): scarta l'audio, non invia nulla."""
    global _stream
    if _stream is not None:
        _stream.stop()
        _stream.close()
        _stream = None
    _frammenti.clear()
    scrivi_stato("inattivo")
    log(f"annullato: {motivo}")


def on_press(key):
    """Tieni premuto Shift destro per parlare (push-to-talk)."""
    global _press_t, _chord, _registrando
    if key == TARGET:
        if _press_t is None:  # la ripetizione automatica del tasto tenuto giù non riparte
            _press_t = time.monotonic()
            _chord = False
            with _lock:
                _registrando = True
            inizia_registrazione()
        return
    if _press_t is not None:
        _chord = True


def on_release(key):
    """Rilascia Shift destro per inviare la richiesta."""
    global _press_t, _chord, _registrando
    if key != TARGET:
        return
    era_combinazione = _chord
    _press_t, _chord = None, False
    with _lock:
        _registrando = False
    if era_combinazione:
        annulla_registrazione()
    else:
        threading.Thread(target=ferma_e_elabora, daemon=True).start()


# --- Il tasto «Voce» del Command Center: la stessa registrazione dello Shift destro, ma a clic.
# Il pannello scrive un file con il comando e l'ora (avvia, invia, annulla); qui lo si legge
# ogni quarto di secondo. Un comando più vecchio di 30 secondi non vale (il motore era spento).
COMANDO_FILE = QUI / ".comando_voce.json"
MASSIMO_PANNELLO_S = 60        # il microfono aperto da un clic non resta aperto per sempre
_avvio_pannello = None         # quando è partita la registrazione a clic (None = non è a clic)


def avvia_da_pannello():
    global _registrando, _avvio_pannello
    if _registrando or _press_t is not None:        # già in ascolto, o Shift destro tenuto giù
        return
    with _lock:
        _registrando = True
    _avvio_pannello = time.monotonic()
    inizia_registrazione()
    log("ascolto dal pannello... (clic su Voce per inviare)")


def chiudi_da_pannello(invia):
    global _registrando, _avvio_pannello
    da_pannello = _avvio_pannello is not None
    _avvio_pannello = None
    if not (_registrando and da_pannello):              # niente da chiudere, o è lo Shift a registrare
        return
    with _lock:
        _registrando = False
    if invia:
        threading.Thread(target=ferma_e_elabora, daemon=True).start()
    else:
        annulla_registrazione("annullato dal pannello")


def ciclo_comandi_pannello():
    while True:
        try:
            if COMANDO_FILE.exists():
                try:
                    dati = json.loads(COMANDO_FILE.read_text(encoding="utf-8-sig"))
                except ValueError:
                    dati = {}
                COMANDO_FILE.unlink(missing_ok=True)
                if time.time() - float(dati.get("ts") or 0) <= 30:
                    cmd = dati.get("cmd")
                    log(f"comando dal pannello: {cmd}")
                    if cmd == "avvia":
                        avvia_da_pannello()
                    elif cmd == "invia":
                        chiudi_da_pannello(True)
                    elif cmd == "annulla":
                        chiudi_da_pannello(False)
            if _avvio_pannello is not None and time.monotonic() - _avvio_pannello > MASSIMO_PANNELLO_S:
                log(f"{MASSIMO_PANNELLO_S} secondi di ascolto: invio quello che ho sentito")
                chiudi_da_pannello(True)
        except Exception as e:  # noqa: BLE001  (il ciclo non deve morire)
            log(f"comandi dal pannello: {e}")
        time.sleep(0.25)


def main():
    scrivi_stato("inattivo")
    COMANDO_FILE.unlink(missing_ok=True)       # un comando rimasto da un'altra volta non deve far partire il microfono
    threading.Thread(target=ciclo_messaggi_scritti, daemon=True).start()
    threading.Thread(target=ciclo_comandi_pannello, daemon=True).start()
    log("pronto: tieni premuto Shift destro per parlare, rilascia per inviare (Ctrl+C per uscire)")
    with keyboard.Listener(on_press=on_press, on_release=on_release) as lis:
        lis.join()


if __name__ == "__main__":
    main()
