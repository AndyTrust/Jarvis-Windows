#!/usr/bin/env python3
"""Assistenza a distanza a pagamento, lato CLIENTE: un tecnico si collega al terminale di questo PC.

Modulo SPENTO di default («abilitata»: false). Si accende con «abilitata»: true in
command-center/assistenza.json (file personale, fuori da git: vedi docs/ASSISTENZA.md).

Come funziona:
- Il tecnico genera sul suo computer un codice monouso firmato e lo manda al cliente. Il codice
  porta i minuti pagati (multipli di 15), una scadenza e un id casuale. La firma è Ed25519
  (RFC 8032); qui c'è solo la VERIFICA, in Python puro, senza librerie esterne. Questo PC non
  può creare codici: la chiave privata sta solo dal tecnico.
- Il cliente incolla il codice nel pannello: si controllano firma, scadenza e che l'id non sia
  già nel registro; poi i minuti vanno a credito e l'id si brucia.
- Il cliente spunta il consenso e chiede assistenza. Due modi di collegamento, tutti e due con un
  collegamento in USCITA (nessuna porta aperta verso l'esterno sul PC):
  1) TUNNEL verso il server del tecnico (2026-10-02), se in assistenza.json c'è la sezione «tunnel»
     e dentro WSL ci sono ssh, sshd e ssh-keygen (pacchetti openssh-client e openssh-server).
     Tutto gira DENTRO WSL, lanciato con wsl.exe: uno script sh (_SCRIPT, passato su stdin, così
     non servono percorsi Windows/WSL né virgolette) crea per la sessione una chiave del cliente e
     una chiave host (ssh-keygen ed25519) in ~/.jarvis-assistenza-cliente/sessione (casa Linux,
     700), avvia un sshd SOLO su 127.0.0.1 che accetta solo la chiave pubblica del tecnico
     (restrict,pty), e apre ssh -R verso l'utente del server con la chiave host del server fissata
     (StrictHostKeyChecking=yes). Il pannello mostra la RICHIESTA da mandare al tecnico:
     jarvis-tunnel:1:PORTA:UTENTE:HOSTKEY:CHIAVE.
     I processi dentro WSL non muoiono con Windows: la chiusura è esplicita (pid scritti nella
     cartella della sessione, TERM ai processi e ai loro figli, poi KILL) e verificata.
     Chiusura per STOP, credito finito, tetto di 8 ore, tunnel caduto. Se il tunnel non si
     stabilisce entro 15 minuti (o il cliente ferma prima), i minuti tornano a credito.
  2) tmate (programma open source, licenza ISC), di riserva se il tunnel non è configurato o
     openssh manca: terminale condiviso verso tmate.io; il pannello mostra la stringa ssh.
  3) SCHERMO condiviso (2026-10-02 sera), insieme al tunnel, se c'è TightVNC: il tecnico vede e usa lo
     schermo vero. TightVNC in modo applicazione solo su 127.0.0.1 con una password di sessione, tunnel
     con l'ssh.exe di Windows, richiesta jarvis-tunnel:2 con la password cifrata per il tecnico. Un solo
     consenso, un solo STOP. Dettagli nel blocco «lo schermo sul PC del cliente» più sotto.
  Su Windows tutti e due girano dentro WSL. Per prepararlo c'è un tasto solo nel pannello,
  «Attiva assistenza» (attiva() qui sotto + strumenti/ASSISTENZA.ps1 -SoloPrepara).
- Conteggio (regola del 2026-10-02): 50 € all'ora = 12,50 € ogni 15 minuti, sempre anticipati.
  All'avvio si scala SOLO il primo blocco da 15 minuti. Poi, 60 secondi prima che il blocco
  finisca, se c'è credito si scala il blocco dopo; se non c'è, la sessione si chiude alla fine
  del blocco già pagato. Ricarica minima 15 minuti. Primo blocco, ricarica minima e scatto sono
  FISSI nel codice (REGOLA_BLOCCHI): un assistenza.json vecchio con 60 scritto dentro non conta più.
  Tunnel: finché il tunnel non si è stabilito non si scalano altri blocchi; se non si stabilisce
  in 15 minuti la sessione si chiude e il primo blocco (15 minuti) torna a credito.
- STOP in ogni momento. I minuti del blocco in corso non si restituiscono.

Tutto lo stato sta in un file JSON (assistenza-registro.json, fuori da git) accanto a
assistenza.json, nella cartella command-center/ oppure in ASSISTENZA_DIR (prove).

Variabili d'ambiente (servono alle prove):
  ASSISTENZA_DIR              cartella di assistenza.json e del registro
  ASSISTENZA_TMATE            percorso di un tmate da lanciare DIRETTAMENTE (un finto tmate nelle
                              prove); se c'è, WSL non si usa
  ASSISTENZA_MODO             «wsl» o «nativo» (default: wsl su Windows, nativo altrove)
  ASSISTENZA_WSL              percorso di wsl.exe (default: quello di Windows; un finto nelle prove)
  ASSISTENZA_WSL_DISTRO       distribuzione WSL da usare (default: quella predefinita; anche
                              «wsl_distro» in assistenza.json)
  ASSISTENZA_CHIAVE_PUBBLICA  file della chiave pubblica (default: <cartella>/assistenza-chiave-pubblica.txt)
  ASSISTENZA_SOCKET           socket di tmate (default: dentro WSL /tmp/jarvis-assistenza.sock;
                              fuori da WSL nella cartella temporanea del sistema)
  ASSISTENZA_SSH, ASSISTENZA_SSHD, ASSISTENZA_SSH_KEYGEN, ASSISTENZA_TMUX
                              i programmi del tunnel, come li vede Linux (finti nelle prove)
  ASSISTENZA_TUNNEL_DIR       cartella delle chiavi del tunnel, percorso Linux
                              (default ~/.jarvis-assistenza-cliente dentro WSL)
  ASSISTENZA_PREPARA          fuori da Windows: programma da lanciare al posto di ASSISTENZA.ps1 (prove)
  ASSISTENZA_VNC, ASSISTENZA_SSH_WIN, ASSISTENZA_NETSTAT, ASSISTENZA_SCHERMO_DIR
                              TightVNC, ssh.exe di Windows, netstat e cartella dello schermo (finti nelle prove)

Uso da riga di comando:
  python strumenti/assistenza.py attiva        crea o completa assistenza.json e accende l'assistenza
  python strumenti/assistenza.py manca         cosa manca per collegarsi (una riga per voce)
  python strumenti/assistenza.py stato
  python strumenti/assistenza.py codice CODICE
  python strumenti/assistenza.py avvia --consenso
  python strumenti/assistenza.py stop
  python strumenti/assistenza.py tick
"""

import base64
import contextlib
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl

QUI = Path(__file__).resolve().parent
CARTELLA_CC = QUI.parent / "command-center"
VERSIONE_CODICE = 1
SU_WINDOWS = os.name == "nt"
# Windows: i programmi a riga di comando lanciati dal pannello (senza console) non aprono finestre
_SENZA_FINESTRE = 0x08000000 if SU_WINDOWS else 0


class ErroreAssistenza(ValueError):
    """Errore da mostrare così com'è al cliente (italiano semplice)."""


# =====================================================================
# Ed25519, solo verifica (RFC 8032, sezione 6: implementazione di riferimento in Python)
# =====================================================================

_P = 2 ** 255 - 19
_Q = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(x):
    return pow(x, _P - 2, _P)


_D = -121665 * _inv(121666) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _sha512_modq(b):
    return int.from_bytes(hashlib.sha512(b).digest(), "little") % _Q


def _somma(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _P
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _P
    C = 2 * P[3] * Q[3] * _D % _P
    D = 2 * P[2] * Q[2] % _P
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _P, G * H % _P, F * G % _P, E * H % _P)


def _moltiplica(s, P):
    R = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            R = _somma(R, P)
        P = _somma(P, P)
        s >>= 1
    return R


def _uguali(P, Q):
    return (P[0] * Q[2] - Q[0] * P[2]) % _P == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _P == 0


def _recupera_x(y, segno):
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1) % _P
    if x2 == 0:
        return None if segno else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != segno:
        x = _P - x
    return x


_GY = 4 * _inv(5) % _P
_GX = _recupera_x(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _decomprimi(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    segno = y >> 255
    y &= (1 << 255) - 1
    x = _recupera_x(y, segno)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def ed25519_verifica(pubblica, messaggio, firma):
    if len(pubblica) != 32 or len(firma) != 64:
        return False
    A = _decomprimi(pubblica)
    if A is None:
        return False
    Rs = firma[:32]
    R = _decomprimi(Rs)
    if R is None:
        return False
    s = int.from_bytes(firma[32:], "little")
    if s >= _Q:
        return False
    h = _sha512_modq(Rs + pubblica + messaggio)
    return _uguali(_moltiplica(s, _G), _somma(R, _moltiplica(h, A)))


def pubblica_da_testo(testo):
    for riga in testo.splitlines():
        riga = riga.strip()
        if riga and not riga.startswith("#"):
            if not re.fullmatch(r"[0-9a-fA-F]{64}", riga):
                raise ErroreAssistenza("la chiave pubblica non è valida (servono 64 cifre esadecimali)")
            return bytes.fromhex(riga)
    raise ErroreAssistenza("la chiave pubblica è vuota: chiedi al tecnico il file giusto")


# =====================================================================
# Il codice monouso (solo lettura e verifica: qui non se ne creano)
# =====================================================================

def _b32_decodifica(codice):
    # chi lo detta confonde 0/O, 1/I, 8/B: il base32 usa solo A-Z e 2-7, si corregge da soli
    t = re.sub(r"[\s\-]", "", str(codice or "")).upper().translate(str.maketrans("018", "OIB"))
    if not t or not re.fullmatch(r"[A-Z2-7]+", t):
        raise ErroreAssistenza("il codice contiene caratteri non validi: copialo di nuovo così come te l'ha mandato il tecnico")
    t += "=" * (-len(t) % 8)
    try:
        return base64.b32decode(t)
    except Exception as e:  # noqa: BLE001
        raise ErroreAssistenza("il codice è incompleto: copialo di nuovo per intero") from e


def leggi_chiave_pubblica():
    f = Path(os.environ.get("ASSISTENZA_CHIAVE_PUBBLICA") or (cartella() / "assistenza-chiave-pubblica.txt"))
    if not f.exists():
        f = CARTELLA_CC / "assistenza-chiave-pubblica.txt"
    if not f.exists():
        raise ErroreAssistenza("manca la chiave pubblica del tecnico (assistenza-chiave-pubblica.txt)")
    return pubblica_da_testo(f.read_text(encoding="utf-8"))


def verifica_codice(codice, pubblica=None, adesso=None):
    """Controlla firma, formato e scadenza. Non guarda il registro: lo fa accredita()."""
    pubblica = leggi_chiave_pubblica() if pubblica is None else pubblica
    adesso = time.time() if adesso is None else adesso
    grezzo = _b32_decodifica(codice)
    if len(grezzo) <= 64:
        raise ErroreAssistenza("il codice è troppo corto: copialo di nuovo per intero")
    corpo, firma = grezzo[:-64], grezzo[-64:]
    if not ed25519_verifica(pubblica, corpo, firma):
        raise ErroreAssistenza("codice non valido: la firma del tecnico non torna. Controlla di averlo copiato bene")
    try:
        dati = json.loads(corpo)
    except ValueError as e:
        raise ErroreAssistenza("codice non leggibile") from e
    if not isinstance(dati, dict) or dati.get("v") != VERSIONE_CODICE:
        raise ErroreAssistenza("codice di una versione che questo pannello non conosce: aggiorna Jarvis")
    m = dati.get("min")
    if not isinstance(m, int) or isinstance(m, bool) or m <= 0 or m % 15:
        raise ErroreAssistenza("codice non valido: i minuti non sono un multiplo di 15")
    if not isinstance(dati.get("id"), str) or not re.fullmatch(r"[0-9a-f]{24}", dati["id"]):
        raise ErroreAssistenza("codice non valido: manca l'identificativo")
    if not isinstance(dati.get("scade"), int) or dati["scade"] <= adesso:
        raise ErroreAssistenza("codice scaduto: chiedi al tecnico un codice nuovo")
    return dati


# =====================================================================
# Configurazione e registro
# =====================================================================

# I dati veri del tecnico (nome, contatti, pagamento) stanno SOLO in assistenza.json sul PC.
CONFIG_DEFAULT = {
    "abilitata": False,
    "tariffa_ora_euro": 50,
    "ricarica_minima_euro": 12.5,
    "ricarica_minima_minuti": 15,
    "scatto_minuti": 15,
    "scatto_euro": 12.5,
    "primo_blocco_minuti": 15,
    "anticipo_scatto_secondi": 60,
    "scadenza_codice_ore": 48,
    "wsl_distro": "",
    "schermo": True,
    "ore_max": 8,
    "tunnel": None,
    "tecnico": {"nome": "DA COMPILARE", "email": "DA COMPILARE", "telefono": "DA COMPILARE", "whatsapp": "DA COMPILARE"},
    "pagamento": {"metodo": "Bonifico", "intestatario": "DA COMPILARE", "iban": "DA COMPILARE", "bic": "DA COMPILARE", "banca": "DA COMPILARE",
                  "bic_banca_corrispondente": "", "valuta": "EUR", "causale": "assistenza a distanza"},
}


# Regola di conteggio del 2026-10-02, fissa: vale anche se assistenza.json (di un cliente, scritto
# prima) porta ancora i valori vecchi (primo blocco e ricarica minima di 60 minuti).
REGOLA_BLOCCHI = {"primo_blocco_minuti": 15, "ricarica_minima_minuti": 15, "ricarica_minima_euro": 12.5,
                  "scatto_minuti": 15, "scatto_euro": 12.5}


def cartella():
    return Path(os.environ.get("ASSISTENZA_DIR") or CARTELLA_CC)


def config():
    """assistenza.json, oppure l'esempio (che è spento). Un file rotto = spento."""
    for nome in ("assistenza.json", "assistenza.esempio.json"):
        f = cartella() / nome
        if f.exists():
            try:
                letto = json.loads(f.read_text(encoding="utf-8-sig"))   # -sig: il Blocco note di Windows mette il BOM
            except (ValueError, OSError):
                return {**CONFIG_DEFAULT, "abilitata": False, "errore_config": f"{nome} non è JSON valido"}
            if not isinstance(letto, dict):
                return {**CONFIG_DEFAULT, "abilitata": False, "errore_config": f"{nome} non è un oggetto JSON"}
            c = {**CONFIG_DEFAULT, **letto}
            c["abilitata"] = letto.get("abilitata") is True
            c.update(REGOLA_BLOCCHI)        # 2026-10-02: la regola dei blocchi da 15 vince sul file
            return c
    return dict(CONFIG_DEFAULT)


def _f_registro():
    return cartella() / "assistenza-registro.json"


def _registro_vuoto():
    return {"credito_min": 0, "codici": [], "sessioni": [], "attiva": None, "log": []}


def _leggi_registro():
    f = _f_registro()
    try:
        r = json.loads(f.read_text(encoding="utf-8"))
        return {**_registro_vuoto(), **r} if isinstance(r, dict) else _registro_vuoto()
    except (OSError, ValueError):
        return _registro_vuoto()


def _blocca(chiave):
    """Chiave esclusiva fra processi: fcntl su macOS/Linux, msvcrt su Windows (sul primo byte)."""
    if SU_WINDOWS:
        while True:
            try:
                chiave.seek(0)
                msvcrt.locking(chiave.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.05)
    fcntl.flock(chiave, fcntl.LOCK_EX)


def _sblocca(chiave):
    if SU_WINDOWS:
        try:
            chiave.seek(0)
            msvcrt.locking(chiave.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        return
    fcntl.flock(chiave, fcntl.LOCK_UN)


def _sostituisci(tmp, f):
    """os.replace; su Windows può fallire per un attimo se un altro processo sta leggendo il file."""
    for i in range(20):
        try:
            os.replace(tmp, f)
            return
        except PermissionError:
            if not SU_WINDOWS or i == 19:
                raise
            time.sleep(0.05)


@contextlib.contextmanager
def _registro():
    """Registro sotto chiave (anche fra processi): si legge, si cambia, si scrive atomico."""
    f = _f_registro()
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(str(f) + ".lock", "a+") as chiave:
        _blocca(chiave)
        try:
            r = _leggi_registro()
            yield r
            r["log"] = r["log"][-500:]
            tmp = f.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
            _sostituisci(tmp, f)
        finally:
            _sblocca(chiave)


def _ora_testo(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _log(r, adesso, testo):
    r["log"].append({"ts": adesso, "ora": _ora_testo(adesso), "testo": testo})
    try:
        with open(cartella() / "assistenza.log", "a", encoding="utf-8") as f:
            f.write(f"{_ora_testo(adesso)}  {testo}\n")
    except OSError:
        pass


def _serve_abilitata():
    c = config()
    if not c["abilitata"]:
        raise ErroreAssistenza("l'assistenza a distanza è spenta su questo computer")
    return c


# =====================================================================
# tmate (su Windows dentro WSL)
# =====================================================================

_NOME_DISTRO = re.compile(r"[A-Za-z0-9._-]{1,64}")
_cache_tmate = {"ts": 0.0, "chiave": None, "valore": None}


def _modo():
    """«nativo» se c'è un tmate indicato a mano o non siamo su Windows, altrimenti «wsl»."""
    if os.environ.get("ASSISTENZA_TMATE"):
        return "nativo"
    m = (os.environ.get("ASSISTENZA_MODO") or "").strip().lower()
    if m in ("wsl", "nativo"):
        return m
    return "wsl" if SU_WINDOWS else "nativo"


def _wsl_exe():
    w = os.environ.get("ASSISTENZA_WSL")
    if w:
        return w if os.path.isfile(w) else None
    w = shutil.which("wsl.exe") or shutil.which("wsl")
    if w:
        return w
    radice = os.environ.get("SystemRoot") or r"C:\Windows"
    for p in (os.path.join(radice, "System32", "wsl.exe"), os.path.join(radice, "Sysnative", "wsl.exe")):
        if os.path.isfile(p):
            return p
    return None


def _distro():
    d = (os.environ.get("ASSISTENZA_WSL_DISTRO") or str(config().get("wsl_distro") or "")).strip()
    return d if d and _NOME_DISTRO.fullmatch(d) else ""


def _prefisso_wsl():
    """[wsl.exe, (-d distro)] oppure None se WSL non c'è."""
    w = _wsl_exe()
    if not w:
        return None
    d = _distro()
    return [w, "-d", d] if d else [w]


def _tmate_in_wsl(prefisso):
    """C'è tmate dentro WSL? (risposta tenuta 60 s: lanciare WSL a ogni lettura del pannello costa)."""
    chiave = tuple(prefisso)
    adesso = time.time()
    if _cache_tmate["chiave"] == chiave and adesso - _cache_tmate["ts"] < 60:
        return _cache_tmate["valore"]
    try:
        p = subprocess.run([*prefisso, "-e", "which", "tmate"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                           stdin=subprocess.DEVNULL, creationflags=_SENZA_FINESTRE)
        valore = p.returncode == 0 and bool(p.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        valore = False
    _cache_tmate.update(ts=adesso, chiave=chiave, valore=valore)
    return valore


def comando_tmate():
    """L'inizio della riga di comando di tmate, come lista, oppure None se manca.
    Nativo: [tmate]. Windows: [wsl.exe, (-d distro), -e, tmate]."""
    t = os.environ.get("ASSISTENZA_TMATE")
    if t:
        return [t]
    if _modo() == "wsl":
        prefisso = _prefisso_wsl()
        if not prefisso or not _tmate_in_wsl(prefisso):
            return None
        return [*prefisso, "-e", "tmate"]
    t = shutil.which("tmate") or next((p for p in ("/opt/homebrew/bin/tmate", "/usr/local/bin/tmate", "/usr/bin/tmate")
                                       if os.access(p, os.X_OK)), None)
    return [t] if t else None


def aiuto_tmate():
    """Cosa dire al cliente quando tmate manca."""
    if _modo() == "wsl":
        return "manca il collegamento per l'assistenza su questo PC: premi «Attiva assistenza» (installa tutto da solo)"
    return "installa tmate (macOS: brew install tmate · Linux: sudo apt-get install tmate)"


def socket_tmate():
    s = os.environ.get("ASSISTENZA_SOCKET")
    if s:
        return s
    if _modo() == "wsl":
        return "/tmp/jarvis-assistenza.sock"            # percorso DENTRO WSL, non su Windows
    uid = os.getuid() if hasattr(os, "getuid") else 0
    return os.path.join(tempfile.gettempdir(), f"jarvis-assistenza-{uid}.sock")


def _tmate(*argomenti, timeout=15):
    t = comando_tmate()
    if not t:
        raise ErroreAssistenza(aiuto_tmate())
    # sempre una lista di argomenti, mai una stringa per la shell
    return subprocess.run([*t, "-S", socket_tmate(), *[str(a) for a in argomenti]], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL,
                          cwd=str(Path.home()), creationflags=_SENZA_FINESTRE)


def _tmate_vivo():
    try:
        return _tmate("has-session", timeout=10).returncode == 0
    except (subprocess.TimeoutExpired, OSError, ErroreAssistenza):
        return False


def _tmate_ferma():
    try:
        _tmate("kill-server", timeout=10)
    except (subprocess.TimeoutExpired, OSError, ErroreAssistenza):
        pass
    _custode_ferma()


# Su Windows la distribuzione WSL può spegnersi quando nessun wsl.exe è più aperto, e con lei
# il server tmate. Il «custode» è un wsl.exe che resta in attesa (tmate wait-for) finché la
# sessione dura: tiene viva la distribuzione ed esce da solo quando il server tmate si ferma.
_custode = {"p": None}


def _custode_avvia():
    if _modo() != "wsl":
        return
    t = comando_tmate()
    if not t:
        return
    try:
        _custode["p"] = subprocess.Popen([*t, "-S", socket_tmate(), "wait-for", "jarvis-assistenza-fine"],
                                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, cwd=str(Path.home()),
                                         creationflags=_SENZA_FINESTRE)
    except OSError:
        _custode["p"] = None


def _custode_ferma():
    p = _custode.get("p")
    _custode["p"] = None
    if p and p.poll() is None:
        try:
            p.terminate()
            p.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass


# =====================================================================
# Tunnel verso il server del tecnico, DENTRO WSL (2026-10-02)
# =====================================================================

TUNNEL_ATTESA_SECONDI = 15 * 60         # tempo per stabilire il tunnel: oltre, chiusura e minuti a credito
TUNNEL_COLLEGATO_SECONDI = 30           # ssh vivo da tanto = autenticato e inoltro accettato
TETTO_SESSIONE_SECONDI = 8 * 3600       # lo stesso tetto del server del tecnico
TMUX_SOCKET = "jarvis-assistenza"
_CHIAVE_ED = re.compile(r"ssh-ed25519 ([A-Za-z0-9+/]{68})(?: .*)?")
_UTENTE_LINUX = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,31}")
_PROCESSI = {}                          # "sshd"/"ssh" -> Popen del wsl.exe che li tiene in primo piano
_cache_ssh = {"ts": 0.0, "chiave": None, "valore": None}

# Lo script che gira dentro Linux. Arriva su stdin (sh -s), mai come file: niente percorsi
# Windows da tradurre, niente virgolette da far passare da wsl.exe. Argomenti fissi:
#   $1 comando · $2 cartella base (vuota = ~/.jarvis-assistenza-cliente) · $3 ssh · $4 sshd · $5 ssh-keygen · $6 tmux
# Ogni processo lungo scrive il suo pid nella cartella della sessione: la chiusura lo cerca lì,
# controlla che la riga di comando contenga la cartella della sessione (niente pid riciclati)
# e ferma lui e tutti i suoi figli (le connessioni del tecnico sono figli di sshd).
_SCRIPT = r'''
set -u
cmd=$1; base=${2:-$HOME/.jarvis-assistenza-cliente}; SSH=$3; SSHD=$4; KEYGEN=$5; TMUX=$6; shift 6
sess=$base/sessione
nostro() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null && ps -o args= -p "$1" 2>/dev/null | grep -qF "$sess" && vivo "$1"; }
vivo() { kill -0 "$1" 2>/dev/null && ! ps -o stat= -p "$1" 2>/dev/null | grep -q '^ *Z'; }
figli() { for c in $(ps -eo pid=,ppid= | awk -v p="$1" '$2==p{print $1}'); do figli "$c"; echo "$c"; done; }
pid_di() { cat "$sess/$1.pid" 2>/dev/null || true; }
case "$cmd" in
programmi)
  for p in "$SSH" "$SSHD" "$KEYGEN"; do command -v "$p" >/dev/null 2>&1 || echo "MANCA $p"; done
  echo FINE ;;
prepara)
  porta_locale=$1; tecnico=$2; kh=$3
  mkdir -p "$base" && chmod 700 "$base" || exit 3
  rm -rf "$sess"; mkdir -m 700 "$sess" || exit 3
  "$KEYGEN" -q -t ed25519 -N "" -C jarvis-assistenza-host -f "$sess/host" </dev/null >/dev/null || exit 4
  "$KEYGEN" -q -t ed25519 -N "" -C jarvis-assistenza-cliente -f "$sess/cliente" </dev/null >/dev/null || exit 4
  printf '%s\n' "$kh" > "$sess/known_hosts"
  t=$(command -v "$TMUX" 2>/dev/null || true)
  opz="restrict,pty"
  [ -n "$t" ] && opz="$opz,command=\"$t -L jarvis-assistenza new-session -A -s assistenza\""
  printf '%s %s tecnico\n' "$opz" "$tecnico" > "$sess/tecnico"
  radice=no
  if [ "$(id -u)" = 0 ]; then radice=prohibit-password; mkdir -p /run/sshd; chmod 755 /run/sshd; fi
  cat > "$sess/sshd_config" <<FINE_CONFIG
ListenAddress 127.0.0.1
Port $porta_locale
HostKey $sess/host
AuthorizedKeysFile $sess/tecnico
PidFile $sess/sshd-interno.pid
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
StrictModes no
PermitRootLogin $radice
AllowTcpForwarding no
AllowAgentForwarding no
X11Forwarding no
PermitTunnel no
GatewayPorts no
AllowStreamLocalForwarding no
MaxAuthTries 3
LogLevel VERBOSE
FINE_CONFIG
  echo "UTENTE $(id -un)"
  echo "HOST $(cut -d' ' -f2 "$sess/host.pub")"
  echo "CLIENTE $(cut -d' ' -f2 "$sess/cliente.pub")"
  echo "TMUX $t"
  echo FINE ;;
sshd)
  echo $$ > "$sess/sshd.pid"
  exec "$SSHD" -D -e -f "$sess/sshd_config" </dev/null >>"$sess/sshd.log" 2>&1 ;;
ssh)
  porta=$1; porta_locale=$2; host=$3; porta_ssh=$4; utente=$5
  echo $$ > "$sess/ssh.pid"
  exec "$SSH" -F /dev/null -N -T -n -o BatchMode=yes -o ExitOnForwardFailure=yes -o IdentitiesOnly=yes \
    -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -o ConnectTimeout=10 \
    -o UserKnownHostsFile="$sess/known_hosts" -o GlobalKnownHostsFile=/dev/null \
    -o StrictHostKeyChecking=yes -o LogLevel=VERBOSE -i "$sess/cliente" -p "$porta_ssh" \
    -R "127.0.0.1:$porta:127.0.0.1:$porta_locale" "$utente@$host" </dev/null >>"$sess/ssh.log" 2>&1 ;;
chiave)
  cat "$sess/cliente" ;;
controlla)
  for n in sshd ssh; do if nostro "$(pid_di $n)"; then echo "$n VIVO"; else echo "$n MORTO"; fi; done
  grep -q "Server listening" "$sess/sshd.log" 2>/dev/null && echo PRONTO
  grep -q "Authenticated to" "$sess/ssh.log" 2>/dev/null && echo AUTENTICATO
  echo "ULTIMA_SSHD $(tail -n 1 "$sess/sshd.log" 2>/dev/null)"
  echo "ULTIMA_SSH $(tail -n 1 "$sess/ssh.log" 2>/dev/null)"
  echo FINE ;;
ferma)
  quali=${1:-tutto}
  lista=""
  for n in ssh sshd; do
    [ "$quali" = ssh ] && [ "$n" = sshd ] && continue
    pid=$(pid_di $n)
    if nostro "$pid"; then lista="$lista $(figli "$pid") $pid"; fi
  done
  vivi=""
  if [ -n "$lista" ]; then
    kill -TERM $lista 2>/dev/null
    i=0
    while [ $i -lt 30 ]; do
      vivi=""; for p in $lista; do vivo "$p" && vivi="$vivi $p"; done
      [ -z "$vivi" ] && break
      sleep 0.1; i=$((i+1))
    done
    if [ -n "$vivi" ]; then
      kill -KILL $vivi 2>/dev/null; sleep 0.3
      vivi=""; for p in $lista; do vivo "$p" && vivi="$vivi $p"; done
    fi
  fi
  if [ "$quali" = tutto ]; then
    t=$(command -v "$TMUX" 2>/dev/null || true)
    [ -n "$t" ] && "$t" -L jarvis-assistenza kill-server >/dev/null 2>&1
    [ -z "$vivi" ] && rm -rf "$sess"
  else
    rm -f "$sess/ssh.pid"
  fi
  if [ -n "$vivi" ]; then echo "RESTANO$vivi"; else echo FERMO; fi ;;
*) echo "comando sconosciuto: $cmd" >&2; exit 2 ;;
esac
'''


def _prog_linux(var, default):
    return os.environ.get(var) or default


def _argomenti_script(comando, *altri):
    return [comando, os.environ.get("ASSISTENZA_TUNNEL_DIR") or "",
            _prog_linux("ASSISTENZA_SSH", "ssh"), _prog_linux("ASSISTENZA_SSHD", "/usr/sbin/sshd"),
            _prog_linux("ASSISTENZA_SSH_KEYGEN", "ssh-keygen"), _prog_linux("ASSISTENZA_TMUX", "tmux"),
            *[str(a) for a in altri]]


def _riga_linux(*argv):
    """La riga per lanciare un programma in Linux: dentro WSL (wsl.exe [-d distro] -e ...) oppure qui."""
    if _modo() == "wsl":
        prefisso = _prefisso_wsl()
        if not prefisso:
            raise ErroreAssistenza(aiuto_tmate())
        return [*prefisso, "-e", *argv]
    return list(argv)


def _script(comando, *altri, timeout=60):
    """Esegue un comando breve dello script e torna (codice, testo)."""
    p = subprocess.run(_riga_linux("sh", "-s", "--", *_argomenti_script(comando, *altri)),
                       input=_SCRIPT.encode("utf-8"),          # byte: niente \r\n aggiunti da Windows
                       capture_output=True, timeout=timeout, cwd=str(Path.home()), creationflags=_SENZA_FINESTRE)
    testo = (p.stdout + p.stderr).decode("utf-8", errors="replace").replace("\0", "")
    return p.returncode, testo


def _righe(testo):
    d = {}
    for r in testo.splitlines():
        k, _, v = r.strip().partition(" ")
        if k:
            d[k] = v.strip()
    return d


def _avvia_lungo(nome, *altri):
    """sshd o ssh in primo piano dentro un wsl.exe che resta aperto: tiene viva la distribuzione
    finché la sessione dura e dal lato Windows si vede subito se il processo è uscito."""
    p = subprocess.Popen(_riga_linux("sh", "-s", "--", *_argomenti_script(nome, *altri)),
                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         cwd=str(Path.home()), creationflags=_SENZA_FINESTRE)
    try:
        p.stdin.write(_SCRIPT.encode("utf-8"))
        p.stdin.close()
    except OSError:
        pass
    vecchio = _PROCESSI.pop(nome, None)
    if vecchio and vecchio.poll() is None:
        _chiudi_popen(vecchio)
    _PROCESSI[nome] = p
    return p


def _chiudi_popen(p):
    if p.poll() is None:
        try:
            p.terminate()
            p.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                p.kill()
                p.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass


def _ssh_in_linux():
    """Ci sono ssh, sshd e ssh-keygen in Linux? (risposta tenuta 60 s, come per tmate)."""
    try:
        chiave = (tuple(_riga_linux("sh")), tuple(_argomenti_script("programmi")))
    except ErroreAssistenza:
        return False
    adesso = time.time()
    if _cache_ssh["chiave"] == chiave and adesso - _cache_ssh["ts"] < 60:
        return _cache_ssh["valore"]
    try:
        codice, testo = _script("programmi", timeout=20)
        valore = codice == 0 and "FINE" in testo and "MANCA" not in testo
    except (subprocess.TimeoutExpired, OSError):
        valore = False
    _cache_ssh.update(ts=adesso, chiave=chiave, valore=valore)
    return valore


def _tunnel_valori(c=None):
    """La sezione «tunnel» di assistenza.json, controllata (senza guardare i programmi). None = non c'è."""
    c = config() if c is None else c
    t = c.get("tunnel")
    if not isinstance(t, dict):
        return None
    host = str(t.get("host") or "").strip()
    utente = str(t.get("utente") or "assistenza").strip()
    kh = str(t.get("known_hosts") or "").strip()
    tec = _CHIAVE_ED.fullmatch(str(t.get("chiave_tecnico") or "").strip())
    porte = t.get("porte") or [47000, 47999]
    try:
        porta_ssh = int(t.get("porta") or 22)
        pmin, pmax = int(porte[0]), int(porte[1])
    except (TypeError, ValueError, IndexError):
        return None
    if (not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host) or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", utente)
            or not tec or "\n" in kh or not re.search(r"\sssh-ed25519\s+[A-Za-z0-9+/]{68}", " " + kh)
            or not 1 <= porta_ssh <= 65535 or not 1024 < pmin <= pmax < 65536):
        return None
    if any(_segnaposto(x) for x in (host, kh)):
        return None
    return {"host": host, "porta": porta_ssh, "utente": utente, "known_hosts": kh,
            "chiave_tecnico": f"ssh-ed25519 {tec.group(1)}", "porte": [pmin, pmax]}


def tunnel_conf(c=None):
    """Come _tunnel_valori, ma None anche se in Linux mancano ssh, sshd o ssh-keygen (allora si usa tmate)."""
    t = _tunnel_valori(c)
    if not t or not _ssh_in_linux():
        return None
    return t


def _tunnel_ferma_processi(quali="tutto"):
    """Ferma i processi del tunnel DENTRO Linux e controlla che siano morti. Torna True se è tutto fermo."""
    fermo = False
    for _ in range(2):
        try:
            codice, testo = _script("ferma", quali, timeout=30)
            fermo = "FERMO" in testo
        except (subprocess.TimeoutExpired, OSError, ErroreAssistenza):
            fermo = False
        if fermo:
            break
    nomi = ("ssh",) if quali == "ssh" else ("ssh", "sshd")
    for n in nomi:
        p = _PROCESSI.pop(n, None)
        if p is not None:
            _chiudi_popen(p)
    return fermo


def _tunnel_controlla_linux():
    try:
        codice, testo = _script("controlla", timeout=30)
    except (subprocess.TimeoutExpired, OSError, ErroreAssistenza):
        return None
    if "FINE" not in testo:
        return None
    d = _righe(testo)
    return {"sshd": d.get("sshd") == "VIVO", "ssh": d.get("ssh") == "VIVO", "pronto": "PRONTO" in d,
            "autenticato": "AUTENTICATO" in d, "ultima_sshd": d.get("ULTIMA_SSHD", ""), "ultima_ssh": d.get("ULTIMA_SSH", "")}


def _comando_guarda(tmux):
    if not tmux:
        return ""
    if _modo() == "wsl":
        d = _distro()
        return ("wsl " + (f"-d {d} " if d else "") + f"-e {tmux} -L {TMUX_SOCKET} attach -r -t assistenza")
    return f"{tmux} -L {TMUX_SOCKET} attach -r -t assistenza"


def _tunnel_avvia(t, avvisi=None):
    """Chiavi, sshd locale e tunnel, dentro Linux. Torna i dati della sessione (senza segreti)."""
    _tunnel_ferma_processi()                    # resti di una sessione di prima: via
    ultimo = ""
    for _ in range(3):                          # la porta locale presa a caso può essere occupata
        porta_locale = 20000 + secrets.randbelow(20000)
        codice, testo = _script("prepara", porta_locale, t["chiave_tecnico"], t["known_hosts"], timeout=60)
        d = _righe(testo)
        if codice != 0 or "FINE" not in d:
            _tunnel_ferma_processi()
            raise ErroreAssistenza(f"non riesco a preparare le chiavi del tunnel: {testo.strip()[-200:]}")
        utente, host_b64, cli_b64 = d.get("UTENTE", ""), d.get("HOST", ""), d.get("CLIENTE", "")
        if not (_UTENTE_LINUX.fullmatch(utente) and re.fullmatch(r"[A-Za-z0-9+/]{68}", host_b64)
                and re.fullmatch(r"[A-Za-z0-9+/]{68}", cli_b64)):
            _tunnel_ferma_processi()
            raise ErroreAssistenza("le chiavi del tunnel create non sono ed25519")
        _avvia_lungo("sshd")
        pronto = False
        fine = time.time() + 15
        while time.time() < fine:
            s = _tunnel_controlla_linux()
            if s and s["pronto"] and s["sshd"]:
                pronto = True
                break
            if s and not s["sshd"] and _PROCESSI["sshd"].poll() is not None:
                ultimo = s["ultima_sshd"]
                break
            time.sleep(0.3)
        if pronto:
            break
        _tunnel_ferma_processi()
    else:
        raise ErroreAssistenza(f"il server ssh locale non parte: {ultimo[:200]}")
    porta = t["porte"][0] + secrets.randbelow(t["porte"][1] - t["porte"][0] + 1)
    _avvia_lungo("ssh", porta, porta_locale, t["host"], t["porta"], t["utente"])
    tmux = d.get("TMUX", "")
    # 2026-10-02 sera: lo schermo condiviso, se c'è TightVNC; se non parte resta il solo terminale
    sch, segreto = (None, "")
    if schermo_pronto():
        sch, segreto = _schermo_avvia(t, porta, time.time(), avvisi.append if avvisi is not None else (lambda x: None))
    richiesta = (f"jarvis-tunnel:2:{porta}:{sch['porta']}:{utente}:{host_b64}:{cli_b64}:{segreto}" if sch
                 else f"jarvis-tunnel:1:{porta}:{utente}:{host_b64}:{cli_b64}")
    return {"porta": porta, "porta_locale": porta_locale, "ssh_avviato": None, "collegato": False, "tentativi": 1,
            "richiesta": richiesta, "schermo": sch,
            "guarda": _comando_guarda(tmux), "tmux": tmux, "utente": utente}


def _tunnel_controlla(r, a, adesso):
    """Un giro sul tunnel. Torna None se va tutto bene, altrimenti (motivo, rimborso)."""
    tu = a["tunnel"]
    if tu.get("ssh_avviato") is None:
        tu["ssh_avviato"] = adesso
    s = _tunnel_controlla_linux()
    if s is None:
        # Linux non risponde (distribuzione spenta o WSL fermo): il tunnel non c'è più
        return "Linux (WSL) non risponde più", not tu.get("collegato")
    if not s["sshd"]:
        return "il server ssh locale si è chiuso", not tu.get("collegato")
    if s["ssh"]:
        if not tu.get("collegato") and (s["autenticato"] or adesso - tu["ssh_avviato"] >= TUNNEL_COLLEGATO_SECONDI):
            tu["collegato"] = True
            _log(r, adesso, f"tunnel stabilito (porta {tu['porta']})")
        _schermo_controlla(r, tu, adesso)
        return None
    if tu.get("collegato"):
        return "tunnel caduto (chiuso dal tecnico o rete persa)", False
    if adesso - a["inizio"] >= TUNNEL_ATTESA_SECONDI:
        return "il tunnel non si è stabilito in 15 minuti", True
    t = _tunnel_valori()
    if not t:
        return "tunnel non più configurato", True
    _tunnel_ferma_processi("ssh")
    _avvia_lungo("ssh", tu["porta"], tu["porta_locale"], t["host"], t["porta"], t["utente"])
    tu["ssh_avviato"] = adesso
    tu["tentativi"] = int(tu.get("tentativi") or 1) + 1
    _schermo_controlla(r, tu, adesso)          # anche lo schermo riprova finché il tecnico non apre la chiave
    return None


# =====================================================================
# Schermo condiviso (2026-10-02): la password del VNC viaggia CIFRATA nella richiesta
# =====================================================================
# Il cliente cifra la password di sessione del VNC con la chiave pubblica ssh del tecnico
# («chiave_tecnico», ed25519): X25519 effimero (RFC 7748) verso la stessa chiave vista come punto
# di Montgomery, SHA-256 come derivazione, XOR sugli 8 caratteri e un'etichetta HMAC di 8 byte.
# Solo chi ha la chiave privata del tecnico la legge: chi vede la richiesta su WhatsApp no.

SCHERMO_ETICHETTA = b"jarvis-schermo-v2"


def _x25519(scalare, u):
    """Moltiplicazione scalare X25519 (RFC 7748, scaletta di Montgomery). Torna un intero."""
    k = int.from_bytes(scalare, "little")
    k &= ~7
    k &= ~(128 << 8 * 31)
    k |= 64 << 8 * 31
    x1, x2, z2, x3, z3, scambio = u % _P, 1, 0, u % _P, 1, 0
    for t in reversed(range(255)):
        bit = (k >> t) & 1
        scambio ^= bit
        if scambio:
            x2, x3, z2, z3 = x3, x2, z3, z2
        scambio = bit
        a, b = x2 + z2, x2 - z2
        aa, bb = a * a % _P, b * b % _P
        e = aa - bb
        c, d = x3 + z3, x3 - z3
        da, cb = d * a % _P, c * b % _P
        x3, z3 = (da + cb) ** 2 % _P, x1 * (da - cb) ** 2 % _P
        x2, z2 = aa * bb % _P, e * (aa + 121665 * e) % _P
    if scambio:
        x2, z2 = x3, z3
    return x2 * pow(z2, _P - 2, _P) % _P


def _montgomery_da_ed25519(pubblica):
    """La u di Montgomery di una chiave pubblica ed25519 (32 byte): u = (1 + y) / (1 - y)."""
    y = int.from_bytes(pubblica, "little") & ((1 << 255) - 1)
    if y >= _P or (1 - y) % _P == 0:
        raise ErroreAssistenza("chiave del tecnico non valida")
    return (1 + y) * pow((1 - y) % _P, _P - 2, _P) % _P


def _chiave_ed_grezza(testo):
    """I 32 byte di una «ssh-ed25519 BASE64»."""
    m = _CHIAVE_ED.fullmatch(str(testo or "").strip())
    if not m:
        raise ErroreAssistenza("chiave del tecnico non valida")
    blob = base64.b64decode(m.group(1))
    if len(blob) != 51 or blob[:15] != b"\x00\x00\x00\x0bssh-ed25519" or blob[15:19] != b"\x00\x00\x00\x20":
        raise ErroreAssistenza("chiave del tecnico non valida")
    return blob[19:]


def _flusso(condiviso, effimera, u_tecnico):
    return hashlib.sha256(SCHERMO_ETICHETTA + condiviso.to_bytes(32, "little") + effimera
                          + u_tecnico.to_bytes(32, "little")).digest()


def cifra_password_schermo(password, chiave_tecnico):
    """password (8 caratteri ASCII) -> 64 caratteri base64 (effimera 32 + cifrato 8 + etichetta 8)."""
    import hmac
    pw = str(password).encode("ascii")
    if len(pw) != 8:
        raise ErroreAssistenza("la password dello schermo deve avere 8 caratteri")
    u = _montgomery_da_ed25519(_chiave_ed_grezza(chiave_tecnico))
    e = secrets.token_bytes(32)
    effimera = _x25519(e, 9).to_bytes(32, "little")
    condiviso = _x25519(e, u)
    if condiviso == 0:
        raise ErroreAssistenza("chiave del tecnico non valida")
    k = _flusso(condiviso, effimera, u)
    cifrato = bytes(a ^ b for a, b in zip(pw, k[:8]))
    etichetta = hmac.new(k[8:], effimera + cifrato, hashlib.sha256).digest()[:8]
    return base64.b64encode(effimera + cifrato + etichetta).decode()


# ---- password del VNC: l'offuscamento standard (DES con la chiave fissa del protocollo VNC)
# TightVNC tiene la password nel registro così; la chiave fissa è nota a tutti: è un formato, non
# una protezione. La protezione vera è che la password vale una sessione sola e sparisce alla fine.

_DES_PC1 = (57, 49, 41, 33, 25, 17, 9, 1, 58, 50, 42, 34, 26, 18, 10, 2, 59, 51, 43, 35, 27, 19, 11, 3, 60, 52, 44, 36,
            63, 55, 47, 39, 31, 23, 15, 7, 62, 54, 46, 38, 30, 22, 14, 6, 61, 53, 45, 37, 29, 21, 13, 5, 28, 20, 12, 4)
_DES_PC2 = (14, 17, 11, 24, 1, 5, 3, 28, 15, 6, 21, 10, 23, 19, 12, 4, 26, 8, 16, 7, 27, 20, 13, 2,
            41, 52, 31, 37, 47, 55, 30, 40, 51, 45, 33, 48, 44, 49, 39, 56, 34, 53, 46, 42, 50, 36, 29, 32)
_DES_GIRI = (1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1)
_DES_IP = (58, 50, 42, 34, 26, 18, 10, 2, 60, 52, 44, 36, 28, 20, 12, 4, 62, 54, 46, 38, 30, 22, 14, 6,
           64, 56, 48, 40, 32, 24, 16, 8, 57, 49, 41, 33, 25, 17, 9, 1, 59, 51, 43, 35, 27, 19, 11, 3,
           61, 53, 45, 37, 29, 21, 13, 5, 63, 55, 47, 39, 31, 23, 15, 7)
_DES_FP = (40, 8, 48, 16, 56, 24, 64, 32, 39, 7, 47, 15, 55, 23, 63, 31, 38, 6, 46, 14, 54, 22, 62, 30,
           37, 5, 45, 13, 53, 21, 61, 29, 36, 4, 44, 12, 52, 20, 60, 28, 35, 3, 43, 11, 51, 19, 59, 27,
           34, 2, 42, 10, 50, 18, 58, 26, 33, 1, 41, 9, 49, 17, 57, 25)
_DES_E = (32, 1, 2, 3, 4, 5, 4, 5, 6, 7, 8, 9, 8, 9, 10, 11, 12, 13, 12, 13, 14, 15, 16, 17,
          16, 17, 18, 19, 20, 21, 20, 21, 22, 23, 24, 25, 24, 25, 26, 27, 28, 29, 28, 29, 30, 31, 32, 1)
_DES_P = (16, 7, 20, 21, 29, 12, 28, 17, 1, 15, 23, 26, 5, 18, 31, 10, 2, 8, 24, 14, 32, 27, 3, 9,
          19, 13, 30, 6, 22, 11, 4, 25)
_DES_S = (
    (14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7, 0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8,
     4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0, 15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13),
    (15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10, 3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5,
     0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15, 13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9),
    (10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8, 13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1,
     13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7, 1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12),
    (7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15, 13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9,
     10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4, 3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14),
    (2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9, 14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6,
     4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14, 11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3),
    (12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11, 10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8,
     9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6, 4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13),
    (4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1, 13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6,
     1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2, 6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12),
    (13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7, 1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2,
     7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8, 2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11),
)


def _permuta(valore, tabella, bit_in):
    out = 0
    for p in tabella:
        out = (out << 1) | ((valore >> (bit_in - p)) & 1)
    return out


def des_cifra(chiave, blocco):
    """DES standard (FIPS 46-3) su un blocco di 8 byte. Serve solo al formato della password VNC."""
    k = _permuta(int.from_bytes(chiave, "big"), _DES_PC1, 64)
    c, d = k >> 28, k & 0xFFFFFFF
    sotto = []
    for g in _DES_GIRI:
        c = ((c << g) | (c >> (28 - g))) & 0xFFFFFFF
        d = ((d << g) | (d >> (28 - g))) & 0xFFFFFFF
        sotto.append(_permuta((c << 28) | d, _DES_PC2, 56))
    b = _permuta(int.from_bytes(blocco, "big"), _DES_IP, 64)
    sx, dx = b >> 32, b & 0xFFFFFFFF
    for k in sotto:
        x = _permuta(dx, _DES_E, 32) ^ k
        f = 0
        for i in range(8):
            sei = (x >> (42 - 6 * i)) & 0x3F
            riga, colonna = ((sei & 0x20) >> 4) | (sei & 1), (sei >> 1) & 0xF
            f = (f << 4) | _DES_S[i][riga * 16 + colonna]
        sx, dx = dx, sx ^ _permuta(f, _DES_P, 32)
    return _permuta((dx << 32) | sx, _DES_FP, 64).to_bytes(8, "big")


VNC_CHIAVE_FISSA = bytes.fromhex("e84ad660c4721ae0")     # {23,82,107,6,35,78,88,7} con i bit girati, come d3des


def vnc_password_cifrata(password):
    """Gli 8 byte che TightVNC tiene nel registro («Password»)."""
    return des_cifra(VNC_CHIAVE_FISSA, str(password).encode("ascii")[:8].ljust(8, b"\0"))


_ALFABETO_SCHERMO = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def password_schermo():
    """8 caratteri a caso (il VNC ne legge al massimo 8), senza quelli che si confondono."""
    return "".join(secrets.choice(_ALFABETO_SCHERMO) for _ in range(8))


# ---- lo schermo sul PC del cliente: TightVNC + ssh.exe di Windows (2026-10-02 sera)
#
# Scelte (vedi docs/ASSISTENZA.md, «Schermo condiviso»):
# - TightVNC Server (GPLv2), installato dal cliente con winget (GlavSoft.TightVNC) da ASSISTENZA.ps1:
#   non lo includiamo né lo distribuiamo. Gira in MODO APPLICAZIONE («tvnserver.exe -run»), non come
#   servizio: condivide il desktop VERO dell'utente (cliente e tecnico vedono lo stesso schermo), parte
#   all'avvio della sessione e si ferma alla chiusura. Impostazioni in HKCU\Software\TightVNC\Server:
#   porta a caso, LoopbackOnly=1 (ascolta solo su 127.0.0.1), password di sessione di 8 caratteri,
#   tolta alla chiusura. Funziona su Windows Home e Pro (l'RDP integrato no: su Home non c'è).
# - Il tunnel dello schermo lo apre l'ssh.exe di WINDOWS (OpenSSH, incluso in Windows 10/11): dentro
#   WSL2 il 127.0.0.1 di Windows non si vede. Usa la stessa chiave di sessione del terminale (copiata
#   da WSL in una cartella dell'utente), verso lo stesso server del tecnico, con -R 127.0.0.1:PORTA_SCHERMO. Il
#   terminale resta dentro WSL com'era.
# - La password non si scrive mai in chiaro: nel registro va nel formato del VNC, nella richiesta va
#   cifrata per il tecnico (cifra_password_schermo).
# - Lo schermo non decide la sessione: se non parte, il terminale funziona lo stesso; se cade il
#   terminale si chiude tutto. STOP, credito finito, 8 ore, tunnel caduto: si ferma anche lo schermo,
#   con verifica (processi morti, porta chiusa, password tolta).

VNC_CHIAVE_REGISTRO = r"Software\TightVNC\Server"
_PROCESSI_WIN = {}                      # pid -> Popen dei programmi Windows dello schermo


def cartella_schermo():
    d = os.environ.get("ASSISTENZA_SCHERMO_DIR")
    if d:
        return Path(d)
    if SU_WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "jarvis-assistenza" / "schermo"
    return Path.home() / ".jarvis-assistenza-schermo"


def _vnc_exe():
    p = os.environ.get("ASSISTENZA_VNC")
    if p:
        return p if os.path.isfile(p) else None
    if not SU_WINDOWS:
        return None
    for radice in (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles(x86)")):
        if radice and os.path.isfile(os.path.join(radice, "TightVNC", "tvnserver.exe")):
            return os.path.join(radice, "TightVNC", "tvnserver.exe")
    return None


def _ssh_win():
    p = os.environ.get("ASSISTENZA_SSH_WIN")
    if p:
        return p if os.path.isfile(p) else None
    if not SU_WINDOWS:
        return None
    radice = os.environ.get("SystemRoot") or r"C:\Windows"
    for p in (os.path.join(radice, "System32", "OpenSSH", "ssh.exe"), os.path.join(radice, "Sysnative", "OpenSSH", "ssh.exe")):
        if os.path.isfile(p):
            return p
    return shutil.which("ssh.exe")


def schermo_pronto(c=None):
    """Si può condividere lo schermo? Serve il tunnel, TightVNC e l'ssh di Windows. «schermo»: false lo spegne."""
    c = config() if c is None else c
    return c.get("schermo", True) is not False and bool(_tunnel_valori(c)) and bool(_vnc_exe()) and bool(_ssh_win())


def _netstat_righe():
    """Le righe di «netstat -ano -p TCP» (Windows) o del finto netstat delle prove. None = non si sa."""
    finto = os.environ.get("ASSISTENZA_NETSTAT")
    argv = [finto] if finto else (["netstat", "-ano", "-p", "TCP"] if SU_WINDOWS else None)
    if not argv:
        return None
    try:
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                           stdin=subprocess.DEVNULL, creationflags=_SENZA_FINESTRE)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout.splitlines() if p.returncode == 0 else None


def vnc_ascolti(porta):
    """(indirizzi su cui qualcosa ASCOLTA la porta, connessioni STABILITE verso la porta). None se non si sa."""
    righe = _netstat_righe()
    if righe is None:
        return None
    ascolto, stabilite = set(), 0
    for r in righe:
        p = r.split()
        if len(p) < 4 or p[0].upper() != "TCP":
            continue
        locale, stato_c = p[1], p[3].upper()
        ind, _, pt = locale.rpartition(":")
        if pt != str(porta):
            continue
        if stato_c in ("LISTENING", "LISTEN", "IN_ASCOLTO"):
            ascolto.add(ind.strip("[]"))
        elif stato_c in ("ESTABLISHED", "STABILITA"):
            stabilite += 1
    return ascolto, stabilite


def _solo_locale(indirizzi):
    return all(i in ("127.0.0.1", "::1") for i in indirizzi)


def _vnc_scrivi_conf(valori, password=None, togli_password=False):
    """Le impostazioni del VNC: registro di Windows (HKCU, modo applicazione) o un JSON nelle prove."""
    if SU_WINDOWS and not os.environ.get("ASSISTENZA_VNC"):
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, VNC_CHIAVE_REGISTRO, 0, winreg.KEY_SET_VALUE) as k:
            for nome, v in valori.items():
                winreg.SetValueEx(k, nome, 0, winreg.REG_DWORD, int(v))
            if password is not None:
                winreg.SetValueEx(k, "Password", 0, winreg.REG_BINARY, vnc_password_cifrata(password))
            if togli_password:
                for nome in ("Password", "PasswordViewOnly"):
                    try:
                        winreg.DeleteValue(k, nome)
                    except OSError:
                        pass
        return
    f = cartella_schermo() / "vnc-finto.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d.update(valori)
    if password is not None:
        d["Password"] = vnc_password_cifrata(password).hex()
    if togli_password:
        d.pop("Password", None)
        d.pop("PasswordViewOnly", None)
    f.write_text(json.dumps(d), encoding="utf-8")


def vnc_password_presente():
    """C'è una password nelle impostazioni del VNC? (dopo la chiusura deve essere False)."""
    if SU_WINDOWS and not os.environ.get("ASSISTENZA_VNC"):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, VNC_CHIAVE_REGISTRO) as k:
                winreg.QueryValueEx(k, "Password")
                return True
        except OSError:
            return False
    try:
        return "Password" in json.loads((cartella_schermo() / "vnc-finto.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False


def _pid_vivo(pid, immagine=""):
    if not pid:
        return False
    p = _PROCESSI_WIN.get(pid)
    if p is not None:
        return p.poll() is None
    if SU_WINDOWS:
        filtro = ["/FI", f"PID eq {int(pid)}"] + (["/FI", f"IMAGENAME eq {immagine}"] if immagine else [])
        try:
            out = subprocess.run(["tasklist", *filtro, "/NH", "/FO", "CSV"], capture_output=True, text=True,
                                 errors="replace", timeout=20, stdin=subprocess.DEVNULL, creationflags=_SENZA_FINESTRE).stdout
        except (OSError, subprocess.TimeoutExpired):
            return True                      # non si sa: meglio crederlo vivo e riprovare
        return f'"{int(pid)}"' in out
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    st = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(st) and not st.startswith("Z")


def _ferma_pid(pid, immagine=""):
    """Ferma un programma Windows dello schermo (e i suoi figli) e controlla che sia morto."""
    if not pid:
        return True
    p = _PROCESSI_WIN.pop(pid, None)
    if p is not None:
        _chiudi_popen(p)
    elif SU_WINDOWS:
        filtro = ["/FI", f"PID eq {int(pid)}"] + (["/FI", f"IMAGENAME eq {immagine}"] if immagine else [])
        try:
            subprocess.run(["taskkill", "/T", "/F", *filtro], capture_output=True, timeout=20,
                           stdin=subprocess.DEVNULL, creationflags=_SENZA_FINESTRE)
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        import signal as _segnale
        for s in (_segnale.SIGTERM, _segnale.SIGKILL):
            try:
                os.kill(int(pid), s)
            except OSError:
                break
            fine = time.time() + 3
            while time.time() < fine and _pid_vivo(pid):
                time.sleep(0.1)
            if not _pid_vivo(pid):
                break
    fine = time.time() + 5
    while time.time() < fine:
        if not _pid_vivo(pid, immagine):
            return True
        time.sleep(0.1)
    return not _pid_vivo(pid, immagine)


def _avvia_win(argv, log, finestra=False):
    with open(log, "ab") as f:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=f, stderr=f, cwd=str(Path.home()),
                             creationflags=0 if finestra else _SENZA_FINESTRE)
    _PROCESSI_WIN[p.pid] = p
    return p.pid


def _porta_locale_libera():
    import socket
    for _ in range(20):
        p = 20000 + secrets.randbelow(20000)
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
            return p
        except OSError:
            continue
        finally:
            s.close()
    raise ErroreAssistenza("nessuna porta locale libera per lo schermo")


def _saluto_vnc(porta, secondi=1.0):
    import socket
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=secondi) as s:
            s.settimeout(secondi)
            return s.recv(12).startswith(b"RFB ")
    except OSError:
        return False


def _comando_ssh_schermo(t, porta_schermo, porta_vnc):
    d = cartella_schermo() / "sessione"
    return [_ssh_win(), "-F", "none", "-N", "-T",
            "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes", "-o", "IdentitiesOnly=yes",
            "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3", "-o", "ConnectTimeout=10",
            "-o", f"UserKnownHostsFile={d / 'known_hosts'}", "-o", "GlobalKnownHostsFile=none",
            "-o", "StrictHostKeyChecking=yes", "-o", "LogLevel=VERBOSE",
            "-i", str(d / "cliente"), "-p", str(t["porta"]),
            "-R", f"127.0.0.1:{porta_schermo}:127.0.0.1:{porta_vnc}", f"{t['utente']}@{t['host']}"]


def _schermo_ferma(sch):
    """Ferma VNC e tunnel dello schermo, toglie la password e la chiave copiata. True = tutto fermo davvero."""
    if not sch:
        return True
    fermo = _ferma_pid(sch.get("pid_ssh"), "ssh.exe" if SU_WINDOWS else "")
    vnc = _vnc_exe()
    if vnc and SU_WINDOWS and _pid_vivo(sch.get("pid_vnc"), "tvnserver.exe"):
        try:                                   # prima con le buone: il VNC chiude i collegamenti e l'icona
            subprocess.run([vnc, "-controlapp", "-shutdown"], capture_output=True, timeout=15,
                           stdin=subprocess.DEVNULL, creationflags=_SENZA_FINESTRE)
        except (OSError, subprocess.TimeoutExpired):
            pass
    fermo = _ferma_pid(sch.get("pid_vnc"), "tvnserver.exe" if SU_WINDOWS else "") and fermo
    try:
        _vnc_scrivi_conf({"AcceptRfbConnections": 0}, togli_password=True)
    except OSError:
        fermo = False
    shutil.rmtree(cartella_schermo() / "sessione", ignore_errors=True)
    if sch.get("porta_vnc") and _saluto_vnc(sch["porta_vnc"], 0.5):
        fermo = False
    return fermo and not vnc_password_presente()


def _schermo_avvia(t, porta, adesso, log):
    """Prepara e accende lo schermo per la sessione. Torna (dati senza segreti, segreto cifrato) o (None, "")."""
    pmin, pmax = t["porte"]
    porta_schermo = porta + 1 if porta + 1 <= pmax else porta - 1
    if not pmin <= porta_schermo <= pmax:
        log("schermo non disponibile: fascia di porte troppo stretta")
        return None, ""
    sch = {"porta": porta_schermo, "collegato": False, "in_uso": False, "tentativi": 1, "chiuso": False}
    try:
        codice, chiave = _script("chiave", timeout=30)
        if codice != 0 or not chiave.strip() or len(chiave) > 10000:
            raise ErroreAssistenza("non riesco a leggere la chiave del tunnel")
        d = cartella_schermo() / "sessione"
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        if not SU_WINDOWS:
            os.chmod(d, 0o700)
        fd = os.open(d / "cliente", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="ascii", newline="\n") as f:
            f.write(chiave.replace("\r\n", "\n").strip() + "\n")
        (d / "known_hosts").write_text(t["known_hosts"] + "\n", encoding="utf-8")
        sch["porta_vnc"] = _porta_locale_libera()
        pw = password_schermo()
        _vnc_scrivi_conf({"RfbPort": sch["porta_vnc"], "LoopbackOnly": 1, "AllowLoopback": 1, "AcceptRfbConnections": 1,
                          "AcceptHttpConnections": 0, "UseVncAuthentication": 1, "RunControlInterface": 1,
                          "RemoveWallpaper": 0, "AlwaysShared": 1, "BlockRemoteInput": 0, "QueryAcceptOnTimeout": 0},
                         password=pw)
        segreto = cifra_password_schermo(pw, t["chiave_tecnico"])
        del pw
        sch["pid_vnc"] = _avvia_win([_vnc_exe(), "-run"], d / "vnc.log", finestra=True)
        fine = time.time() + 15
        while time.time() < fine and not _saluto_vnc(sch["porta_vnc"]):
            if not _pid_vivo(sch["pid_vnc"]):
                raise ErroreAssistenza("il server dello schermo (TightVNC) non parte: forse è già aperto")
            time.sleep(0.2)
        if not _saluto_vnc(sch["porta_vnc"]):
            raise ErroreAssistenza("il server dello schermo (TightVNC) non risponde")
        asc = vnc_ascolti(sch["porta_vnc"])
        if asc is not None and not _solo_locale(asc[0]):
            raise ErroreAssistenza("il server dello schermo ascolta anche fuori da questo PC: lo fermo per sicurezza")
        sch["pid_ssh"] = _avvia_win(_comando_ssh_schermo(t, porta_schermo, sch["porta_vnc"]), d / "ssh.log")
        sch["ssh_avviato"] = adesso
        return sch, segreto
    except (ErroreAssistenza, OSError, subprocess.TimeoutExpired, ValueError) as e:
        _schermo_ferma(sch)
        log(f"schermo non disponibile, resta il terminale: {e}")
        return None, ""


def _schermo_autenticato():
    try:
        return "Authenticated to" in (cartella_schermo() / "sessione" / "ssh.log").read_text(errors="replace")
    except OSError:
        return False


def _schermo_controlla(r, tu, adesso):
    """Un giro sullo schermo (il terminale è vivo). Lo schermo non chiude mai la sessione."""
    sch = tu.get("schermo")
    if not sch or sch.get("chiuso"):
        return
    if not _pid_vivo(sch.get("pid_vnc")):
        _schermo_ferma(sch)
        sch.update(chiuso=True, collegato=False, in_uso=False)
        _log(r, adesso, "schermo condiviso chiuso: il server dello schermo non c'è più (il terminale resta)")
        return
    asc = vnc_ascolti(sch["porta_vnc"])
    if asc is not None and not _solo_locale(asc[0]):
        _schermo_ferma(sch)
        sch.update(chiuso=True, collegato=False, in_uso=False)
        _log(r, adesso, "ATTENZIONE: il server dello schermo ascoltava fuori da 127.0.0.1: schermo fermato")
        return
    sch["in_uso"] = bool(asc and asc[1])
    if _pid_vivo(sch.get("pid_ssh")):
        if not sch.get("collegato") and (_schermo_autenticato()
                                         or adesso - float(sch.get("ssh_avviato") or adesso) >= TUNNEL_COLLEGATO_SECONDI):
            sch["collegato"] = True
            _log(r, adesso, f"schermo condiviso pronto (porta {sch['porta']})")
        return
    t = _tunnel_valori()
    if not t:
        return
    if sch.get("collegato"):
        _log(r, adesso, "schermo condiviso: tunnel caduto, lo riapro")
    _ferma_pid(sch.get("pid_ssh"))
    try:
        (cartella_schermo() / "sessione" / "ssh.log").unlink()
    except OSError:
        pass
    sch["pid_ssh"] = _avvia_win(_comando_ssh_schermo(t, sch["porta"], sch["porta_vnc"]),
                                cartella_schermo() / "sessione" / "ssh.log")
    sch.update(collegato=False, in_uso=False, ssh_avviato=adesso, tentativi=int(sch.get("tentativi") or 1) + 1)


# =====================================================================
# Attivazione a un tasto (2026-10-02): crea o completa assistenza.json
# =====================================================================

def _leggi_json(f):
    return json.loads(Path(f).read_text(encoding="utf-8-sig"))


def _modello_tunnel():
    """I valori PUBBLICI del tunnel (indirizzo del server, chiave host, chiave pubblica del tecnico)."""
    for f in (cartella() / "assistenza-tunnel.json", CARTELLA_CC / "assistenza-tunnel.json"):
        if f.exists():
            t = _leggi_json(f)
            if isinstance(t, dict):
                return {k: v for k, v in t.items() if not k.startswith("_")}
    return None


def attiva(distro=None):
    """Il tasto «Attiva assistenza». Se assistenza.json manca lo crea dal modello con la sezione
    «tunnel»; se c'è aggiunge solo quello che manca, senza cambiare i valori che ci sono, e
    accende «abilitata» (è quello che il cliente ha chiesto premendo il tasto).
    I dati del tecnico e del pagamento non si copiano: senza, il pannello non li mostra.
    distro: la distribuzione WSL dove ASSISTENZA.ps1 ha installato i programmi; si scrive solo se
    «wsl_distro» è vuoto (così il pannello usa la stessa, anche se la predefinita di WSL è un'altra)."""
    f = cartella() / "assistenza.json"
    if f.exists():
        try:
            c = _leggi_json(f)
        except (ValueError, OSError) as e:
            raise ErroreAssistenza("assistenza.json non è leggibile: correggilo o cancellalo, poi premi di nuovo «Attiva assistenza»") from e
        if not isinstance(c, dict):
            raise ErroreAssistenza("assistenza.json non è un oggetto JSON: correggilo o cancellalo")
        creato = False
    else:
        c, creato = {}, True
    prima = json.dumps(c, sort_keys=True)
    aggiunti = []
    modello = {}
    for m in (cartella() / "assistenza.esempio.json", CARTELLA_CC / "assistenza.esempio.json"):
        if m.exists():
            try:
                modello = _leggi_json(m)
            except (ValueError, OSError):
                modello = {}
            break
    for k, v in (modello or {}).items():
        if k.startswith("_") or k in ("tecnico", "pagamento", "abilitata") or k in c:
            continue
        c[k] = v
        aggiunti.append(k)
    tun = _modello_tunnel()
    if tun:
        if not isinstance(c.get("tunnel"), dict):
            c["tunnel"] = dict(tun)
            aggiunti.append("tunnel")
        else:
            for k, v in tun.items():
                if k not in c["tunnel"]:
                    c["tunnel"][k] = v
                    aggiunti.append(f"tunnel.{k}")
    if distro and _NOME_DISTRO.fullmatch(str(distro)) and not str(c.get("wsl_distro") or "").strip():
        c["wsl_distro"] = str(distro)
        aggiunti.append("wsl_distro")
    if c.get("abilitata") is not True:
        c["abilitata"] = True
        aggiunti.append("abilitata")
    if json.dumps(c, sort_keys=True) != prima:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _sostituisci(tmp, f)
    _cache_tmate.update(ts=0.0)
    _cache_ssh.update(ts=0.0)
    return {"creato": creato, "aggiunti": aggiunti, "tunnel": bool(_tunnel_valori(c))}


def cosa_manca(c=None):
    """Le cose che mancano per collegarsi, in parole semplici. Lista vuota = pronto."""
    c = config() if c is None else c
    manca = []
    if not c.get("abilitata"):
        manca.append("assistenza spenta (assistenza.json)")
    if _modo() == "wsl" and not os.environ.get("ASSISTENZA_TMATE"):
        prefisso = _prefisso_wsl()
        if not prefisso:
            return manca + ["WSL (il Linux di Windows)"]
        tmate = _tmate_in_wsl(prefisso)
    else:
        tmate = bool(comando_tmate())
    if _tunnel_valori(c):
        if not _ssh_in_linux():
            manca.append("openssh dentro Linux (ssh, sshd, ssh-keygen)" + ("" if tmate else " e tmate"))
        if (SU_WINDOWS or os.environ.get("ASSISTENZA_VNC")) and c.get("schermo", True) is not False:
            if not _vnc_exe():
                manca.append("TightVNC, per lo schermo condiviso (il terminale funziona lo stesso)")
            if not _ssh_win():
                manca.append("ssh di Windows (OpenSSH), per lo schermo condiviso")
    else:
        manca.append("sezione «tunnel» in assistenza.json")
        if not tmate:
            manca.append("tmate dentro Linux")
    return manca


def prepara_windows():
    """Apre la finestra di ASSISTENZA.ps1 -SoloPrepara (WSL, Ubuntu, tmate, openssh). Visibile: può
    chiedere i permessi di amministratore o un riavvio. Fuori da Windows lancia ASSISTENZA_PREPARA (prove)."""
    finto = os.environ.get("ASSISTENZA_PREPARA")
    if finto:
        subprocess.Popen([finto, "-SoloPrepara"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return True
    script = QUI / "ASSISTENZA.ps1"
    if not SU_WINDOWS or not script.exists():
        return False
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-File", str(script),
                      "-SoloPrepara"], creationflags=0x00000010)          # CREATE_NEW_CONSOLE
    return True


# =====================================================================
# Le operazioni
# =====================================================================

def accredita(codice, adesso=None, pubblica=None):
    """Verifica il codice, controlla che non sia già stato usato, accredita i minuti e brucia l'id."""
    c = _serve_abilitata()
    adesso = time.time() if adesso is None else adesso
    dati = verifica_codice(codice, pubblica=pubblica, adesso=adesso)
    with _registro() as r:
        if any(x.get("id") == dati["id"] for x in r["codici"]):
            raise ErroreAssistenza("questo codice è già stato usato: ogni codice vale una volta sola. "
                                   "Chiedi al tecnico un codice nuovo")
        minimo = int(c["ricarica_minima_minuti"])
        if not r["codici"] and dati["min"] < minimo:
            raise ErroreAssistenza(f"la prima ricarica deve essere di almeno {minimo} minuti "
                                   f"({c['ricarica_minima_euro']} €): chiedi al tecnico il codice giusto")
        r["credito_min"] = int(r["credito_min"]) + dati["min"]
        r["codici"].append({"id": dati["id"], "min": dati["min"], "cli": dati.get("cli", ""),
                            "scade": dati["scade"], "accreditato": adesso, "ora": _ora_testo(adesso)})
        _log(r, adesso, f"ricarica di {dati['min']} minuti (codice …{dati['id'][-6:]}); "
                        f"credito ora {r['credito_min']} minuti")
    return stato(adesso)


def avvia_sessione(consenso, adesso=None):
    """Parte solo con consenso esplicito (True) e almeno il primo blocco di credito."""
    c = _serve_abilitata()
    if consenso is not True:
        raise ErroreAssistenza("serve il tuo consenso esplicito: spunta la casella prima di chiedere assistenza")
    adesso = time.time() if adesso is None else adesso
    primo = int(c["primo_blocco_minuti"])
    with _registro() as r:
        if r["attiva"]:
            raise ErroreAssistenza("c'è già una sessione di assistenza attiva")
        if int(r["credito_min"]) < primo:
            raise ErroreAssistenza(f"credito insufficiente: per iniziare servono almeno {primo} minuti "
                                   f"(ne hai {r['credito_min']}). Chiedi al tecnico un codice di ricarica")
        base = {"id": uuid.uuid4().hex[:12], "inizio": adesso, "ora_inizio": _ora_testo(adesso),
                "consenso": adesso, "pagato_fino": adesso + primo * 60,
                "blocchi": [{"inizio": adesso, "min": primo}], "ultimo_blocco": False}
        tun = tunnel_conf(c)
        if tun:
            # 2026-10-02: tunnel verso il server del tecnico, dentro WSL; tmate resta la riserva
            avvisi = []
            try:
                tu = _tunnel_avvia(tun, avvisi)
            except (subprocess.TimeoutExpired, OSError) as e:
                _tunnel_ferma_processi()
                raise ErroreAssistenza("Linux (WSL) non risponde: riprova fra un minuto o premi «Attiva assistenza»") from e
            for x in avvisi:
                _log(r, adesso, x)
            r["credito_min"] = int(r["credito_min"]) - primo
            r["attiva"] = {**base, "modo": "tunnel", "tunnel": tu, "ssh": tu["richiesta"], "ssh_ro": tu["guarda"]}
            _log(r, adesso, f"sessione avviata con il consenso del cliente (tunnel, porta {tu['porta']}"
                            + (f", schermo {tu['schermo']['porta']}" if tu.get("schermo") else "") + "); "
                            f"scalati {primo} minuti, credito ora {r['credito_min']} minuti")
        else:
            if not comando_tmate():
                raise ErroreAssistenza(aiuto_tmate())
            _tmate_ferma()                         # un server rimasto da prima non deve servire la sessione nuova
            try:
                p = _tmate("new-session", "-d", timeout=30)
                if p.returncode != 0:
                    raise ErroreAssistenza(f"tmate non parte: {(p.stderr or p.stdout).strip()[:200]}")
                _custode_avvia()
                _tmate("wait", "tmate-ready", timeout=30)
                ssh = ssh_ro = ""
                for _ in range(20):
                    ssh = _tmate("display", "-p", "#{tmate_ssh}").stdout.strip()
                    ssh_ro = _tmate("display", "-p", "#{tmate_ssh_ro}").stdout.strip()
                    if ssh:
                        break
                    time.sleep(0.5)
                if not ssh:
                    raise ErroreAssistenza("tmate non ha dato l'indirizzo di collegamento: controlla la connessione a internet")
            except subprocess.TimeoutExpired as e:
                _tmate_ferma()
                raise ErroreAssistenza("tmate non riesce a collegarsi (tmate.io): controlla la connessione a internet") from e
            except ErroreAssistenza:
                _tmate_ferma()
                raise
            r["credito_min"] = int(r["credito_min"]) - primo
            r["attiva"] = {**base, "modo": "tmate", "ssh": ssh, "ssh_ro": ssh_ro}
            _log(r, adesso, f"sessione avviata con il consenso del cliente; scalati {primo} minuti, "
                            f"credito ora {r['credito_min']} minuti")
    return stato(adesso)


def _chiudi(r, adesso, motivo, fine=None, rimborso=False):
    """rimborso=True solo per un tunnel che non si è mai stabilito: il servizio non è partito."""
    a = r["attiva"]
    fine = adesso if fine is None else fine
    if a.get("modo") == "tunnel":
        sch = (a.get("tunnel") or {}).get("schermo")
        if sch and not _schermo_ferma(sch):
            r["schermo_resti"] = {k: sch.get(k) for k in ("pid_vnc", "pid_ssh", "porta_vnc")}
            _log(r, adesso, "ATTENZIONE: lo schermo non risulta fermo del tutto; lo riprovo a fermare al prossimo STOP")
        if not _tunnel_ferma_processi():
            r["tunnel_resti"] = True
            _log(r, adesso, "ATTENZIONE: dentro Linux restano processi del tunnel; li riprovo a fermare al prossimo STOP")
    else:
        _tmate_ferma()
    pagati = sum(b["min"] for b in a["blocchi"])
    if rimborso:
        r["credito_min"] = int(r["credito_min"]) + pagati
        _log(r, adesso, f"tunnel mai stabilito: {pagati} minuti tornano a credito")
    usati = max(0, math.ceil((fine - a["inizio"]) / 60))
    r["sessioni"].append({"id": a["id"], "inizio": a["inizio"], "fine": fine, "ora_inizio": _ora_testo(a["inizio"]),
                          "ora_fine": _ora_testo(fine), "minuti_usati": usati, "minuti_pagati": pagati,
                          "blocchi": len(a["blocchi"]), "motivo": motivo, "modo": a.get("modo") or "tmate",
                          "rimborsati": pagati if rimborso else 0})
    r["attiva"] = None
    _log(r, adesso, f"sessione chiusa ({motivo}): {usati} minuti usati, {pagati} pagati in {len(a['blocchi'])} blocchi")


def ferma_sessione(motivo="fermata dal cliente", adesso=None):
    """Lo STOP funziona sempre, anche se il modulo è stato spento nel frattempo."""
    adesso = time.time() if adesso is None else adesso
    with _registro() as r:
        if r["attiva"]:
            a = r["attiva"]
            mai = a.get("modo") == "tunnel" and not (a.get("tunnel") or {}).get("collegato")
            _chiudi(r, adesso, motivo, rimborso=mai)
        else:
            _tmate_ferma()
            if r.get("tunnel_resti") and _tunnel_ferma_processi():   # resti di una chiusura non riuscita
                r["tunnel_resti"] = False
                _log(r, adesso, "fermati i processi del tunnel rimasti da prima")
            if r.get("schermo_resti") and _schermo_ferma(r["schermo_resti"]):
                r["schermo_resti"] = None
                _log(r, adesso, "fermato lo schermo rimasto da prima")
    return stato(adesso)


def tick(adesso=None):
    """Da chiamare ogni 20 s. Scala i blocchi in anticipo, chiude a credito finito.
    Restituisce il testo di un fatto nuovo (per gli eventi del pannello) o None."""
    adesso = time.time() if adesso is None else adesso
    if not _leggi_registro().get("attiva"):
        return None
    c = config()
    scatto = int(c["scatto_minuti"])
    anticipo = float(c["anticipo_scatto_secondi"])
    with _registro() as r:
        a = r["attiva"]
        if not a:
            return None
        if not c["abilitata"]:
            _chiudi(r, adesso, "assistenza spenta nella configurazione")
            return "assistenza: sessione chiusa perché il modulo è stato spento"
        if a.get("modo") == "tunnel":
            if adesso - a["inizio"] >= TETTO_SESSIONE_SECONDI:
                _chiudi(r, adesso, "tetto di 8 ore per sessione")
                return "assistenza: sessione chiusa, raggiunto il tetto di 8 ore"
            esito = _tunnel_controlla(r, a, adesso)
            if esito:
                motivo, rimborso = esito
                _chiudi(r, adesso, motivo, rimborso=rimborso)
                return f"assistenza: sessione chiusa, {motivo}"
        elif not _tmate_vivo():
            _chiudi(r, adesso, "terminale condiviso chiuso fuori dal pannello")
            return "assistenza: il terminale condiviso si è chiuso"
        if adesso > a["pagato_fino"] + 120:
            # il pannello è rimasto fermo (computer in stop): non si fa pagare il tempo di pausa
            _chiudi(r, adesso, "pannello fermo oltre la fine del tempo pagato", fine=a["pagato_fino"])
            return "assistenza: sessione chiusa, il pannello era fermo"
        in_attesa = a.get("modo") == "tunnel" and not (a.get("tunnel") or {}).get("collegato")
        if adesso >= a["pagato_fino"] - anticipo and not a.get("ultimo_blocco") and not in_attesa:
            # (tunnel non ancora stabilito: niente blocco nuovo; a 15 minuti chiude e rimborsa il primo)
            if int(r["credito_min"]) >= scatto:
                r["credito_min"] = int(r["credito_min"]) - scatto
                a["blocchi"].append({"inizio": a["pagato_fino"], "min": scatto})
                a["pagato_fino"] += scatto * 60
                _log(r, adesso, f"scalato un blocco di {scatto} minuti; credito ora {r['credito_min']} minuti")
                return f"assistenza: scalati {scatto} minuti, restano {r['credito_min']}"
            a["ultimo_blocco"] = True
            _log(r, adesso, "credito finito: la sessione si chiude alla fine del blocco già pagato")
            return "assistenza: credito finito, chiusura alla fine del blocco"
        if adesso >= a["pagato_fino"]:
            _chiudi(r, adesso, "credito finito", fine=a["pagato_fino"])
            return "assistenza: sessione chiusa, credito finito"
    return None


def stato(adesso=None):
    adesso = time.time() if adesso is None else adesso
    c = config()
    r = _leggi_registro()
    tariffa = float(c["tariffa_ora_euro"])
    tunnel = bool(tunnel_conf(c))
    ha_tmate = bool(comando_tmate())
    pronto = tunnel or ha_tmate
    uscita = {
        "abilitata": c["abilitata"],
        # «tmate» per il pannello vuol dire «c'è un modo di collegarsi» (tunnel o tmate)
        "tmate": pronto,
        "collegamento": "tunnel" if tunnel else ("tmate" if ha_tmate else None),
        "tmate_via": _modo(),
        "tmate_aiuto": "" if pronto else aiuto_tmate(),
        "schermo": bool(tunnel and schermo_pronto(c)),
        "condizioni": {k: c[k] for k in ("tariffa_ora_euro", "ricarica_minima_euro", "ricarica_minima_minuti",
                                         "scatto_minuti", "scatto_euro", "primo_blocco_minuti")},
        # nessun dato del tecnico o del conto nella pagina: arrivano solo dopo la scelta delle ore (crea_ordine)
        "ore_max": int(c.get("ore_max") or 8),
        "pagamento_pronto": _coordinate_pronte(c),
        "credito_min": int(r["credito_min"]),
        "credito_euro": round(int(r["credito_min"]) * tariffa / 60, 2),
        "primo_codice": not r["codici"],
        "attiva": None,
        "sessioni": list(reversed(r["sessioni"][-10:])),
        "log": list(reversed(r["log"][-20:])),
        "ora_ts": adesso,
    }
    if c.get("errore_config"):
        uscita["errore_config"] = c["errore_config"]
    a = r.get("attiva")
    if a:
        uscita["attiva"] = {"inizio": a["inizio"], "ora_inizio": a["ora_inizio"], "ssh": a["ssh"], "ssh_ro": a["ssh_ro"],
                            "secondi": int(adesso - a["inizio"]), "pagato_fino": a["pagato_fino"],
                            "secondi_pagati_rimasti": max(0, int(a["pagato_fino"] - adesso)),
                            "blocchi": len(a["blocchi"]), "minuti_pagati": sum(b["min"] for b in a["blocchi"]),
                            "ultimo_blocco": bool(a.get("ultimo_blocco")), "modo": a.get("modo") or "tmate"}
        if a.get("modo") == "tunnel":
            tu = a.get("tunnel") or {}
            uscita["attiva"].update(richiesta=tu.get("richiesta", ""), porta=tu.get("porta"),
                                    collegato=bool(tu.get("collegato")), guarda=tu.get("guarda", ""))
            sch = tu.get("schermo")
            uscita["attiva"]["schermo"] = ({"porta": sch.get("porta"), "pronto": bool(sch.get("collegato")) and not sch.get("chiuso"),
                                            "in_uso": bool(sch.get("in_uso")) and not sch.get("chiuso"),
                                            "chiuso": bool(sch.get("chiuso"))} if sch else None)
    return uscita


# =====================================================================
# Ordine: il cliente sceglie le ore e riceve i collegamenti per pagare (30/09/2026)
# =====================================================================

def _segnaposto(v):
    return (not str(v or "").strip()) or "DA COMPILARE" in str(v) or str(v).strip() in ("...", "…")


def _coordinate_pronte(c):
    p, t = c.get("pagamento") or {}, c.get("tecnico") or {}
    return not any(_segnaposto(p.get(k)) for k in ("intestatario", "iban"))


def _cifre(v):
    return re.sub(r"\D", "", str(v or ""))


def _euro(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def _testo_coordinate(o, c):
    p = c.get("pagamento") or {}
    righe = [f"Coordinate per il bonifico · assistenza remota ({o['ore']} {'ora' if o['ore'] == 1 else 'ore'})", ""]
    for et, k in (("Metodo", "metodo"), ("Intestatario", "intestatario"), ("IBAN", "iban"), ("BIC", "bic"),
                  ("Banca", "banca"), ("BIC banca corrispondente", "bic_banca_corrispondente")):
        if not _segnaposto(p.get(k)):
            righe.append(f"{et}: {p[k]}")
    righe += [f"Valuta: {p.get('valuta') or 'EUR'}", f"Importo: {_euro(o['importo'])}", f"Causale: {o['causale']}", "",
              "Dopo il bonifico manda la ricevuta su WhatsApp: ricevi il codice per la ricarica."]
    return "\n".join(righe)


def _collegamenti(o, c):
    from urllib.parse import quote
    t = c.get("tecnico") or {}
    testo = _testo_coordinate(o, c)
    numero = _cifre(t.get("whatsapp"))
    ricevuta = (f"Ricevuta del bonifico per l'assistenza remota. Rif. {o['rif'][:6].upper()} · {o['ore']} "
                f"{'ora' if o['ore'] == 1 else 'ore'} · {_euro(o['importo'])}. Allego la ricevuta.")
    return {
        "mailto": "mailto:?subject=" + quote(f"Coordinate bonifico assistenza (rif. {o['rif'][:6].upper()})", safe="") + "&body=" + quote(testo, safe=""),
        "stampa": f"/assistenza/coordinate/{o['rif']}",
        "whatsapp": (f"https://wa.me/{numero}?text=" + quote(ricevuta, safe="")) if len(numero) >= 8 else None,
    }


def crea_ordine(ore, adesso=None):
    """Il cliente sceglie le ore: torna importo, causale e i tre collegamenti (email, stampa, WhatsApp).
    I dati del conto compaiono solo qui, mai nello stato della pagina."""
    adesso = time.time() if adesso is None else adesso
    c = _serve_abilitata()
    if not _coordinate_pronte(c):
        raise ErroreAssistenza("il pagamento non è ancora configurato su questo computer: scrivi al tecnico")
    try:
        ore = int(ore)
    except (TypeError, ValueError):
        raise ErroreAssistenza("scegli quante ore vuoi (un numero intero)")
    massimo = max(1, int(c.get("ore_max") or 8))
    if not 1 <= ore <= massimo:
        raise ErroreAssistenza(f"puoi scegliere da 1 a {massimo} ore")
    rif = uuid.uuid4().hex[:16]
    base = str((c.get("pagamento") or {}).get("causale") or "assistenza remota").strip()
    o = {"rif": rif, "ore": ore, "minuti": ore * 60, "importo": round(ore * float(c["tariffa_ora_euro"]), 2),
         "causale": f"{base} {rif[:6].upper()}", "ts": adesso, "ora": _ora_testo(adesso)}
    with _registro() as r:
        r.setdefault("ordini", []).append(o)
        r["ordini"] = r["ordini"][-50:]
        _log(r, adesso, f"ordine di {ore} {'ora' if ore == 1 else 'ore'} ({_euro(o['importo'])}), rif. {rif[:6].upper()}")
    return {**{k: o[k] for k in ("rif", "ore", "minuti", "importo", "causale")}, "importo_testo": _euro(o["importo"]),
            **_collegamenti(o, c)}


def pagina_coordinate(rif):
    """La pagina «stampa le coordinate» di un ordine, in HTML da stampare."""
    import html as h
    if not re.fullmatch(r"[0-9a-f]{16}", str(rif or "")):
        raise ErroreAssistenza("collegamento non valido")
    c = _serve_abilitata()
    o = next((x for x in _leggi_registro().get("ordini", []) if x.get("rif") == rif), None)
    if not o:
        raise ErroreAssistenza("ordine non trovato su questo computer")
    corpo = h.escape(_testo_coordinate(o, c))
    return ("<!doctype html><html lang=\"it\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Coordinate per il bonifico</title><style>body{font:16px/1.5 system-ui,sans-serif;max-width:640px;margin:32px auto;padding:0 16px}"
            "pre{white-space:pre-wrap;background:#f4f4f4;padding:16px;border-radius:8px}button{font:inherit;padding:8px 16px}"
            "@media print{button{display:none}}</style></head><body><h1>Coordinate per il bonifico</h1><pre>" + corpo +
            "</pre><button onclick=\"window.print()\">Stampa</button></body></html>")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Assistenza a distanza (lato cliente)")
    sub = ap.add_subparsers(dest="cosa", required=True)
    p = sub.add_parser("attiva")
    p.add_argument("--distro", default="", help="distribuzione WSL preparata da ASSISTENZA.ps1")
    sub.add_parser("manca")
    sub.add_parser("stato")
    p = sub.add_parser("codice")
    p.add_argument("codice")
    p = sub.add_parser("avvia")
    p.add_argument("--consenso", action="store_true", help="il cliente acconsente a questa sessione")
    sub.add_parser("stop")
    sub.add_parser("tick")
    a = ap.parse_args(argv)
    try:
        if a.cosa == "attiva":
            out = attiva(a.distro or None)
        elif a.cosa == "manca":
            manca = cosa_manca()
            print("\n".join(manca) if manca else "PRONTO")
            return 0 if not manca else 1
        elif a.cosa == "stato":
            out = stato()
        elif a.cosa == "codice":
            out = accredita(a.codice)
        elif a.cosa == "avvia":
            out = avvia_sessione(a.consenso)
        elif a.cosa == "stop":
            out = ferma_sessione()
        else:
            out = {"fatto": tick()}
    except ErroreAssistenza as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")    # la console di Windows non è UTF-8
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
