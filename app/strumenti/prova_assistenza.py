#!/usr/bin/env python3
"""Prove dell'assistenza a distanza lato cliente (strumenti/assistenza.py), con un wsl.exe FINTO.

Creato il 2026-10-02. Gira su macOS o Linux (non su Windows: il finto wsl.exe è uno script).
Il finto wsl.exe toglie «-d DISTRO» e «-e» e lancia il resto su questa macchina: così lo script
sh del tunnel gira davvero, come dentro WSL. ssh, sshd, ssh-keygen e tmate sono finti: nessuna
rete, nessun server vero. Tutto in una cartella temporanea che alla fine si cancella.

Cosa controlla:
  A  il tasto «Attiva assistenza»: crea assistenza.json se manca (abilitata, sezione tunnel, niente
     dati di pagamento) e, se c'è già, aggiunge solo quello che manca senza cambiare i valori
  B  tunnel dentro WSL: apertura (chiavi, sshd solo locale, ssh -R con chiave host fissata,
     richiesta jarvis-tunnel), tunnel stabilito, STOP con chiusura verificata dei processi Linux
     (anche i figli di sshd) e della cartella delle chiavi
  C  tetto di 8 ore · D tunnel caduto · E rimborso se il tunnel non si stabilisce in 15 minuti ·
  F  STOP prima del collegamento = rimborso · G Linux che non risponde: chiusura e pulizia dopo
  H  riserva tmate senza sezione tunnel o senza openssh · I pannello senza dati di pagamento
Esce con 1 se una prova fallisce.

Uso:  python3 strumenti/prova_assistenza.py
"""

import base64
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent
PY = sys.executable
TMP = Path(tempfile.mkdtemp(prefix="prova-assistenza-win-"))
for d in ("cc", "bin", "bin-tmate", "linux-casa"):
    (TMP / d).mkdir()
CASA_TUNNEL = TMP / "linux-casa" / ".jarvis-assistenza-cliente"
SESS = CASA_TUNNEL / "sessione"
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
}
os.environ.pop("ASSISTENZA_TMATE", None)
os.environ.pop("ASSISTENZA_PREPARA", None)
os.environ.update(AMB)
# il PATH senza le cartelle dove c'è un tmate vero (sul computer di chi prova può esserci)
SENZA_TMATE = os.pathsep.join(d for d in os.environ.get("PATH", "").split(os.pathsep)
                              if d and not os.access(os.path.join(d, "tmate"), os.X_OK))
CON_TMATE = str(TMP / "bin-tmate") + os.pathsep + SENZA_TMATE


def scrivi_bin(nome, testo, cartella="bin"):
    f = TMP / cartella / nome
    f.write_text(f"#!{PY}\n" + testo)
    os.chmod(f, 0o755)


# ---- finto wsl.exe: «[-d DISTRO] -e PROGRAMMA ARG...» -> lancia PROGRAMMA qui (stdin compreso)
scrivi_bin("wsl.exe", f"""import sys, os, json
a = sys.argv[1:]
open({str(TMP / 'wsl.log')!r}, "a").write(json.dumps(a) + "\\n")
if os.path.exists({str(TMP / 'wsl-rotto')!r}):
    print("Errore: la distribuzione non risponde", file=sys.stderr); sys.exit(1)
if a[:1] == ["-d"]:
    a = a[2:]
if a[:1] != ["-e"]:
    print("finto wsl: manca -e", file=sys.stderr); sys.exit(2)
os.execvp(a[1], a[1:])
""")

# ---- finto ssh-keygen: una chiave ed25519 pubblica ben formata (32 byte a caso)
scrivi_bin("ssh-keygen", """import sys, os, base64
a = sys.argv[1:]
f = a[a.index("-f") + 1]
c = a[a.index("-C") + 1]
pub = b"\\x00\\x00\\x00\\x0bssh-ed25519\\x00\\x00\\x00\\x20" + os.urandom(32)
open(f, "w").write("FINTA CHIAVE PRIVATA\\n")
os.chmod(f, 0o600)
open(f + ".pub", "w").write("ssh-ed25519 " + base64.b64encode(pub).decode() + " " + c + "\\n")
""")

# ---- finto sshd: ascolta sulla porta della configurazione, dice «Server listening» come il vero,
#      e tiene un processo figlio (come la connessione del tecnico) per provare che la chiusura lo ferma
scrivi_bin("sshd", f"""import sys, socket, re, subprocess
a = sys.argv[1:]
cfg = open(a[a.index("-f") + 1]).read()
porta = int(re.search(r"^Port (\\d+)", cfg, re.M).group(1))
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", porta)); s.listen(5)
figlio = subprocess.Popen(["sleep", "1000"])
open({str(TMP / 'figlio-sshd.pid')!r}, "w").write(str(figlio.pid))
print(f"Server listening on 127.0.0.1 port {{porta}}.", file=sys.stderr, flush=True)
while True:
    c, _ = s.accept(); c.sendall(b"SSH-2.0-finto\\r\\n"); c.close()
""")

# ---- finto ssh: con -R fa il tunnel. ssh-modo: ok (autenticato), rifiuta (esce), zitto (vivo senza dirlo)
scrivi_bin("ssh", f"""import sys, os, time, json
a = sys.argv[1:]
open({str(TMP / 'ssh.log')!r}, "a").write(json.dumps(a) + "\\n")
f = {str(TMP / 'ssh-modo')!r}
modo = open(f).read().strip() if os.path.exists(f) else "ok"
if modo == "rifiuta":
    print("assistenza@server: Permission denied (publickey).", file=sys.stderr); sys.exit(255)
if modo == "ok":
    print("Authenticated to server-finto ([192.0.2.1]:22) using \\"publickey\\".", file=sys.stderr, flush=True)
while True:
    time.sleep(1)
""")

# ---- finto tmate (la riserva)
scrivi_bin("tmate", """import sys, os
a = sys.argv[1:]
if "-S" not in a:
    sys.exit(0)
sock = a[a.index("-S") + 1]; vivo = sock + ".vivo"; cmd = a[a.index("-S") + 2]
if cmd == "new-session": open(vivo, "w").close()
elif cmd == "display":
    print("ssh -p22 FINTOrw@lon1.tmate.io" if a[-1] == "#{tmate_ssh}" else "ssh -p22 FINTOro@lon1.tmate.io")
elif cmd == "has-session": sys.exit(0 if os.path.exists(vivo) else 1)
elif cmd == "kill-server" and os.path.exists(vivo): os.remove(vivo)
elif cmd == "wait-for":
    import time
    while os.path.exists(vivo): time.sleep(0.2)
""", cartella="bin-tmate")

sys.path.insert(0, str(QUI))
import assistenza as A  # noqa: E402

# ---- firma Ed25519 di prova (il modulo del cliente sa solo verificare)
def _comprimi(P):
    zi = A._inv(P[2])
    x, y = P[0] * zi % A._P, P[1] * zi % A._P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _espandi(segreto):
    import hashlib
    h = hashlib.sha512(segreto).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


SEGRETO = os.urandom(32)
_a, _pre = _espandi(SEGRETO)
PUBBLICA = _comprimi(A._moltiplica(_a, A._G))
Path(AMB["ASSISTENZA_CHIAVE_PUBBLICA"]).write_text("# chiave di prova\n" + PUBBLICA.hex() + "\n")


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


def vivo(pid):
    """Vivo davvero: esiste e non è uno zombie (un figlio morto che nessuno ha ancora raccolto)."""
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    stato = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(stato) and not stato.startswith("Z")


def pid_sessione():
    return {n: (SESS / f"{n}.pid").read_text().strip() for n in ("sshd", "ssh") if (SESS / f"{n}.pid").exists()}


def azzera_cache():
    A._cache_tmate.update(ts=0.0)
    A._cache_ssh.update(ts=0.0)


def aspetta(cond, secondi=5.0):
    fine = time.time() + secondi
    while time.time() < fine:
        if cond():
            return True
        time.sleep(0.1)
    return cond()


def autenticato():
    """Il finto ssh ha scritto «Authenticated to» nel suo registro (come il vero dopo l'accesso)."""
    f = SESS / "ssh.log"
    return aspetta(lambda: f.exists() and "Authenticated to" in f.read_text(errors="replace"))


def reg():
    return json.loads((TMP / "cc" / "assistenza-registro.json").read_text())


CONF = TMP / "cc" / "assistenza.json"
TUNNEL_MODELLO = {k: v for k, v in json.loads((QUI.parent / "command-center" / "assistenza-tunnel.json").read_text(encoding="utf-8")).items()
                  if not k.startswith("_")}
# 2026-10-10: nella distribuzione neutra il modello pubblico è vuoto (nessun tecnico): la prova usa un tecnico FINTO
# con un indirizzo di documentazione (RFC 5737) e chiavi inventate, scritto nella cartella di prova dell'assistenza.
if not TUNNEL_MODELLO.get("host"):
    import base64 as _b64
    def _chiave_finta(seme):
        corpo = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + bytes((seme + i) % 256 for i in range(32))
        return "ssh-ed25519 " + _b64.b64encode(corpo).decode()
    TUNNEL_MODELLO = {"host": "192.0.2.10", "porta": 22, "utente": "assistenza",
                      "known_hosts": "192.0.2.10 " + _chiave_finta(1), "chiave_tecnico": _chiave_finta(2), "porte": [47000, 47999]}
    (Path(os.environ["ASSISTENZA_DIR"]) / "assistenza-tunnel.json").write_text(json.dumps(TUNNEL_MODELLO), encoding="utf-8")
RICHIESTA = re.compile(r"jarvis-tunnel:1:(\d{4,5}):([A-Za-z0-9_][A-Za-z0-9._-]{0,31}):([A-Za-z0-9+/]{68}):([A-Za-z0-9+/]{68})")
estranei = []

try:
    # ================================================================ A  il tasto «Attiva assistenza»
    print("\nA  Attiva assistenza")
    prova("A1 prima del tasto l'assistenza è spenta", A.config()["abilitata"] is False)
    e = A.attiva()
    c = json.loads(CONF.read_text(encoding="utf-8"))
    prova("A2 assistenza.json creato, abilitata true", e["creato"] and c.get("abilitata") is True, e)
    prova("A3 sezione tunnel uguale al modello pubblico", c.get("tunnel") == TUNNEL_MODELLO, c.get("tunnel"))
    prova("A4 niente dati del tecnico o del pagamento, niente «DA COMPILARE»",
          "tecnico" not in c and "pagamento" not in c and "DA COMPILARE" not in CONF.read_text(encoding="utf-8"))
    prova("A5 il tunnel risulta configurato", A._tunnel_valori() is not None and e["tunnel"])
    # file del cliente già presente: non si toccano i suoi valori
    mio = {"abilitata": False, "tariffa_ora_euro": 70, "wsl_distro": "Debian",
           "tunnel": {"host": "assistenza.esempio.it", "porta": 2222},
           "pagamento": {"intestatario": "Mario Rossi", "iban": "IT00X0000000000000000000000"}}
    CONF.write_text(json.dumps(mio), encoding="utf-8")
    e = A.attiva()
    c = json.loads(CONF.read_text(encoding="utf-8"))
    prova("A6 file esistente: tariffa, distro, host, porta e pagamento del cliente restano",
          c["tariffa_ora_euro"] == 70 and c["wsl_distro"] == "Debian" and c["tunnel"]["host"] == "assistenza.esempio.it"
          and c["tunnel"]["porta"] == 2222 and c["pagamento"] == mio["pagamento"], c)
    prova("A7 file esistente: aggiunte solo le chiavi mancanti del tunnel e delle condizioni",
          all(c["tunnel"][k] == TUNNEL_MODELLO[k] for k in ("utente", "known_hosts", "chiave_tecnico", "porte"))
          and "tunnel.host" not in e["aggiunti"] and "scatto_minuti" in c and not e["creato"], e)
    prova("A8 il tasto accende «abilitata»", c["abilitata"] is True and "abilitata" in e["aggiunti"])
    e2 = A.attiva()
    prova("A9 premuto di nuovo: niente da aggiungere", e2["aggiunti"] == [], e2)
    e3 = A.attiva(distro="Ubuntu-24.04")
    prova("A9b la distro preparata non sostituisce quella scelta dal cliente",
          e3["aggiunti"] == [] and json.loads(CONF.read_text(encoding="utf-8"))["wsl_distro"] == "Debian", e3)
    CONF.write_text("{ rotto", encoding="utf-8")
    try:
        A.attiva()
        prova("A10 assistenza.json rotto: errore e file lasciato com'è", False, "non ha rifiutato")
    except A.ErroreAssistenza as x:
        prova("A10 assistenza.json rotto: errore e file lasciato com'è", CONF.read_text(encoding="utf-8") == "{ rotto", x)
    CONF.unlink()
    e = A.attiva(distro="Ubuntu")
    prova("A10b file nuovo: si segna la distro preparata", json.loads(CONF.read_text(encoding="utf-8")).get("wsl_distro") == "Ubuntu", e)
    scrivi_bin("prepara-finto", f"""import sys
open({str(TMP / 'prepara.log')!r}, "w").write(" ".join(sys.argv[1:]))
""")
    os.environ["ASSISTENZA_PREPARA"] = str(TMP / "bin" / "prepara-finto")
    lanciato = A.prepara_windows()
    prova("A11 il tasto apre la preparazione (ASSISTENZA.ps1 -SoloPrepara)",
          lanciato and aspetta(lambda: (TMP / "prepara.log").exists()) and (TMP / "prepara.log").read_text() == "-SoloPrepara")
    del os.environ["ASSISTENZA_PREPARA"]

    # ================================================================ B  tunnel dentro WSL
    print("\nB  Tunnel dentro WSL")
    os.environ["PATH"] = SENZA_TMATE
    azzera_cache()
    prova("B1 openssh c'è (via wsl.exe) e il tunnel è configurato", A.tunnel_conf() is not None)
    prova("B2 non manca niente", A.cosa_manca() == [], A.cosa_manca())
    s = A.stato()
    prova("B3 stato: collegamento «tunnel» anche senza tmate", s["collegamento"] == "tunnel" and s["tmate"] is True, s["collegamento"])
    A.accredita(codice(240))
    (TMP / "wsl.log").write_text("")
    T0 = time.time()
    s = A.avvia_sessione(True, adesso=T0)
    a = s["attiva"] or {}
    m = RICHIESTA.fullmatch(a.get("richiesta") or "")
    prova("B4 sessione aperta in modo tunnel, scalato SOLO il primo blocco da 15 (credito 225)", a.get("modo") == "tunnel" and s["credito_min"] == 225, s["credito_min"])
    prova("B5 la richiesta ha la forma che il tecnico accetta", bool(m), a.get("richiesta"))
    porta = int(m.group(1)) if m else 0
    prova("B6 porta dentro la fascia del modello", TUNNEL_MODELLO["porte"][0] <= porta <= TUNNEL_MODELLO["porte"][1], porta)
    prova("B7 utente = utente Linux che fa girare sshd", m and m.group(2) == subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip())
    righe = [json.loads(x) for x in (TMP / "wsl.log").read_text().splitlines() if x.strip()]
    prova("B8 ogni comando passa da wsl.exe -d Ubuntu -e sh -s (script su stdin, niente percorsi Windows)",
          righe and all(r[:5] == ["-d", "Ubuntu", "-e", "sh", "-s"] for r in righe), righe[:2])
    cfg = (SESS / "sshd_config").read_text()
    prova("B9 sshd solo su 127.0.0.1, niente password, niente inoltri",
          "ListenAddress 127.0.0.1" in cfg and "PasswordAuthentication no" in cfg and "AllowTcpForwarding no" in cfg
          and "GatewayPorts no" in cfg)
    prova("B10 sshd accetta solo la chiave del tecnico, con restrict,pty",
          (SESS / "tecnico").read_text().strip() == f"restrict,pty {TUNNEL_MODELLO['chiave_tecnico']} tecnico")
    prova("B11 cartella delle chiavi con permessi 700", (SESS.stat().st_mode & 0o777) == 0o700)
    aspetta(lambda: (TMP / "ssh.log").exists() and "ssh" in pid_sessione())
    ssh = json.loads((TMP / "ssh.log").read_text().splitlines()[-1])
    prova("B12 ssh -R 127.0.0.1:PORTA verso l'utente del server, chiave host fissata",
          f"127.0.0.1:{porta}:127.0.0.1:" in " ".join(ssh) and "StrictHostKeyChecking=yes" in ssh
          and ssh[-1] == f"{TUNNEL_MODELLO['utente']}@{TUNNEL_MODELLO['host']}" and "BatchMode=yes" in ssh, ssh)
    prova("B13 known_hosts della sessione = quello del modello",
          (SESS / "known_hosts").read_text().strip() == TUNNEL_MODELLO["known_hosts"])
    pids = pid_sessione()
    figlio = (TMP / "figlio-sshd.pid").read_text().strip()
    prova("B14 sshd, ssh e il figlio di sshd sono vivi", len(pids) == 2 and all(vivo(p) for p in pids.values()) and vivo(figlio), pids)
    # un processo estraneo con un pid nel file della sessione non va toccato
    estraneo = subprocess.Popen(["sleep", "1000"])
    estranei.append(estraneo)
    autenticato()
    A.tick(adesso=T0 + 20)
    s = A.stato(adesso=T0 + 20)
    prova("B15 tunnel stabilito (ssh dice «Authenticated to»)", s["attiva"] and s["attiva"]["collegato"] is True)
    s = A.ferma_sessione(adesso=T0 + 600)
    prova("B16 STOP: processi Linux fermati, figlio di sshd compreso",
          aspetta(lambda: not any(vivo(p) for p in list(pids.values()) + [figlio])), pids)
    prova("B17 STOP: cartella delle chiavi cancellata", not SESS.exists())
    prova("B18 STOP: nessun wsl.exe del tunnel rimasto aperto", not A._PROCESSI)
    prova("B19 STOP dopo il collegamento: niente rimborso", s["credito_min"] == 225 and s["sessioni"][0]["rimborsati"] == 0, s["credito_min"])
    prova("B20 il processo estraneo è ancora vivo", estraneo.poll() is None)
    # pid riciclato: nel file c'è il pid di un processo estraneo -> la chiusura non lo tocca
    SESS.mkdir(parents=True)
    (SESS / "sshd.pid").write_text(str(estraneo.pid))
    fermo = A._tunnel_ferma_processi()
    prova("B21 pid riciclato nel file: il processo estraneo non si tocca", fermo and estraneo.poll() is None)

    # ================================================================ C  tetto di 8 ore
    print("\nC  Tetto di 8 ore")
    T0 = time.time()
    A.avvia_sessione(True, adesso=T0)
    pids = pid_sessione()
    autenticato()
    A.tick(adesso=T0 + 20)
    # a 8 ore (con credito finto abbondante per non chiudere prima per i soldi)
    with A._registro() as r:
        r["attiva"]["pagato_fino"] = T0 + 9 * 3600
    fatto = A.tick(adesso=T0 + 8 * 3600)
    s = A.stato()
    prova("C1 a 8 ore la sessione si chiude", s["attiva"] is None and "8 ore" in (fatto or ""), fatto)
    prova("C2 processi fermati e chiavi cancellate", aspetta(lambda: not any(vivo(p) for p in pids.values())) and not SESS.exists())

    # ================================================================ D  tunnel caduto
    print("\nD  Tunnel caduto")
    A.accredita(codice(120))
    T0 = time.time()
    s = A.avvia_sessione(True, adesso=T0)
    credito = s["credito_min"]
    autenticato()
    A.tick(adesso=T0 + 20)
    pids = pid_sessione()
    os.kill(int(pids["ssh"]), signal.SIGKILL)
    aspetta(lambda: not vivo(pids["ssh"]))
    fatto = A.tick(adesso=T0 + 40)
    s = A.stato()
    prova("D1 tunnel caduto dopo il collegamento: sessione chiusa", s["attiva"] is None and "caduto" in (fatto or ""), fatto)
    prova("D2 niente rimborso (il servizio era partito)", s["credito_min"] == credito, s["credito_min"])
    prova("D3 anche sshd fermato", aspetta(lambda: not vivo(pids["sshd"])))

    # ================================================================ E  rimborso dopo 15 minuti
    print("\nE  Tunnel che non si stabilisce")
    (TMP / "ssh-modo").write_text("rifiuta")
    T0 = time.time()
    s = A.avvia_sessione(True, adesso=T0)
    credito = s["credito_min"]
    aspetta(lambda: "ssh" in pid_sessione() and not vivo(pid_sessione()["ssh"]))
    autenticato()
    A.tick(adesso=T0 + 20)
    s = A.stato(adesso=T0 + 20)
    prova("E1 ssh rifiutato: la sessione resta aperta e si riprova", s["attiva"] is not None
          and reg()["attiva"]["tunnel"]["tentativi"] == 2 and not s["attiva"]["collegato"])
    time.sleep(0.5)
    A.tick(adesso=T0 + 840)
    prova("E1b tunnel non ancora stabilito: a 14 minuti nessun secondo blocco", reg()["attiva"] is not None
          and len(reg()["attiva"]["blocchi"]) == 1 and reg()["credito_min"] == credito, reg()["credito_min"])
    pids = pid_sessione()
    time.sleep(0.5)
    fatto = A.tick(adesso=T0 + 15 * 60 + 5)
    s = A.stato()
    prova("E2 dopo 15 minuti senza tunnel: sessione chiusa", s["attiva"] is None and "15 minuti" in (fatto or ""), fatto)
    prova("E3 il primo blocco (15 minuti) torna a credito", s["credito_min"] == credito + 15 and s["sessioni"][0]["rimborsati"] == 15, s["credito_min"])
    prova("E4 processi fermati", aspetta(lambda: not any(vivo(p) for p in pids.values())) and not SESS.exists())

    # ================================================================ F  STOP prima del collegamento
    print("\nF  STOP prima del collegamento")
    (TMP / "ssh-modo").write_text("zitto")
    T0 = time.time()
    s = A.avvia_sessione(True, adesso=T0)
    credito = s["credito_min"]
    A.tick(adesso=T0 + 5)
    s = A.ferma_sessione(adesso=T0 + 10)
    prova("F1 STOP prima che il tunnel si stabilisca: 15 minuti a credito", s["credito_min"] == credito + 15, s["credito_min"])
    prova("F2 cartella delle chiavi cancellata", not SESS.exists())
    (TMP / "ssh-modo").write_text("ok")

    # ================================================================ G  Linux che non risponde
    print("\nG  Linux (WSL) che non risponde")
    T0 = time.time()
    A.avvia_sessione(True, adesso=T0)
    autenticato()
    A.tick(adesso=T0 + 20)
    pids = pid_sessione()
    (TMP / "wsl-rotto").write_text("")
    fatto = A.tick(adesso=T0 + 40)
    s = A.stato()
    prova("G1 WSL non risponde: la sessione si chiude", s["attiva"] is None and "non risponde" in (fatto or ""), fatto)
    prova("G2 la chiusura non verificata resta segnata nel registro", reg().get("tunnel_resti") is True)
    (TMP / "wsl-rotto").unlink()
    for p in A._PROCESSI.values():
        pass
    A.ferma_sessione()
    prova("G3 al primo STOP dopo, i processi rimasti si fermano davvero",
          aspetta(lambda: not any(vivo(p) for p in pids.values())) and not reg().get("tunnel_resti") and not SESS.exists(), pids)

    # ================================================================ H  riserva tmate
    print("\nH  Riserva tmate")
    os.environ["PATH"] = CON_TMATE
    os.environ["ASSISTENZA_SSHD"] = str(TMP / "bin" / "sshd-che-non-c-e")
    azzera_cache()
    prova("H1 senza sshd in Linux il tunnel non è pronto", A.tunnel_conf() is None)
    prova("H2 «cosa manca» lo dice in parole semplici", any("openssh" in x for x in A.cosa_manca()), A.cosa_manca())
    s = A.stato()
    prova("H3 si usa tmate come riserva", s["collegamento"] == "tmate" and s["tmate"], s["collegamento"])
    s = A.avvia_sessione(True)
    prova("H4 sessione tmate aperta con la riga ssh", s["attiva"]["modo"] == "tmate" and s["attiva"]["ssh"].startswith("ssh "), s["attiva"])
    s = A.ferma_sessione()
    prova("H5 STOP della sessione tmate", s["attiva"] is None)
    os.environ["ASSISTENZA_SSHD"] = AMB["ASSISTENZA_SSHD"]
    c = json.loads(CONF.read_text(encoding="utf-8"))
    del c["tunnel"]
    CONF.write_text(json.dumps(c), encoding="utf-8")
    azzera_cache()
    s = A.stato()
    prova("H6 senza sezione tunnel: tmate", s["collegamento"] == "tmate", s["collegamento"])
    os.environ["PATH"] = SENZA_TMATE
    azzera_cache()
    manca = A.cosa_manca()
    prova("H7 senza tunnel e senza tmate: manca la sezione tunnel e tmate", len(manca) == 2 and A.stato()["tmate"] is False, manca)
    A.attiva()
    azzera_cache()
    prova("H8 premendo di nuovo il tasto torna la sezione tunnel", A.cosa_manca() == [], A.cosa_manca())

    # ================================================================ I  niente dati di pagamento
    print("\nI  Pannello senza dati di pagamento")
    s = A.stato()
    testo = json.dumps(s, ensure_ascii=False)
    prova("I1 stato: pagamento non pronto, nessun «DA COMPILARE», nessun IBAN",
          s["pagamento_pronto"] is False and "DA COMPILARE" not in testo and "iban" not in testo.lower())
    try:
        A.crea_ordine(1)
        prova("I2 ordine rifiutato senza dati di pagamento", False, "non ha rifiutato")
    except A.ErroreAssistenza:
        prova("I2 ordine rifiutato senza dati di pagamento", True)
    p = subprocess.run(["sh", "-n"], input=A._SCRIPT.encode(), capture_output=True)  # noqa: E501
    prova("I3 lo script del tunnel ha sintassi sh corretta", p.returncode == 0, p.stderr)
    prova("I4 lo script non ha ritorni a capo di Windows", b"\r" not in A._SCRIPT.encode())

    # ================================================================ J  blocchi da 15 (regola del 2026-10-02)
    print("\nJ  Conteggio a blocchi da 15")
    c = json.loads(CONF.read_text(encoding="utf-8"))
    c.update(primo_blocco_minuti=60, ricarica_minima_minuti=60, ricarica_minima_euro=50)   # json di un cliente, scritto prima
    CONF.write_text(json.dumps(c), encoding="utf-8")
    k = A.config()
    prova("J1 assistenza.json vecchio con 60: vale la regola dei 15 (primo blocco, ricarica minima 15 = 12,50 €)",
          k["primo_blocco_minuti"] == 15 and k["ricarica_minima_minuti"] == 15 and k["ricarica_minima_euro"] == 12.5, k)
    (TMP / "cc" / "assistenza-registro.json").unlink()
    s = A.accredita(codice(15))
    prova("J2 primo codice da 15 minuti accettato: 12,50 €", s["credito_min"] == 15 and s["credito_euro"] == 12.5, s["credito_min"])
    A.accredita(codice(15))
    T0 = time.time()
    s = A.avvia_sessione(True, adesso=T0)
    prova("J3 avvio: scalati solo 15 minuti, pagato fino a 15 minuti", s["credito_min"] == 15
          and reg()["attiva"]["pagato_fino"] == T0 + 900, s["credito_min"])
    autenticato()
    A.tick(adesso=T0 + 20)
    prova("J4 a 10 minuti non si scala niente", A.tick(adesso=T0 + 600) is None and reg()["credito_min"] == 15)
    A.tick(adesso=T0 + 840)
    prova("J5 a 14 minuti scalato il secondo blocco (credito 0, pagato fino a 30 minuti)",
          reg()["credito_min"] == 0 and reg()["attiva"]["pagato_fino"] == T0 + 1800)
    fatto = A.tick(adesso=T0 + 1740)
    prova("J6 credito finito: avviso, la sessione resta aperta fino a fine blocco",
          "credito finito" in (fatto or "") and reg()["attiva"]["ultimo_blocco"], fatto)
    pids = pid_sessione()
    fatto = A.tick(adesso=T0 + 1801)
    ult = reg()["sessioni"][-1]
    prova("J7 a fine blocco la sessione si chiude: 30 minuti pagati in 2 blocchi, processi fermati",
          reg()["attiva"] is None and ult["minuti_pagati"] == 30 and ult["blocchi"] == 2
          and aspetta(lambda: not any(vivo(p) for p in pids.values())), ult)
finally:
    try:
        A.ferma_sessione()
    except Exception:  # noqa: BLE001
        pass
    for n in list(A._PROCESSI):
        A._chiudi_popen(A._PROCESSI.pop(n))
    for e in estranei:
        e.kill()
    f = TMP / "figlio-sshd.pid"
    if f.exists() and vivo(f.read_text().strip()):
        os.kill(int(f.read_text().strip()), signal.SIGKILL)
    shutil.rmtree(TMP, ignore_errors=True)

print(f"\n{sum(esiti)}/{len(esiti)} prove passate")
sys.exit(0 if all(esiti) else 1)
