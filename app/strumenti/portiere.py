#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Il portiere delle chiavi. Confronta quello che gli agenti dicono con quello
che le macchine fanno davvero.

Perché esiste (l'utente, 20/09/2026 12:55): «un orchestratore che si accerta quante
chiavi sono in giro e cosa stanno usando». Le chiavi le dà e le riprende
`lavori.py`. Questo è il controllo che le due metà non si separino, e nasce da
un fatto: un tunnel verso il database di produzione è rimasto aperto sette
ore, la sessione batteva regolarmente, e nessuno se n'è accorto.

Non è un agente e non è un modello. È uno script: dare, contare e ritirare
chiavi non richiede nessun giudizio, e un LLM acceso h24 su una cosa
deterministica costa e sbaglia a caso. Quando c'è davvero da giudicare — un
lavoro bloccato, una chiave che nessuno vuole mollare — il portiere lo scrive
nel resoconto e decide Jarvis.

Le quattro cose che cerca:

  FANTASMA   chiave presa, nessun processo dietro. La sessione è morta e la
             chiave è rimasta lì a bloccare tutti.
  SCADUTA    chiave tenuta oltre i minuti che aveva chiesto. Il caso del tunnel.
  ABUSIVO    una risorsa è accesa davvero (un tunnel ssh aperto, il Chrome di
             debug in ascolto) e nessuno ha la chiave. Qualcuno l'ha aperta
             senza dirlo: è il buco che rende inutile tutto il resto.
  MUTO       una sessione di Claude lavora da un pezzo e non ha preso niente.

Comandi:

    portiere.py                 il giro: guarda e riferisce, non tocca niente
    portiere.py --json          lo stesso per il Command Center e il battito
    portiere.py --ritira        ritira le chiavi FANTASMA e SCADUTE
    portiere.py --fantasmi      ritira solo le prese col processo morto, subito,
                                con o senza chiavi (vedi `ritira_fantasmi`)
    portiere.py --vps           guarda anche i contenitori sulla VPS (in lettura)

`--ritira` scrive nello storico di `lavori.py`, quindi si vede sempre chi teneva
cosa e perché gli è stata tolta. Non chiude processi e non ferma contenitori:
quello resta una decisione di l'utente.

Non è un doppione di `strumenti/agenti.py`: quello risponde a «chi gira a vuoto»
misurando il processore, questo a «chi tiene cosa». I recapiti in /tmp/cc-socks
sono la stessa fonte, e se cambia il modo di riconoscere una sessione vanno
cambiati tutti e due.

Uscita: 0 tutto in ordine, 3 c'è qualcosa da guardare.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lavori  # noqa: E402  stesso registro, nessuna seconda fonte
import processi  # noqa: E402
try:
    import agenti  # noqa: E402  chi è «in ascolto» lo decide agenti.py (sulla VPS non c'è: niente sessioni lì)
except ImportError:
    agenti = None


def comando(c, timeout=15):
    """Un comando di sola lettura. Se non c'è o fallisce si torna vuoto: il
    portiere non deve mai morire per colpa di quello che sta controllando."""
    if callable(c):           # le spie di Windows sono funzioni Python, non pipeline di shell
        try:
            return str(c())
        except Exception:
            return ''
    try:
        r = subprocess.run(c, shell=True, capture_output=True, text=True, errors="replace", timeout=timeout)
        return r.stdout
    except Exception:
        return ''


def processo_vivo(pid):
    if not pid:
        return None  # non lo sappiamo: le prese vecchie non scrivevano il pid
    if processi.WIN:          # su Windows os.kill(pid, 0) termina il processo
        return processi.vivo(pid)
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # esiste, è di un altro utente
    except Exception:
        return None


def sessioni_claude():
    """I recapiti in /tmp/cc-socks/: il nome del file è il PID della sessione.
    Stessa fonte di strumenti/agenti.py, che spiega perché si guarda qui."""
    fuori = []
    if processi.WIN:          # nessun recapito: le sessioni sono i claude.exe di Claude Code
        return [{'pid': p, 'vivo': True} for p in processi.sessioni_claude()]
    d = pathlib.Path('/tmp/cc-socks')
    if not d.exists():
        return fuori
    for f in d.glob('*.sock'):
        try:
            pid = int(f.stem)
        except ValueError:
            continue
        fuori.append({'pid': pid, 'vivo': processo_vivo(pid) is not False})
    return fuori


# Come si riconosce che una risorsa è accesa DAVVERO, senza chiedere a nessuno.
# Sono tutti comandi di lettura.
#
# 🔴 La prima versione cercava `[s]sh.*server-tuo.*5432`, cioè un tunnel che
# non esiste: gli script del database vanno diritti a `root@203.0.113.10`
# senza alias e senza porta. La spia non trovava mai niente e il portiere diceva
# che andava tutto bene mentre qualcuno scriveva in produzione senza chiave.
# Perciò si cerca l'indirizzo O l'alias, e il nome del contenitore del database.
VPS = r'(server-tuo|203\.0\.113\.10)'
SPIE = {
    'database': "ps -eo args | grep -cE '[s]sh.*%s.*(5432)'" % VPS,
    # solo le shell interattive (la riga finisce col nome dell'host): i tunnel (-N/-L/-R/-D) e le ssh
    # con un comando dopo l'host (il ponte del telefono) non sono una shell che modifica (26/09/2026)
    'vps-shell': "ps -eo args | grep -E '[s]sh( |.* )%s$' | grep -vcE ' -(N|L|R|D)( |$)'" % VPS,
    'chrome-debug': "lsof -nP -iTCP:9222 -sTCP:LISTEN 2>/dev/null | grep -c LISTEN",
    'ponte-9223': "lsof -nP -iTCP:9223 -sTCP:LISTEN 2>/dev/null | grep -c LISTEN",
    'telefono-adb': "adb devices 2>/dev/null | grep -c 'device$'",
}

# Sulla VPS le stesse risorse si guardano da un'altra parte: lì il database non
# è «un ssh che esce», è un `docker exec ... psql` che entra. Le spie del Mac
# non troverebbero mai niente, e un portiere che non trova mai niente dice
# sempre che va tutto bene — l'errore già fatto una volta oggi.
SPIE_VPS = {
    'database': "ps -eo args | grep -c '[d]ocker exec.*psql'",
    'vps-shell': "who 2>/dev/null | grep pts | grep -vc tmux",   # le finestre tmux persistenti non contano (26/09/2026)
}

# I contenitori accesi NON sono spie: girano sempre, e segnarli abusivi a ogni
# giro sarebbe rumore. La chiave su un contenitore serve per *modificarli*,
# non per il fatto che stanno in piedi.

# Le risorse che NON hanno una spia: qui il portiere si fida di quello che è
# dichiarato, e un abusivo passa. Si dice in chiaro invece di lasciar credere
# che «nessuna nota» voglia dire «nessun problema».
# Accese apposta, decisione di l'utente del 20/09/2026 14:00: il telefono resta collegato
# via ADB per il lavoro sull'app Android. Non è abusivo. Chi ha bisogno del telefono
# per una prova che lo scalza continua a ritirare la chiave `telefono-adb`.
NORMALI = ('telefono-adb',)

SENZA_SPIA = ('sito', 'automazioni', 'mac-schermo', 'cartella-sincronizzata')


def sulla_vps():
    """Siamo sulla VPS o sul Mac? Si guarda una cosa che sul Mac non c'è e che
    non si sposta: la cartella del ponte dell'app Jarvis."""
    return pathlib.Path('@@CARTELLA_SERVER@@').is_dir()


# Su Windows non ci sono VPS, tunnel ssh, ADB né MetaTrader: restano le due porte del Chrome di
# debug. Sono funzioni Python (senza `ps`, `grep`, `lsof`, che qui non ci sono).
def _conta_processi(pezzo):
    return sum(1 for p in processi.elenco() if pezzo in p['cmd'])


SPIE_WIN = {
    'chrome-debug': lambda: int(processi.porta_aperta(9222)),
    'ponte-9223': lambda: int(processi.porta_aperta(9223)),
}


def spie():
    if processi.WIN:
        return SPIE_WIN
    return SPIE_VPS if sulla_vps() else SPIE


def risorse_accese():
    fuori = {}
    for nome, c in spie().items():
        out = comando(c).strip()
        try:
            fuori[nome] = int(out.splitlines()[0]) > 0 if out else False
        except (ValueError, IndexError):
            fuori[nome] = False
    return fuori


def giro(vps=False):
    attivi = lavori.leggi_attivi()
    occupate = lavori.chiavi_in_giro(attivi)
    accese = risorse_accese()
    sess = sessioni_claude()

    note = []

    for d in attivi:
        ch = lavori.chiavi_di(d)
        # 🔴 `lavori.vivo` e non `processo_vivo`: il PID di una presa vale solo
        # sulla macchina che l'ha scritta. Senza questo controllo il portiere
        # sulla VPS guardava se il PID del Mac esisteva *sulla VPS*, non lo
        # trovava e dichiarava fantasma ogni presa viva dell'altra macchina —
        # visto dal vivo il 20/09/2026 al primo giro sulla VPS. Con `--ritira`
        # avrebbe tolto le chiavi a chi stava lavorando sull'altra macchina.
        vivo = lavori.vivo(d)
        # Una presa senza chiavi col processo morto è fantasma lo stesso: non
        # tiene risorse, ma tiene i file, e `lavori.py chi` la mostra viva fino
        # a quando il battito non invecchia di MORTA_DOPO_MIN.
        if vivo is False or (ch and d.get('morta')):
            note.append({'tipo': 'FANTASMA', 'chiavi': ch, 'presa': d,
                         'perche': f"processo morto (pid {d.get('pid')})" if vivo is False else
                                   f'nessun battito da oltre {lavori.MORTA_DOPO_MIN} min'})
        elif ch and d.get('scaduta'):
            note.append({'tipo': 'SCADUTA', 'chiavi': ch, 'presa': d,
                         'perche': f'presa {lavori.eta_di(d, "inizio")}, '
                                   f'ne aveva chiesti {lavori.max_min(d)}'})

    for nome, viva in accese.items():
        if viva and nome not in occupate and nome not in NORMALI:
            note.append({'tipo': 'ABUSIVO', 'chiavi': [nome], 'presa': None,
                         'perche': f'{lavori.RISORSE.get(nome, nome)}: è accesa e '
                                   'nessuno ha ritirato la chiave'})

    # MUTO: una sessione di Claude che gira e non compare nel registro. Si
    # guardano solo i PID di questa macchina: le prese delle altre macchine
    # hanno PID che qui non vogliono dire niente.
    # Decisione di l'utente del 2026-09-26: Telegram, il telefono (Remote Control), la voce e
    # la Cloud Chat sono «in ascolto»: aspettano apposta e non prendono chiavi. Non sono
    # MUTO, stanno in una riga a parte; si controllano e si riavviano, non si chiudono.
    miei = {str(d.get('pid')) for d in attivi
            if d.get('macchina') == lavori.macchina() and d.get('pid')}
    in_ascolto = []
    # Su Windows le sessioni sono tutti i claude.exe aperti, chat comprese: una chat che aspetta
    # non è MUTO. Lo è solo se sta lavorando adesso (processore in 2 secondi) senza aver preso niente.
    lavora_ora = None
    if processi.WIN:
        prima = {s['pid']: processi.cpu_secondi(s['pid']) for s in sess}
        time.sleep(2)
        lavora_ora = {p: (processi.cpu_secondi(p) or 0) - (c or 0) > 0.1 for p, c in prima.items()}
    for s in sess:            # su una macchina senza Claude Code la lista è vuota
        if not s['vivo'] or str(s['pid']) in miei:
            continue
        nome = agenti.in_ascolto(s['pid']) if agenti else ''
        if nome:
            in_ascolto.append({'pid': s['pid'], 'nome': nome})
            continue
        if lavora_ora is not None and not lavora_ora.get(s['pid']):
            continue
        if agenti and agenti.del_pannello(s['pid']):
            continue          # chat e missioni lanciate dal Command Center: non sono «non registrate»
        note.append({'tipo': 'MUTO', 'chiavi': [], 'presa': None,
                     'perche': f'sessione pid {s["pid"]} aperta e non registrata '
                               '(se sta solo leggendo va bene)'})

    # 🔴 Un sottoagente non diventa mai FANTASMA: `pid_sessione()` gli dà il PID
    # della sessione che l'ha lanciato, che resta vivo finché Jarvis è vivo.
    # L'unica rete che gli resta è la scadenza, quindi una scadenza lunga su un
    # sottoagente è una chiave che può restare bloccata per ore.
    for d in attivi:
        if (lavori.chiavi_di(d) and not d.get('scaduta')
                and lavori.slug(d.get('agente')) != 'jarvis'
                and lavori.max_min(d) > 30):
            note.append({'tipo': 'LUNGA', 'chiavi': lavori.chiavi_di(d), 'presa': d,
                         'perche': f'sottoagente con scadenza a {lavori.max_min(d)} min: '
                                   'se muore, la chiave resta bloccata fino a lì '
                                   '(per i sottoagenti stare sotto i 30)'})

    vivi = [d for d in attivi if not d.get('morta')]
    fuori = {'ora': lavori.ora(), 'macchina': lavori.macchina(),
             'vps_locale': sulla_vps(),
             'lavori_vivi': len(vivi),
             'lavori_morti': len(attivi) - len(vivi),
             'in_ascolto': in_ascolto,
             'senza_spia': [r for r in SENZA_SPIA if r in occupate],
             'cieche': len(SENZA_SPIA),
             'chiavi_in_giro': {k: len(v) for k, v in occupate.items()},
             'lavori_attivi': len(attivi), 'sessioni': len(sess),
             'risorse_accese': accese, 'note': note}
    if vps and not sulla_vps():
        fuori['vps'] = comando("ssh -o BatchMode=yes -o ConnectTimeout=10 server-tuo "
                               "'docker ps --format \"{{.Names}}|{{.Status}}\"'", 30).strip()
        # Il portiere gira anche là, per conto suo, ogni 30 minuti: qui si legge
        # il suo ultimo giro invece di indovinare cosa succede dall'altra parte.
        fuori['vps_portiere'] = comando(
            "ssh -o BatchMode=yes -o ConnectTimeout=10 server-tuo "
            "'grep -A3 \"^-----\" @@CARTELLA_SERVER@@/portiere.log | tail -20'", 30).strip()
    return fuori


def chiudi_presa(d, esito):
    """Chiude una presa come fa `lavori.py finito`: riga nello storico, poi
    «chiuso» scritto DENTRO il file, poi la cancellazione.

    🔴 Prima si scrive, poi si cancella. OneDrive non propaga in modo affidabile
    le cancellazioni: una presa solo cancellata dal Mac resta aperta per sempre
    vista dalla VPS e dal PC dell'amministrazione, con le chiavi ancora in mano.
    La prima versione di `ritira` faceva solo `unlink`."""
    f = d['_file']
    if lavori.CLIENTE:
        # Dal 2026-10-05 il registro sta sulla VPS: dal Mac si chiede a lei di chiudere.
        return lavori.inoltra(['chiudi-file', esito, f.name])
    lavori.riga_storico(d, esito)
    pulita = {k: v for k, v in d.items() if not k.startswith('_')
              and k not in ('morta', 'scaduta')}
    pulita['chiuso'] = lavori.adesso()
    pulita['esito'] = esito
    lavori.scrivi(f, pulita)
    f.unlink(missing_ok=True)


def fantasmi():
    """Le prese di QUESTA macchina col processo morto, lette adesso dal disco.

    Solo `lavori.vivo(d) is False`: vuol dire stessa macchina, pid scritto, e
    `kill -0` che risponde «non esiste». Tutto il resto (None) non si tocca:

      - una presa della VPS o del PC Windows ha un pid che qui non significa
        niente (errore del 20/09/2026, dieci prese vive dichiarate fantasma);
      - una presa vecchia senza pid non si può giudicare;
      - un pid riusato da un altro processo dà «vivo»: si sbaglia dalla parte
        prudente, la presa resta fino alla scadenza."""
    return [d for d in lavori.leggi_attivi() if lavori.vivo(d) is False]


def ritira_fantasmi():
    """Ritira le prese fantasma senza aspettare `max_min` né il battito.

    Differenza con `--ritira`: quello toglie anche le chiavi SCADUTE, che hanno
    dietro una sessione viva. Questo toglie solo quello che è morto per certo,
    con o senza chiavi, quindi si può lanciare quando si vuole.

    Ogni presa si rilegge dal disco un attimo prima di chiuderla: fra il giro e
    il ritiro il suo padrone può aver scritto `finito` da solo."""
    tolte = 0
    for d in fantasmi():
        f = d['_file']
        try:
            ora_su_disco = json.loads(f.read_text())
        except Exception:
            continue          # sparita o a metà scrittura: non è più affar nostro
        if ora_su_disco.get('chiuso') or lavori.vivo(ora_su_disco) is not False:
            continue
        ch = lavori.chiavi_di(d)
        chiudi_presa(d, f"presa fantasma ritirata dal portiere: processo {d.get('pid')} "
                        f"morto su {d.get('macchina')}"
                        + (f", chiavi rese: {', '.join(ch)}" if ch else ''))
        print(f"  ritirata la presa di {d.get('agente')} su «{d.get('progetto')}» "
              f"(pid {d.get('pid')} morto)" + (f" — chiavi: {', '.join(ch)}" if ch else ''))
        tolte += 1
    if tolte:
        if not lavori.CLIENTE:   # sul Mac l'indice lo rifà la VPS a ogni chiusura
            lavori.cmd_indice(argparse.Namespace(pulisci=False))
    print(f'prese fantasma ritirate: {tolte}')
    return tolte


def ritira(stato):
    """Toglie le chiavi FANTASMA e SCADUTE. Scrive sempre nello storico: una
    chiave tolta senza traccia è peggio di una chiave dimenticata."""
    tolte = 0
    for n in stato['note']:
        if n['tipo'] not in ('FANTASMA', 'SCADUTA'):
            continue
        d = n['presa']
        # Ognuno pulisce casa propria. Il registro sta su OneDrive e arriva con
        # ritardo: quello che da qui sembra rimasto lì può essere già chiuso di
        # là. Le prese di un'altra macchina si segnalano e basta.
        if d.get('macchina') != lavori.macchina():
            print(f"  lasciata a {d.get('macchina')}: {', '.join(n['chiavi'])} "
                  f"({n['tipo']}) — la pulisce la macchina che l'ha presa")
            continue
        chiudi_presa(d, f"chiave ritirata dal portiere — {n['tipo'].lower()}: {n['perche']}")
        print(f"  ritirata {', '.join(n['chiavi'])} a {d.get('agente')} ({n['tipo']})")
        tolte += 1
    if tolte:
        if not lavori.CLIENTE:   # sul Mac l'indice lo rifà la VPS a ogni chiusura
            lavori.cmd_indice(argparse.Namespace(pulisci=False))
    print(f'chiavi ritirate: {tolte}')
    return tolte


def stampa(s):
    print(f"Portiere — {s['ora']} su {s['macchina']}"
          + ('  (VPS)' if s.get('vps_locale') else ''))
    morti = s.get('lavori_morti', 0)
    print(f"  lavori al lavoro: {s.get('lavori_vivi', s['lavori_attivi'])}"
          + (f" (+{morti} prese rimaste a metà)" if morti else '')
          + f" · sessioni aperte: {s['sessioni']}"
          + f" · chiavi in giro: {sum(s['chiavi_in_giro'].values())}")
    if s['chiavi_in_giro']:
        for k, n in sorted(s['chiavi_in_giro'].items()):
            print(f"      🔑 {k}" + (f' ×{n}' if n > 1 else ''))
    acc = [k for k, v in s['risorse_accese'].items() if v]
    print('  risorse accese davvero: ' + (', '.join(acc) if acc else 'nessuna'))
    print('  risorse senza spia: %d — lì si fida del dichiarato, e per quelle '
          'una spia non esiste (vedi SENZA_SPIA)' % s.get('cieche', 0))
    if s.get('in_ascolto'):
        print('  in ascolto: ' + ', '.join(f"{a['nome']} (pid {a['pid']})" for a in s['in_ascolto']))
    if s.get('vps'):
        su = [r for r in s['vps'].split('\n') if r]
        print(f'  contenitori sulla VPS: {len(su)} attivi')
    if s.get('vps_portiere'):
        print('  ultimo giro del portiere sulla VPS:')
        for r in s['vps_portiere'].split('\n')[-6:]:
            print('     ', r)
    if not s['note']:
        print('\nTutto in ordine: ogni chiave ha dietro un processo vivo, '
              'e niente è acceso senza chiave.')
        return 0
    print(f"\nDa guardare ({len(s['note'])}):")
    for n in s['note']:
        d = n['presa']
        chi = f" — {d.get('agente')} su {d.get('macchina')}, «{d.get('cosa')}»" if d else ''
        print(f"  {n['tipo']:<9} {', '.join(n['chiavi']) or '—'}{chi}")
        print(f"            {n['perche']}")
    if any(n['tipo'] == 'FANTASMA' for n in s['note']):
        print('\nSolo le fantasma: python3 strumenti/portiere.py --fantasmi')
    if any(n['tipo'] in ('FANTASMA', 'SCADUTA') for n in s['note']):
        print('\nPer liberarle: python3 strumenti/portiere.py --ritira')
    return 3


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--json', action='store_true')
    p.add_argument('--ritira', action='store_true', help='ritira le chiavi fantasma e scadute')
    p.add_argument('--fantasmi', action='store_true',
                   help='ritira subito le prese di questa macchina col processo morto')
    p.add_argument('--vps', action='store_true', help='guarda anche i contenitori sulla VPS')
    a = p.parse_args()

    if a.fantasmi:
        ritira_fantasmi()
        return 0

    s = giro(vps=a.vps)
    if a.json:
        print(json.dumps(s, ensure_ascii=False, indent=1, default=str))
        return 3 if s['note'] else 0
    esito = stampa(s)
    if a.ritira:
        print()
        ritira(s)
    return esito


if __name__ == '__main__':
    sys.exit(main())
