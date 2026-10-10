"""Prova di /api/agente-attivita contro il server acceso (127.0.0.1, porta CC_PORTA o 7777), in sola lettura. Controlla: formato, contatori coerenti con le righe, filtro errori, errore su agente mancante, avvisi per
richieste fra agenti senza collegamento, formato dello storico (attivita-agenti.jsonl accanto a questo file).
CC_AGENTE_PROVA (facoltativo, «progetto:nome») è l'agente da interrogare: di base il primo capogruppo del catalogo.
Uso: CC_PORTA=7778 python prova_attivita.py"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = f"http://127.0.0.1:{os.environ.get('CC_PORTA') or 7777}"
QUI = Path(__file__).resolve().parent
ESITI = []


def verifica(nome, ok, dettaglio=""):
    ESITI.append(bool(ok))
    print(f"{'OK     ' if ok else 'FALLITO'}  {nome}" + (f"  [{dettaglio}]" if dettaglio and not ok else ""))


TOKEN = re.search(r'CC_TOKEN\s*=\s*"([^"]+)"', urllib.request.urlopen(BASE + "/", timeout=10).read().decode()).group(1)


def get(percorso):
    r = urllib.request.Request(BASE + percorso, headers={"X-Token": TOKEN})
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            return x.status, json.loads(x.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


c, spazi = get("/api/spazi")
agenti = [f"{p['id']}:{a['nome']}" for s in spazi["spazi"] for p in s["progetti"] for a in p["agenti"]]
verifica("0  il catalogo ha agenti", len(agenti) >= 1, str(len(agenti)))
capi = [f"{p['id']}:{p['capogruppo']}" for s in spazi["spazi"] for p in s["progetti"] if p.get("capogruppo")]
AG = os.environ.get("CC_AGENTE_PROVA") or (capi[0] if capi else agenti[0])
q = urllib.parse.quote(AG)

c, d = get("/api/agente-attivita?agente=" + q)
verifica("1a risposta 200 con agente, contatori, righe e avvisi", c == 200 and {"agente", "contatori", "righe", "avvisi"} <= set(d), f"{c} {list(d)}")
verifica("1b contatori coerenti con le righe (ricevute+inviate = righe, limite 100)",
         d["contatori"]["ricevute"] + d["contatori"]["inviate"] >= len(d["righe"]) and
         len([r for r in d["righe"] if r["verso"] == "ricevuta"]) <= d["contatori"]["ricevute"])
verifica("1c ogni riga ha ora, verso, controparte, stato", all({"ts", "verso", "controparte", "stato", "testo"} <= set(r) for r in d["righe"]))

c, d2 = get("/api/agente-attivita?agente=" + urllib.parse.quote(AG.split(":")[-1]))
verifica("2  anche con il solo nome si trova lo stesso agente", c == 200 and d2["agente"] == AG, d2.get("agente"))

c, e = get("/api/agente-attivita?agente=" + q + "&errori=1")
verifica("3  filtro errori: solo righe in errore", c == 200 and all(r["stato"] == "errore" for r in e["righe"]))

c, v = get("/api/agente-attivita?agente=")
verifica("4  agente mancante: 400 con messaggio", c == 400 and bool(v.get("errore")), f"{c} {v}")

tot = {"ricevute": 0, "inviate": 0}
for k in agenti:
    cc, x = get("/api/agente-attivita?agente=" + urllib.parse.quote(k))
    if cc != 200:
        verifica(f"5  {k} risponde", False, str(cc))
        break
    tot["ricevute"] += x["contatori"]["ricevute"]
    tot["inviate"] += x["contatori"]["inviate"]
else:
    verifica("5  tutti gli agenti rispondono 200", True)
print(f"   (totali sullo storico: {tot})")

arch = QUI / "attivita-agenti.jsonl"
verifica("6a lo storico per agente esiste sul disco (attivita-agenti.jsonl)", arch.exists() or sum(tot.values()) == 0)
if arch.exists():
    righe = arch.read_text(encoding="utf-8").splitlines()
    ok = True
    for r in righe:
        try:
            j = json.loads(r)
            ok &= {"id", "ts", "da", "a", "stato", "visto_ts"} <= set(j)
        except ValueError:
            ok = False
    verifica("6b ogni riga dello storico è un JSON con id, ts, da, a, stato, visto_ts", ok)

sys.exit(0 if all(ESITI) else 1)
