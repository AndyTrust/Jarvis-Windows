#!/usr/bin/env python3
"""Controllo di pulizia della distribuzione: fallisce se resta un dato personale, un segreto o un indirizzo privato.

    python CONTROLLA-PULIZIA.py            controlla i file che entrerebbero in git (tracciati + nuovi non ignorati)
    python CONTROLLA-PULIZIA.py --tutti    controlla anche i file ignorati da .gitignore (tranne .git e .venv)

Cosa cerca (2026-10-10, versione rinforzata):
  1. MARCATORI personali: nomi, aziende, servizi e agenti di chi ha scritto il programma (lista sotto).
  2. SEGRETI: chiavi sk-, ghp_/gho_/github_pat_, AIza, xox?-, AKIA, token JWT (eyJ...eyJ...), chiavi private PEM.
  3. INDIRIZZI IP pubblici (gli IP privati, di loopback e di documentazione sono ammessi).
  4. MAIL: ogni indirizzo che non sia di esempio (example.com/org/net, *.invalid, noreply del codice ospite).
  5. TELEFONI: numeri con prefisso internazionale (+39 …) o cellulari italiani scritti per intero.
  6. PERCORSI personali: /Users/<nome>/, /home/<nome>/, C:\\Users\\<nome>\\ (ammessi i segnaposto <utente>, Nome, Mario…).
  7. NOMI DI FILE con un marcatore.
  8. PARTENZA A ZERO (2026-10-10): nessun progetto, spazio, azienda o capogruppo inventato o precaricato (lista DA_ZERO,
     controllata sulla riga intera, senza eccezioni). Gli esempi generici si scrivono come <nome-progetto>.
Le eccezioni approvate stanno in CONTROLLA-PULIZIA-ammessi.txt (una regex per riga): si tolgono dalla riga prima di
cercare. Esce con 1 se trova qualcosa (e stampa file:riga e il tipo, MAI il valore intero di un segreto).
"""
import ipaddress
import os
import re
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent
MARCATORI = (r"telegram|vps|hostinger|grok|jarviboss|jboss|\bboss\b|andr[e]a|man[a]i|m[a]meli|140 ?gr[a]mmi|140gr[a]mmi|priv[a]te ?jet"
             r"|s[a]rdinia|alpine ?priv[a]te|\bspj\b|giusepp[e]|odoo|supabase|asterisk|thunderbird|postino|andyTr[u]st|ital[o]marziano"
             r"|instinct\.py|inoltra.instinct|patrimoni[a]_|onedrive-personale|\bceo\b"
             r"|azienda (uno|due)|progetto-b\b|titolare (brain|personale)|\bmy-?140|crm-?140|-140\b|_140\b|air-dynamic|crm1-odoo"
             r"|locale-onedrive|segreti-dal-vault|chiavi-app-android|passbolt")
DA_ZERO = (r"azienda[ _-]?(uno|due|tre)|jarvis[ _-]brain|progetto[ _-](uno|due|tre|crm)|vita personale|patrimonio"
           r"|prodotto-uno|jarvis-titolare|titolare brain|agenti-utente|archivista|crm-uno|sito-uno|cambusa"
           r"|\bceo-[a-z]|\bvice-ceo|\bfpmarket|\bpienissimo|\bcrm\b|n8n|instinct|/opt/jarvis-vps|\bg140\b|db-140"
           r"|vps-shell|passbolt|giuseppe|finocchiett|due-due|due-gestionale|garante-dati|fase 2: serve")
SEGRETI = [
    ("chiave sk-", r"(?<![A-Za-z0-9])sk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    ("token GitHub", r"(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    ("chiave Google", r"AIza[0-9A-Za-z_-]{35}"),
    ("token Slack", r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    ("chiave AWS", r"AKIA[0-9A-Z]{16}"),
    ("token JWT", r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}"),
    ("chiave privata", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
MAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MAIL_OK = re.compile(r"(@(example\.(com|org|net)|[a-z0-9.-]+\.invalid|anthropic\.com|users\.noreply\.github\.com)$"
                     r"|^[a-z]@[a-z]\.[a-z]{2,3}$|^FINT|\.service$)", re.I)      # x@y.it delle prove, FINTO..., unità systemd
TELEFONO = re.compile(r"(?<![\w.])(?:\+|00)\d{2}[\s.-]?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{2,4}(?![\w.])|(?<![\w.])3\d{2}[\s.-]?\d{7}(?![\w.])")
IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\w.])")
PERCORSO = re.compile(r"(/Users/|/home/|[A-Za-z]:\\\\?Users\\\\?)([A-Za-z0-9._-]+)", re.I)
PERCORSO_OK = {"<utente>", "utente", "nome", "yourname", "mario", "public", "default", "shared", "runner", "user", "username",
               "tuonome", "tu", "esempio", "x", "foo", "you", "me", "admin", "vscode", "root", "jarvis", "..."}
FILE_SALTATI = {"CONTROLLA-PULIZIA.py", "CONTROLLA-PULIZIA-ammessi.txt"}
ESTENSIONI_BINARIE = {".png", ".webp", ".jpg", ".jpeg", ".gif", ".ico", ".onnx", ".bin", ".pdf", ".zip", ".woff", ".woff2", ".ttf"}

_F_AMMESSI = RADICE / "CONTROLLA-PULIZIA-ammessi.txt"
AMMESSI = [re.compile(r, re.I) for r in (_F_AMMESSI.read_text(encoding="utf-8").splitlines() if _F_AMMESSI.exists() else [])
           if r.strip() and not r.startswith("#")]


def elenco(tutti: bool):
    try:
        args = ["git", "-C", str(RADICE), "ls-files", "-co"] + ([] if tutti else ["--exclude-standard"])
        out = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()
        return sorted(set(out))
    except (subprocess.CalledProcessError, FileNotFoundError):
        res = []
        for r, dirs, files in os.walk(RADICE):
            dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__", "node_modules")]
            res += [str((Path(r) / f).relative_to(RADICE)).replace("\\", "/") for f in files]
        return sorted(res)


def togli_ammessi(testo: str) -> str:
    for a in AMMESSI:
        testo = a.sub("", testo)
    return testo


def ip_pubblico(s: str) -> bool:
    try:
        ip = ipaddress.ip_address(s)
    except ValueError:
        return False
    if ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_reserved or ip.is_multicast or ip.is_link_local:
        return False
    if any(ip in ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")):
        return False
    return str(ip) not in ("1.1.1.1", "8.8.8.8", "8.8.4.4", "9.9.9.9")      # DNS pubblici citati nelle prove di rete


def controlla_riga(riga: str):
    trovati = []
    pulita = togli_ammessi(riga)
    m = re.search(MARCATORI, pulita, re.I)
    if m:
        trovati.append(f"marcatore «{m.group(0)}»")
    z = re.search(DA_ZERO, riga, re.I)          # sulla riga intera: qui non valgono le eccezioni
    if z:
        trovati.append(f"nome precaricato «{z.group(0)}» (si parte da zero)")
    for nome, rx in SEGRETI:
        if re.search(rx, pulita):
            trovati.append(nome)
    for ip in IPV4.findall(pulita):
        if ip_pubblico(ip):
            trovati.append(f"IP pubblico {ip}")
    for mail in MAIL.findall(pulita):
        if not MAIL_OK.search(mail) and not re.search(r"\.(png|jpg|webp|svg|js|css|py)$", mail, re.I):
            trovati.append(f"mail {mail}")
    if TELEFONO.search(pulita):
        trovati.append("numero di telefono")
    for _, nome in PERCORSO.findall(pulita):
        if nome.lower() not in PERCORSO_OK and not nome.startswith(("$", "%", "<", "@@")):
            trovati.append(f"percorso personale …{nome}")
    return trovati


def main():
    tutti = "--tutti" in sys.argv
    righe, nomi = [], []
    for rel in elenco(tutti):
        if rel in FILE_SALTATI or rel.startswith((".venv/", ".git/")):
            continue
        if re.search(MARCATORI, togli_ammessi(rel), re.I) or re.search(DA_ZERO, rel, re.I):
            nomi.append(rel)
        p = RADICE / rel
        if p.suffix.lower() in ESTENSIONI_BINARIE or not p.is_file():
            continue
        try:
            testo = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, riga in enumerate(testo.splitlines(), 1):
            for t in controlla_riga(riga):
                righe.append(f"{rel}:{n}: {t}")
    for r in nomi:
        print("FILE  ", r)
    for r in righe:
        print(r[:200])
    print(f"\n{len(nomi)} nomi di file e {len(righe)} righe da guardare")
    return 1 if (nomi or righe) else 0


if __name__ == "__main__":
    sys.exit(main())
