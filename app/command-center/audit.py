"""Registro di audit delle azioni degli agenti: una riga JSON per evento in audit-azioni.jsonl.

registra(evento) aggiunge UNA riga con solo i campi previsti (ts, missione, agente, banca, tool,
sintesi, verdetto, regola, approvato_da). La sintesi si tronca a 200 caratteri e si ripulisce da
quello che somiglia a un segreto. Non si scrivono mai contenuti di file ne' input interi.
legge_ultime(n, filtri) rilegge le ultime righe, anche filtrate per campo.
"""
import json
import re
import threading
import time
from pathlib import Path

AUDIT_FILE = Path(__file__).resolve().parent / "audit-azioni.jsonl"
CAMPI = ("ts", "missione", "agente", "banca", "tool", "sintesi", "verdetto", "regola", "approvato_da")
SINTESI_MAX = 200
_LOCK = threading.Lock()

# quello che sembra un segreto non entra mai nel registro
SEGRETO = re.compile(
    r"(?i)\b(authorization\s*[=:]?\s*(bearer\s+)?|bearer\s+)\S+"
    r"|(?i:\b(token|password|passwd|pwd|secret|api[_-]?key)\b\s*[=:]?\s*\S+)"
    r"|\bsk-[A-Za-z0-9_-]{8,}|\bghp_[A-Za-z0-9]{8,}|\bxox[abp]-[A-Za-z0-9-]{8,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")


def banca_da_testo(testo):
    """Quale banca di memoria nomina un percorso o una sintesi: 'privata', 'personale', 'crm' o ''.
    Guarda solo il testo, non apre niente."""
    t = str(testo or "").replace("\\", "/").lower()
    if "crm" in t and ".claude/memoria" in t:
        return "crm"
    if ".claude/memoria-" in t:
        return "personale"
    if re.search(r"\.claude/memoria(/|$|\s|\"|')", t):
        return "privata"
    return ""


def _pulisci(sintesi):
    s = SEGRETO.sub("[omesso]", str(sintesi or ""))
    return s.replace("\n", " ")[:SINTESI_MAX]


def registra(evento, percorso=None):
    """Aggiunge una riga al registro. Restituisce la riga scritta (dict)."""
    evento = evento or {}
    riga = {c: evento.get(c, "") for c in CAMPI}
    riga["ts"] = evento.get("ts") or time.strftime("%Y-%m-%dT%H:%M:%S")
    riga["sintesi"] = _pulisci(evento.get("sintesi"))
    if not riga["banca"]:
        riga["banca"] = banca_da_testo(evento.get("sintesi"))
    for c in CAMPI:
        if c != "sintesi" and not isinstance(riga[c], (str, int, float)):
            riga[c] = str(riga[c])[:80]
    f = Path(percorso) if percorso else AUDIT_FILE
    with _LOCK:
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(riga, ensure_ascii=False) + "\n")
    return riga


def legge_ultime(n=50, filtri=None, percorso=None):
    """Le ultime n righe (la piu' recente per prima) che rispettano i filtri {campo: valore}."""
    f = Path(percorso) if percorso else AUDIT_FILE
    try:
        righe = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    filtri = {k: v for k, v in (filtri or {}).items() if k in CAMPI and v not in (None, "")}
    fuori = []
    for riga in reversed(righe):
        try:
            r = json.loads(riga)
        except ValueError:
            continue
        if all(str(r.get(k, "")) == str(v) for k, v in filtri.items()):
            fuori.append(r)
            if len(fuori) >= max(1, int(n)):
                break
    return fuori
