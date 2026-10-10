#!/usr/bin/env python3
"""scompatta_sorgenti.py — dagli zip caricati su WordPress alla cartella leggibile.

Progetto Due teneva solo gli zip compilati: ogni modifica partiva da un archivio da
aprire a mano, e i grafi del codice leggevano un binario invece che dei file.
Alpine invece aveva i sorgenti scompattati. Questo pareggia i due.

Per ogni `<nome>.zip` prende la **versione più alta** fra i suoi fratelli
(`<nome>-1.2.3.zip`) e la scompatta in `sorgenti/<nome>/`. Se la cartella c'è
già e il contenuto è identico non tocca niente; se è diverso lo dice e si ferma,
perché sovrascrivere sorgenti modificati a mano è il modo di perdere lavoro.

    ./scompatta_sorgenti.py <cartella-plugin>            # mostra cosa farebbe
    ./scompatta_sorgenti.py <cartella-plugin> --conferma # scompatta davvero
"""
import argparse, hashlib, re, shutil, sys, zipfile
from pathlib import Path

VERS = re.compile(r"^(?P<nome>.+?)-(?P<ver>\d+(?:\.\d+)*)\.zip$")

def chiave_ver(s):
    return tuple(int(x) for x in s.split("."))

def impronta(d: Path):
    """sha1 dei file di testo, così una ricompilazione identica non risulta diversa"""
    h = hashlib.sha1()
    for f in sorted(p for p in d.rglob("*") if p.is_file()):
        h.update(str(f.relative_to(d)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()

def famiglie(cartella: Path):
    """{nome plugin: zip da usare} — la versione più alta, o lo zip senza numero"""
    fam = {}
    for z in cartella.glob("*.zip"):
        m = VERS.match(z.name)
        nome = m.group("nome") if m else z.stem
        ver = chiave_ver(m.group("ver")) if m else None
        prec = fam.get(nome)
        # lo zip senza numero e' quello "buono" solo se non c'e' niente di piu' alto
        if prec is None or (ver is not None and (prec[0] is None or ver > prec[0])):
            fam[nome] = (ver, z)
    return {k: v[1] for k, v in fam.items()}

def main():
    ap = argparse.ArgumentParser(description="zip dei plugin -> sorgenti/ leggibili")
    ap.add_argument("cartella", help="la cartella che contiene gli zip")
    ap.add_argument("--conferma", action="store_true")
    a = ap.parse_args()

    base = Path(a.cartella).expanduser().resolve()
    sorgenti = base / "sorgenti"
    if not base.is_dir():
        sys.exit(f"{base} non esiste")
    sorgenti.mkdir(exist_ok=True)

    nuovi = uguali = diversi = 0
    for nome, z in sorted(famiglie(base).items()):
        dest = sorgenti / nome
        try:
            with zipfile.ZipFile(z) as zf:
                cime = {n.split("/")[0] for n in zf.namelist() if n.strip("/")}
                if not cime:
                    continue
                tmp = sorgenti / f".tmp-{nome}"
                shutil.rmtree(tmp, ignore_errors=True)
                zf.extractall(tmp)
        except zipfile.BadZipFile:
            print(f"⚠️  {z.name}: non e' uno zip valido"); continue

        # se lo zip ha una sola cartella in cima, e' quella il sorgente
        radice = tmp / cime.pop() if len(cime) == 1 and (tmp / list(cime)[0] if False else True) else tmp
        radice = radice if radice.is_dir() else tmp

        if dest.exists():
            if impronta(dest) == impronta(radice):
                print(f"=  {nome:<28} già scompattato e identico"); uguali += 1
            else:
                print(f"⚠️  {nome:<28} ESISTE ED È DIVERSO da {z.name} — non lo tocco")
                diversi += 1
            shutil.rmtree(tmp, ignore_errors=True); continue

        if a.conferma:
            shutil.move(str(radice), str(dest))
            print(f"+  {nome:<28} <- {z.name}  ({sum(1 for _ in dest.rglob('*') if _.is_file())} file)")
        else:
            print(f"+  {nome:<28} <- {z.name}  (prova a vuoto)")
        nuovi += 1
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{nuovi} da scompattare · {uguali} già a posto · {diversi} divergenti")
    if not a.conferma and nuovi:
        print("Niente è stato scritto. Aggiungi --conferma per scompattare.")

if __name__ == "__main__":
    main()
