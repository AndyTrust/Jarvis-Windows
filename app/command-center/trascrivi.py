#!/usr/bin/env python3
"""Trascrizione locale della dettatura nella chat.

Il browser registra la voce e la manda qui; si trascrive sul PC con faster-whisper (lo stesso modello del motore
vocale, italiano) e torna solo il testo. L'audio vive in memoria per il tempo della trascrizione: non si salva
su disco, non si registra nel log e non esce dal computer.

Il modello si carica alla prima dettatura (qualche secondo) e si scarica dalla memoria dopo SCARICA_DOPO_S secondi
di inattivita', per non tenere mezzo giga occupato.
"""
import gc
import io
import threading
import time
from pathlib import Path

MODELLO = "small"                 # lo stesso di strumenti/talk_to_jarvis_windows.py
MAX_BYTE = 12_000_000             # circa 5 minuti di audio compresso
MAX_SECONDI = 150                 # oltre questo tempo si rifiuta: la dettatura e' per frasi, non per riunioni
SCARICA_DOPO_S = 300

_lock = threading.Lock()
_modello = None
_ultimo_uso = 0.0
_timer = None


class ErroreDettatura(Exception):
    """Un errore da mostrare all'utente in parole semplici."""


def _in_cache():
    """Il modello e' gia' sul disco? (Mai scaricare mezzo giga di nascosto da una richiesta della pagina.)"""
    import os
    if os.environ.get("HF_HUB_CACHE"):
        base = Path(os.environ["HF_HUB_CACHE"])
    elif os.environ.get("HF_HOME"):
        base = Path(os.environ["HF_HOME"]) / "hub"
    else:
        base = Path.home() / ".cache" / "huggingface" / "hub"
    return (base / ("models--Systran--faster-whisper-" + MODELLO)).is_dir()


def stato():
    """{disponibile, motivo}: serve faster-whisper, PyAV, numpy e il modello gia' scaricato."""
    try:
        import av  # noqa: F401
        import faster_whisper  # noqa: F401
        import numpy  # noqa: F401
    except Exception as e:  # noqa: BLE001
        return {"disponibile": False, "motivo": "manca " + str(e).split("'")[1] if "'" in str(e) else "mancano i componenti"}
    if not _in_cache():
        return {"disponibile": False, "motivo": "il modello vocale non è ancora scaricato"}
    return {"disponibile": True, "modello": MODELLO}


def _scarica_se_fermo():
    global _modello, _timer
    with _lock:
        if _modello is not None and time.time() - _ultimo_uso >= SCARICA_DOPO_S:
            _modello = None
            gc.collect()
        _timer = None


def _avvia_timer():
    global _timer
    if _timer is None:
        _timer = threading.Timer(SCARICA_DOPO_S + 5, _scarica_se_fermo)
        _timer.daemon = True
        _timer.start()


def _carica():
    global _modello
    if _modello is None:
        from faster_whisper import WhisperModel
        _modello = WhisperModel(MODELLO, device="cpu", compute_type="int8")
    return _modello


def decodifica(dati):
    """Audio compresso (webm/opus, ogg, wav, mp4...) -> float32 mono a 16 kHz."""
    import av
    import numpy as np
    pezzi = []
    try:
        contenitore = av.open(io.BytesIO(dati))
    except Exception as e:  # noqa: BLE001
        raise ErroreDettatura("L'audio non è in un formato che riesco a leggere.") from e
    with contenitore:
        if not contenitore.streams.audio:
            raise ErroreDettatura("Nella registrazione non c'è audio.")
        r = av.AudioResampler(format="s16", layout="mono", rate=16000)

        def aggiungi(risultato):
            if risultato is None:
                return
            for f in (risultato if isinstance(risultato, (list, tuple)) else [risultato]):
                pezzi.append(f.to_ndarray().reshape(-1))

        for frame in contenitore.decode(contenitore.streams.audio[0]):
            aggiungi(r.resample(frame))
        aggiungi(r.resample(None))
    if not pezzi:
        raise ErroreDettatura("La registrazione è vuota.")
    audio = np.concatenate(pezzi).astype(np.float32) / 32768.0
    if len(audio) / 16000 > MAX_SECONDI:
        raise ErroreDettatura("La registrazione è troppo lunga: detta una frase o due alla volta.")
    return audio


def trascrivi(dati):
    """Il testo detto, in italiano. Solleva ErroreDettatura con un messaggio per l'utente."""
    global _ultimo_uso
    if not isinstance(dati, (bytes, bytearray)) or not dati:
        raise ErroreDettatura("Non è arrivato nessun audio.")
    if len(dati) > MAX_BYTE:
        raise ErroreDettatura("La registrazione è troppo grande.")
    s = stato()
    if not s["disponibile"]:
        raise ErroreDettatura("La trascrizione sul PC non è disponibile (" + s.get("motivo", "") + ").")
    audio = decodifica(bytes(dati))
    if float(abs(audio).max()) < 0.003:
        return ""                                       # silenzio: niente da trascrivere
    with _lock:
        modello = _carica()
        segmenti, _ = modello.transcribe(audio, language="it", vad_filter=True, beam_size=1, condition_on_previous_text=False)
        testo = " ".join(s_.text.strip() for s_ in segmenti).strip()
        _ultimo_uso = time.time()
        _avvia_timer()
    return " ".join(testo.split())
