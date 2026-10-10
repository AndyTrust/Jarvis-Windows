"""Prova del riquadro «Assistenza a distanza» contro il server acceso (127.0.0.1, porta CC_PORTA o 7777).

Creato il 2026-10-02. Controlla:
  1  a modulo spento lo stato dice «modulo»: il riquadro mostra il solo tasto «Attiva assistenza»
  2  la pagina ha il tasto «Attiva assistenza» e nessun «DA COMPILARE»; il vecchio tasto «Prepara» non c'è più
  3  il tasto (POST /api/assistenza/attiva) crea assistenza.json con «abilitata» e la sezione tunnel
  4  dopo, lo stato è acceso e non porta dati di pagamento (niente IBAN, niente «DA COMPILARE»)
  5  senza dati di pagamento l'ordine è rifiutato; senza consenso la sessione non parte
  6  premuto di nuovo, il tasto non aggiunge niente
Alla fine rimette assistenza.json com'era (o lo cancella se prima non c'era).
Su Windows, se manca qualcosa (WSL, Ubuntu, openssh), il punto 3 apre davvero la finestra di ASSISTENZA.ps1.
Uso:  CC_PORTA=7778 python prova_assistenza_pannello.py            (il server deve essere acceso)
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = f"http://127.0.0.1:{os.environ.get('CC_PORTA') or 7777}"
QUI = Path(__file__).resolve().parent
CARTELLA = Path(os.environ.get("ASSISTENZA_DIR") or QUI)
CONF = CARTELLA / "assistenza.json"
ESITI = []


def verifica(nome, ok, dettaglio=""):
    ESITI.append(bool(ok))
    print(f"{'OK     ' if ok else 'FALLITO'}  {nome}" + (f"  [{dettaglio}]" if dettaglio and not ok else ""))


HTML = urllib.request.urlopen(BASE + "/", timeout=10).read().decode("utf-8")
TOKEN = re.search(r'CC_TOKEN\s*=\s*"([^"]+)"', HTML).group(1)


def chiama(metodo, percorso, corpo=None):
    dati = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(BASE + percorso, data=dati, method=metodo,
                               headers={"X-Token": TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=90) as x:
            return x.status, json.loads(x.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except ValueError:
            return e.code, {}


PRIMA = CONF.read_bytes() if CONF.exists() else None
try:
    if CONF.exists():
        CONF.unlink()
    c, s = chiama("GET", "/api/assistenza/stato")
    verifica("1  modulo spento: stato {abilitata: false, modulo: true}", c == 200 and s.get("abilitata") is False and s.get("modulo") is True, s)

    js = urllib.request.urlopen(BASE + "/static/app.js", timeout=10).read().decode("utf-8")
    verifica("2a la pagina ha il tasto «Attiva assistenza»", 'id="assist-attiva"' in HTML and "Attiva assistenza" in HTML)
    verifica("2b nessun «DA COMPILARE» nella pagina e nello script", "DA COMPILARE" not in HTML and "DA COMPILARE" not in js)
    verifica("2c il vecchio tasto «Prepara tutto e avvia» non c'è più", "assist-prepara" not in HTML and "assist-prepara" not in js)
    verifica("2d lo script chiama /api/assistenza/attiva", "/api/assistenza/attiva" in js)

    c, r = chiama("POST", "/api/assistenza/attiva", {})
    conf = json.loads(CONF.read_text(encoding="utf-8")) if CONF.exists() else {}
    verifica("3a il tasto risponde 200 con un messaggio", c == 200 and r.get("messaggio"), r)
    verifica("3b assistenza.json creato, abilitata e con la sezione tunnel",
             conf.get("abilitata") is True and isinstance(conf.get("tunnel"), dict) and conf["tunnel"].get("host"), conf)
    verifica("3c la risposta dice cosa manca e se ha aperto la finestra", isinstance(r.get("manca"), list) and "finestra" in r, r)

    c, s = chiama("GET", "/api/assistenza/stato")
    testo = json.dumps(s, ensure_ascii=False)
    verifica("4a dopo il tasto lo stato è acceso", c == 200 and s.get("abilitata") is True, s)
    verifica("4b nessun dato di pagamento nello stato", s.get("pagamento_pronto") is False and "DA COMPILARE" not in testo
             and "iban" not in testo.lower())

    c, r = chiama("POST", "/api/assistenza/ordine", {"ore": 1})
    verifica("5a senza dati di pagamento l'ordine è rifiutato", c == 400 and "pagamento" in (r.get("errore") or ""), (c, r))
    c, r = chiama("POST", "/api/assistenza/avvia", {"consenso": False})
    verifica("5b senza consenso la sessione non parte", c == 400 and "consenso" in (r.get("errore") or ""), (c, r))

    c, r = chiama("POST", "/api/assistenza/attiva", {})
    verifica("6  premuto di nuovo: niente da aggiungere", c == 200 and r.get("aggiunti") == [], r)
finally:
    if PRIMA is None:
        if CONF.exists():
            CONF.unlink()
    else:
        CONF.write_bytes(PRIMA)

print(f"\n{sum(ESITI)}/{len(ESITI)} controlli passati")
sys.exit(0 if all(ESITI) else 1)
