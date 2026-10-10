#!/usr/bin/env python3
"""Le Routine del Command Center sul PC Windows (2026-10-05): quello che sul Mac fa launchd, qui lo fa l'Utilità di
pianificazione. routine.py arriva dal Mac uguale (porta_su_windows.py) e in fondo chiama aggancia(): da lì in poi

  win   le attività pianificate di questo PC il cui nome comincia con «\\Jarvis» (es. «\\Jarvis Avvio», «\\Jarvis Battito»,
        «\\Jarvis\\<nome>»); altre radici con «routine_pc_prefissi» in configurazione.json. Lettura: schtasks /query /fo CSV
        /v /nh (le colonne si leggono per posizione, uguali in ogni lingua di Windows).
  vps   le routine della VPS (timer systemd e cron) si vedono SOLO se configurazione.json ha «routine_vps» (il nome ssh
        del server, es. quello della chiave del CRM) e SOLO quelle del CRM: «id descrizione comando» deve combaciare con
        «routine_vps_filtro» (default FILTRO_VPS). Il confine è quello di PROMPT-PC-WINDOWS.md: il PC lavora solo sul CRM.
        Dal PC non si creano routine nuove sulla VPS.

Azioni sulle attività del PC:
  avvia   schtasks /run /tn <nome>, senza conferma (come «Avvia ora» sul Mac); lo stato si segue con /query.
  log     le righe di schtasks /query /v /fo LIST di quell'attività (l'Utilità di pianificazione non ha un file di log).
  modifica e nuova: solo cose semplici, con la stessa conferma a due tempi di routine.py (prepara → codice → conferma):
          attiva/disattiva (/change /enable|/disable), ora di partenza (/change /st HH:MM), comando (/change /tr),
          nuova in «\\Jarvis\\<nome>» ogni giorno a un'ora (/sc daily /st) oppure ogni N minuti (/sc minute /mo N).
          I comandi si eseguono come liste di argomenti, senza shell.
Solo libreria standard. Sul Mac il modulo non si aggancia (routine.py lo chiama solo con sys.platform == "win32"); le
funzioni che leggono il testo di schtasks si provano anche da lì.
"""
import csv
import io
import json
import re
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime

R = None                       # il modulo routine, dopo aggancia()
PREFISSI = ("\\Jarvis",)
CARTELLA_NUOVE = "\\Jarvis\\"
FILTRO_VPS = r"g140|odoo|crm|condiviso|report-direzione|servizio-(pranzo|cena|live)"
GRUPPI_PC = {"gruppi": [{"id": "crm", "nome": "CRM", "alias": ["crm"]}, {"id": "pc", "nome": "Questo PC", "alias": ["pc"]}],
             "routine": {}, "regole": []}
IN_CORSO = ("running", "in esecuzione")
SPENTA = ("disabled", "disabilitata", "disabilitato", "disattivata")
MAI_PARTITA = 267011           # 0x41303: l'attività non è mai partita
GIRA_ADESSO = 267009           # 0x41301: l'attività sta girando
FORMATI_DATA = ("%d/%m/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S")
_C = {"ts": 0.0, "win": [], "errore": ""}
_LOCK = threading.Lock()


# ---------------------------------------------------------------- configurazione

def conf():
    for nome in ("configurazione.json",):
        try:
            return json.loads((R.QUI / nome).read_text(encoding="utf-8-sig")) if R else {}
        except (OSError, ValueError):
            pass
    return {}


def prefissi():
    p = conf().get("routine_pc_prefissi")
    return tuple(x for x in p if isinstance(x, str) and x) if isinstance(p, list) and p else PREFISSI


def filtro_vps():
    try:
        return re.compile(conf().get("routine_vps_filtro") or FILTRO_VPS, re.I)
    except re.error:
        return re.compile(FILTRO_VPS, re.I)


def gruppi_pc():
    """routine-gruppi.json se c'è (scritto dalla pagina dopo una «Nuova»), se no i due gruppi del PC."""
    if R and R.FILE_GRUPPI.is_file():
        g = R.carica_gruppi()
        if g.get("gruppi"):
            return g
    return json.loads(json.dumps(GRUPPI_PC))


# ---------------------------------------------------------------- lettura di schtasks

def _esegui(argv, timeout=30):
    """Come routine.ESEGUI, ma decodifica l'uscita di schtasks nella codepage della console (oem) e senza finestre."""
    kw = {"creationflags": 0x08000000} if sys.platform == "win32" else {}      # CREATE_NO_WINDOW
    try:
        r = subprocess.run(argv, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL, **kw)
    except subprocess.TimeoutExpired:
        return 124, "tempo scaduto"
    except OSError as e:
        return 1, str(e)
    def dec(b):
        for cod in ("oem", "mbcs", "utf-8"):
            try:
                return b.decode(cod)
            except (LookupError, UnicodeDecodeError):
                continue
        return b.decode("utf-8", errors="replace")
    return r.returncode, dec(r.stdout or b"") + (("\n" + dec(r.stderr)) if r.stderr and r.returncode else "")


def _data(testo):
    testo = (testo or "").strip()
    for f in FORMATI_DATA:
        try:
            return datetime.strptime(testo, f).timestamp()
        except ValueError:
            continue
    return None


def _id(nome):
    s = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    return "win:" + (s[:80] or "attivita")


def _int(t):
    t = (t or "").strip()
    try:
        return int(t, 0) if t.lower().startswith("0x") else int(t)
    except ValueError:
        return None


def _intervallo_testo(ripeti):
    """«Ogni 0 ora/e, 15 minuto/i» (italiano) o «0 Hour(s), 15 Minute(s)» → «15 minuti»; il resto resta com'è."""
    h = re.search(r"(\d+)\s*(?:ora|ore|hour)", ripeti, re.I)
    m = re.search(r"(\d+)\s*minut", ripeti, re.I)
    if not (h or m):
        return ripeti
    h, m = int(h.group(1)) if h else 0, int(m.group(1)) if m else 0
    pezzi = []
    if h:
        pezzi.append("ora" if h == 1 and not m else f"{h} ore" if h > 1 else "1 ora")
    if m:
        pezzi.append("minuto" if m == 1 and not h else f"{m} minuti" if m > 1 else "1 minuto")
    return " e ".join(pezzi) or ripeti


def _orario(righe):
    """Il testo dell'orario dalle righe di una stessa attività (una per innesco)."""
    parti = []
    for c in righe:
        tipo, ora, giorni, ripeti = c[18].strip(), c[19].strip()[:5], c[22].strip(), c[24].strip()
        if not tipo or tipo.upper() in ("N/A", "N/D"):
            continue
        t = tipo.strip().lower()
        if t.startswith(("at logon", "all'accesso", "accesso")):
            parti.append("all'accesso")
        elif t.startswith(("at system start", "all'avvio", "avvio")):
            parti.append("all'accensione")
        elif ripeti and ripeti.upper() not in ("N/A", "N/D", "DISABLED", "DISATTIVATO", "DISABILITATO"):
            parti.append(f"ogni {_intervallo_testo(ripeti)}" + (f" dalle {ora}" if ora and ora[0].isdigit() else ""))
        elif t.startswith(("daily", "giornalier", "ogni giorno")):
            parti.append(f"ogni giorno {ora}")
        elif t.startswith(("weekly", "settimanal")):
            parti.append(f"{giorni} {ora}".strip())
        else:
            parti.append(f"{tipo} {ora}".strip())
    return "; ".join(dict.fromkeys(parti)) or "a mano"


def routine_win(csv_testo, pref=None, adesso=None):
    """Il testo di «schtasks /query /fo CSV /v /nh» → le routine del PC (formato di routine.py)."""
    pref = pref or PREFISSI
    per_nome = {}
    for c in csv.reader(io.StringIO(csv_testo)):
        if len(c) < 25 or c[1] in ("TaskName", "Nome attività") or not c[1].startswith(pref):
            continue
        per_nome.setdefault(c[1], []).append(c)
    out = []
    for nome, righe in sorted(per_nome.items()):
        c = righe[0]
        stato, stato_att = c[3].strip().lower(), c[11].strip().lower()
        codice = _int(c[6])
        in_corso = stato in IN_CORSO or codice == GIRA_ADESSO
        attiva = stato_att not in SPENTA and stato not in SPENTA
        esito = "in_corso" if in_corso else (None if codice in (None, MAI_PARTITA) else ("ok" if codice == 0 else "errore"))
        out.append({
            "id": _id(nome), "fonte": "win", "dove": "PC", "nome": nome, "file": "",
            "descrizione": (c[10].strip() if c[10].strip().upper() not in ("N/A", "N/D") else "") or nome.lstrip("\\"),
            "orario": _orario(righe), "attivo": attiva, "caricato": True, "sempre": False,
            "in_corso": in_corso, "pid": None, "esito": esito, "codice": codice,
            "ultimo": _data(c[5]), "prossimo": _data(c[2]) if attiva else None,
            "comando": R._pulisci(c[8].strip(), 600) if R else c[8].strip()[:600], "log_file": None,
            "avviabile": attiva and not in_corso, "perche_no": "" if attiva else "disattivata: riattivala con «Modifica» → attiva",
            "modifica": {"orario": True, "comando": True, "descrizione": False, "attivo": True},
        })
    return out


def leggi_win(forza=False):
    with _LOCK:
        if not forza and time.time() - _C["ts"] < (R.CACHE_S if R else 45):
            return _C["win"], _C["errore"]
        cod, out = _esegui(["schtasks", "/query", "/fo", "CSV", "/v", "/nh"], timeout=40)
        if cod == 0:
            _C.update(win=routine_win(out, prefissi()), errore="")
        else:
            _C["errore"] = f"Utilità di pianificazione non letta ({cod}): {out.strip()[:160]}"
        _C["ts"] = time.time()
        return _C["win"], _C["errore"]


# ---------------------------------------------------------------- l'elenco: PC + VPS del CRM

def _elenco(originale):
    def elenco(forza=False, extra_gruppi=()):
        d = dict(originale(forza, extra_gruppi))
        win, errore = leggi_win(forza)
        filtro, gc = filtro_vps(), gruppi_pc()
        esplicite = gc.get("routine") or {}
        routine = []
        for r in d.get("routine") or []:
            if r.get("fonte") in ("vps", "cron"):
                testo = f"{r['id']} {r.get('descrizione', '')} {r.get('comando', '')}"
                if not filtro.search(testo):
                    continue                                   # non è del CRM: dal PC non si vede
                r = dict(r)
                v = esplicite.get(r["id"]) or {}
                r["gruppo"], r["tipo"] = v.get("gruppo") or "crm", v.get("tipo") or ""
                routine.append(r)
        for r in win:
            r = dict(r)
            v = esplicite.get(r["id"]) or {}
            r["gruppo"], r["tipo"] = v.get("gruppo") or "pc", v.get("tipo") or ""
            r["ultimo_testo"], r["prossimo_testo"] = R.testo_ora(r.get("ultimo")), R.testo_ora(r.get("prossimo"))
            routine.append(r)
        avvisi = list(d.get("avvisi") or []) + ([errore] if errore else [])
        conta = {}
        for r in routine:
            conta[r["fonte"]] = conta.get(r["fonte"], 0) + 1
        d.update(routine=routine, avvisi=avvisi, conta=conta, gruppi=R.gruppi_per_lavagna(routine, extra_gruppi, gc),
                 nomi_gruppi={g["id"]: g.get("nome", g["id"]) for g in gc.get("gruppi") or [] if isinstance(g, dict)})
        return d
    return elenco


def _leggi_vps_spenta():
    return {"ok": False, "errore": "VPS: nessun server per le routine (configurazione.json → «routine_vps»): "
                                   "sul PC si vedono solo le attività di questo PC"}


# ---------------------------------------------------------------- avvia e log

def _stato_win(nome):
    cod, out = _esegui(["schtasks", "/query", "/tn", nome, "/fo", "CSV", "/v", "/nh"], timeout=20)
    if cod != 0:
        return None
    for c in csv.reader(io.StringIO(out)):
        if len(c) >= 12:
            return c[3].strip().lower(), _int(c[6])
    return None


def _segui_win(eid, nome):
    inizio, visto = time.time(), False
    while time.time() - inizio < R.SEGUI_MAX_S:
        time.sleep(2)
        s = _stato_win(nome)
        if s is None:
            continue
        stato, cod = s
        if stato in IN_CORSO or cod == GIRA_ADESSO:
            visto = True
            R._aggiorna_esec(eid, stato="in_corso", esito="in corso")
            continue
        if visto or time.time() - inizio > 6:
            ok = cod in (0, None)
            e = R._aggiorna_esec(eid, stato="ok" if ok else "errore", codice=cod, finito=time.time(),
                                 esito="finita bene" if ok else f"finita con errore (codice {cod})")
            R.registra("avvia", e["id"] if e else eid, "ok" if ok else "errore", uscita=e.get("esito") if e else "")
            R.invalida()
            with _LOCK:
                _C["ts"] = 0.0
            return
    R._aggiorna_esec(eid, stato="lunga", esito="in corso da più di 30 minuti: guarda il log")


def _avvia(originale):
    def avvia(rid, chi="pagina"):
        if not str(rid).startswith("win:"):
            return originale(rid, chi)
        r = R.trova(rid)
        if not r.get("avviabile"):
            raise R.RoutineNonValida(r.get("perche_no") or "questa routine non si avvia da qui")
        with R._ESEC_LOCK:
            for e in R._ESEC.values():
                if e["id"] == rid and e["stato"] in ("partenza", "in_corso"):
                    return dict(e)
        eid = secrets.token_hex(6)
        with R._ESEC_LOCK:
            R._ESEC[eid] = {"eid": eid, "id": rid, "nome": r["nome"], "descrizione": r["descrizione"], "partito": time.time(),
                            "stato": "partenza", "esito": "parte…", "codice": None, "finito": None, "chi": chi}
        cod, out = _esegui(["schtasks", "/run", "/tn", r["nome"]], timeout=20)
        if cod != 0:
            R._aggiorna_esec(eid, stato="errore", esito=f"non partita: {R._pulisci(out, 200).strip()}", finito=time.time())
            R.registra("avvia", rid, "errore", uscita=out)
            return R._aggiorna_esec(eid)
        threading.Thread(target=_segui_win, args=(eid, r["nome"]), daemon=True).start()
        R.registra("avvia", rid, "partito", chi=chi)
        return R._aggiorna_esec(eid, stato="in_corso", esito="partita")
    return avvia


def _log(originale):
    def log(rid, righe=80):
        if not str(rid).startswith("win:"):
            return originale(rid, righe)
        r = R.trova(rid)
        cod, out = _esegui(["schtasks", "/query", "/tn", r["nome"], "/v", "/fo", "LIST"], timeout=20)
        testo = f"--- Utilità di pianificazione: {r['nome']}\n" + (out if cod == 0 or out else f"non letta ({cod})")
        testo += "\n(le attività pianificate non hanno un file di log: qui c'è l'ultimo esito e il prossimo avvio)"
        return {"id": rid, "testo": R._pulisci(testo, 60000), "letto": time.time()}
    return log


# ---------------------------------------------------------------- modifica e nuova: stessa conferma a due tempi

def comandi_win(nome, nuovo, orario, comando, attivo):
    """→ (lista di argv, riepilogo). orario: ("daily", "HH:MM") o ("minute", N)."""
    cmd, riep = [], []
    if nuovo:
        argv = ["schtasks", "/create", "/tn", nome, "/tr", comando]
        if orario[0] == "minute":
            argv += ["/sc", "minute", "/mo", str(orario[1])]
            riep.append(f"nuova: ogni {orario[1]} min")
        else:
            argv += ["/sc", "daily", "/st", orario[1]]
            riep.append(f"nuova: ogni giorno alle {orario[1]}")
        cmd.append(argv)
        if attivo is False:
            cmd.append(["schtasks", "/change", "/tn", nome, "/disable"])
            riep.append("creata disattivata")
        return cmd, riep
    if orario:
        if orario[0] != "daily":
            raise R.RoutineNonValida("sul PC, per un'attività che c'è già, si cambia solo l'ora di partenza (HH:MM)")
        cmd.append(["schtasks", "/change", "/tn", nome, "/st", orario[1]])
        riep.append(f"ora di partenza {orario[1]}")
    if comando:
        cmd.append(["schtasks", "/change", "/tn", nome, "/tr", comando])
        riep.append("comando nuovo")
    if attivo is not None:
        cmd.append(["schtasks", "/change", "/tn", nome, "/enable" if attivo else "/disable"])
        riep.append("attiva" if attivo else "disattiva")
    return cmd, riep


def orario_win(v):
    v = R._testo_breve(v, "orario", 80)
    minuti = R._intervallo(v)
    if minuti:
        if minuti > 1439:
            raise R.RoutineNonValida("sul PC: al massimo ogni 1439 minuti; per una volta al giorno scrivi l'ora")
        return ("minute", minuti)
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", v)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise R.RoutineNonValida("orario sul PC: «07:30» (ogni giorno) oppure «ogni 15 min»")
    return ("daily", f"{int(m.group(1)):02d}:{m.group(2)}")


def _prepara(originale):
    def prepara(dati, chi="pagina"):
        if not isinstance(dati, dict):
            raise R.RoutineNonValida("serve un oggetto JSON")
        nuovo = dati.get("nuova") is True
        if nuovo and dati.get("fonte") in ("vps", "cron", "mac"):
            raise R.RoutineNonValida("dal PC le routine nuove si creano solo su questo PC (Dove: «PC»)")
        if not ((nuovo and dati.get("fonte") == "win") or str(dati.get("id", "")).startswith("win:")):
            return originale(dati, chi)
        if nuovo:
            n = dati.get("nome")
            if not isinstance(n, str) or not R.NOME.fullmatch(n):
                raise R.RoutineNonValida("nome: minuscole, cifre e trattini, da 1 a 40 caratteri")
            nome = CARTELLA_NUOVE + n
            rid = _id(nome)
            if any(x["id"] == rid for x in R.elenco()["routine"]):
                raise R.RoutineNonValida(f"esiste già un'attività «{nome}»")
            if dati.get("orario") in (None, "") or dati.get("comando") in (None, ""):
                raise R.RoutineNonValida("una routine nuova vuole orario e comando")
            r = {"id": rid, "nome": nome, "attivo": None}
        else:
            r = R.trova(dati.get("id"))
            nome, rid = r["nome"], r["id"]
        orario = orario_win(dati["orario"]) if dati.get("orario") not in (None, "") else None
        comando = R._testo_breve(dati["comando"], "comando", 600) if dati.get("comando") not in (None, "") else None
        attivo = None
        if dati.get("attivo") is not None:
            if not isinstance(dati["attivo"], bool):
                raise R.RoutineNonValida("attivo: vero o falso")
            if nuovo or dati["attivo"] != r.get("attivo"):
                attivo = dati["attivo"]
        if dati.get("descrizione") not in (None, "") and not nuovo:
            raise R.RoutineNonValida("sul PC la descrizione non si cambia da qui")
        gruppo, tipo = dati.get("gruppo"), dati.get("tipo")
        if gruppo is not None and (not isinstance(gruppo, str) or not R.NOME.fullmatch(gruppo)):
            raise R.RoutineNonValida("gruppo: minuscole, cifre e trattini")
        if tipo not in (None, "", "controllo", "dati"):
            raise R.RoutineNonValida("tipo: controllo, dati o vuoto")
        if not nuovo and all(x is None for x in (orario, comando, attivo)):
            raise R.RoutineNonValida("niente da cambiare")
        argv, riepilogo = comandi_win(nome, nuovo, orario, comando, attivo)
        testo = "\n".join(subprocess.list2cmdline(a) for a in argv) + "\n"
        pid, codice = secrets.token_hex(8), secrets.token_hex(16)
        prep = {"prep": pid, "id": rid, "fonte": "win", "nuova": nuovo, "dove": "PC (questo computer, Utilità di pianificazione)",
                "riepilogo": riepilogo, "comando": testo, "preparato": time.time(), "scade": time.time() + R.PREP_MAX_S,
                "gruppo": gruppo if nuovo or gruppo else None, "tipo": tipo}
        with R._PREP_LOCK:
            for k in [k for k, v in R._PREP.items() if time.time() > v["scade"]]:
                del R._PREP[k]
            R._PREP[pid] = {**prep, "script": testo, "argv": argv, "codice": codice}
        R.registra("prepara", rid, "preparato", chi=chi, riepilogo="; ".join(riepilogo))
        return {**prep, "codice": codice, "valido_s": R.PREP_MAX_S}
    return prepara


def _conferma(originale):
    def conferma(pid, codice, chi="pagina"):
        with R._PREP_LOCK:
            p = R._PREP.get(pid) if isinstance(pid, str) else None
            win = bool(p) and p.get("fonte") == "win"
        if not win:
            return originale(pid, codice, chi)
        with R._PREP_LOCK:                                   # gli stessi controlli di routine.conferma
            p = R._PREP.get(pid)
            if not p:
                raise R.RoutineNonValida("nessun comando preparato con questo id")
            if not isinstance(codice, str) or not secrets.compare_digest(codice.encode(), p["codice"].encode()):
                R.registra("conferma", p["id"], "rifiutato", motivo="codice di conferma mancante o sbagliato")
                raise R.RoutineNonValida("serve la conferma esplicita dalla pagina: codice mancante o sbagliato")
            if time.time() - p["preparato"] < R.PREP_MIN_S:
                raise R.RoutineNonValida("conferma troppo veloce: leggi il comando, poi conferma")
            del R._PREP[pid]
        if time.time() > p["scade"]:
            R.registra("conferma", p["id"], "rifiutato", motivo="scaduto")
            raise R.RoutineNonValida("il comando preparato è scaduto (10 minuti): rifai «Prepara»")
        R.registra("conferma", p["id"], "partito", chi=chi, comando=p["script"])
        uscite, cod = [], 0
        for argv in p["argv"]:
            cod, out = _esegui(argv, timeout=30)
            uscite.append(f"> {subprocess.list2cmdline(argv)}\n{out.strip()}")
            if cod != 0:
                break
        ok = cod == 0
        if ok and (p.get("gruppo") or p.get("tipo")):
            R._salva_gruppo(p["id"], p.get("gruppo"), p.get("tipo"))
        out = "\n".join(uscite)
        R.registra("conferma", p["id"], "ok" if ok else "errore", uscita=out, codice=cod)
        R.invalida()
        with _LOCK:
            _C["ts"] = 0.0
        return {"ok": ok, "id": p["id"], "codice": cod, "uscita": R._pulisci(out, 6000)}
    return conferma


# ---------------------------------------------------------------- l'aggancio

def aggancia(modulo):
    """Chiamata in fondo a routine.py su Windows. Una volta sola."""
    global R
    if getattr(modulo, "_PC_AGGANCIATO", False):
        return
    R = modulo
    R._PC_AGGANCIATO = True
    R.ID = re.compile(r"(vps|cron|mac|win):[A-Za-z0-9._-]{1,80}")
    vps = conf().get("routine_vps")
    import os
    if os.environ.get("CC_ROUTINE_VPS"):
        vps = os.environ["CC_ROUTINE_VPS"]
    if isinstance(vps, str) and re.fullmatch(r"[A-Za-z0-9@._-]{1,80}", vps):
        R.VPS = vps
    else:
        R.leggi_vps = _leggi_vps_spenta
    R.elenco = _elenco(R.elenco)
    R.avvia = _avvia(R.avvia)
    R.log = _log(R.log)
    R.prepara = _prepara(R.prepara)
    R.conferma = _conferma(R.conferma)
