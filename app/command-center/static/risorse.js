// Risorse del computer nel piede della colonna sinistra: "CPU 27%  RAM 71%", ciascuna con un puntino
// colorato (verde sotto 70, ambra da 70 a 89, rosso da 90).
// Legge /api/risorse ogni 5 secondi solo se la scheda e' visibile, una richiesta alla volta.
// Se manca l'endpoint o i valori sono null mostra "n.d." senza errori in console.
(function () {
  "use strict";
  const PERIODO = 5000;
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };

  function voce(nome) {
    const w = el("span", "ris-voce nd");
    const p = el("i", "ris-punto");
    p.setAttribute("aria-hidden", "true");
    const t = el("span", "ris-txt", nome + " n.d.");
    w.append(p, t);
    return { w, t, nome };
  }
  function mostra(v, val) {
    const ok = typeof val === "number" && isFinite(val);
    if (!ok) { v.w.className = "ris-voce nd"; v.t.textContent = v.nome + " n.d."; return; }
    const p = Math.max(0, Math.min(100, Math.round(val)));
    v.w.className = "ris-voce " + (p >= 90 ? "rosso" : p >= 70 ? "ambra" : "verde");
    v.t.textContent = v.nome + " " + p + "%";
  }

  function avvia() {
    const piede = document.getElementById("lato-piede");
    if (!piede) return;
    const cpu = voce("CPU"), ram = voce("RAM");
    piede.replaceChildren(cpu.w, ram.w);

    let inVolo = false, fermo = false;
    async function leggi() {
      if (document.hidden || inVolo || fermo) return;
      inVolo = true;
      try {
        const r = await fetch("/api/risorse", { headers: { "X-Token": window.CC_TOKEN || "" }, cache: "no-store" });
        if (r.status === 404) fermo = true;      // endpoint assente: non si insiste
        const d = r.ok ? await r.json() : null;
        mostra(cpu, d ? d.cpu : null);
        mostra(ram, d ? d.ram : null);
      } catch (e) {
        mostra(cpu, null); mostra(ram, null);
      } finally { inVolo = false; }
    }
    setInterval(leggi, PERIODO);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) leggi(); });
    leggi();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia); else avvia();
})();
