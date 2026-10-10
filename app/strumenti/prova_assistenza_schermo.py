#!/usr/bin/env python3
"""Prove dello SCHERMO condiviso dell'assistenza (strumenti/assistenza.py), con programmi FINTI.

Creato il 2026-10-02. Gira su macOS o Linux (non su Windows: i finti programmi sono script).
Come prova_assistenza.py, il finto wsl.exe lancia qui lo script del tunnel. In più:
  - un finto TightVNC (tvnserver.exe): legge le impostazioni scritte dal modulo (porta, solo
    127.0.0.1, password nel formato del VNC), ascolta e saluta «RFB 003.008»;
  - un finto ssh.exe di Windows: con -R 127.0.0.1:PORTA_SCHERMO:127.0.0.1:PORTA_VNC ascolta sulla
    PORTA_SCHERMO (come farebbe il server del tecnico) e gira i byte al VNC, così si prova il percorso intero;
  - un finto netstat che stampa le righe di Windows («TCP 127.0.0.1:5900 ... LISTENING pid»).
Il tecnico è simulato: ha una sua chiave ed25519 e decifra il segreto della richiesta.
Esce con 1 se una prova fallisce.

Uso:  python3 strumenti/prova_assistenza_schermo.py
"""

import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent
PY = sys.executable
TMP = Path(tempfile.mkdtemp(prefix="prova-assistenza-schermo-"))
for d in ("cc", "bin", "linux-casa", "netstat", "schermo"):
    (TMP / d).mkdir()
CASA_TUNNEL = TMP / "linux-casa" / ".jarvis-assistenza-cliente"
SESS = CASA_TUNNEL / "sessione"
SCH = TMP / "schermo"
AMB = {
    "ASSISTENZA_DIR": str(TMP / "cc"),
    "ASSISTENZA_CHIAVE_PUBBLICA": str(TMP / "cc" / "chiave-pubblica-prova.txt"),
    "ASSISTENZA_MODO": "wsl",
    "ASSISTENZA_WSL": str(TMP / "bin" / "wsl.exe"),
    "ASSISTENZA_WSL_DISTRO": "Ubuntu",
    "ASSISTENZA_SSH": str(TMP / "bin" / "ssh"),
    "ASSISTENZA_SSHD": str(TMP / "bin" / "sshd"),
    "ASSISTENZA_SSH_KEYGEN": str(TMP / "bin" / "ssh-keygen"),
    "ASSISTENZA_TMUX": str(TMP / "bin" / "tmux-che-non-c-e"),
    "ASSISTENZA_TUNNEL_DIR": str(CASA_TUNNEL),
    "ASSISTENZA_SOCKET": str(TMP / "tmate.sock"),
    "ASSISTENZA_VNC": str(TMP / "bin" / "tvnserver.exe"),
    "ASSISTENZA_SSH_WIN": str(TMP / "bin" / "ssh.exe"),
    "ASSISTENZA_NETSTAT": str(TMP / "bin" / "netstat"),
    "ASSISTENZA_SCHERMO_DIR": str(SCH),
}
os.environ.pop("ASSISTENZA_TMATE", None)
os.environ.pop("ASSISTENZA_PREPARA", None)
os.environ.update(AMB)
os.environ["PATH"] = os.pathsep.join(d for d in os.environ.get("PATH", "").split(os.pathsep)
                                     if d and not os.access(os.path.join(d, "tmate"), os.X_OK))


def scrivi_bin(nome, testo):
    f = TMP / "bin" / nome
    f.write_text(f"#!{PY}\n" + testo)
    os.chmod(f, 0o755)


scrivi_bin("wsl.exe", """import sys, os
a = sys.argv[1:]
if a[:1] == ["-d"]:
    a = a[2:]
os.execvp(a[1], a[1:])
""")
scrivi_bin("ssh-keygen", """import sys, os, base64
a = sys.argv[1:]
f = a[a.index("-f") + 1]
c = a[a.index("-C") + 1]
pub = b"\\x00\\x00\\x00\\x0bssh-ed25519\\x00\\x00\\x00\\x20" + os.urandom(32)
open(f, "w").write("-----BEGIN OPENSSH PRIVATE KEY-----\\nFINTA " + os.urandom(8).hex() + "\\n-----END OPENSSH PRIVATE KEY-----\\n")  # gitleaks:allow (chiave FINTA della prova)
os.chmod(f, 0o600)
open(f + ".pub", "w").write("ssh-ed25519 " + base64.b64encode(pub).decode() + " " + c + "\\n")
""")
scrivi_bin("sshd", """import sys, socket, re
a = sys.argv[1:]
cfg = open(a[a.index("-f") + 1]).read()
porta = int(re.search(r"^Port (\\d+)", cfg, re.M).group(1))
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", porta)); s.listen(5)
print(f"Server listening on 127.0.0.1 port {porta}.", file=sys.stderr, flush=True)
while True:
    c, _ = s.accept(); c.sendall(b"SSH-2.0-finto\\r\\n"); c.close()
""")
scrivi_bin("ssh", f"""import sys, time, os
modo = open({str(TMP / 'ssh-modo')!r}).read().strip() if os.path.exists({str(TMP / 'ssh-modo')!r}) else "ok"
if modo == "rifiuta":
    print("Permission denied (publickey).", file=sys.stderr); sys.exit(255)
print("Authenticated to server-finto ([192.0.2.1]:22) using \\"publickey\\".", file=sys.stderr, flush=True)
while True:
    time.sleep(1)
""")

# ---- finto TightVNC: impostazioni dal JSON scritto dal modulo (al posto del registro di Windows)
scrivi_bin("tvnserver.exe", f"""import sys, os, json, socket, threading, signal
a = sys.argv[1:]
if "-controlapp" in a:
    sys.exit(0)
conf = json.load(open(os.path.join(os.environ["ASSISTENZA_SCHERMO_DIR"], "vnc-finto.json")))
open({str(TMP / 'vnc-avvii.log')!r}, "a").write(json.dumps(conf) + "\\n")
porta = int(conf["RfbPort"])
ind = "0.0.0.0" if os.path.exists({str(TMP / 'vnc-tutti')!r}) or conf.get("LoopbackOnly") != 1 else "127.0.0.1"
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((ind, porta)); s.listen(5)
riga = {str(TMP / 'netstat')!r} + f"/vnc-{{os.getpid()}}.txt"
aperte = []
def scrivi():
    r = [f"  TCP    {{ind}}:{{porta}}           0.0.0.0:0              LISTENING       {{os.getpid()}}"]
    r += [f"  TCP    127.0.0.1:{{porta}}         127.0.0.1:{{p}}       ESTABLISHED     {{os.getpid()}}" for p in aperte]
    open(riga, "w").write("\\n".join(r) + "\\n")
def fine(*_):
    try: os.remove(riga)
    except OSError: pass
    os._exit(0)
signal.signal(signal.SIGTERM, fine)
scrivi()
def servi(c, p):
    try:
        c.sendall(b"RFB 003.008\\n")
        while c.recv(1024): pass
    except OSError: pass
    aperte.remove(p); scrivi(); c.close()
while True:
    c, (_, p) = s.accept()
    aperte.append(p); scrivi()
    threading.Thread(target=servi, args=(c, p), daemon=True).start()
""")

# ---- finto ssh.exe di Windows: -R 127.0.0.1:PS:127.0.0.1:PV -> ascolta su PS («il server») e gira al VNC
scrivi_bin("ssh.exe", f"""import sys, os, json, socket, threading, time
a = sys.argv[1:]
open({str(TMP / 'sshwin.log')!r}, "a").write(json.dumps(a) + "\\n")
f = {str(TMP / 'sshwin-modo')!r}
modo = open(f).read().strip() if os.path.exists(f) else "ok"
if modo == "rifiuta":
    print("assistenza@server: Permission denied (publickey).", file=sys.stderr); sys.exit(255)
chiave = a[a.index("-i") + 1]
if not open(chiave).read().startswith("-----BEGIN"):
    print("chiave rotta", file=sys.stderr); sys.exit(255)
ps, pv = int(a[a.index("-R") + 1].split(":")[1]), int(a[a.index("-R") + 1].split(":")[3])
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", ps)); s.listen(5)
print("Authenticated to server-finto ([192.0.2.1]:22) using \\"publickey\\".", file=sys.stderr, flush=True)
def gira(x, y):
    try:
        while True:
            b = x.recv(4096)
            if not b: break
            y.sendall(b)
    except OSError: pass
    for z in (x, y):
        try: z.close()
        except OSError: pass
while True:
    c, _ = s.accept()
    try:
        v = socket.create_connection(("127.0.0.1", pv))
    except OSError:
        c.close(); continue
    threading.Thread(target=gira, args=(c, v), daemon=True).start()
    threading.Thread(target=gira, args=(v, c), daemon=True).start()
""")
scrivi_bin("netstat", f"""import os, glob
print("\\nActive Connections\\n\\n  Proto  Local Address          Foreign Address        State           PID")
for f in sorted(glob.glob({str(TMP / 'netstat')!r} + "/*.txt")):
    try: print(open(f).read(), end="")
    except OSError: pass
""")

sys.path.insert(0, str(QUI))
import assistenza as A  # noqa: E402


# ---- il tecnico di prova: chiave ed25519 sua, e la decifratura del segreto (come assistenza_codice.py sul Mac)
def _comprimi(P):
    zi = A._inv(P[2])
    x, y = P[0] * zi % A._P, P[1] * zi % A._P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _scalare(seme):
    a = int.from_bytes(hashlib.sha512(seme).digest()[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a


SEME_TEC = os.urandom(32)
PUB_TEC = _comprimi(A._moltiplica(_scalare(SEME_TEC), A._G))
CHIAVE_TEC = "ssh-ed25519 " + base64.b64encode(b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + PUB_TEC).decode()


def decifra(segreto, seme=SEME_TEC, pub=PUB_TEC):
    g = base64.b64decode(segreto)
    eff, cif, et = g[:32], g[32:40], g[40:]
    u = A._montgomery_da_ed25519(pub)
    k = A._flusso(A._x25519(hashlib.sha512(seme).digest()[:32], int.from_bytes(eff, "little")), eff, u)
    if not hmac.compare_digest(hmac.new(k[8:], eff + cif, hashlib.sha256).digest()[:8], et):
        return None
    return bytes(x ^ y for x, y in zip(cif, k[:8])).decode()


# ---- i codici di ricarica (firma ed25519 di prova)
SEGRETO = os.urandom(32)
_a = _scalare(SEGRETO)
_pre = hashlib.sha512(SEGRETO).digest()[32:]
PUBBLICA = _comprimi(A._moltiplica(_a, A._G))
Path(AMB["ASSISTENZA_CHIAVE_PUBBLICA"]).write_text(PUBBLICA.hex() + "\n")


def codice(minuti):
    corpo = json.dumps({"v": 1, "id": os.urandom(12).hex(), "min": minuti, "scade": int(time.time() + 3600)},
                       separators=(",", ":")).encode()
    r = A._sha512_modq(_pre + corpo)
    Rs = _comprimi(A._moltiplica(r, A._G))
    s = (r + A._sha512_modq(Rs + PUBBLICA + corpo) * _a) % A._Q
    return base64.b32encode(corpo + Rs + s.to_bytes(32, "little")).decode().rstrip("=")


esiti = []


def prova(nome, cond, dettaglio=""):
    esiti.append(bool(cond))
    print(f"{'OK  ' if cond else 'FALLITA'}  {nome}" + (f"  ({dettaglio})" if dettaglio and not cond else ""))


def aspetta(cond, secondi=6.0):
    fine = time.time() + secondi
    while time.time() < fine:
        if cond():
            return True
        time.sleep(0.1)
    return cond()


def vivo(pid):
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    st = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(st) and not st.startswith("Z")


def risponde(porta, inizio=b"RFB "):
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=1) as s:
            s.settimeout(2)
            return s.recv(12).startswith(inizio)
    except OSError:
        return False


def reg():
    return json.loads((TMP / "cc" / "assistenza-registro.json").read_text())


def conf_vnc():
    try:
        return json.loads((SCH / "vnc-finto.json").read_text())
    except (OSError, ValueError):
        return {}


CONF = TMP / "cc" / "assistenza.json"
MODELLO = {k: v for k, v in json.loads((QUI.parent / "command-center" / "assistenza-tunnel.json").read_text(encoding="utf-8")).items()
           if not k.startswith("_")}
# 2026-10-10: nella distribuzione neutra il modello pubblico è vuoto (nessun tecnico): la prova usa un tecnico FINTO
# con un indirizzo di documentazione (RFC 5737) e chiavi inventate, scritto nella cartella di prova dell'assistenza.
if not MODELLO.get("host"):
    import base64 as _b64
    def _chiave_finta(seme):
        corpo = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + bytes((seme + i) % 256 for i in range(32))
        return "ssh-ed25519 " + _b64.b64encode(corpo).decode()
    MODELLO = {"host": "192.0.2.10", "porta": 22, "utente": "assistenza",
                      "known_hosts": "192.0.2.10 " + _chiave_finta(1), "chiave_tecnico": _chiave_finta(2), "porte": [47000, 47999]}
    (Path(os.environ["ASSISTENZA_DIR"]) / "assistenza-tunnel.json").write_text(json.dumps(MODELLO), encoding="utf-8")
RICH2 = re.compile(r"jarvis-tunnel:2:(\d{4,5}):(\d{4,5}):([A-Za-z0-9_][A-Za-z0-9._-]{0,31}):([A-Za-z0-9+/]{68}):"
                   r"([A-Za-z0-9+/]{68}):([A-Za-z0-9+/]{64})")
RICH1 = re.compile(r"jarvis-tunnel:1:(\d{4,5}):([A-Za-z0-9_][A-Za-z0-9._-]{0,31}):([A-Za-z0-9+/]{68}):([A-Za-z0-9+/]{68})")


def configura(**extra):
    c = {"abilitata": True, "tunnel": {**MODELLO, "chiave_tecnico": CHIAVE_TEC + " tecnico"}}
    c.update(extra)
    CONF.write_text(json.dumps(c), encoding="utf-8")
    A._cache_ssh.update(ts=0.0)
    A._cache_tmate.update(ts=0.0)


def pids_schermo():
    a = reg().get("attiva") or {}
    s = (a.get("tunnel") or {}).get("schermo") or {}
    return s.get("pid_vnc"), s.get("pid_ssh"), s.get("porta"), s.get("porta_vnc")


try:
    configura()
    A.accredita(codice(600))

    # ================================================================ K  avvio con lo schermo
    print("\nK  Avvio: terminale e schermo insieme")
    prova("K1 schermo pronto (finti TightVNC e ssh.exe) e nulla manca", A.schermo_pronto() and A.cosa_manca() == [], A.cosa_manca())
    prova("K2 lo stato dice al pannello che c'è lo schermo (consenso per schermo e terminale)", A.stato()["schermo"] is True)
    T0 = time.time()
    s = A.avvia_sessione(True, adesso=T0)
    a = s["attiva"] or {}
    m = RICH2.fullmatch(a.get("richiesta") or "")
    prova("K3 un solo consenso apre tutto: richiesta versione 2 con la porta dello schermo", bool(m), a.get("richiesta"))
    porta, porta_s = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    lo, hi = MODELLO["porte"]
    prova("K4 porta dello schermo accanto a quella del terminale, nella fascia", abs(porta_s - porta) == 1 and lo <= porta_s <= hi,
          (porta, porta_s))
    pw = decifra(m.group(6)) if m else None
    prova("K5 il tecnico (e solo con la sua chiave) decifra la password: 8 caratteri", bool(pw) and len(pw) == 8, pw and len(pw))
    altro = os.urandom(32)
    prova("K6 con un'altra chiave la password NON si decifra",
          m and decifra(m.group(6), altro, _comprimi(A._moltiplica(_scalare(altro), A._G))) is None)
    cv = conf_vnc()
    prova("K7 il VNC ha la STESSA password (formato del VNC, mai in chiaro)",
          pw and cv.get("Password") == A.vnc_password_cifrata(pw).hex() and pw not in json.dumps(cv), cv.get("Password"))
    prova("K8 impostazioni del VNC: solo 127.0.0.1, autenticazione, porta di sessione",
          cv.get("LoopbackOnly") == 1 and cv.get("AllowLoopback") == 1 and cv.get("UseVncAuthentication") == 1
          and cv.get("AcceptRfbConnections") == 1 and cv.get("AcceptHttpConnections") == 0, cv)
    pv_, ps_, porta_sch, porta_vnc = pids_schermo()
    asc = A.vnc_ascolti(porta_vnc)
    prova("K9 il VNC ascolta SOLO su 127.0.0.1 (netstat)", asc is not None and asc[0] == {"127.0.0.1"}, asc)
    aspetta(lambda: (TMP / "sshwin.log").exists() and (TMP / "sshwin.log").read_text().strip())
    righe = [json.loads(x) for x in (TMP / "sshwin.log").read_text().splitlines() if x.strip()]
    argv = righe[-1] if righe else []
    prova("K10 ssh.exe di Windows: -R 127.0.0.1:SCHERMO:127.0.0.1:VNC verso il server, chiave host fissata",
          argv and argv[argv.index("-R") + 1] == f"127.0.0.1:{porta_s}:127.0.0.1:{porta_vnc}"
          and "StrictHostKeyChecking=yes" in argv and "BatchMode=yes" in argv and "ExitOnForwardFailure=yes" in argv
          and argv[-1] == f"{MODELLO['utente']}@{MODELLO['host']}", argv)
    prova("K11 ssh.exe usa la chiave di sessione del terminale, copiata con permessi 600",
          (SCH / "sessione" / "cliente").read_text().strip() == (SESS / "cliente").read_text().strip()
          and (os.stat(SCH / "sessione" / "cliente").st_mode & 0o777) == 0o600)
    prova("K12 known_hosts dello schermo = quello del server", (SCH / "sessione" / "known_hosts").read_text().strip() == MODELLO["known_hosts"])
    prova("K13 dalla porta dello schermo «sul server» risponde il VNC del PC (RFB)", aspetta(lambda: risponde(porta_s)))
    A.tick(adesso=T0 + 20)
    st = A.stato(adesso=T0 + 20)["attiva"]
    prova("K14 il giro segna terminale e schermo pronti", st["collegato"] and st["schermo"]["pronto"] and not st["schermo"]["in_uso"], st.get("schermo"))
    tecnico = socket.create_connection(("127.0.0.1", porta_s))
    tecnico.recv(12)
    aspetta(lambda: (A.vnc_ascolti(porta_vnc) or (set(), 0))[1] > 0)
    A.tick(adesso=T0 + 40)
    prova("K15 tecnico collegato allo schermo: il pannello dice «Schermo condiviso attivo»",
          A.stato(adesso=T0 + 40)["attiva"]["schermo"]["in_uso"] is True)
    tecnico.close()
    tutto = "\n".join(p.read_text(errors="replace") for p in TMP.rglob("*") if p.is_file() and p.suffix in (".json", ".log", ".txt"))
    prova("K16 la password in chiaro non compare in registro, log, impostazioni, stato o richiesta",
          pw and pw not in tutto and pw not in json.dumps(A.stato()) and pw not in a.get("richiesta", ""))

    # ---- lo schermo cade da solo: si riapre, la sessione resta
    os.kill(int(ps_), signal.SIGKILL)
    aspetta(lambda: not vivo(ps_))
    A.tick(adesso=T0 + 60)
    tu = reg()["attiva"]["tunnel"]
    prova("K17 tunnel dello schermo caduto da solo: si riapre, il terminale resta",
          reg()["attiva"] and tu["schermo"]["tentativi"] == 2 and tu["schermo"]["pid_ssh"] != ps_ and aspetta(lambda: risponde(porta_s)))

    # ---- STOP: tutto fermo, password tolta
    pv_, ps_, _, _ = pids_schermo()
    s = A.ferma_sessione(adesso=T0 + 120)
    prova("K18 STOP: un solo tasto ferma VNC e tunnel dello schermo", aspetta(lambda: not vivo(pv_) and not vivo(ps_)), (pv_, ps_))
    prova("K19 STOP: porte dello schermo chiuse (sul «server» e sul PC)", not risponde(porta_s) and not risponde(porta_vnc))
    prova("K20 STOP: password tolta dalle impostazioni del VNC, connessioni rifiutate",
          not A.vnc_password_presente() and conf_vnc().get("AcceptRfbConnections") == 0, conf_vnc())
    prova("K21 STOP: chiave copiata cancellata, terminale chiuso", not (SCH / "sessione").exists() and not SESS.exists() and s["attiva"] is None)

    # ================================================================ L  chiusure automatiche
    print("\nL  Chiusure automatiche")
    T0 = time.time()
    A.avvia_sessione(True, adesso=T0)
    A.tick(adesso=T0 + 20)
    pv_, ps_, porta_s, porta_vnc = pids_schermo()
    pid_ssh_wsl = (SESS / "ssh.pid").read_text().strip()
    os.kill(int(pid_ssh_wsl), signal.SIGKILL)
    aspetta(lambda: not vivo(pid_ssh_wsl))
    f = A.tick(adesso=T0 + 40)
    prova("L1 cade il terminale: si chiude tutto, anche lo schermo",
          reg()["attiva"] is None and "caduto" in (f or "") and aspetta(lambda: not vivo(pv_) and not vivo(ps_))
          and not risponde(porta_s) and not A.vnc_password_presente(), f)

    T0 = time.time()
    A.avvia_sessione(True, adesso=T0)
    A.tick(adesso=T0 + 20)
    pv_, ps_, porta_s, porta_vnc = pids_schermo()
    os.kill(int(pv_), signal.SIGTERM)                  # il cliente chiude TightVNC dall'icona
    aspetta(lambda: not vivo(pv_))
    A.tick(adesso=T0 + 40)
    st = A.stato()["attiva"]
    prova("L2 il cliente chiude il VNC: schermo chiuso, terminale ancora aperto",
          st and st["schermo"]["chiuso"] and aspetta(lambda: not vivo(ps_)) and not A.vnc_password_presente(), st and st.get("schermo"))
    with A._registro() as r:                           # credito: chiude alla fine del blocco in corso
        r["credito_min"] = 0
    A.tick(adesso=T0 + 840)
    A.tick(adesso=T0 + 901)
    prova("L3 credito finito: sessione chiusa", reg()["attiva"] is None)

    T0 = time.time()
    with A._registro() as r:
        r["credito_min"] = 120
    A.avvia_sessione(True, adesso=T0)
    A.tick(adesso=T0 + 20)
    pv_, ps_, porta_s, porta_vnc = pids_schermo()
    with A._registro() as r:
        r["attiva"]["pagato_fino"] = T0 + 9 * 3600
    f = A.tick(adesso=T0 + 8 * 3600)
    prova("L4 tetto di 8 ore: chiuso anche lo schermo", reg()["attiva"] is None and "8 ore" in (f or "")
          and aspetta(lambda: not vivo(pv_) and not vivo(ps_)) and not A.vnc_password_presente(), f)

    # STOP da un ALTRO processo (riga di comando / ASSISTENZA.ps1 -Ferma): i pid non sono figli suoi
    T0 = time.time()
    A.avvia_sessione(True, adesso=T0)
    A.tick(adesso=T0 + 20)
    pv_, ps_, porta_s, porta_vnc = pids_schermo()
    p = subprocess.run([PY, str(QUI / "assistenza.py"), "stop"], capture_output=True, text=True, timeout=120)
    prova("L5 STOP da un altro processo (assistenza.py stop): schermo fermato lo stesso",
          p.returncode == 0 and aspetta(lambda: not vivo(pv_) and not vivo(ps_)) and not risponde(porta_s)
          and not A.vnc_password_presente(), p.stderr[-300:])
    for pid in (pv_, ps_):                              # gli zombie del processo di prova
        pp = A._PROCESSI_WIN.pop(pid, None)
        if pp:
            pp.wait(timeout=5)
    for n in list(A._PROCESSI):
        A._chiudi_popen(A._PROCESSI.pop(n))

    # tunnel dello schermo rifiutato (chiave non ancora aperta sul server): si riprova a ogni giro
    (TMP / "sshwin-modo").write_text("rifiuta")
    T0 = time.time()
    A.avvia_sessione(True, adesso=T0)
    aspetta(lambda: not A._pid_vivo(pids_schermo()[1]))
    A.tick(adesso=T0 + 20)
    A.tick(adesso=T0 + 40)
    prova("L6 ssh.exe rifiutato: lo schermo si riprova a ogni giro, la sessione resta",
          reg()["attiva"] and reg()["attiva"]["tunnel"]["schermo"]["tentativi"] >= 2
          and not reg()["attiva"]["tunnel"]["schermo"]["collegato"])
    A.ferma_sessione()
    (TMP / "sshwin-modo").write_text("ok")

    # ================================================================ M  sicurezza e compatibilità
    print("\nM  Sicurezza e compatibilità")
    (TMP / "vnc-tutti").write_text("")
    s = A.avvia_sessione(True)
    a = s["attiva"]
    avv = [json.loads(x) for x in (TMP / "vnc-avvii.log").read_text().splitlines()][-1]
    prova("M1 VNC che ascolta anche fuori da 127.0.0.1: schermo rifiutato e fermato, resta il terminale",
          RICH1.fullmatch(a["richiesta"]) and a.get("schermo") is None and not risponde(int(avv["RfbPort"]))
          and not A.vnc_password_presente()
          and any("fuori da questo PC" in x["testo"] for x in reg()["log"]), a["richiesta"][:20])
    A.ferma_sessione()
    (TMP / "vnc-tutti").unlink()

    configura(schermo=False)
    s = A.avvia_sessione(True)
    prova("M2 «schermo»: false in assistenza.json: solo terminale (richiesta versione 1)",
          RICH1.fullmatch(s["attiva"]["richiesta"]) and s["attiva"].get("schermo") is None and A.stato()["schermo"] is False)
    A.ferma_sessione()

    configura()
    os.environ["ASSISTENZA_VNC"] = str(TMP / "bin" / "tvnserver-che-non-c-e.exe")
    s = A.avvia_sessione(True)
    prova("M3 PC senza TightVNC: solo terminale, nessun errore", RICH1.fullmatch(s["attiva"]["richiesta"])
          and s["attiva"].get("schermo") is None)
    prova("M4 «cosa manca» dice che per lo schermo serve TightVNC (il terminale va lo stesso)",
          any("TightVNC" in x for x in A.cosa_manca()), A.cosa_manca())
    A.ferma_sessione()
    os.environ["ASSISTENZA_VNC"] = AMB["ASSISTENZA_VNC"]

    c = json.loads(CONF.read_text())
    del c["tunnel"]
    CONF.write_text(json.dumps(c))
    prova("M5 senza sezione tunnel lo schermo non c'è (tmate resta solo terminale)", A.schermo_pronto() is False)
    configura()

    prova("M6 DES del VNC giusto (vettore noto: «Secure!» = d7a514d8c556aade)",
          A.vnc_password_cifrata("Secure!").hex() == "d7a514d8c556aade")
    pw2 = A.password_schermo()
    prova("M7 password di sessione: 8 caratteri, ogni volta diversa", len(pw2) == 8 and pw2 != A.password_schermo()
          and re.fullmatch(r"[A-Za-z0-9]{8}", pw2))
    p = subprocess.run(["sh", "-n"], input=A._SCRIPT.encode(), capture_output=True)
    prova("M8 lo script del tunnel (con il comando «chiave») ha sintassi sh corretta", p.returncode == 0, p.stderr)
    righe_ns = ["  TCP    0.0.0.0:5900   0.0.0.0:0   LISTENING   4", "  TCP    127.0.0.1:5900   127.0.0.1:50000   ESTABLISHED   4",
                "  TCP    [::]:5900   [::]:0   LISTENING   4", "  TCP    127.0.0.1:59000   0.0.0.0:0   LISTENING   4"]
    vecchio = A._netstat_righe
    A._netstat_righe = lambda: righe_ns
    asc = A.vnc_ascolti(5900)
    A._netstat_righe = vecchio
    prova("M9 lettura di netstat di Windows: 0.0.0.0 e [::] riconosciuti come «fuori», una connessione stabilita",
          asc == ({"0.0.0.0", "::"}, 1) and not A._solo_locale(asc[0]), asc)
finally:
    try:
        A.ferma_sessione()
    except Exception:  # noqa: BLE001
        pass
    for n in list(A._PROCESSI):
        A._chiudi_popen(A._PROCESSI.pop(n))
    for pid in list(A._PROCESSI_WIN):
        A._ferma_pid(pid)
    subprocess.run(["pkill", "-f", str(TMP)], capture_output=True)
    shutil.rmtree(TMP, ignore_errors=True)

print(f"\n{sum(esiti)}/{len(esiti)} prove passate")
sys.exit(0 if all(esiti) else 1)
