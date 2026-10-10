#!/usr/bin/env python3
"""Collega la memoria condivisa su questo PC: Claude Code, Jarvis e gli altri harness leggono e scrivono nello stesso posto.

    python strumenti\\collega_memoria.py                         guarda e racconta, non scrive niente
    python strumenti\\collega_memoria.py --applica               crea la struttura e i collegamenti che mancano
    python strumenti\\collega_memoria.py --applica --zitto       come sopra, stampa solo avvisi ed errori (per i ganci)

Opzioni:
    --memoria <cartella>   la memoria condivisa (di base: risposte-avvio.json, poi percorsi.json, poi
                           %USERPROFILE%\\Jarvis-Memoria). Può stare in OneDrive o in un vault Obsidian che esiste già.
    --spazi "A,B"          gli spazi di lavoro (cartelle in cima alla memoria). Di base da risposte-avvio.json.
    --harness "codex,gemini"  scrive il file d'ingresso anche nella cartella di quell'harness (~/.codex, ~/.gemini).
    --con-sessioni         copia anche le trascrizioni delle sessioni di Claude Code (copia sincronizzata, a senso unico).
    --home <cartella>      la cartella utente (per le prove: una HOME finta che imita Windows).

Cosa fa con --applica (si può rilanciare: non duplica niente e NON CANCELLA MAI niente):
  1. struttura:  <memoria>\\Comune  <memoria>\\<spazio>  <memoria>\\Diario  <memoria>\\Report  <memoria>\\Sessioni
                 <memoria>\\Claude\\projects  <memoria>\\Claude\\piani  (+ Stato.md per ogni spazio)
  2. collega ogni %USERPROFILE%\\.claude\\projects\\<progetto>\\memory a <memoria>\\Claude\\projects\\<progetto>\\memory
     con una GIUNZIONE (mklink /J: non serve l'amministratore). Se la cartella ha già dei file li UNISCE alla memoria
     condivisa (un file con lo stesso nome e contenuto diverso si tiene con il suffisso .da-<pc>), rinomina l'originale
     in memory.prima-del-collegamento-<data> e solo dopo crea la giunzione. Lo dichiara riga per riga.
  3. collega la cache dei piani di Claude Code (~\\.claude\\plans) a <memoria>\\Claude\\piani, con la stessa regola.
  4. file d'ingresso per gli altri harness nella memoria: AGENTS.md (Codex, Cursor e altri), GEMINI.md, CLAUDE.md.
  5. registro di tutto in %USERPROFILE%\\.jarvis\\percorsi.json (lo leggono i ganci, Jarvis e gli agenti).
  6. cerca segreti dentro la memoria condivisa e li elenca (percorso e riga, mai il valore).
Sulle macchine che non sono Windows (prove) la giunzione diventa un collegamento simbolico.
"""
import argparse
import filecmp
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROGETTI = "Claude/projects"      # stessi nomi del Mac (2026-10-10)
PIANI = "Claude/piani"
SESSIONI_CC = "Claude/sessioni"
CARTELLE_FISSE = ("Comune", "Diario", "Report", "Sessioni")


def guardia_prova(home):
    """Prove: con JARVIS_PROVA=1 si scrive solo in una casa sotto JARVIS_PROVA_RADICE (una o più cartelle separate da
    os.pathsep), mai nella casa vera."""
    if os.environ.get("JARVIS_PROVA") == "1":
        radice = os.environ.get("JARVIS_PROVA_RADICE", "")
        h = os.path.realpath(str(home))
        if not radice or not any((h + os.sep).startswith(os.path.realpath(r).rstrip(os.sep) + os.sep) for r in radice.split(os.pathsep) if r):
            sys.exit(f"JARVIS_PROVA=1: la casa {h} non è sotto JARVIS_PROVA_RADICE ({radice or 'non impostata'}): mi fermo")


def adesso():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def leggi_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def scrivi_se_manca(p: Path, testo: str, righe: list, applica: bool):
    if p.exists():
        return
    if applica:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(testo, encoding="utf-8")
        righe.append(f"OK    creato {p}")
    else:
        righe.append(f"MANCA {p}")


def nome_spazio(s: str) -> str:
    """Un nome di cartella valido su Windows: niente < > : \" / \\ | ? * e niente spazi in coda."""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", str(s)).strip().strip(".")
    return s or "Generale"


def e_collegamento(p: Path) -> bool:
    """Vero per un collegamento simbolico e per una giunzione di Windows."""
    if p.is_symlink():
        return True
    is_junction = getattr(os.path, "isjunction", None)      # Python 3.12+
    if is_junction and is_junction(p):
        return True
    if sys.platform == "win32" and p.exists():
        try:
            return bool(os.lstat(p).st_file_attributes & 0x400)   # FILE_ATTRIBUTE_REPARSE_POINT
        except (OSError, AttributeError):
            return False
    return False


def stesso_posto(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def crea_collegamento(dest: Path, src: Path):
    """dest diventa un collegamento alla cartella src. Windows: giunzione (mklink /J), senza amministratore."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(dest), str(src)], capture_output=True, text=True)
        if r.returncode != 0:
            raise OSError((r.stdout + r.stderr).strip() or f"mklink /J uscita {r.returncode}")
    else:
        os.symlink(src, dest, target_is_directory=True)


def unisci(da: Path, a: Path, righe: list) -> int:
    """Copia in «a» i file di «da» che non ci sono. Stesso nome e contenuto diverso: si tengono tutti e due
    (la copia di questo PC prende il suffisso .da-<pc>). Torna il numero di file copiati. Non cancella niente."""
    pc = re.sub(r"[^A-Za-z0-9-]", "", socket.gethostname())[:20] or "pc"
    copiati = 0
    for f in sorted(da.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(da)
        t = a / rel
        if not t.exists():
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            copiati += 1
        elif not filecmp.cmp(f, t, shallow=False):
            doppio = t.with_name(f"{t.stem}.da-{pc}{t.suffix}")
            if not doppio.exists():
                shutil.copy2(f, doppio)
                copiati += 1
                righe.append(f"AVVISO {rel}: nella memoria condivisa c'era già un file diverso, tenuti tutti e due ({doppio.name})")
    return copiati


def collega_cartella(locale: Path, condivisa: Path, applica: bool, righe: list, registro: list):
    """La cartella locale (di Claude Code) diventa una giunzione alla cartella nella memoria condivisa."""
    voce = {"locale": str(locale), "condivisa": str(condivisa), "tipo": "giunzione" if sys.platform == "win32" else "symlink"}
    if e_collegamento(locale):
        if stesso_posto(locale, condivisa):
            righe.append(f"OK    {locale} è già collegata")
            voce["stato"] = "collegata"
        else:
            righe.append(f"AVVISO {locale} è un collegamento che porta altrove: non lo tocco")
            voce["stato"] = "porta altrove"
        registro.append(voce)
        return
    if not applica:
        righe.append(f"MANCA {locale} → {condivisa}" + (" (ha già dei file: verranno uniti, non cancellati)" if locale.is_dir() and any(locale.iterdir()) else ""))
        voce["stato"] = "da collegare"
        registro.append(voce)
        return
    condivisa.mkdir(parents=True, exist_ok=True)
    try:
        if locale.exists():
            if locale.is_dir():
                n = unisci(locale, condivisa, righe)
                parcheggio = locale.with_name(f"{locale.name}.prima-del-collegamento-{datetime.now():%Y%m%d-%H%M%S}")
                locale.rename(parcheggio)
                righe.append(f"OK    {locale}: {n} file uniti alla memoria condivisa, l'originale resta in {parcheggio.name}")
                voce["parcheggio"] = str(parcheggio)
            else:
                righe.append(f"AVVISO {locale} è un file, non una cartella: non lo tocco")
                voce["stato"] = "file"
                registro.append(voce)
                return
        crea_collegamento(locale, condivisa)
        righe.append(f"OK    collegata {locale} → {condivisa}")
        voce["stato"] = "collegata"
    except Exception as e:  # noqa: BLE001 — si racconta e si va avanti
        righe.append(f"ERRORE non riesco a collegare {locale}: {e}")
        voce["stato"] = f"errore: {e}"
        if not locale.exists() and "parcheggio" in voce:     # rimette a posto l'originale
            try:
                Path(voce["parcheggio"]).rename(locale)
                righe.append(f"OK    rimessa a posto {locale}")
            except OSError:
                pass
    registro.append(voce)


def copia_sessioni(projects: Path, dest: Path, righe: list) -> int:
    """Copia sincronizzata a senso unico delle trascrizioni (*.jsonl): solo i file nuovi o cambiati."""
    n = 0
    for f in projects.glob("*/*.jsonl"):
        t = dest / f.parent.name / f.name
        try:
            if t.exists() and t.stat().st_size == f.stat().st_size and t.stat().st_mtime >= f.stat().st_mtime:
                continue
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            n += 1
        except OSError as e:
            righe.append(f"AVVISO sessione {f.name} non copiata: {e}")
    return n


def cerca_segreti(cartella: Path, massimo=20):
    """I segreti stanno solo in %USERPROFILE%\\.env.jarvis, mai nella memoria. Elenca percorso e riga, mai il valore."""
    esempio = re.compile(r"\.(example|esempio|sample)$", re.I)
    nomi = re.compile(r"(^\.env($|\.)|\.pem$|\.key$|\.keystore$|\.jks$|\.pfx$|\.p12$|^id_rsa|^id_ed25519)", re.I)
    forme = [("token/chiave", re.compile(r"(?<![A-Za-z0-9])(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
                                         r"|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|AKIA[0-9A-Z]{16}"
                                         r"|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,})")),
             ("chiave privata", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"))]
    trovati = []
    for r, dirs, files in os.walk(cartella):
        dirs[:] = [d for d in dirs if d not in (".git", ".obsidian", "node_modules", "sessioni")]
        for f in files:
            p = Path(r) / f
            if esempio.search(f):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if nomi.search(f):
                trovati.append(f"{p.relative_to(cartella)}  (nome da segreto)")
            elif p.suffix.lower() in (".md", ".txt", ".json", ".py", ".env", ".yml", ".yaml", ".ps1") and st.st_size < 300_000:
                try:
                    for n, riga in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        for etichetta, rx in forme:
                            if rx.search(riga):
                                trovati.append(f"{p.relative_to(cartella)}:{n}  ({etichetta})")
                                break
                except OSError:
                    pass
            if len(trovati) >= massimo:
                return trovati
    return trovati


def ingresso(nome_file: str, harness: str, nome_assistente: str, utente: str) -> str:
    return (f"# Memoria condivisa ({harness})\n\n"
            f"Questa cartella è la memoria condivisa di {utente or 'chi usa questo PC'}: la usano {nome_assistente}, Claude Code e gli "
            f"altri harness collegati. Leggi prima `Comune/Memoria.md`, poi `<spazio>/Stato.md` dello spazio su cui lavori.\n\n"
            "- Una sola fonte per ogni fatto: correggi la nota che c'è, non aggiungere doppioni.\n"
            "- Data e ora sempre (AAAA-MM-GG HH:MM).\n"
            "- Nessun segreto qui dentro: chiavi e token stanno solo in `%USERPROFILE%\\.env.jarvis`.\n"
            "- Gli spazi non si mescolano: ogni progetto scrive nel suo.\n"
            "- `<spazio>/Stato.md` lo aggiorna da solo il gancio di Claude Code (FATTO, DA FARE, ERRORI, data e ora).\n"
            f"\n(file creato da collega_memoria.py: {nome_file})\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--applica", action="store_true")
    ap.add_argument("--zitto", action="store_true")
    ap.add_argument("--memoria", default="")
    ap.add_argument("--spazi", default=None)
    ap.add_argument("--harness", default=None)
    ap.add_argument("--con-sessioni", action="store_true")
    ap.add_argument("--home", default="")
    ap.add_argument("--solo-progetti", action="store_true", help="collega solo le memorie di progetto nuove (gancio di fine sessione)")
    a = ap.parse_args(argv)

    home = Path(a.home).expanduser() if a.home else Path.home()
    jarvis_cfg = home / ".jarvis"
    guardia_prova(home)
    risposte = leggi_json(jarvis_cfg / "risposte-avvio.json")
    percorsi_vecchi = leggi_json(jarvis_cfg / "percorsi.json")
    utente_json = {}
    for cand in (home / "jarvis" / "utente.json",):
        utente_json = leggi_json(cand) or utente_json

    memoria = a.memoria or (risposte.get("memoria") or {}).get("cartella", "") or percorsi_vecchi.get("memoria", "")
    memoria = Path(os.path.expandvars(memoria)).expanduser() if memoria else home / "Jarvis-Memoria"
    if a.spazi is not None:
        spazi = [s.strip() for s in a.spazi.split(",") if s.strip()]
    else:
        spazi = [s.get("nome", "") if isinstance(s, dict) else str(s) for s in (risposte.get("spazi") or [])]
        spazi = [s for s in spazi if s] or [x.get("nome") for x in percorsi_vecchi.get("spazi", []) if x.get("nome")]
    spazi = [nome_spazio(s) for s in spazi]       # si parte da zero: le cartelle degli spazi le crea crea_progetto.py
    harness = [h.strip().lower() for h in (a.harness.split(",") if a.harness is not None else (risposte.get("harness") or [])) if h and h.strip()]
    nome_assistente = (risposte.get("assistente") or {}).get("nome") or utente_json.get("nome_assistente") or "Jarvis"
    utente = (risposte.get("utente") or {}).get("nome") or utente_json.get("nome") or ""

    righe, registro = [], []
    righe.append(f"{'OK   ' if memoria.is_dir() else 'MANCA'} memoria condivisa: {memoria}")

    # 1. struttura
    for d in (*CARTELLE_FISSE, *spazi, PROGETTI, PIANI):
        p = memoria / d
        if not p.is_dir():
            if a.applica:
                p.mkdir(parents=True, exist_ok=True)
                righe.append(f"OK    creata {p}")
            else:
                righe.append(f"MANCA {p}")
    scrivi_se_manca(memoria / "Comune" / "Memoria.md",
                    f"# Memoria\n\n*Creata: {adesso()}*\n\nPorta d'ingresso della memoria condivisa. Spazi: "
                    + (", ".join(f"[[{s}/Stato|{s}]]" for s in spazi) or "nessuno ancora (nascono con i progetti: ogni spazio ha <spazio>/Stato.md)")
                    + ".\n\n## Dove sta cosa\n\n- Diario del giorno: `Diario/AAAA-MM-GG.md` (Fatto, Da fare, Errori da non ripetere)\n"
                    "- Report: `Report/` · Sessioni: `Sessioni/` · memoria automatica di Claude Code: `Claude/projects/`\n\n## Profilo\n\n- Nome: " + (utente or "(da scrivere)")
                    + f"\n- Assistente: {nome_assistente}\n\n## Regole\n\n- Prove, non ipotesi.\n- Conferma prima dell'irreversibile.\n", righe, a.applica)
    for s in spazi:
        scrivi_se_manca(memoria / s / "Stato.md",
                        f"# Stato — {s}\n\n*Aggiornato: {adesso()} (creato da collega_memoria.py)*\n\n## FATTO\n\n## DA FARE\n\n## ERRORI\n\n## Ultime sessioni\n",
                        righe, a.applica)

    # 2. memorie dei progetti di Claude Code
    projects = home / ".claude" / "projects"
    if projects.is_dir():
        for prog in sorted(p for p in projects.iterdir() if p.is_dir() and not p.name.startswith(".")):
            collega_cartella(prog / "memory", memoria / PROGETTI / prog.name / "memory", a.applica, righe, registro)
    else:
        righe.append(f"AVVISO {projects} non c'è ancora: si crea alla prima sessione di Claude Code (poi rilancia, o lo fa il gancio)")
    # 3. cache dei piani
    if not a.solo_progetti:
        collega_cartella(home / ".claude" / "plans", memoria / PIANI, a.applica, righe, registro)
    # sessioni (facoltativo)
    if a.con_sessioni and projects.is_dir() and a.applica:
        n = copia_sessioni(projects, memoria / SESSIONI_CC, righe)
        righe.append(f"OK    trascrizioni copiate: {n} nuove o cambiate (copia a senso unico)")

    # 4. file d'ingresso per gli harness
    for nome, h in (("AGENTS.md", "Codex, Cursor e altri harness"), ("GEMINI.md", "Gemini CLI"), ("CLAUDE.md", "Claude Code")):
        scrivi_se_manca(memoria / nome, ingresso(nome, h, nome_assistente, utente), righe, a.applica)
    sezione = f"\n## Memoria condivisa (collega_memoria.py)\nLeggi `{memoria / 'AGENTS.md'}` e la memoria in `{memoria}`.\n"
    for h, f in (("codex", home / ".codex" / "AGENTS.md"), ("gemini", home / ".gemini" / "GEMINI.md")):
        if h not in harness:
            continue
        attuale = f.read_text(encoding="utf-8-sig") if f.exists() else ""
        if "## Memoria condivisa (collega_memoria.py)" in attuale:
            righe.append(f"OK    {f} punta già alla memoria condivisa")
        elif a.applica:
            f.parent.mkdir(parents=True, exist_ok=True)
            if f.exists():
                shutil.copy2(f, f.with_name(f"{f.name}.bak-jarvis-{datetime.now():%Y%m%d-%H%M%S}"))
            f.write_text(attuale.rstrip("\n") + "\n" + sezione, encoding="utf-8")
            righe.append(f"OK    {f}: aggiunta la sezione della memoria condivisa (copia di sicurezza fatta)")
        else:
            righe.append(f"MANCA {f}: sezione della memoria condivisa")

    # 6. segreti
    if memoria.is_dir():
        segreti = cerca_segreti(memoria)
        if segreti:
            righe.append(f"ERRORE segreti nella memoria ({len(segreti)}): stanno solo in %USERPROFILE%\\.env.jarvis. Da togliere:")
            righe += ["      " + x for x in segreti]
        else:
            righe.append("OK    nella memoria nessun segreto")

    # 5. registro
    percorsi = {"aggiornato": adesso(), "memoria": str(memoria), "comune": str(memoria / "Comune"),
                "repo": str(Path(__file__).resolve().parent.parent),
                "spazi": [{"nome": s, "stato": str(memoria / s / "Stato.md"),
                           "cartelle": next((x.get("cartelle", []) for x in (risposte.get("spazi") or []) if isinstance(x, dict) and nome_spazio(x.get("nome", "")) == s), [])}
                          for s in spazi],
                "diario": str(memoria / "Diario"), "report": str(memoria / "Report"), "sessioni": str(memoria / "Sessioni"),
                "harness": harness, "collegamenti": registro,
                # compatibilità con i lettori di prima (2026-10-05)
                "vault": percorsi_vecchi.get("vault", ""),
                "memoria_claude_code": [v["condivisa"] for v in registro if v.get("stato") == "collegata" and "progetti" in v["condivisa"]],
                "memoria_jarvis": [str(m) for m in sorted((home / ".claude").glob("memoria-*")) if m.is_dir()]}
    f = jarvis_cfg / "percorsi.json"
    if a.applica:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(percorsi, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        righe.append(f"OK    scritto {f}")
    else:
        righe.append(f"{'OK   ' if f.exists() else 'MANCA'} {f}" + ("" if f.exists() else " (--applica lo scrive)"))

    errori = [r for r in righe if r.startswith("ERRORE")]
    for r in righe:
        if not a.zitto or not r.startswith("OK"):
            print(r)
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
