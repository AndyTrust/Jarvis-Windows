#!/usr/bin/env python3
"""Prove di routine_pc.py (le Routine sul PC Windows) senza Windows: schtasks è finto, la VPS non si chiama mai.
  python prova_routine_pc.py        esce con 1 se una prova fallisce (gira anche su macOS e Linux)"""
import os
import sys
import tempfile
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))
TMP = Path(tempfile.mkdtemp(prefix="prova-routine-pc-"))
os.environ["CC_ROUTINE_DIR"] = str(TMP / "registro")
os.environ["CC_ROUTINE_GRUPPI"] = str(TMP / "routine-gruppi.json")      # non c'è: valgono i gruppi del PC
os.environ.pop("CC_ROUTINE_VPS", None)
import routine as R          # noqa: E402
import routine_pc as P       # noqa: E402

esiti = []


def v(nome, ok):
    esiti.append(bool(ok))
    print(("✅ " if ok else "🔴 ") + nome)


# colonne di «schtasks /query /fo CSV /v /nh» (per posizione: 28)
def riga(nome, prossimo="06/10/2026 07:30:00", stato="Ready", ultimo="05/10/2026 07:30:00", codice="0",
         comando="C:\\jarvis\\.venv\\Scripts\\pythonw.exe sincro\\ogni30.py", commento="N/A", attiva="Enabled",
         tipo="Daily ", ora="07:30:00", ripeti="Disabled"):
    c = ["PC", nome, prossimo, stato, "Interactive only", ultimo, codice, "utente", comando, "C:\\jarvis", commento, attiva,
         "Disabled", "", "utente", "Disabled", "72:00:00", "Scheduling data is not available in this format.", tipo, ora,
         "05/10/2026", "N/A", "Every 1 day(s)", "N/A", ripeti, "Disabled", "Disabled", "Disabled"]
    return ",".join('"' + x.replace('"', '""') + '"' for x in c)


CSV = "\n".join([
    riga("\\Jarvis Battito", tipo="One Time Only, Minute ", ripeti="0 Hour(s), 15 Minute(s)", ora="09:00:00"),
    riga("\\Jarvis Avvio", tipo="At logon time", prossimo="N/A", codice="267011", ultimo="N/A"),
    riga("\\Jarvis\\giro-dati", codice="1", commento="Giro dati del progetto"),
    riga("\\Jarvis\\spento", attiva="Disabled", stato="Disabled"),
    riga("\\Microsoft\\Windows\\Defrag\\ScheduledDefrag"),
])

# 1. lettura
r = {x["nome"]: x for x in P.routine_win(CSV)}
v("solo le attività che cominciano con \\Jarvis", set(r) == {"\\Jarvis Battito", "\\Jarvis Avvio", "\\Jarvis\\giro-dati", "\\Jarvis\\spento"})
v("id sicuro (win:…)", r["\\Jarvis\\giro-dati"]["id"] == "win:jarvis-giro-dati")
v("esito: 0 = ok, 1 = errore, mai partita = nessuno", (r["\\Jarvis Battito"]["esito"], r["\\Jarvis\\giro-dati"]["esito"], r["\\Jarvis Avvio"]["esito"]) == ("ok", "errore", None))
v("orari: ripetizione, all'accesso, ogni giorno", r["\\Jarvis Battito"]["orario"].startswith("ogni 15 minuti")
  and r["\\Jarvis Avvio"]["orario"] == "all'accesso" and r["\\Jarvis\\giro-dati"]["orario"] == "ogni giorno 07:30")
v("data letta (gg/mm/aaaa)", abs((r["\\Jarvis\\giro-dati"]["ultimo"] or 0) - time.mktime((2026, 10, 5, 7, 30, 0, 0, 0, -1))) < 2)
v("disattivata: non avviabile", r["\\Jarvis\\spento"]["attivo"] is False and not r["\\Jarvis\\spento"]["avviabile"])
v("commento come descrizione", r["\\Jarvis\\giro-dati"]["descrizione"] == "Giro dati del progetto")

# 2. aggancio con schtasks finto (registra i comandi) e senza VPS configurata
COMANDI = []


def finto(argv, timeout=30):
    COMANDI.append(list(argv))
    if argv[:2] == ["schtasks", "/query"] and "/tn" in argv:
        nome = argv[argv.index("/tn") + 1]
        return 0, riga(nome, codice="0")
    if argv[:2] == ["schtasks", "/query"]:
        return 0, CSV
    return 0, "OPERAZIONE RIUSCITA"


P._esegui = finto
P.aggancia(R)
v("R.ID accetta win:", R.ID.fullmatch("win:jarvis-giro-dati") is not None)
d = R.elenco(forza=True)
v("senza «routine_vps» la VPS non si chiama e lo dice", any("routine_vps" in a for a in d["avvisi"]) and d["conta"].get("win") == 4)
v("gruppo «pc» per le attività del PC", {x["gruppo"] for x in d["routine"]} == {"pc"})

# 3. filtro della VPS: solo le routine condivise (originale finto)
falso = lambda forza=False, extra=(): {"routine": [
    {"id": "vps:jarvis-giro-condiviso", "fonte": "vps", "descrizione": "giro", "comando": "x"},
    {"id": "vps:jarvis-allerta-altro", "fonte": "vps", "descrizione": "altro progetto", "comando": "y"},
    {"id": "cron:altro-vigilanza", "fonte": "cron", "descrizione": "", "comando": "z"}], "avvisi": [], "letto": time.time()}
d2 = P._elenco(falso)(True)
ids = {x["id"] for x in d2["routine"]}
v("dalla VPS solo il condiviso (giro-condiviso sì, gli altri no)", "vps:jarvis-giro-condiviso" in ids and "vps:jarvis-allerta-altro" not in ids
  and "cron:altro-vigilanza" not in ids)

# 4. avvia: schtasks /run, senza conferma
COMANDI.clear()
e = R.avvia("win:jarvis-giro-dati", chi="prova")
v("avvia lancia schtasks /run /tn <nome>", ["schtasks", "/run", "/tn", "\\Jarvis\\giro-dati"] in COMANDI and e["stato"] == "in_corso")

# 5. modifica a due tempi
COMANDI.clear()
try:
    R.prepara({"nuova": True, "fonte": "vps", "nome": "x", "orario": "07:00", "comando": "true"})
    v("nuova sulla VPS dal PC: rifiutata", False)
except R.RoutineNonValida:
    v("nuova sulla VPS dal PC: rifiutata", True)
p = R.prepara({"id": "win:jarvis-giro-dati", "orario": "08:15", "attivo": False})
v("prepara non esegue niente", not any(c[:2] == ["schtasks", "/change"] for c in COMANDI))
v("il comando preparato è quello esatto", "schtasks /change /tn \\Jarvis\\giro-dati /st 08:15" in p["comando"] and "/disable" in p["comando"])
try:
    R.conferma(p["prep"], "codice-sbagliato")
    v("codice sbagliato: rifiutato", False)
except R.RoutineNonValida:
    v("codice sbagliato: rifiutato", True)
time.sleep(R.PREP_MIN_S + 0.1)
c = R.conferma(p["prep"], p["codice"])
v("conferma con il codice: esegue i due comandi", c["ok"] and ["schtasks", "/change", "/tn", "\\Jarvis\\giro-dati", "/st", "08:15"] in COMANDI
  and ["schtasks", "/change", "/tn", "\\Jarvis\\giro-dati", "/disable"] in COMANDI)
try:
    R.conferma(p["prep"], p["codice"])
    v("la stessa conferma non vale due volte", False)
except R.RoutineNonValida:
    v("la stessa conferma non vale due volte", True)
n = R.prepara({"nuova": True, "fonte": "win", "nome": "prova-nuova", "orario": "ogni 20 min", "comando": "python x.py"})
v("nuova sul PC: /create in \\Jarvis\\ ogni N minuti", "schtasks /create /tn \\Jarvis\\prova-nuova /tr" in n["comando"] and "/sc minute /mo 20" in n["comando"])
try:
    R.prepara({"id": "win:jarvis-giro-dati", "orario": "ogni 5 min"})
    v("su un'attività esistente l'intervallo non si cambia", False)
except R.RoutineNonValida:
    v("su un'attività esistente l'intervallo non si cambia", True)

print(f"\n{sum(esiti)}/{len(esiti)} prove passate")
sys.exit(0 if all(esiti) else 1)
