"""Prove di audit, policy, budget e banca_stato. File temporanei, nessun server avviato.
Esecuzione: python3 prova_gateway.py"""
import ast
import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))
import audit  # noqa: E402
import budget  # noqa: E402
import conferme  # noqa: E402


def _banca_stato():
    """banca_stato di server.py, estratta dal sorgente senza importare (e avviare) il server."""
    src = (QUI / "server.py").read_text(encoding="utf-8")
    nodo = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "banca_stato")
    ns = {"Path": Path, "re": re, "datetime": datetime}
    exec(compile(ast.Module([nodo], []), "server.py", "exec"), ns)
    return ns["banca_stato"]


class Audit(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.f = Path(self.d.name) / "audit.jsonl"

    def tearDown(self):
        self.d.cleanup()

    def test_una_riga_per_evento_con_i_campi(self):
        audit.registra({"agente": "a", "tool": "Bash", "sintesi": "ls", "verdetto": "consentito",
                        "intruso": "x"}, self.f)
        audit.registra({"agente": "b", "tool": "Read", "sintesi": "x", "verdetto": "negato"}, self.f)
        righe = self.f.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(righe), 2)
        r = json.loads(righe[0])
        self.assertEqual(list(r), list(audit.CAMPI))

    def test_sintesi_troncata_e_senza_segreti(self):
        r = audit.registra({"sintesi": "x" * 500}, self.f)
        self.assertEqual(len(r["sintesi"]), 200)
        audit.registra({"sintesi": "curl -H Authorization: Bearer abc123 sk-ABCDEFGH12345 password=hunter2"}, self.f)
        testo = self.f.read_text(encoding="utf-8")
        for segreto in ("abc123", "sk-ABCDEFGH12345", "hunter2"):
            self.assertNotIn(segreto, testo)

    def test_banca_e_filtri(self):
        audit.registra({"agente": "a", "sintesi": "Read C:/Users/x/jarvis/.claude/memoria-utente/MEMORIA.md"}, self.f)
        audit.registra({"agente": "b", "sintesi": "Read C:/Users/x/jarvis/.claude/memoria/nota.md"}, self.f)
        audit.registra({"agente": "a", "sintesi": "ls"}, self.f)
        self.assertEqual(len(audit.legge_ultime(10, None, self.f)), 3)
        self.assertEqual(audit.legge_ultime(10, {"banca": "personale"}, self.f)[0]["agente"], "a")
        self.assertEqual(audit.legge_ultime(10, {"banca": "privata"}, self.f)[0]["agente"], "b")
        self.assertEqual(len(audit.legge_ultime(10, {"agente": "a"}, self.f)), 2)
        self.assertEqual(len(audit.legge_ultime(1, None, self.f)), 1)
        self.assertEqual(audit.legge_ultime(5, None, self.f.with_name("manca.jsonl")), [])


class Policy(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.p = Path(self.d.name) / "policy.json"
        self.radici = [Path(self.d.name).resolve()]

    def tearDown(self):
        self.d.cleanup()

    def mot(self, ag, tool, inp):
        return conferme.motivo(tool, inp, self.radici, agente=ag, policy_file=self.p)

    def test_senza_file_comportamento_identico(self):
        manca = Path(self.d.name) / "non-c-e.json"
        casi = [("Read", {}), ("Bash", {"command": "rm -rf x"}), ("Bash", {"command": "ls"}),
                ("mcp__x__send_message", {}), ("Write", {"file_path": "/etc/x"})]
        for tool, inp in casi:
            self.assertEqual(conferme.motivo(tool, inp, self.radici, agente="a", policy_file=manca),
                             conferme.motivo(tool, inp, self.radici))
        self.p.write_text("{rotto", encoding="utf-8")          # file illeggibile = come se mancasse
        self.assertEqual(self.mot("a", "Bash", {"command": "rm -rf x"}), "cancella")

    def test_allow_deny_per_agente(self):
        self.p.write_text(json.dumps({"agenti": {
            "*": {"deny": [{"tool": "Bash", "contiene": "memoria-utente"}]},
            "fisc": {"allow": [{"tool": "Bash", "contiene": "^rm -f tmp"}], "deny": ["mcp__*__send_*"]}}}),
            encoding="utf-8")
        self.assertTrue(self.mot("zz", "Bash", {"command": "cat memoria-utente/x.md"}).startswith("policy:"))
        self.assertTrue(self.mot("fisc", "mcp__slack__send_message", {}).startswith("policy:"))
        self.assertIsNone(self.mot("fisc", "Bash", {"command": "rm -f tmp1"}))             # allow esplicito
        self.assertEqual(self.mot("zz", "Bash", {"command": "rm -f tmp1"}), "cancella")    # altro agente: come sempre
        self.assertEqual(self.mot("zz", "mcp__slack__send_message", {}), "servizio esterno")  # default invariato

    def test_policy_di_esempio_valida(self):
        d = json.loads((QUI / "policy.esempio.json").read_text(encoding="utf-8"))
        self.assertEqual(d["default"], "invariato")
        self.assertIsNone(conferme.motivo("Read", {}, self.radici, agente="analista-finanziario",
                                          policy_file=QUI / "policy.esempio.json"))
        self.assertTrue(conferme.motivo("mcp__x__send_mail", {}, self.radici, agente="analista-finanziario",
                                        policy_file=QUI / "policy.esempio.json").startswith("policy:"))


class Budget(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.f = Path(self.d.name) / "budget.json"

    def tearDown(self):
        self.d.cleanup()

    def test_senza_tetto_nulla_cambia(self):
        self.assertIsNone(budget.superato("a", self.f))        # file assente
        budget.aggiungi_costo("a", 99.0, self.f)
        self.assertIsNone(budget.superato("a", self.f))        # costo ma niente tetto
        self.assertEqual(json.loads(self.f.read_text())["agenti"]["a"]["costo_usd"], 99.0)

    def test_tetto_superato(self):
        self.f.write_text(json.dumps({"agenti": {"a": {"costo_usd": 0, "tetto_usd": 1.0}}}))
        budget.aggiungi_costo("a", 0.6, self.f)
        self.assertIsNone(budget.superato("a", self.f))
        budget.aggiungi_costo("a", 0.5, self.f)
        self.assertIn("budget superato", budget.superato("a", self.f))
        self.assertEqual(json.loads(self.f.read_text())["agenti"]["a"]["tetto_usd"], 1.0)   # il tetto resta
        self.assertIsNone(budget.superato("b", self.f))        # altro agente senza tetto

    def test_tetto_default(self):
        self.f.write_text(json.dumps({"tetto_default_usd": 0.5}))
        budget.aggiungi_costo("x", 0.7, self.f)
        self.assertIsNotNone(budget.superato("x", self.f))


class Banche(unittest.TestCase):
    def test_banca_stato(self):
        banca_stato = _banca_stato()
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            self.assertEqual(banca_stato(t / "manca"), {"presente": False})
            (t / "MEMORIA.md").write_text("- [A](a.md)\n- [B](b.md)\n", encoding="utf-8")
            (t / "a.md").write_text("a")
            (t / "b.md").write_text("b")
            r = banca_stato(t)
            self.assertEqual((r["file_md"], r["indice_allineato"]), (3, "si"))
            (t / "c.md").write_text("c")                       # file non indicizzato
            r = banca_stato(t)
            self.assertEqual((r["file_md"], r["indice_allineato"]), (4, "no"))
            self.assertTrue(r["ultima_modifica"])

    def test_boss_solo_spia_nel_sorgente(self):
        src = (QUI / "server.py").read_text(encoding="utf-8")
        corpo = src[src.index("def memoria_banche"):src.index("def _att_righe")]
        privata = corpo[corpo.index('"privata"'):]
        self.assertIn('"spia"', privata)
        for vietato in ("rglob", "glob(", "listdir", "iterdir", "read_text", "banca_stato"):
            self.assertNotIn(vietato, privata)


def _estrai(nomi, extra=None):
    """Funzioni e costanti di server.py estratte dal sorgente con ast, senza avviare il server."""
    src = (QUI / "server.py").read_text(encoding="utf-8")
    nodi = []
    for n in ast.parse(src).body:
        if isinstance(n, ast.FunctionDef) and n.name in nomi:
            nodi.append(n)
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in nomi for t in n.targets):
            nodi.append(n)
    import contextvars
    ns = {"re": re, "os": os, "time": time, "threading": threading, "json": json, "Path": Path, "contextvars": contextvars}
    ns.update(extra or {})
    exec(compile(ast.Module(nodi, []), "server.py", "exec"), ns)
    return ns


class ModoApprovazione(unittest.TestCase):
    def _ns(self, modo_config="lavoro", registro=None):
        registro = registro if registro is not None else []
        # DAL_PONTE e modo_sicuro: dal Mac (2026-10-03/04), azione() e claude_comando() li usano
        ns = _estrai({"MODI_CHAT", "modo_chat", "claude_comando", "azione", "_azione", "controlla_dal_ponte", "DAL_PONTE", "modo_sicuro"}, {
            "config_caldo": lambda k, d=None: modo_config,
            "scrivi_config": lambda k, v: registro.append((k, v)),
            "evento": lambda m: None, "tocca": lambda n: None,
            # dal Mac (2026-10-03): «approvazione» chiede strumento per strumento al gestore dei permessi (MCP)
            "config_mcp_approvazioni": lambda *a, **k: "/tmp/mcp-prova.json",
            "approvazioni": type("A", (), {"regole_ask": staticmethod(lambda: ["Bash"])})})
        return ns, registro

    def test_approvazione_accettata_e_uguale_a_lettura_nei_permessi(self):
        ns, scritti = self._ns()
        self.assertEqual(ns["MODI_CHAT"], ("lavoro", "lettura", "approvazione"))
        r = ns["azione"]({"tipo": "modo_chat", "modo": "approvazione"})
        self.assertEqual(r["modo"], "approvazione")
        self.assertEqual(scritti, [("modo_chat", "approvazione")])
        cl = ns["claude_comando"]
        # dal Mac (2026-10-03): non più uguale a «lettura», ma ogni strumento passa dal gestore dei permessi
        self.assertIn("--permission-prompt-tool", cl("x", modo="approvazione"))
        self.assertIn("plan", cl("x", modo="lettura"))
        self.assertNotIn("--dangerously-skip-permissions", cl("x", modo="approvazione"))
        self.assertIn("--dangerously-skip-permissions", cl("x", modo="lavoro"))

    def test_modo_chat_riporta_approvazione_col_suo_nome(self):
        ns, _ = self._ns("approvazione")
        self.assertEqual(ns["modo_chat"](), "approvazione")
        self.assertIn("--permission-prompt-tool", ns["claude_comando"]("x"))       # senza modo: quello di configurazione
        ns2, _ = self._ns("inventato")
        self.assertEqual(ns2["modo_chat"](), "lavoro")

    def test_modo_non_valido_rifiutato_col_messaggio_giusto(self):
        ns, scritti = self._ns()
        for brutto in ("sudo", "", None, 5):
            with self.assertRaises(ValueError) as c:
                ns["azione"]({"tipo": "modo_chat", "modo": brutto})
            self.assertIn("lavoro, lettura o approvazione", str(c.exception))
        self.assertEqual(scritti, [])

    def test_decisione_chat_scrive_una_riga_e_tronca(self):
        ns, _ = self._ns()
        with tempfile.TemporaryDirectory() as t:
            vecchio = audit.AUDIT_FILE
            audit.AUDIT_FILE = Path(t) / "a.jsonl"
            try:
                r1 = ns["azione"]({"tipo": "decisione_chat", "decisione": "approvata",
                                   "richiesta": "R" * 500, "agente": "analista-finanziario"})
                r2 = ns["azione"]({"tipo": "decisione_chat", "decisione": "rifiutata", "richiesta": "ciao"})
                righe = [json.loads(x) for x in audit.AUDIT_FILE.read_text(encoding="utf-8").splitlines()]
            finally:
                audit.AUDIT_FILE = vecchio
        self.assertEqual((r1, r2), ({"ok": True}, {"ok": True}))
        self.assertEqual(len(righe), 2)
        a, b = righe
        self.assertEqual((a["verdetto"], a["tool"], a["regola"], a["approvato_da"], a["agente"]),
                         ("approvato", "chat", "modo approvazione", "utente", "analista-finanziario"))
        self.assertEqual(len(a["sintesi"]), 200)
        self.assertEqual((b["verdetto"], b["agente"], b["sintesi"]), ("rifiutato", "", "ciao"))

    def test_decisione_chat_non_scrive_segreti(self):
        ns, _ = self._ns()
        with tempfile.TemporaryDirectory() as t:
            vecchio = audit.AUDIT_FILE
            audit.AUDIT_FILE = Path(t) / "a.jsonl"
            try:
                ns["azione"]({"tipo": "decisione_chat", "decisione": "approvata",
                              "richiesta": "usa password=SuperSegreto123 e sk-abcdefghijkl"})
                testo = audit.AUDIT_FILE.read_text(encoding="utf-8")
            finally:
                audit.AUDIT_FILE = vecchio
        self.assertNotIn("SuperSegreto123", testo)
        self.assertNotIn("sk-abcdefghijkl", testo)

    def test_decisione_chat_input_non_valido_rifiutato(self):
        ns, _ = self._ns()
        with tempfile.TemporaryDirectory() as t:
            vecchio = audit.AUDIT_FILE
            audit.AUDIT_FILE = Path(t) / "a.jsonl"
            try:
                for dati in ({"decisione": "forse", "richiesta": "x"},
                             {"decisione": None, "richiesta": "x"},
                             {"decisione": "approvata"},
                             {"decisione": "approvata", "richiesta": "   "},
                             {"decisione": "approvata", "richiesta": 42},
                             {"decisione": "approvata", "richiesta": "x", "agente": "../../etc"},
                             {"decisione": "approvata", "richiesta": "x", "agente": ["a"]}):
                    with self.assertRaises(ValueError, msg=str(dati)):
                        ns["azione"]({"tipo": "decisione_chat", **dati})
                self.assertFalse(audit.AUDIT_FILE.exists())
            finally:
                audit.AUDIT_FILE = vecchio


class Risorse(unittest.TestCase):
    def _risorse(self):
        return _estrai({"_RIS", "_RIS_LOCK", "_cpu_tempi_win", "_cpu_percento", "_ram_percento", "risorse"},
                       {"_RIS_LOCK_": None, "threading": threading})["risorse"]

    def test_risorse_interi_0_100_o_null(self):
        r = self._risorse()()
        self.assertEqual(set(r), {"cpu", "ram", "ts"})
        for k in ("cpu", "ram"):
            self.assertTrue(r[k] is None or (isinstance(r[k], int) and not isinstance(r[k], bool)
                                              and 0 <= r[k] <= 100), (k, r[k]))
        self.assertIsInstance(r["ts"], int)
        if sys.platform == "win32":
            self.assertIsNotNone(r["ram"])

    def test_risorse_cache_di_2_secondi_e_mai_eccezioni(self):
        risorse = self._risorse()
        a = risorse()
        self.assertEqual(risorse(), a)                  # entro 2 s: la stessa lettura
        ns = _estrai({"_RIS", "_RIS_LOCK", "_cpu_percento", "_ram_percento", "risorse"})
        def boom():
            raise RuntimeError("x")
        ns["_cpu_percento"] = ns["_ram_percento"] = boom
        r = ns["risorse"]()
        self.assertEqual((r["cpu"], r["ram"]), (None, None))


if __name__ == "__main__":
    unittest.main(verbosity=1)
