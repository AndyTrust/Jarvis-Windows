#!/usr/bin/env python3
"""Gancio di Claude Code: aggiorna da solo lo stato di avanzamento dello spazio su cui si lavora.

Si installa (installa_claude.py) su tre eventi: Stop (fine di ogni risposta), PreCompact (prima di compattare il
contesto) e SessionEnd (fine della sessione). Claude Code passa su stdin un JSON con session_id, transcript_path,
cwd e hook_event_name. Il gancio legge solo la parte nuova della trascrizione e scrive in
<memoria condivisa>\\<spazio>\\Stato.md:

  FATTO          i file modificati (Edit/Write) e le righe «FATTO: ...» che Claude scrive nelle risposte
  DA FARE        le righe «DA FARE: ...»; una riga «FATTO: X» uguale a un «DA FARE: X» lo toglie dal DA FARE
  ERRORI         i risultati di strumenti finiti in errore e le righe «ERRORE: ...»
  Ultime sessioni  una riga per sessione: data e ora, cartella, ultima richiesta, evento
  *Aggiornato: AAAA-MM-GG HH:MM*

Lo spazio si trova da %USERPROFILE%\\.jarvis\\percorsi.json (lo scrive collega_memoria.py): lo spazio la cui cartella
contiene la cartella di lavoro; altrimenti quello il cui nome compare nel percorso; altrimenti «Generale».
A fine sessione (SessionEnd) aggiunge una riga al diario del giorno e, con --jarvis <cartella>, rilancia
collega_memoria.py --applica --zitto, così anche la memoria di un progetto nuovo entra nella memoria condivisa.

Non blocca mai Claude Code: esce sempre con 0, gli errori vanno in %USERPROFILE%\\.jarvis\\stato-ganci.log.
I testi passano da un filtro che toglie token e chiavi prima di scrivere.

Prova a mano (senza Claude Code):
    python stato_progetti.py --prova <trascrizione.jsonl> --cwd <cartella> [--evento Stop] [--home <cartella>]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

MAX = {"FATTO": 40, "DA FARE": 40, "ERRORI": 30, "Ultime sessioni": 15}
SEZIONI = ("FATTO", "DA FARE", "ERRORI", "Ultime sessioni")
MARCA = re.compile(r"^\s*[-*]?\s*\**(FATTO|DA FARE|ERRORE|ERRORI|DA SALVARE)\**\s*:\s*(.+?)\s*$", re.I | re.M)
SEGRETI = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{12,}|github_pat_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{8,}"
                     r"|AIza[0-9A-Za-z_-]{20,}|AKIA[0-9A-Z]{12,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_.-]+"
                     r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:password|passwd|token|secret|api[_-]?key)\s*[=:]\s*\S+)")


def adesso():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def pulisci(t: str, n=160) -> str:
    t = SEGRETI.sub("[tolto]", " ".join(str(t).split()))
    return t if len(t) <= n else t[: n - 1] + "…"


def base(percorso: str) -> str:
    """Il nome del file da un percorso Windows o POSIX, su qualunque sistema."""
    return re.split(r"[\\/]", str(percorso).rstrip("\\/"))[-1]


def leggi_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def dentro(figlio: str, padre: str) -> bool:
    try:
        f, p = os.path.normcase(os.path.abspath(figlio)), os.path.normcase(os.path.abspath(padre))
        return f == p or f.startswith(p.rstrip("\\/") + os.sep)
    except (TypeError, ValueError):
        return False


def trova_spazio(percorsi: dict, cwd: str) -> str:
    spazi = percorsi.get("spazi") or []
    for s in spazi:
        for c in s.get("cartelle") or []:
            if c and dentro(cwd, os.path.expandvars(os.path.expanduser(c))):
                return s["nome"]
    parti = [p.lower() for p in re.split(r"[\\/]", cwd) if p]
    for s in spazi:
        if s.get("nome", "").lower() in parti:
            return s["nome"]
    return "Generale"


def leggi_nuovo(trascrizione: Path, inizio: int):
    """Le righe della trascrizione dopo il byte «inizio». Torna (righe, nuovo inizio)."""
    try:
        with open(trascrizione, "rb") as f:
            f.seek(0, 2)
            fine = f.tell()
            if inizio > fine:            # trascrizione riscritta (compattazione): si riparte
                inizio = 0
            f.seek(inizio)
            dati = f.read()
    except OSError:
        return [], inizio
    ultimo_a_capo = dati.rfind(b"\n")
    if ultimo_a_capo < 0:
        return [], inizio
    righe = []
    for r in dati[: ultimo_a_capo + 1].splitlines():
        try:
            righe.append(json.loads(r))
        except ValueError:
            continue
    return righe, inizio + ultimo_a_capo + 1


def testi(contenuto):
    if isinstance(contenuto, str):
        return [contenuto]
    return [c.get("text", "") for c in contenuto or [] if isinstance(c, dict) and c.get("type") == "text"]


def analizza(righe: list):
    file_toccati, errori, marche, ultima = [], [], [], ""
    for r in righe:
        m = r.get("message") or {}
        tipo = r.get("type") or m.get("role")
        cont = m.get("content")
        if tipo == "assistant" and isinstance(cont, list):
            for c in cont:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use" and c.get("name") in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                    fp = (c.get("input") or {}).get("file_path") or (c.get("input") or {}).get("notebook_path")
                    if fp and fp not in file_toccati:
                        file_toccati.append(fp)
                elif c.get("type") == "text":
                    for chi, testo in MARCA.findall(c.get("text", "")):
                        marche.append((chi.upper(), pulisci(testo, 220)))
        elif tipo == "user":
            if isinstance(cont, list):
                for c in cont:
                    if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"):
                        t = c.get("content")
                        t = t if isinstance(t, str) else " ".join(testi(t))
                        errori.append(pulisci(t.splitlines()[0] if t.strip() else "errore senza testo", 160))
            if not r.get("isMeta"):
                t = " ".join(testi(cont)).strip()
                if t and not t.startswith("<"):
                    ultima = pulisci(t, 120)
    return file_toccati, errori, marche, ultima


def leggi_stato(f: Path, spazio: str):
    sez = {k: [] for k in SEZIONI}
    testa = []
    if f.exists():
        corrente = None
        for riga in f.read_text(encoding="utf-8-sig").splitlines():
            if riga.startswith("## "):
                corrente = riga[3:].strip()
                sez.setdefault(corrente, [])
                continue
            if corrente is None:
                if not riga.startswith("*Aggiornato:"):
                    testa.append(riga)
            elif riga.strip():
                sez[corrente].append(riga)
    while testa and not testa[-1].strip():
        testa.pop()
    if not any(r.startswith("# ") for r in testa):
        testa.insert(0, f"# Stato — {spazio}")
    return testa, sez


def senza_data(voce: str) -> str:
    return re.sub(r"^- (\[[ x]\] )?(\d{4}-\d{2}-\d{2} \d{2}:\d{2} · )?", "", voce).strip().lower()


def aggiungi(lista: list, voce: str, massimo: int):
    chiave = senza_data(voce)
    lista[:] = [v for v in lista if senza_data(v) != chiave]
    lista.insert(0, voce)
    del lista[massimo:]


def scrivi_stato(f: Path, testa: list, sez: dict, evento: str, sessione: str):
    corpo = testa + ["", f"*Aggiornato: {adesso()} ({evento}, sessione {sessione[:8]})*", ""]
    for k in list(SEZIONI) + [k for k in sez if k not in SEZIONI]:
        corpo += [f"## {k}", ""] + sez.get(k, []) + [""]
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text("\n".join(corpo).rstrip("\n") + "\n", encoding="utf-8")
    os.replace(tmp, f)


class Lucchetto:
    """Più sessioni insieme sullo stesso Stato.md: un file-lucchetto, attesa massima 3 secondi."""
    def __init__(self, f: Path):
        self.f = f.with_name(f.name + ".lock")

    def __enter__(self):
        for _ in range(30):
            try:
                os.close(os.open(self.f, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.f.stat().st_mtime > 30:    # lucchetto dimenticato
                        self.f.unlink()
                        continue
                except OSError:
                    pass
                time.sleep(0.1)
        raise TimeoutError(f"lucchetto occupato: {self.f}")

    def __exit__(self, *a):
        try:
            self.f.unlink()
        except OSError:
            pass


def esegui(dati: dict, home: Path, jarvis: str = ""):
    cfg = home / ".jarvis"
    percorsi = leggi_json(cfg / "percorsi.json")
    if not percorsi.get("memoria"):
        return "memoria condivisa non configurata (manca percorsi.json): niente da fare"
    memoria = Path(percorsi["memoria"])
    sessione = str(dati.get("session_id") or "senza-id")
    evento = str(dati.get("hook_event_name") or "Stop")
    cwd = str(dati.get("cwd") or os.getcwd())
    trascrizione = Path(dati.get("transcript_path") or "")
    stato_ganci = cfg / "stato-ganci.json"
    posizioni = leggi_json(stato_ganci)
    righe, nuovo = leggi_nuovo(trascrizione, int(posizioni.get(sessione, 0))) if trascrizione.is_file() else ([], 0)
    file_toccati, errori, marche, ultima = analizza(righe)

    spazio = trova_spazio(percorsi, cwd)
    f = memoria / spazio / "Stato.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    ora = adesso()
    with Lucchetto(f):
        testa, sez = leggi_stato(f, spazio)
        if file_toccati:
            nomi = ", ".join(base(x) for x in file_toccati[:8]) + (f" e altri {len(file_toccati) - 8}" if len(file_toccati) > 8 else "")
            aggiungi(sez["FATTO"], f"- {ora} · modificati: {nomi} ({base(cwd)})", MAX["FATTO"])
        for chi, testo in marche:
            if chi == "FATTO":
                aggiungi(sez["FATTO"], f"- {ora} · {testo}", MAX["FATTO"])
                sez["DA FARE"] = [v for v in sez["DA FARE"] if senza_data(v) != testo.lower()]
            elif chi == "DA FARE":
                aggiungi(sez["DA FARE"], f"- [ ] {testo}", MAX["DA FARE"])
            elif chi in ("ERRORE", "ERRORI"):
                aggiungi(sez["ERRORI"], f"- {ora} · {testo}", MAX["ERRORI"])
        for e in errori[-5:]:
            aggiungi(sez["ERRORI"], f"- {ora} · strumento in errore: {e}", MAX["ERRORI"])
        precedente = next((v for v in sez["Ultime sessioni"] if f"sessione {sessione[:8]}" in v), "")
        if not ultima and precedente:
            m = re.search(r"ultima richiesta: «(.*)»", precedente)
            ultima = m.group(1) if m else ""
        sez["Ultime sessioni"] = [v for v in sez["Ultime sessioni"] if f"sessione {sessione[:8]}" not in v]
        sez["Ultime sessioni"].insert(0, f"- {ora} · sessione {sessione[:8]} · {base(cwd)} · {evento}"
                                         + (f" · ultima richiesta: «{ultima}»" if ultima else ""))
        del sez["Ultime sessioni"][MAX["Ultime sessioni"]:]
        scrivi_stato(f, testa, sez, evento, sessione)

    if evento == "SessionEnd":
        posizioni.pop(sessione, None)
        diario = memoria / "Diario" / f"{datetime.now():%Y-%m-%d}.md"
        diario.parent.mkdir(parents=True, exist_ok=True)
        with open(diario, "a", encoding="utf-8") as d:
            d.write(f"- {ora} · {spazio} · sessione {sessione[:8]} chiusa ({base(cwd)})"
                    + (f": {len(file_toccati)} file modificati" if file_toccati else "") + "\n")
        cm = Path(jarvis) / "strumenti" / "collega_memoria.py" if jarvis else None
        if cm and cm.exists():
            subprocess.run([sys.executable, str(cm), "--applica", "--zitto", "--home", str(home)],
                           capture_output=True, text=True, timeout=25)
    else:
        posizioni[sessione] = nuovo
    # si tengono solo le ultime 200 sessioni
    posizioni = dict(list(posizioni.items())[-200:])
    cfg.mkdir(parents=True, exist_ok=True)
    stato_ganci.write_text(json.dumps(posizioni), encoding="utf-8")
    return f"{spazio}: {len(file_toccati)} file, {len(marche)} righe marcate, {len(errori)} errori → {f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jarvis", default="")
    ap.add_argument("--home", default="")
    ap.add_argument("--prova", default="", help="trascrizione da leggere senza Claude Code")
    ap.add_argument("--cwd", default="")
    ap.add_argument("--evento", default="Stop")
    ap.add_argument("--sessione", default="prova-a-mano")
    a, _ = ap.parse_known_args()
    home = Path(a.home).expanduser() if a.home else Path.home()
    try:
        if a.prova:
            dati = {"session_id": a.sessione, "transcript_path": a.prova, "cwd": a.cwd or os.getcwd(), "hook_event_name": a.evento}
        else:
            grezzo = sys.stdin.read() if not sys.stdin.isatty() else "{}"
            dati = json.loads(grezzo or "{}")
        esito = esegui(dati, home, a.jarvis)
        if a.prova:
            print(esito)
    except Exception as e:  # noqa: BLE001 — un gancio non deve mai fermare Claude Code
        try:
            log = home / ".jarvis" / "stato-ganci.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"{adesso()} {type(e).__name__}: {e}\n")
        except OSError:
            pass
        if a.prova:
            raise
    sys.exit(0)


if __name__ == "__main__":
    main()
