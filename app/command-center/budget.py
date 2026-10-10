"""Budget degli agenti: costo accumulato e tetto, in budget-agenti.json.

Formato: {"agenti": {"nome": {"costo_usd": 1.2, "tetto_usd": 5.0}}, "tetto_default_usd": null}
Senza file, o senza tetto per quell'agente, non si nega mai niente.
"""
import json
import threading
from pathlib import Path

BUDGET_FILE = Path(__file__).resolve().parent / "budget-agenti.json"
_LOCK = threading.Lock()


def _leggi(percorso):
    try:
        d = json.loads(Path(percorso).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _tetto(d, agente):
    t = ((d.get("agenti") or {}).get(agente) or {}).get("tetto_usd")
    if t is None:
        t = d.get("tetto_default_usd")
    return t if isinstance(t, (int, float)) and not isinstance(t, bool) else None


def aggiungi_costo(agente, usd, percorso=None):
    """Somma usd al costo accumulato dell'agente (crea la voce se manca). Il tetto non si tocca."""
    p = Path(percorso) if percorso else BUDGET_FILE
    if not isinstance(usd, (int, float)) or usd <= 0:
        return
    with _LOCK:
        d = _leggi(p)
        voce = d.setdefault("agenti", {}).setdefault(agente, {})
        voce["costo_usd"] = round(float(voce.get("costo_usd") or 0) + usd, 6)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)


def superato(agente, percorso=None):
    """None se si puo' andare avanti, se no una frase col motivo."""
    d = _leggi(percorso or BUDGET_FILE)
    tetto = _tetto(d, agente)
    if tetto is None:
        return None
    costo = float(((d.get("agenti") or {}).get(agente) or {}).get("costo_usd") or 0)
    if costo >= tetto:
        return f"budget superato per {agente}: {costo:.2f} USD su un tetto di {tetto:.2f}"
    return None
