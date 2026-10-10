#!/usr/bin/env python3
"""Prove di «Aggiorna ora» sulla copia installata di Windows (aggiornamento.py, 2026-10-05).

Sul PC il pannello gira da %USERPROFILE%\\jarvis, che NON è un clone git: CLONE.txt dice dov'è il clone
(jarvis-privato-windows) e VERSIONE.installata quale versione è installata. «Aggiorna ora» lancia AGGIORNA.ps1 del clone
(git pull + INSTALLA) e poi il pannello si riavvia da solo. Qui: repository finti in una cartella temporanea, niente rete,
niente AGGIORNA.ps1 vero (applica(prova=True) si ferma prima di lanciarlo). Gira anche sul Mac.

  python app/command-center/prova_aggiornamento_windows.py
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SORGENTE = Path(__file__).resolve().parent / "aggiornamento.py"
ESITI = []


def git(cartella, *a):
    p = subprocess.run(["git", "-C", str(cartella), *a], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"git {a}: {p.stderr}")
    return p.stdout.strip()


def commit(cartella, nome, testo):
    (cartella / nome).write_text(testo, encoding="utf-8")
    git(cartella, "add", nome)
    git(cartella, "commit", "-q", "-m", f"cambia {nome}")


def controlla(nome, cond, dettaglio=""):
    ESITI.append(bool(cond))
    print(("OK    " if cond else "ERRORE") + f" {nome}" + (f"  ({dettaglio})" if not cond and dettaglio else ""))


def carica(installata):
    """Un aggiornamento.py fresco dentro installata/command-center (QUI = quella cartella)."""
    dst = installata / "command-center" / "aggiornamento.py"
    shutil.copy(SORGENTE, dst)
    spec = importlib.util.spec_from_file_location(f"agg_{id(dst)}_{len(ESITI)}", dst)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    tmp = Path(tempfile.mkdtemp(prefix="prova-agg-win-"))
    os.environ.update(GIT_AUTHOR_NAME="p", GIT_AUTHOR_EMAIL="p@p", GIT_COMMITTER_NAME="p", GIT_COMMITTER_EMAIL="p@p")
    try:
        origine = tmp / "origine.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origine)], check=True)
        clone, altro = tmp / "clone", tmp / "altro"
        subprocess.run(["git", "clone", "-q", str(origine), str(clone)], check=True, capture_output=True)
        commit(clone, "a.txt", "uno\n")
        git(clone, "push", "-q", "-u", "origin", "main")
        subprocess.run(["git", "clone", "-q", str(origine), str(altro)], check=True, capture_output=True)

        installata = tmp / "jarvis"                       # la copia installata: niente .git
        (installata / "command-center").mkdir(parents=True)
        (installata / "CLONE.txt").write_text(str(clone), encoding="utf-8")
        (installata / "VERSIONE.installata").write_text(git(clone, "rev-parse", "HEAD"), encoding="ascii")

        m = carica(installata)
        controlla("radice = il clone di CLONE.txt", m.radice() == clone, m.radice())
        controlla("copia installata riconosciuta", m.copia_installata())
        s = m.stato(True)
        controlla("tutto allineato: niente avviso", s.get("attivo") and not s.get("disponibile"), s)
        r = m.applica(prova=True)
        controlla("tutto allineato: il pulsante non lancia niente", r.get("avviato") is False, r)

        # GitHub va avanti: avviso con le novità
        commit(altro, "b.txt", "due\n")
        git(altro, "push", "-q")
        m = carica(installata)
        s = m.stato(True)
        controlla("GitHub avanti: aggiornamento disponibile", s.get("disponibile") and s.get("da_scaricare"), s)
        controlla("le novità sono i messaggi dei commit", s.get("novita") == ["cambia b.txt"], s.get("novita"))

        # una chat in corso: chiede prima, non lancia
        r = m.applica(occupato=["chat: una domanda in corso"], prova=True)
        controlla("chat in corso: chiede conferma", r.get("chiede_conferma") and not r.get("avviato"), r)
        controlla("chat in corso: dice cosa interrompe", r.get("occupato") == ["chat: una domanda in corso"], r)
        controlla("chat in corso: nessun riavvio segnato", not m._riavvio["in_corso"])
        r = m.applica(forza=True, occupato=["chat: una domanda in corso"], prova=True)
        controlla("«riavvia lo stesso»: parte", r.get("avviato") and r.get("prova"), r)
        r = m.applica(prova=True)
        controlla("niente in corso: parte senza chiedere", r.get("avviato") and r.get("prova"), r)

        # il clone scaricato a mano ma la copia installata no (VERSIONE.installata vecchia): va riallineata
        vecchia = git(clone, "rev-parse", "HEAD")
        git(clone, "merge", "-q", "--ff-only", "@{u}")
        m = carica(installata)
        s = m.stato(True)
        controlla("clone avanti, installata indietro: avviso", s.get("disponibile") and s.get("da_riavviare"), s)
        controlla("da = versione installata", s.get("locale") == vecchia[:7], (s.get("locale"), vecchia[:7]))

        # INSTALLA.ps1 ha già riacceso il pannello ma AGGIORNA.ps1 non ha ancora segnato la versione: VERSIONE.in-corso
        (installata / "VERSIONE.in-corso").write_text(git(clone, "rev-parse", "HEAD"), encoding="ascii")
        m = carica(installata)
        s = m.stato(True)
        controlla("installazione in corso di questa versione: niente avviso", not s.get("disponibile"), s)
        vecchio = time.time() - 3600
        os.utime(installata / "VERSIONE.in-corso", (vecchio, vecchio))
        s = m.stato(True)
        controlla("segno «in corso» vecchio di un'ora (AGGIORNA interrotto): l'avviso torna", s.get("disponibile"), s)
        (installata / "VERSIONE.in-corso").unlink()

        # AGGIORNA.ps1 ha segnato la versione nuova: niente più avviso
        (installata / "VERSIONE.installata").write_text(git(clone, "rev-parse", "HEAD"), encoding="ascii")
        m = carica(installata)
        s = m.stato(True)
        controlla("dopo l'aggiornamento: il riquadro sparisce", not s.get("disponibile"), s)

        # aggiornamento già partito: un secondo clic non ne lancia un altro
        commit(altro, "c.txt", "tre\n")
        git(altro, "push", "-q")
        m = carica(installata)
        m._riavvio["in_corso"] = True
        r = m.applica()
        controlla("secondo clic durante l'aggiornamento: niente doppio AGGIORNA.ps1", r.get("gia"), r)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(ESITI)}/{len(ESITI)} prove passate")
    return 0 if all(ESITI) else 1


if __name__ == "__main__":
    sys.exit(main())
