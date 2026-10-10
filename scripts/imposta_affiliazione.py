#!/usr/bin/env python3
"""Mette il link di affiliazione della VPS facoltativa in tutti i documenti (stessa logica di imposta-affiliazione.ps1).

    python scripts/imposta_affiliazione.py            sostituisce e dice dove
    python scripts/imposta_affiliazione.py --prova    dice cosa cambierebbe, senza scrivere

Fonte unica: docs/affiliazione.txt (prima riga che non comincia con «#»). Nei documenti sostituisce il segnaposto
{{LINK_AFFILIAZIONE_VPS}} e il link applicato la volta prima (docs/affiliazione-applicata.txt).
"""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
SEGNAPOSTO = "{{LINK_AFFILIAZIONE_VPS}}"
FONTE = RADICE / "docs" / "affiliazione.txt"
APPLICATA = RADICE / "docs" / "affiliazione-applicata.txt"
DOVE = ["README.md", "INIZIA-QUI.md", "CLAUDE.md", "docs/*.md", ".claude/commands/*.md"]


def main():
    prova = "--prova" in sys.argv
    righe = [r.strip() for r in FONTE.read_text(encoding="utf-8").splitlines() if r.strip() and not r.lstrip().startswith("#")]
    if not righe or not righe[0].startswith("https://"):
        sys.exit(f"{FONTE}: manca il link (una riga che comincia con https://)")
    nuovo = righe[0]
    vecchio = APPLICATA.read_text(encoding="utf-8").strip() if APPLICATA.exists() else ""
    cambiati = 0
    for modello in DOVE:
        for f in sorted(RADICE.glob(modello)):
            t = f.read_text(encoding="utf-8")
            n = t.replace(SEGNAPOSTO, nuovo)
            if vecchio and vecchio != nuovo:
                n = n.replace(vecchio, nuovo)
            if n != t:
                cambiati += 1
                print(f"{'cambierebbe' if prova else 'aggiornato'}: {f.relative_to(RADICE)}")
                if not prova:
                    f.write_text(n, encoding="utf-8")
    if not prova:
        APPLICATA.write_text(nuovo + "\n", encoding="utf-8")
    print(f"{cambiati} documenti {'da aggiornare' if prova else 'aggiornati'}; link: {nuovo}")


if __name__ == "__main__":
    main()
