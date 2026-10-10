#!/usr/bin/env python3
"""Collega Jarvis a Claude Code sul PC dell'utente, senza toccare il resto delle sue impostazioni.

  installa_claude.py --jarvis <cartella jarvis> [--home <casa>] [--claude-md <file con la sezione da aggiungere>]

Fa, in modo ripetibile (si può rilanciare senza duplicare niente):
  1. copia di sicurezza di ~/.claude/settings.json (settings.json.bak-jarvis-AAAAMMGG-HHMMSS)
  2. aggiunge i ganci: SessionStart (carica Jarvis e la memoria dell'utente) e quelli della lavagna in tempo reale
     (UserPromptSubmit, Stop, SubagentStop, PreToolUse/PostToolUse) e, se copiati, la guardia dei comandi e quella delle
     connessioni (PreToolUse) — riconosce i propri per il nome dello script,
     quindi i ganci dell'utente restano com'erano
  3. aggiunge a ~/.claude/CLAUDE.md la sezione «Chi usa questo PC», se non c'è già
  4. (2026-10-10) ganci della memoria automatica: stato_avanzamento.py (Stop, PreCompact, SessionEnd → <memoria>/<spazio>/
     Stato.md e diario del giorno) e conferma_salva.py (UserPromptSubmit sulle conferme → giro + aggiorna-memoria). Le guardie valgono per Bash e per PowerShell (matcher «Bash|PowerShell»).
  --python <exe>  l'interprete dei ganci (di base «python»; l'installatore passa quello di .venv, mai «python3»)
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


def guardia_prova(home):
    """Prove: con JARVIS_PROVA=1 si scrive solo in una casa sotto JARVIS_PROVA_RADICE (una o più cartelle separate da
    os.pathsep), mai nella casa vera."""
    if os.environ.get("JARVIS_PROVA") == "1":
        radice = os.environ.get("JARVIS_PROVA_RADICE", "")
        h = os.path.realpath(str(home))
        if not radice or not any((h + os.sep).startswith(os.path.realpath(r).rstrip(os.sep) + os.sep) for r in radice.split(os.pathsep) if r):
            sys.exit(f"JARVIS_PROVA=1: la casa {h} non è sotto JARVIS_PROVA_RADICE ({radice or 'non impostata'}): mi fermo")

ap = argparse.ArgumentParser()
ap.add_argument("--jarvis", required=True)
ap.add_argument("--home", default=str(Path.home()))
ap.add_argument("--claude-md", default="")
ap.add_argument("--python", default="python")
a = ap.parse_args()

HOME = Path(a.home)
guardia_prova(HOME)
JARVIS = Path(a.jarvis)
CLAUDE = HOME / ".claude"
CLAUDE.mkdir(parents=True, exist_ok=True)
SETTINGS = CLAUDE / "settings.json"
sl = JARVIS.as_posix()
# interprete dei ganci: un percorso con spazi va fra virgolette
PY = f'"{Path(a.python).as_posix()}"' if (" " in a.python or "/" in a.python or "\\" in a.python) else a.python

if SETTINGS.exists():
    shutil.copy2(SETTINGS, SETTINGS.with_name(f"settings.json.bak-jarvis-{datetime.now():%Y%m%d-%H%M%S}"))
    try:
        s = json.loads(SETTINGS.read_text(encoding="utf-8-sig"))
    except ValueError as e:
        sys.exit(f"~/.claude/settings.json non è un JSON valido ({e}): non lo tocco. Correggilo e rilancia.")
else:
    s = {}
hooks = s.setdefault("hooks", {})


def gancio(script, evento=""):
    cmd = f'{PY} "{script}"' + (f" {evento}" if evento else "")
    return {"type": "command", "command": cmd, "timeout": 10 if evento else 15}


def firma(cmd):
    """Il gancio si riconosce dal nome dello script e dagli argomenti, non dall'interprete (python, .venv, py):
    rilanciando l'installazione con un altro interprete il gancio si aggiorna invece di raddoppiare."""
    import re
    m = re.search(r'([\w.-]+\.py)"?(.*)$', cmd or "")
    return (m.group(1), m.group(2).strip()) if m else (cmd, "")


def imposta(nome, voce, matcher=None):
    """Aggiunge la voce in hooks[nome]; se c'è già un gancio con la stessa firma ne aggiorna comando, timeout e matcher."""
    gruppi = hooks.setdefault(nome, [])
    for g in gruppi:
        for h in g.get("hooks", []):
            if firma(h.get("command")) == firma(voce["command"]):
                cambiato = h.get("command") != voce["command"] or (matcher and g.get("matcher") != matcher)
                h["command"], h["timeout"] = voce["command"], voce["timeout"]
                if matcher and len(g.get("hooks", [])) == 1:
                    g["matcher"] = matcher
                return "aggiornato" if cambiato else "già presente"
    gruppo = {"hooks": [voce]}
    if matcher:
        gruppo = {"matcher": matcher, "hooks": [voce]}
    gruppi.append(gruppo)
    return "aggiunto"


avvio = f"{HOME.as_posix()}/.claude/hooks/jarvis_avvio.py"
stato = f"{sl}/.claude/hooks/jarvis_status.py"
esiti = {
    "SessionStart": imposta("SessionStart", gancio(avvio)),
    "UserPromptSubmit": imposta("UserPromptSubmit", gancio(stato, "prompt")),
    "Stop": imposta("Stop", gancio(stato, "stop")),
    "SubagentStop": imposta("SubagentStop", gancio(stato, "sub-stop")),
    "PreToolUse(Agent)": imposta("PreToolUse", gancio(stato, "pre-agent"), "Agent"),
    "PostToolUse(Agent)": imposta("PostToolUse", gancio(stato, "post-agent"), "Agent"),
    "PostToolUse(*)": imposta("PostToolUse", gancio(stato, "post"), "*"),
}
# 2026-10-05: i ganci di sicurezza, se l'installatore li ha copiati (valgono anche con il bypass dei permessi)
guardia = CLAUDE / "hooks" / "guardia_comandi.py"
if guardia.exists():
    esiti["PreToolUse(Bash) guardia"] = imposta("PreToolUse", {"type": "command", "command": f'{PY} "{guardia.as_posix()}"', "timeout": 5}, "Bash|PowerShell")
conn = CLAUDE / "hooks" / "connessioni_guardia.py"
if conn.exists():
    esiti["PreToolUse(Bash|mcp) connessioni"] = imposta("PreToolUse", {"type": "command", "command": f'{PY} "{conn.as_posix()}"', "timeout": 5}, "Bash|PowerShell|mcp__.*")
# 2026-10-10: lo stato di avanzamento degli spazi (stato_avanzamento.py) e il diario del giorno con la spinta ad
# aggiorna-memoria (conferma_salva.py) si aggiornano da soli. Il vecchio stato_progetti.py, se c'era, esce.
for nome_ev in ("Stop", "PreCompact", "SessionEnd"):
    for g in hooks.get(nome_ev, []):
        g["hooks"] = [h for h in g.get("hooks", []) if "stato_progetti.py" not in (h.get("command") or "")]
    hooks[nome_ev] = [g for g in hooks.get(nome_ev, []) if g.get("hooks")]
sa = CLAUDE / "hooks" / "stato_avanzamento.py"
if sa.exists():
    voce_sa = {"type": "command", "command": f'{PY} "{sa.as_posix()}"', "timeout": 30}
    for nome_ev in ("Stop", "PreCompact", "SessionEnd"):
        esiti[f"{nome_ev} stato"] = imposta(nome_ev, voce_sa)
ma = CLAUDE / "hooks" / "conferma_salva.py"
if ma.exists():
    esiti["UserPromptSubmit conferma"] = imposta("UserPromptSubmit", {"type": "command", "command": f'{PY} "{ma.as_posix()}"', "timeout": 30})
for nome_ev in ("UserPromptSubmit", "Stop", "PreCompact", "SessionEnd"):     # il gancio di prova di prima, se c'era, esce
    for g in hooks.get(nome_ev, []):
        g["hooks"] = [h for h in g.get("hooks", []) if "memoria_auto.py" not in (h.get("command") or "")]
    hooks[nome_ev] = [g for g in hooks.get(nome_ev, []) if g.get("hooks")]
SETTINGS.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for k, v in esiti.items():
    print(f"  gancio {k}: {v}")

if a.claude_md:
    sezione = Path(a.claude_md).read_text(encoding="utf-8")
    md = CLAUDE / "CLAUDE.md"
    attuale = md.read_text(encoding="utf-8-sig") if md.exists() else ""
    if "## Chi usa questo PC (Jarvis" in attuale:
        print("  CLAUDE.md globale: sezione già presente")
    else:
        md.write_text(attuale.rstrip("\n") + "\n" + sezione, encoding="utf-8")
        print("  CLAUDE.md globale: sezione aggiunta")
print("Fatto. Apri una nuova sessione di Claude Code perché i ganci partano.")
