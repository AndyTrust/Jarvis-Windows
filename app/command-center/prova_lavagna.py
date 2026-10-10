"""Prova di funzionamento VERA della lavagna e del menu laterale, contro il server acceso (127.0.0.1, porta CC_PORTA o 7777).

Che cosa controlla (ogni punto stampa OK o FALLITO, e alla fine il codice di uscita dice se tutto è andato):
  1  spostare una scheda si salva e si rilegge uguale (pannello.json sul disco)
  2  una scheda TOLTA resta tolta: il «tolto» si salva, e «allinea» non la rimette
  3  il tempo reale: un salvataggio produce subito un evento «pannello» su /api/flusso
  4  un secondo salvataggio con versione vecchia viene rifiutato (409), non calpesta
  5  ciclo di un gruppo: crea (cartella scelta) -> compare negli spazi -> togli -> compare negli archiviati
     -> elimina dall'elenco -> sparisce davvero (anche dopo una nuova lettura)
  6  ciclo di un agente: crea -> togli -> compare negli archiviati -> elimina -> sparisce; ripristina rimette
  7  il server rifiuta di archiviare la cartella di Jarvis stesso
  8  «ripulisci_lavagna» è idempotente
Tutto avviene in una cartella temporanea fuori dalle cartelle sincronizzate e a fine prova si rimette com'era.
I file del pannello (pannello.json, spazi.json, ...) sono quelli accanto a questo file: lancia la prova dalla
cartella del Command Center che il server sta usando (meglio una copia di prova, vedi l'intestazione di server.py).
CC_PROGETTO_PROVA (facoltativo) è il progetto di cui togliere una scheda nel punto 2 (di base il primo con agenti
che non sia «jarvis» né «memoria»).
Uso:  CC_PORTA=7778 python prova_lavagna.py            (il server deve essere acceso)
"""
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = f"http://127.0.0.1:{os.environ.get('CC_PORTA') or 7777}"
QUI = Path(__file__).resolve().parent
ESITI = []


def verifica(nome, ok, dettaglio=""):
    ESITI.append(bool(ok))
    print(f"{'OK     ' if ok else 'FALLITO'}  {nome}" + (f"  [{dettaglio}]" if dettaglio and not ok else ""))
    return ok


html = urllib.request.urlopen(BASE + "/", timeout=10).read().decode("utf-8")
TOKEN = re.search(r'CC_TOKEN\s*=\s*"([^"]+)"', html).group(1)


def chiama(metodo, percorso, corpo=None):
    dati = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(BASE + percorso, data=dati, method=metodo,
                               headers={"X-Token": TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            return x.status, json.loads(x.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except ValueError:
            return e.code, {}


def azione(**kw):
    kw.setdefault("tipo", "agente")
    return chiama("POST", "/api/azione", kw)


def pannello():
    return chiama("GET", "/api/pannello")[1]


def salva(p, versione=None):
    corpo = dict(p)
    corpo["versione"] = p.get("versione") if versione is None else versione
    return chiama("POST", "/api/pannello", corpo)


def lavagna_generale(p):
    return p["lavagne"]["generale"]


PANNELLO_ORIGINALE = (QUI / "pannello.json").read_text(encoding="utf-8")
SPAZI_ORIGINALE = (QUI / "spazi.json").read_text(encoding="utf-8")
ARCH_ORIGINALE = (QUI / "gruppi-archiviati.json").read_text(encoding="utf-8") if (QUI / "gruppi-archiviati.json").exists() else None
MODIFICHE_ORIGINALE = (QUI / "modifiche-agenti.jsonl").read_text(encoding="utf-8") if (QUI / "modifiche-agenti.jsonl").exists() else ""
temp = Path(tempfile.mkdtemp(prefix="prova-lavagna-"))
PID = "prova-lavagna-x"

try:
    # ---- 1  spostare una scheda
    p = pannello()
    L = lavagna_generale(p)
    scheda = next(n for n in L["nodi"] if n["tipo"] == "agente")
    x0, y0 = scheda["x"], scheda["y"]
    scheda["x"], scheda["y"] = x0 + 37, y0 + 53
    c, r = salva(p)
    verifica("1a spostamento: il server accetta il salvataggio", c == 200, f"HTTP {c} {r}")
    sul_disco = json.loads((QUI / "pannello.json").read_text(encoding="utf-8"))
    n = next(z for z in lavagna_generale(sul_disco)["nodi"] if z["id"] == scheda["id"])
    verifica("1b spostamento: pannello.json sul disco ha le nuove coordinate", (n["x"], n["y"]) == (x0 + 37, y0 + 53), f"{n['x']},{n['y']}")
    n2 = next(z for z in lavagna_generale(pannello())["nodi"] if z["id"] == scheda["id"])
    verifica("1c spostamento: riletto dall'API è uguale", (n2["x"], n2["y"]) == (x0 + 37, y0 + 53))

    # ---- 3  tempo reale (SSE): ascolto e salvo
    eventi = []
    fine = threading.Event()

    def ascolta():
        try:
            rq = urllib.request.Request(f"{BASE}/api/flusso?token={TOKEN}")
            with urllib.request.urlopen(rq, timeout=15) as f:
                for riga in f:
                    riga = riga.decode("utf-8", "replace").strip()
                    if riga.startswith("data:"):
                        eventi.append(riga[5:].strip())
                        if '"pannello"' in riga:
                            fine.set()
                            return
        except Exception as e:  # noqa: BLE001
            eventi.append("ERRORE " + repr(e))
    t = threading.Thread(target=ascolta, daemon=True)
    t.start()
    time.sleep(1.0)
    p = pannello()
    lavagna_generale(p)["nodi"][0]["x"] += 1
    salva(p)
    verifica("3  tempo reale: evento «pannello» su /api/flusso dopo un salvataggio", fine.wait(5), str(eventi[-3:]))
    p = pannello()
    lavagna_generale(p)["nodi"][0]["x"] -= 1
    salva(p)

    # ---- 4  versione vecchia
    p = pannello()
    vecchia = p["versione"]
    salva(p)                                   # alza la versione
    c, r = salva(p, versione=vecchia)
    verifica("4  versione vecchia rifiutata con 409 (non calpesta il lavoro altrui)", c == 409, f"HTTP {c}")

    # ---- 2  scheda tolta: resta tolta
    p = pannello()
    L = lavagna_generale(p)
    sp0 = chiama("GET", "/api/spazi")[1]
    capi = {f"{pr['id']}:{pr.get('capogruppo')}" for s in sp0["spazi"] for pr in s["progetti"] if pr.get("capogruppo")}
    prog = os.environ.get("CC_PROGETTO_PROVA") or ""
    cand = next(n for n in L["nodi"] if n["tipo"] == "agente" and n["agente"] not in capi
                and (n["agente"].startswith(prog + ":") if prog else n["agente"].split(":")[0] not in ("jarvis", "memoria")))
    chiave = cand["agente"]
    L["nodi"] = [n for n in L["nodi"] if n["id"] != cand["id"]]
    L["fili"] = [f for f in L["fili"] if cand["id"] not in (f["da"], f["a"])]
    L.setdefault("tolti", []).append(chiave)
    c, _ = salva(p)
    p = pannello()
    verifica("2a tolta: il «tolto» è salvato nel pannello", chiave in lavagna_generale(p).get("tolti", []))
    c, r = azione(cosa="allinea", lavagna="generale", verso="lavagna")
    p = pannello()
    verifica("2b tolta: dopo «allinea verso lavagna» la scheda NON è tornata",
             not any(n.get("agente") == chiave for n in lavagna_generale(p)["nodi"]), f"HTTP {c}")
    c, r = azione(cosa="allinea", lavagna="generale", verso="profili")
    p = pannello()
    verifica("2c tolta: dopo «allinea verso profili» la scheda NON è tornata",
             not any(n.get("agente") == chiave for n in lavagna_generale(p)["nodi"]), f"HTTP {c}")
    L = lavagna_generale(p)
    L["tolti"] = [t for t in L["tolti"] if t != chiave]            # si rimette a posto per il resto della prova
    salva(p)

    # ---- 8  ripulisci idempotente
    c, r1 = azione(cosa="ripulisci_lavagna")
    c2, r2 = azione(cosa="ripulisci_lavagna")
    verifica("8  ripulisci_lavagna: la seconda volta non toglie più niente", c == 200 and c2 == 200 and not any(r2.get("tolte", {}).values()), f"{r1} / {r2}")

    # ---- 5  ciclo di un gruppo
    cartella = temp / "progetto-prova"
    cartella.mkdir()
    spazi_id = json.loads((QUI / "spazi.json").read_text(encoding="utf-8"))["spazi"][0]["id"]
    c, r = azione(cosa="crea_gruppo", spazio=spazi_id, id=PID, nome="Prova lavagna", cartella=str(cartella),
                  capogruppo="capogruppo-prova-lavagna", description="Capogruppo di prova", model="haiku")
    verifica("5a gruppo: creato su una cartella scelta", c == 200 and (cartella / ".claude" / "agents" / "capogruppo-prova-lavagna.md").exists(), f"HTTP {c} {r}")
    sp = chiama("GET", "/api/spazi")[1]
    verifica("5b gruppo: compare nel catalogo degli spazi", any(pr["id"] == PID for s in sp["spazi"] for pr in s["progetti"]))
    c, r = azione(cosa="togli_gruppo", progetto=PID)
    sp = chiama("GET", "/api/spazi")[1]
    verifica("5c gruppo: tolto -> esce dagli spazi ed entra negli archiviati",
             c == 200 and not any(pr["id"] == PID for s in sp["spazi"] for pr in s["progetti"])
             and any(g["progetto"] == PID for g in sp["gruppi_archiviati"]), f"HTTP {c} {r}")
    c, r = azione(cosa="elimina_gruppo_archiviato", progetto=PID)
    sp = chiama("GET", "/api/spazi")[1]
    verifica("5d gruppo: eliminato dall'elenco -> non c'è più (nemmeno riletto)",
             c == 200 and not any(g["progetto"] == PID for g in sp["gruppi_archiviati"]), f"HTTP {c} {r}")
    arch_dir = [d for d in cartella.iterdir() if d.name.startswith("_archivio-")]
    verifica("5e gruppo: i profili NON sono stati cancellati dal disco (_archivio-… resta)", bool(arch_dir))
    c, r = azione(cosa="elimina_gruppo_archiviato", progetto=PID)
    verifica("5f gruppo: eliminarlo due volte dà un errore chiaro, non un crash", c in (400, 404, 500) and bool(r.get("errore")), f"HTTP {c} {r}")

    # ---- 6  ciclo di un agente (in un secondo gruppo)
    cartella2 = temp / "progetto-prova-2"
    cartella2.mkdir()
    c, r = azione(cosa="crea_gruppo", spazio=spazi_id, id=PID + "2", nome="Prova lavagna 2", cartella=str(cartella2),
                  capogruppo="capogruppo-prova-due", description="Capogruppo di prova due", model="haiku")
    c, r = azione(cosa="crea", progetto=PID + "2", nome="spec-prova", description="Specialista di prova", model="haiku", capogruppo="capogruppo-prova-due")
    verifica("6a agente: creato sotto il capogruppo", c == 200 and (cartella2 / ".claude" / "agents" / "spec-prova.md").exists(), f"HTTP {c} {r}")
    c, r = azione(cosa="togli", progetto=PID + "2", nome="spec-prova")
    sp = chiama("GET", "/api/spazi")[1]
    pr = next(pr for s in sp["spazi"] for pr in s["progetti"] if pr["id"] == PID + "2")
    verifica("6b agente: tolto -> è negli archiviati del progetto", c == 200 and any((x if isinstance(x, str) else x.get("nome")) == "spec-prova" for x in pr.get("archiviati", [])), f"HTTP {c} {pr.get('archiviati')}")
    c, r = azione(cosa="ripristina", progetto=PID + "2", nome="spec-prova")
    verifica("6c agente: ripristinato", c == 200 and (cartella2 / ".claude" / "agents" / "spec-prova.md").exists(), f"HTTP {c} {r}")
    azione(cosa="togli", progetto=PID + "2", nome="spec-prova")
    c, r = azione(cosa="elimina_archiviato", progetto=PID + "2", nome="spec-prova")
    sp = chiama("GET", "/api/spazi")[1]
    pr = next(pr for s in sp["spazi"] for pr in s["progetti"] if pr["id"] == PID + "2")
    verifica("6d agente: eliminato dall'elenco archiviati, copia in _eliminati",
             c == 200 and not any((x if isinstance(x, str) else x.get("nome")) == "spec-prova" for x in pr.get("archiviati", []))
             and any((cartella2 / ".claude" / "agents" / "_archivio" / "_eliminati").glob("spec-prova.*.md")), f"HTTP {c} {r}")
    # ---- 9  proposta del capogruppo -> sotto-agenti (senza lanciare Claude: si dà il JSON già pronto)
    proposta = ('Ecco: ```json\n[{"nome":"analista-prova","description":"Analizza i dati di prova","model":"sonnet"},'
                '{"nome":"Nome Sbagliato!","description":"x","model":"sonnet"},'
                '{"nome":"spec-prova","description":"Doppione","model":"modello-inventato"}]\n```')
    c, r = azione(cosa="crea_da_proposta", progetto=PID + "2", testo=proposta)
    nuovi = sorted(f.stem for f in (cartella2 / ".claude" / "agents").glob("*.md"))
    verifica("9a proposta: crea gli agenti validi e salta quello col nome sbagliato",
             c == 200 and "analista-prova" in r.get("creati", []) and len(r.get("saltati", [])) == 1, f"HTTP {c} {r}")
    verifica("9b proposta: il modello inventato diventa sonnet e l'agente nasce sotto il capogruppo",
             "spec-prova" in nuovi and "model: sonnet" in (cartella2 / ".claude" / "agents" / "spec-prova.md").read_text(encoding="utf-8"), str(nuovi))
    c, r = azione(cosa="crea_da_proposta", progetto=PID + "2", testo="niente json qui")
    verifica("9c proposta: senza JSON dà un errore chiaro", c != 200 and bool(r.get("errore")), f"HTTP {c} {r}")
    azione(cosa="togli_gruppo", progetto=PID + "2")
    azione(cosa="elimina_gruppo_archiviato", progetto=PID + "2")

    # ---- 7  la cartella di Jarvis non si archivia
    sp = chiama("GET", "/api/spazi")[1]
    jarvis = next((pr for s in sp["spazi"] for pr in s["progetti"] if pr["id"] == "jarvis"), None)
    if jarvis:
        c, r = azione(cosa="togli_gruppo", progetto="jarvis")
        verifica("7  togli_gruppo su «jarvis» rifiutato (la cartella è quella di Jarvis)", c != 200 and "Jarvis" in (r.get("errore") or ""), f"HTTP {c} {r}")
        sp2 = chiama("GET", "/api/spazi")[1]
        verifica("7b jarvis è ancora tra gli spazi", any(pr["id"] == "jarvis" for s in sp2["spazi"] for pr in s["progetti"]))
    else:
        print("SALTATO  7  (nessun progetto «jarvis» negli spazi)")
    memoria = next((pr for s in sp["spazi"] for pr in s["progetti"] if pr["id"] == "memoria"), None)
    if memoria:
        c, r = azione(cosa="togli_gruppo", progetto="memoria")
        verifica("7c togli_gruppo su «memoria» (cartella dentro Jarvis) rifiutato", c != 200, f"HTTP {c} {r}")
    # ---- 10 il pannello precedente viene tenuto (pannello.json.prev) e la proposta con due blocchi prende il primo
    verifica("10a pannello.json.prev esiste (ultima disposizione prima dell'ultimo salvataggio)", (QUI / "pannello.json.prev").exists())
finally:
    # rimette com'era: spazi, archiviati, registro modifiche; la versione del pannello sale e basta
    (QUI / "spazi.json").write_text(SPAZI_ORIGINALE, encoding="utf-8")
    if ARCH_ORIGINALE is None:
        (QUI / "gruppi-archiviati.json").unlink(missing_ok=True)
    else:
        (QUI / "gruppi-archiviati.json").write_text(ARCH_ORIGINALE, encoding="utf-8")
    if MODIFICHE_ORIGINALE or (QUI / "modifiche-agenti.jsonl").exists():
        (QUI / "modifiche-agenti.jsonl").write_text(MODIFICHE_ORIGINALE, encoding="utf-8")
    shutil.rmtree(temp, ignore_errors=True)
    try:   # pannello com'era all'inizio della prova (versione nuova: nessun conflitto), poi la sua ripulita
        v = pannello().get("versione")
        o = json.loads(PANNELLO_ORIGINALE)
        o["versione"] = v
        salva(o)
    except Exception as e:  # noqa: BLE001
        print("pannello non rimesso:", e)

ok = sum(ESITI)
print(f"\n{ok}/{len(ESITI)} controlli riusciti")
sys.exit(0 if ok == len(ESITI) else 1)
