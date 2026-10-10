#!/usr/bin/env python3
"""SessionStart: carica Jarvis e la memoria del suo utente all'apertura di ogni chat.

Legge <cartella Jarvis>/utente.json (nome dell'utente, ruolo, personalità, cartella della memoria): niente
nomi o percorsi scritti qui. Stampa, e quindi mette nel contesto: jarvis/CLAUDE.md, il profilo dell'utente e
l'indice della MEMORIA DELL'UTENTE.
Il lunedì, alla prima connessione della settimana, aggiunge l'ordine della battuta."""
import io
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = Path.home()
JARVIS = Path(os.environ.get("JARVIS_DIR") or "@@JARVIS_DIR@@")
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


def leggi(p, max_c=None):
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return t if max_c is None or len(t) <= max_c else t[:max_c] + "\n[... troncato: apri il file per il resto]"


def config():
    try:
        return json.loads((JARVIS / "utente.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


CFG = config()
UTENTE = CFG.get("nome") or "l'utente"
ASSISTENTE = CFG.get("nome_assistente") or "Jarvis"      # 2026-10-10: il nome lo sceglie l'utente alle domande di avvio


def percorso(v, base=JARVIS):
    if not v:
        return None
    p = Path(str(v).replace("~", str(H), 1)) if str(v).startswith("~") else Path(str(v))
    return p if p.is_absolute() else base / p


MEM_U = percorso(CFG.get("memoria_dir")) or (JARVIS / ".claude" / "memoria-utente")


def oggi():
    # JARVIS_OGGI=AAAA-MM-GG serve solo per provare il lunedì
    try:
        return date.fromisoformat(os.environ["JARVIS_OGGI"])
    except (KeyError, ValueError):
        return datetime.now().date()


def battuta_del_lunedi(d):
    """Vale una volta a settimana: il segno è scritto subito, così una seconda chat non la ripete."""
    if d.weekday() != 0 or CFG.get("battuta_lunedi") is False:      # "battuta_lunedi": false in utente.json la spegne
        return None
    # la prova di VERIFICA.ps1 non scrive niente: il 29/09 (lunedì) un JARVIS_DIR storpiato aveva creato
    # in ~/.claude/hooks una cartella dal nome rotto con dentro .claude/memoria-utente/.lunedi_fatto (2026-10-05)
    if os.environ.get("JARVIS_AVVIO_PROVA") == "1" or not JARVIS.is_absolute() or not JARVIS.is_dir():
        return None
    anno, sett, _ = d.isocalendar()
    chiave = f"{anno}-W{sett:02d}"
    segno = MEM_U / ".lunedi_fatto"
    try:
        MEM_U.mkdir(parents=True, exist_ok=True)
        if segno.exists() and segno.read_text(encoding="utf-8").strip() == chiave:
            return None
        segno.write_text(chiave, encoding="utf-8")
    except OSError:
        return None
    gia = [r[2:].strip() for r in (leggi(MEM_U / "battute-lunedi.md") or "").splitlines() if r.startswith("- ")]
    elenco = "\n".join(f"  · {r}" for r in gia[-25:]) or "  (nessuna ancora)"
    return (f"\n## ORDINE DEL LUNEDÌ ({d.isoformat()}, settimana {chiave})\n"
            f"È la prima connessione della settimana: **una sola volta**, all'inizio della tua prima risposta, saluta {UTENTE} "
            "con UNA battuta umoristica nuova, sul lavoro, sul weekend o sui numeri della settimana. Stile: complice, ironica, "
            f"con personalità, pulita (niente volgarità, niente contro nessuno). Poi subito al lavoro, con dati e fonti vere: "
            "la battuta non inventa mai un numero.\n"
            f"Battute già usate, NON ripeterle né riformularle:\n{elenco}\n"
            f"Dopo averla detta, aggiungi in coda a `{MEM_U / 'battute-lunedi.md'}` la riga `- {d.isoformat()} — <testo>`.")


d = oggi()
print(f"# {ASSISTENTE.upper()} DI {UTENTE.upper()} (Windows). Ti chiami {ASSISTENTE}. Interlocutore: {UTENTE}, chiamalo così. "
      f"La memoria di {UTENTE} resta sua.\n")
if CFG.get("lingua") or CFG.get("fuso_orario"):
    print(f"Lingua: {CFG.get('lingua') or 'italiano'}. Fuso orario: {CFG.get('fuso_orario') or 'quello di Windows'}.")
if CFG.get("non_toccare"):
    print(f"NON TOCCARE MAI: {CFG['non_toccare']}")
print(f"Oggi è {GIORNI[d.weekday()]} {d.isoformat()}.")
profilo = [(k, CFG.get(k)) for k in ("ruolo", "vita_privata", "personalita", "uso") if CFG.get(k)]
if profilo:
    etichette = {"ruolo": "Lavoro", "vita_privata": "Vita privata", "personalita": f"Tono di {ASSISTENTE}", "uso": f"Come vuole usare {ASSISTENTE}"}
    print("\n## Profilo di " + UTENTE + " (da utente.json)\n" + "\n".join(f"- {etichette[k]}: {v}" for k, v in profilo))
pezzi = [("jarvis/CLAUDE.md", JARVIS / "CLAUDE.md", None),
         (f"MEMORIA DI {UTENTE.upper()} ({MEM_U / 'MEMORIA.md'})", MEM_U / "MEMORIA.md", 4000)]
for etichetta, p, lim in pezzi:
    t = leggi(p, lim)
    print(f"\n## {etichetta}\n" + (t if t else f"(non trovato: {p})"))
print(f"\n## Percorsi\n- Cartella Jarvis: {JARVIS}\n- Memoria di {UTENTE}: {MEM_U}\n"
      "- Command Center: http://127.0.0.1:@@PORTA@@\n"
      "- Consultazione chirurgica: leggi il grafo/indice, poi UN solo file .md alla volta.")
# 2026-10-10: la memoria condivisa (collega_memoria.py) e lo stato dei progetti (gancio stato_progetti.py)
try:
    PERC = json.loads((H / ".jarvis" / "percorsi.json").read_text(encoding="utf-8-sig"))
except (OSError, ValueError):
    PERC = {}
if PERC.get("memoria"):
    print(f"\n## Memoria condivisa\n- Cartella: {PERC['memoria']} (porta d'ingresso: Comune/Memoria.md)")
    for s in PERC.get("spazi", [])[:12]:
        st = leggi(Path(s.get("stato", ""))) if s.get("stato") else ""
        da_fare = [r for r in (st or "").splitlines() if r.startswith("- [ ]")][:3]
        print(f"- Spazio {s.get('nome')}: {s.get('stato')}" + ("".join(f"\n    {r}" for r in da_fare)))
    print("- Lo stato si aggiorna da solo. Quando chiudi un lavoro scrivi nella risposta righe «FATTO: …», «DA FARE: …», "
          "«ERRORE: …»: il gancio le porta in <spazio>/Stato.md.")
b = battuta_del_lunedi(d)
if b:
    print(b)
