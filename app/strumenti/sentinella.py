#!/usr/bin/env python3
"""La sentinella di Jarvis: guarda, ripulisce e scrive il rapporto. Solo Python, nessun modello.

Ogni 15 minuti guarda lo stato e, se ci sono problemi, li riferisce a Jarvis, che
si attiva con gli agenti per risolvere e ripulire. Le sessioni ferme anomale si chiudono.

Due metà, in ordine:

  1. LA PULIZIA (`pulisci`), uno script senza modello. Fa quello che è già deciso:
       - ritira le prese fantasma (processo morto) del registro dei lavori;
       - cancella i recapiti orfani;
       - chiude le sessioni di Claude ferme da più di 4 ore che NON sono in ascolto
         (la voce e la Cloud Chat sono ascoltatori: mai chiusi).
  2. IL RAPPORTO (`rapporto`), per quello che resta dopo la pulizia: al massimo 5 righe
     da una tabella fissa (cosa vuol dire, gravità, a chi tocca). Non lancia modelli.

Chi la lancia:
  - il Command Center (server.py, ciclo «sentinella»): guarda ogni minuto, agisce al
    massimo ogni 15 minuti (pulizia + rapporto, sotto «Ultimo rapporto» nel box Sentinella);
  - l'attività pianificata: `--giro` fa tutto da solo SOLO se il Command Center è
    spento, se no lascia fare a lui.

    python strumenti/sentinella.py --pulisci [--json]   solo la pulizia
    python strumenti/sentinella.py --quadro             le anomalie che vede da solo
    python strumenti/sentinella.py --giro [--zitto]     pulizia + rapporto nel registro
"""
import argparse
import datetime
import json
import os
import re
import pathlib
import socket
import subprocess
import sys

try:
    import fcntl
except ImportError:            # Windows: niente fcntl, lucchetto con msvcrt
    fcntl = None
    import msvcrt

QUI =pathlib.Path(__file__).resolve().parent
AGENTE = QUI.parent
HOME = pathlib.Path.home()
sys.path.insert(0, str(QUI))
import agenti  # noqa: E402
import lavori  # noqa: E402
import portiere  # noqa: E402

PORTA_PANNELLO = 7777
OGNI_MIN = 15
LUCCHETTO = HOME / ".jarvis-locale" / "sentinella.lock"
LOG_DIR = AGENTE / "command-center" / "lavori"
PATH_ENV = f"{HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + os.environ.get("PATH", "")
ENV = {**os.environ, "PATH": PATH_ENV}


def ora():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _sh(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV,
                           stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 1, "timeout"
    except OSError as e:
        return 1, str(e)


# ---------------------------------------------------------------- la pulizia

def pulisci(secondi=3):
    """Torna {fatto: [righe], chiuse, orfane, fantasmi, ascolto: [...]}."""
    fatto, esito = [], {"quando": ora()}

    # 1. prese fantasma (il portiere stampa; qui si vuole solo il numero)
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            esito["fantasmi"] = portiere.ritira_fantasmi()
        except Exception as e:  # noqa: BLE001
            esito["fantasmi"] = 0
            fatto.append(f"prese fantasma: errore {e}")
    if esito["fantasmi"]:
        fatto.append(f"ritirate {esito['fantasmi']} prese fantasma")
    # 1a. dal 2026-10-05 il registro sta sulla VPS, che non vede i processi del Mac:
    # le prese del Mac col processo vivo ricevono un battito, se no dopo 45 minuti
    # sembrerebbero morte e la loro chiave tornerebbe libera mentre lavorano.
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            portiere.lavori.battito_vivi()
    except Exception as e:  # noqa: BLE001
        fatto.append(f"battito delle prese vive: errore {e}")

    # 1b. badge di lavoro (command-center/badge.py): rinnova quelli con un lavoro aperto, revoca gli altri
    try:
        sys.path.insert(0, str(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "command-center")))
        import badge as _badge
        rev, rin = _badge.giro(_badge._sessioni_con_presa())
        esito["badge"] = {"revocati": rev, "rinnovati": rin}
        if rev:
            fatto.append(f"revocati {rev} badge di lavoro senza più un lavoro aperto")
    except Exception as e:  # noqa: BLE001
        esito["badge"] = {"errore": type(e).__name__}

    # 2. sessioni: orfane via, ferme vecchie chiuse, ascoltatori lasciati stare
    righe, orfani = agenti.guarda(secondi)
    esito["orfane"] = agenti.pulisci_orfane(orfani)
    if esito["orfane"]:
        fatto.append(f"tolti {esito['orfane']} recapiti orfani")
    esito["ascolto"] = [{"pid": r["pid"], "nome": r["ascolto"]} for r in righe if r["ascolto"]]
    chiuse, non_chiuse = [], []
    for r in agenti.da_chiudere(righe):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ok = agenti.chiudi(r["pid"], chiedi=False)
        (chiuse if ok else non_chiuse).append(r["pid"])
        dove = (r["dove"] or r["cosa"]).replace(str(HOME), "~")
        fatto.append(f"{'chiusa' if ok else 'NON chiusa'} la sessione {r['pid']} ferma da {r['ore']:.1f} h in {dove}")
    esito["chiuse"], esito["non_chiuse"] = chiuse, non_chiuse

    esito["fatto"] = fatto
    return esito


def righe_pulizia(esito):
    """Una riga per l'evento del pannello e per il registro."""
    testo = "; ".join(esito.get("fatto") or []) or "niente da ripulire"
    return testo


# ---------------------------------------------------------------- il battito della memoria

BATTITO_MAX_MIN = 30
# server remoto facoltativo (alias ssh e cartella di sincro): su Windows battito_vps() non si chiama mai
VPS = os.environ.get("JARVIS_VPS_SSH", "vps")
SINCRO_VPS = os.environ.get("JARVIS_VPS_SINCRO", "/opt/jarvis/sincro")


def _quando(testo):
    try:
        return datetime.datetime.strptime(testo.strip()[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def battito_vps():
    """L'ultimo giro ogni30 sulla VPS, in ora italiana (il servizio ha TZ=Europe/Rome).
    Una sola chiamata ssh: legge «quando» di ultimo.json e l'inizio dell'ultima riga di ogni30.log,
    e tiene il più recente. Torna (datetime, None), oppure (None, errore) se la VPS non risponde."""
    c, out = _sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", VPS,
                  f"python3 -c 'import json;print(json.load(open(\"{SINCRO_VPS}/ultimo.json\"))[\"quando\"])'; "
                  f"tail -n 1 {SINCRO_VPS}/ogni30.log"], 15)
    date = [d for d in (_quando(r) for r in out.splitlines()) if d]
    if date:
        return max(date), None
    if c == 255 or out.strip() == "timeout":
        return None, f"ssh: {out.strip()[-120:] or 'nessuna risposta'}"
    return None, f"illeggibile: {out.strip()[-120:] or 'nessuna risposta'}"


def battito(metti, ultimo_mac):
    """Fermo solo se è vecchio il giro del Mac E quello della VPS. VPS non raggiungibile:
    nessun allarme qui, c'è già «vps:ssh»."""
    passato = (datetime.datetime.now() - _quando(ultimo_mac)).total_seconds()
    if passato <= BATTITO_MAX_MIN * 60:
        return
    if sys.platform == "win32":
        metti("sincronia", "sincronia:battito", f"battito della memoria fermo: ultimo giro {int(passato // 60)} min fa")
        return
    vps, errore = battito_vps()
    if errore and errore.startswith("ssh"):
        return
    if vps is None:
        metti("sincronia", "sincronia:battito",
              f"battito della memoria fermo: copia del Mac vecchia di {int(passato // 60)} min, "
              f"quella della VPS {errore}")
        return
    passato_vps = (datetime.datetime.now() - vps).total_seconds()
    if passato_vps > BATTITO_MAX_MIN * 60:
        metti("sincronia", "sincronia:battito",
              f"battito della memoria fermo: vecchie tutte e due le copie, Mac {int(passato // 60)} min, "
              f"VPS {int(passato_vps // 60)} min (ultimo giro VPS {vps:%Y-%m-%d %H:%M})")


# ---------------------------------------------------------------- il quadro (da soli, senza pannello)

def quadro():
    """Le anomalie che la sentinella vede da sola: portiere, battito. Il Command
    Center ne vede di più (raccoglitori, lavori, missioni): questo serve quando è spento."""
    fuori = {}

    def metti(tipo, chiave, testo):
        fuori[chiave] = {"tipo": tipo, "chiave": chiave, "testo": testo[:300]}

    try:
        g = portiere.giro()
    except Exception as e:  # noqa: BLE001
        g = {"note": []}
        metti("portiere", "portiere:errore", f"il portiere non risponde: {e}")
    for n in g.get("note") or []:
        chi = ",".join(n.get("chiavi") or []) or (n.get("presa") or {}).get("agente") or ""
        import re
        m = re.search(r"\bpid (\d+)", n.get("perche") or "")
        chi = chi or (m.group(1) if m else "?")
        metti("portiere", f"portiere:{n['tipo']}:{chi}", f"{n['tipo']}: {n.get('perche')}")
    try:
        b = json.loads((AGENTE / "sincro" / "ultimo.json").read_text())
        datetime.datetime.strptime(b["quando"], "%Y-%m-%d %H:%M")   # se è rotto, va nell'except
        battito(metti, b["quando"])
        for p in b.get("progetti") or []:
            if p.get("semaforo") in ("🟡", "🔴"):
                metti("sincronia", f"sincronia:{p.get('progetto')}:{p['semaforo']}",
                      f"{p['semaforo']} {p.get('progetto')}: {p.get('esito')}")
    except Exception as e:  # noqa: BLE001
        metti("sincronia", "sincronia:battito", f"ultimo.json non leggibile: {e}")
    return fuori


# ---------------------------------------------------------------- il rapporto (solo Python)
# Il rapporto lo scrive `rapporto()` con una tabella fissa: cosa vuol dire,
# gravità e a chi tocca. Nessun modello, nessun lavoro lanciato.

# (tipo della nota, gravità, a chi, cosa fare). «a chi»: jarvis = la chat master; capogruppo = il
# capogruppo dello spazio del progetto; nessuno = si sistema da sé o con un clic dell'utente.
TABELLA = {
    "FANTASMA": ("giallo", "nessuno", "presa di un processo morto: si ritira con «Ritira i fantasmi»"),
    "SCADUTA": ("giallo", "nessuno", "presa scaduta: si ritira con «Ritira i fantasmi»"),
    "ABUSIVO": ("giallo", "jarvis", "risorsa accesa senza chiave: si spegne o prende la chiave"),
    "MUTO": ("giallo", "nessuno", "sessione non registrata: se legge soltanto va bene"),
    "LUNGA": ("giallo", "jarvis", "sottoagente oltre il tempo: controllare in Squadra"),
    "🟡": ("giallo", "capogruppo", "progetto con lavoro più recente della memoria: salva in memoria"),
    "🔴": ("rosso", "jarvis", "cartella o memoria mancante: correggere spazi.json"),
    "battito": ("rosso", "jarvis", "battito della memoria fermo: rilanciare sincro/controlla.py"),
    "carico": ("giallo", "jarvis", "Mac sovraccarico: l'audio può cracchiare; chiudere o riavviare il processo più pesante, non il Mac"),
    "salute": ("rosso", "jarvis", None),         # None: il testo è l'errore del raccoglitore
    "lavoro": ("giallo", "jarvis", None),        # «guardare il lavoro X»
    "missione": ("giallo", "nessuno", "rispondere in Missioni"),
}
MASSIMO_RIGHE = 5


def voce_tabella(a):
    """(chiave della TABELLA, testo corto) per un'anomalia {tipo, chiave, testo}."""
    tipo, chiave, testo = a.get("tipo"), a.get("chiave") or "", a.get("testo") or ""
    if tipo == "portiere":
        sotto = chiave.split(":")[1] if chiave.count(":") >= 1 else ""
        return (sotto if sotto in TABELLA else "ABUSIVO"), testo
    if tipo == "carico":
        return "carico", testo
    if tipo == "sincronia":
        if chiave == "sincronia:battito":
            return "battito", testo
        return ("🔴" if chiave.endswith("🔴") else "🟡"), testo
    return (tipo if tipo in TABELLA else "salute"), testo


def rapporto(anomalie_nuove, rientrate=(), capogruppo_di=None, quando=None):
    """Il rapporto della sentinella in al massimo 5 righe, senza modello.

    anomalie_nuove: le anomalie da riferire ({tipo, chiave, testo}); rientrate: quelle
    sparite dal giro prima; capogruppo_di: nome progetto -> capogruppo (per le 🟡)."""
    capogruppo_di = capogruppo_di or {}
    quando = quando or ora()
    righe = []
    for a in anomalie_nuove:
        voce, testo = voce_tabella(a)
        gravita, a_chi, cosa = TABELLA[voce]
        if voce == "salute":
            cosa = testo[:140]
        elif voce == "lavoro":
            cosa = "guardare il " + testo.replace("lavoro in errore: ", "lavoro «", 1)[:120] + "»"
        if a_chi == "capogruppo":
            m = re.match(r"\S+ (.+?): ", testo)
            progetto = m.group(1) if m else ""
            a_chi = capogruppo_di.get(progetto) or "jarvis"
            cosa = f"{progetto}: {cosa}" if progetto else cosa
        elif voce in ("FANTASMA", "MUTO", "LUNGA", "ABUSIVO", "SCADUTA"):
            m = re.search(r"\(([^)]{1,60})\)|pid (\d+)", testo)
            dove = (m.group(1) or f"pid {m.group(2)}") if m else ""
            cosa = f"{cosa} ({dove})" if dove else cosa
        segno = "🔴" if gravita == "rosso" else "🟡"
        chi = {"jarvis": "Jarvis (chat master)", "nessuno": "nessuno"}.get(a_chi, a_chi)
        etichetta = {"🟡": "memoria", "🔴": "progetto"}.get(voce, voce)
        righe.append((gravita != "rosso", f"{segno} {etichetta}: {cosa} → a chi: {chi}"))
    righe.sort(key=lambda r: r[0])                 # prima i rossi
    testi = [r[1] for r in righe]
    coda = []
    if rientrate:
        coda.append(f"rientrate da sole: {len(rientrate)}")
    if not testi:
        return f"{quando} · nessuna anomalia da riferire" + (f" · {coda[0]}" if coda else "")
    posto = MASSIMO_RIGHE - 1                       # la prima riga è la testa
    if len(testi) > posto:
        altre = len(testi) - (posto - 1)
        testi = testi[:posto - 1] + [f"… e altre {altre} (lista nel box Sentinella)"]
    rossi = sum(1 for r in righe if not r[0])
    testa = f"{quando} · {len(righe)} anomali{'a' if len(righe) == 1 else 'e'} ({rossi} ross{'a' if rossi == 1 else 'e'})" + (f" · {coda[0]}" if coda else "")
    return "\n".join([testa] + testi)


# ---------------------------------------------------------------- giro dall'attività pianificata

def pannello_acceso():
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", PORTA_PANNELLO)) == 0


def registro(testo):
    d = HOME / ".jarvis-locale" / "log"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "sentinella.log", "a", encoding="utf-8") as f:
        f.write(f"{ora()}  {testo}\n")


def giro(zitto=False):
    if pannello_acceso():
        if not zitto:
            print("Command Center acceso: la sentinella la fa lui.")
        return 0
    LUCCHETTO.parent.mkdir(parents=True, exist_ok=True)
    with open(LUCCHETTO, "w") as lk:
        try:
            if fcntl:
                fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                msvcrt.locking(lk.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            registro("giro saltato: un altro giro è ancora in corso")
            return 0
        pul = pulisci()
        registro("pulizia: " + righe_pulizia(pul))
        an = list(quadro().values())
        if not an:
            registro("quadro pulito")
            if not zitto:
                print("Pulizia: " + righe_pulizia(pul) + "\nNessuna anomalia.")
            return 0
        testo = rapporto(an)                      
        registro("rapporto: " + testo.replace("\n", " | "))
        if not zitto:
            print(f"Pulizia: {righe_pulizia(pul)}\n{testo}")
        return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pulisci", action="store_true")
    p.add_argument("--quadro", action="store_true")
    p.add_argument("--giro", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--zitto", action="store_true")
    a = p.parse_args()
    if a.giro:
        return giro(a.zitto)
    if a.quadro:
        q = quadro()
        print(json.dumps(q, ensure_ascii=False, indent=1) if a.json else
              ("\n".join(f"[{x['tipo']}] {x['testo']}" for x in q.values()) or "nessuna anomalia"))
        return 3 if q else 0
    if a.pulisci:
        e = pulisci()
        print(json.dumps(e, ensure_ascii=False, indent=1, default=str) if a.json else
              f"Pulizia delle {e['quando']}: {righe_pulizia(e)}")
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
