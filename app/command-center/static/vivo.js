// Interfaccia viva: rilettura automatica ogni 15 secondi, anello
// "aggiornato alle", tasto Rileggi con icona che ruota, count-up dei numeri.
// Solo JS vanilla. Si anima solo con transform e opacity (le regole stanno in super.css).
// Con prefers-reduced-motion: reduce non parte nulla: restano gli stati finali.
(function () {
  "use strict";
  const PERIODO = 15000;          // rilettura automatica
  const MIN_GIRO = 600;           // l'icona di Rileggi gira almeno questo tempo, cosi' si vede
  const RID = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };
  const ridotto = () => !!RID.matches;
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const hhmm = (d) => d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });

  // ------------------------------------------------------------------ rilettura automatica
  const viste = {};               // nome -> { leggi, inVolo, ultimo, ind, txt, eraVis }
  let tic = null;

  const sezione = (nome) => document.querySelector('.vista[data-vista="' + nome + '"]');
  const visibile = (nome) => { const s = sezione(nome); return !document.hidden && !!s && s.classList.contains("attiva"); };

  function collega(nome, leggi) {
    viste[nome] = viste[nome] || { inVolo: false, ultimo: 0, ind: null, txt: null, eraVis: false };
    viste[nome].leggi = leggi;
    avviaTic();
  }

  // anello + testo "aggiornato alle HH:MM"; l'elemento e' unico per vista e va solo riappoggiato
  function indicatore(nome) {
    const v = (viste[nome] = viste[nome] || { inVolo: false, ultimo: 0, ind: null, txt: null, eraVis: false });
    if (v.ind) return v.ind;
    const w = el("span", "vivo-ind");
    w.setAttribute("role", "status");
    const anello = el("span", "anello");
    anello.setAttribute("aria-hidden", "true");
    for (const c of ["ad", "as"]) { const m = el("span", "meta " + c); m.appendChild(el("i")); anello.appendChild(m); }
    v.txt = el("span", "vivo-txt", "in attesa");
    w.appendChild(anello); w.appendChild(v.txt);
    v.ind = w;
    return w;
  }

  function riavviaAnello(v) {
    if (!v.ind || !v.ind.getAnimations) return;
    for (const a of v.ind.getAnimations({ subtree: true })) { try { a.currentTime = 0; a.play(); } catch (e) { /* niente */ } }
  }
  function sincronizza(nome) {
    const v = viste[nome];
    if (!v || !v.ind || !v.ultimo || !v.ind.getAnimations) return;
    const t = Math.min(Date.now() - v.ultimo, PERIODO);
    for (const a of v.ind.getAnimations({ subtree: true })) { try { a.currentTime = t; } catch (e) { /* niente */ } }
  }

  function segnaRileggi(nome, acceso) {
    const s = sezione(nome);
    if (!s) return;
    for (const b of s.querySelectorAll(".btn-rileggi")) {
      b.classList.toggle("leggendo", acceso);
      b.setAttribute("aria-busy", acceso ? "true" : "false");
    }
  }

  // una sola richiesta in volo per vista; leggi() ritorna null se va bene, il motivo se fallisce
  async function esegui(nome) {
    const v = viste[nome];
    if (!v || !v.leggi || v.inVolo) return false;
    v.inVolo = true;
    const t0 = Date.now();
    segnaRileggi(nome, true);
    let errore = null;
    try { errore = await v.leggi(); } catch (e) { errore = String((e && e.message) || "non raggiungibile"); }
    v.inVolo = false;
    v.ultimo = Date.now();
    if (v.txt) {
      v.txt.textContent = errore ? "non disponibile" + (typeof errore === "string" ? " (" + errore + ")" : "") : "aggiornato alle " + hhmm(new Date());
      v.ind.title = errore ? "Ultima lettura non riuscita" : "Prossima rilettura automatica fra 15 secondi";
    }
    riavviaAnello(v);
    const resto = ridotto() ? 0 : Math.max(0, MIN_GIRO - (Date.now() - t0));
    setTimeout(() => { if (!v.inVolo) segnaRileggi(nome, false); }, resto);
    return true;
  }

  function tick() {
    if (document.hidden) return;
    const ora = Date.now();
    for (const nome of Object.keys(viste)) {
      const v = viste[nome];
      const vis = visibile(nome);
      if (vis && !v.eraVis) sincronizza(nome);
      v.eraVis = vis;
      if (vis && !v.inVolo && v.leggi && ora - v.ultimo >= PERIODO) esegui(nome);
    }
  }
  function avviaTic() { if (!tic && !document.hidden) tic = setInterval(tick, 1000); }
  function fermaTic() { if (tic) { clearInterval(tic); tic = null; } for (const n of Object.keys(viste)) viste[n].eraVis = false; }
  document.addEventListener("visibilitychange", () => { if (document.hidden) fermaTic(); else { avviaTic(); tick(); } });
  window.addEventListener("hashchange", () => requestAnimationFrame(tick));

  // ------------------------------------------------------------------ tasto Rileggi
  function bottoneRileggi(nome) {
    const b = el("button", "piccolo btn-rileggi");
    b.type = "button";
    const i = el("span", "ico-rileggi", "↻");
    i.setAttribute("aria-hidden", "true");
    b.appendChild(i);
    b.appendChild(el("span", null, "Rileggi"));
    b.addEventListener("click", () => esegui(nome));
    const v = viste[nome];
    if (v && v.inVolo) { b.classList.add("leggendo"); b.setAttribute("aria-busy", "true"); }
    return b;
  }

  // ------------------------------------------------------------------ count-up (600 ms di default)
  function contaSu(nodo, fine, ms) {
    fine = Number(fine);
    if (!isFinite(fine) || ridotto() || !window.requestAnimationFrame) { nodo.textContent = String(fine); return; }
    const durata = ms || 600;
    const t0 = performance.now();
    nodo.textContent = "0";
    function passo(t) {
      if (!nodo.isConnected) return;
      const k = Math.min(1, (t - t0) / durata);
      const e = 1 - Math.pow(1 - k, 3);
      nodo.textContent = String(Math.round(fine * e));
      if (k < 1) requestAnimationFrame(passo); else nodo.textContent = String(fine);
    }
    requestAnimationFrame(passo);
  }

  window.CCVivo = { collega, indicatore, bottoneRileggi, esegui, contaSu, ridotto };

})();
