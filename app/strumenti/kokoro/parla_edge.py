#!/usr/bin/env python3
"""Sintesi vocale primaria: Microsoft Edge TTS, voce italiana, velocità 1x.

Serve internet. Se la rete manca o Edge non risponde, chi chiama ripiega su
Kokoro Sara (parla.py), che resta la voce secondaria e funziona offline.

Uso: python strumenti/kokoro/parla_edge.py "testo da leggere" [out.wav]
"""
import asyncio
import sys

VOCE = "it-IT-ElsaNeural"   # alternative: it-IT-IsabellaNeural, it-IT-DiegoNeural
VELOCITA = "+0%"            # 1,0x
TIMEOUT_S = 20


async def _sintetizza(testo, dest_mp3):
    import edge_tts
    await asyncio.wait_for(
        edge_tts.Communicate(testo, VOCE, rate=VELOCITA).save(dest_mp3), TIMEOUT_S)


def parla(testo, dest="output.wav"):
    """Scrive il parlato in `dest` (wav). Solleva eccezione se Edge non è raggiungibile."""
    import os
    import tempfile
    import soundfile as sf

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        mp3 = f.name
    try:
        asyncio.run(_sintetizza(testo, mp3))
        dati, freq = sf.read(mp3, dtype="float32")
        sf.write(dest, dati, freq)
    finally:
        if os.path.exists(mp3):
            os.unlink(mp3)
    return dest


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    print(f"salvato: {parla(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'output.wav')}")
