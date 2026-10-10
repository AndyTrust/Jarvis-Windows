// Smistamento: mentre scrivi nella chat con Jarvis, suggerisce a quale agente di un progetto potrebbe andare la domanda.
// Regole a parole chiave, tutte qui, tutte nel browser: il testo non va da nessuna parte e non si chiama nessun modello.
// Punto d'innesto per un classificatore vero (per esempio Laya): window.CC_SMISTA_ESTERNO = async (testo, agenti) =>
//   [{ key, punteggio }] con punteggio da 0 a 1; se risponde, vince sulle regole; se fallisce, restano le regole.
(function () {
  "use strict";
  // regole: window.CC_SMISTA_REGOLE, da smista-regole.js (nome dell'agente in minuscolo -> [[espressione, peso]]).
  // Si suggerisce solo un agente che esiste nel catalogo. Senza regole non si suggerisce niente.
  let COMPILATE = null;
  function compila() {
    const r = window.CC_SMISTA_REGOLE;
    COMPILATE = r && typeof r === "object"
      ? Object.entries(r).map(([nome, regole]) => [nome.toLowerCase(), regole.map(([re, peso]) => [new RegExp(re, "i"), peso])]) : [];
  }
  const MIN_PUNTEGGIO = 2, MIN_LUNGHEZZA = 12, MAX_SUGGERITI = 2;

  let agenti = null, caricando = false, ultimaLettura = 0;
  async function leggiCatalogo() {
    if (caricando || (agenti && Date.now() - ultimaLettura < 300000)) return;
    caricando = true;
    try {
      const r = await fetch("/api/catalogo", { headers: { "X-Token": window.CC_TOKEN }, cache: "no-store" });
      if (!r.ok) throw new Error(String(r.status));
      const c = await r.json();
      const lista = [];
      for (const s of c.spazi || []) for (const p of s.progetti || []) for (const a of p.agenti || []) {
        if (a && a.nome) lista.push({ key: p.id + ":" + a.nome, nome: String(a.nome), progetto: String(p.nome || p.id || ""),
          descr: String(a.descrizione || a.description || "") });
      }
      agenti = lista; ultimaLettura = Date.now();
    } catch (e) { /* senza catalogo non si suggerisce niente */ } finally { caricando = false; }
  }

  // punteggio di un testo per ogni agente del catalogo: somma dei pesi delle regole che scattano (ognuna una volta)
  function punteggi(testo) {
    const out = [];
    for (const a of agenti || []) {
      if (!COMPILATE) compila();
      let regola = COMPILATE.find(([nome]) => nome === a.nome.toLowerCase());
      if (!regola && a.descr) {     // nessuna regola scritta: le parole lunghe della missione, una volta sola, peso 1
        const radici = [...new Set((a.descr.toLowerCase().match(/[a-zàèéìòù]{6,}/g) || []).map((w) => w.slice(0, 6)))].slice(0, 25);
        regola = [a.nome.toLowerCase(), radici.map((r) => [new RegExp(r, "i"), 1])];
      }
      if (!regola) continue;
      let p = 0;
      for (const [re, peso] of regola[1]) if (re.test(testo)) p += peso;
      if (p > 0) out.push({ agente: a, punteggio: p });
    }
    return out.sort((x, y) => y.punteggio - x.punteggio);
  }

  async function suggerisci(testo) {
    const t = testo.trim();
    if (t.length < MIN_LUNGHEZZA || t.startsWith("/")) return [];
    if (typeof window.CC_SMISTA_ESTERNO === "function") {
      try {
        const r = await window.CC_SMISTA_ESTERNO(t, agenti || []);
        if (Array.isArray(r) && r.length) {
          return r.map((x) => ({ agente: (agenti || []).find((a) => a.key === x.key), punteggio: x.punteggio }))
            .filter((x) => x.agente && x.punteggio >= 0.5).slice(0, MAX_SUGGERITI);
        }
      } catch (e) { /* ripiego: le regole */ }
    }
    return punteggi(t).filter((x) => x.punteggio >= MIN_PUNTEGGIO).slice(0, MAX_SUGGERITI);
  }

  function el(tag, cls, txt) { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }

  function avvia() {
    const ta = document.getElementById("chiedi-testo");
    const form = document.getElementById("form-chiedi");
    if (!ta || !form || document.getElementById("smista")) return;
    const box = el("div", "smista nascosto");
    box.id = "smista"; box.setAttribute("role", "status"); box.setAttribute("aria-live", "polite");
    form.insertAdjacentElement("beforebegin", box);
    let timer = null, versione = 0;

    function mostra(lista, testo) {
      box.textContent = "";
      if (!lista.length) { box.classList.add("nascosto"); return; }
      box.appendChild(el("span", "smista-etichetta", "Sembra per:"));
      for (const x of lista) {
        const b = el("button", "smista-chip", x.agente.nome);
        b.type = "button";
        b.title = "Apri la chat con " + x.agente.nome + " (" + x.agente.progetto + "). Il testo che hai scritto resta.";
        b.addEventListener("click", () => {
          const scritto = ta.value;
          if (typeof window.apriChat === "function") window.apriChat(x.agente.key);
          setTimeout(() => { const c = document.getElementById("chiedi-testo"); if (c && !c.value) { c.value = scritto; c.focus(); } }, 150);
          box.classList.add("nascosto");
        });
        box.appendChild(b);
      }
      box.appendChild(el("small", "smista-nota", "a parole chiave, nel tuo browser"));
      box.classList.remove("nascosto");
    }

    ta.addEventListener("input", () => {
      clearTimeout(timer);
      const mia = ++versione;
      timer = setTimeout(async () => {
        await leggiCatalogo();
        const lista = await suggerisci(ta.value);
        if (mia === versione) mostra(lista, ta.value);
      }, 300);
    });
    form.addEventListener("submit", () => { versione++; box.classList.add("nascosto"); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia); else avvia();
  window.CC_SMISTA_PROVA = { punteggi: (t, a) => { agenti = a; return punteggi(t); } };   // solo per le prove automatiche
})();
