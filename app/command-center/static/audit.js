// Vista Audit: registro delle azioni degli agenti. Dati: GET /api/audit (puo' mancare).
// Colonne: quando, chi, cosa, banca, esito, dettaglio. Filtri: agente, banca, tipo, solo errori.
// Tutto il testo entra nel DOM con textContent. Il token e' quello gia' usato da app.js.
(function () {
  "use strict";
  const V = window.CCVivo || null;   // effetti vivi (vivo.js); senza, tutto funziona lo stesso
  let righe = [];
  let stato = "attesa";        // attesa | ok | assente
  let motivo = "";
  let viste = new Set();       // chiavi delle righe gia' mostrate: le altre entrano dall'alto
  let nuove = new Set();       // righe arrivate con l'ultima lettura (si usa una volta sola)
  const tremate = new Set();   // righe "bloccato" che hanno gia' tremato
  let firma = "";              // se nulla cambia la tabella non si ridisegna
  const filtri = { agente: "", banca: "", tipo: "", errori: false };

  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const prima = (o, chiavi) => { for (const k of chiavi) if (o[k] != null && o[k] !== "") return o[k]; return ""; };
  const txt = (v) => (v == null ? "" : typeof v === "object" ? JSON.stringify(v) : String(v));

  function normalizza(r) {
    if (!r || typeof r !== "object") return { quando: "", chi: "", cosa: txt(r), banca: "", esito: "", tipo: "", dettaglio: "", ts: 0, k: "x|" + txt(r) };
    const q = prima(r, ["quando", "ts", "ora", "data", "timestamp", "t"]);
    const ts = typeof q === "number" ? (q < 1e12 ? q * 1000 : q) : Date.parse(q) || 0;
    const o = {
      quando: ts ? new Date(ts).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : txt(q),
      ts,
      chi: txt(prima(r, ["chi", "agente", "attore", "autore"])),
      cosa: txt(prima(r, ["cosa", "azione", "operazione", "evento", "sintesi", "tool"])),
      banca: txt(prima(r, ["banca", "memoria"])),
      esito: txt(prima(r, ["esito", "risultato", "verdetto", "stato"])),
      tipo: txt(prima(r, ["tipo", "categoria"])),
      dettaglio: prima(r, ["dettaglio", "dettagli", "nota", "messaggio", "regola"]),
    };
    o.k = [o.ts, o.chi, o.cosa, o.banca, o.esito].join("|");
    return o;
  }
  const eErrore = (x) => { const e = x.esito.toLowerCase(); return !!e && !["ok", "riuscito", "successo", "eseguito", "true", "consentito", "approvato", "allow"].includes(e); };
  const eBloccata = (x) => /bloccat|negat|deny|denied|rifiutat/i.test(x.esito);

  async function leggi() {
    let err = null;
    try {
      const r = await fetch("/api/audit", { headers: { "X-Token": window.CC_TOKEN }, cache: "no-store" });
      if (!r.ok) throw new Error(r.status === 404 ? "endpoint non presente" : "risposta " + r.status);
      const j = await r.json();
      const lista = Array.isArray(j) ? j : j && (j.voci || j.righe || j.eventi || j.audit || j.registro);
      if (!Array.isArray(lista)) throw new Error("formato non riconosciuto");
      righe = lista.map(normalizza).sort((a, b) => b.ts - a.ts);
      // dalla seconda lettura in poi le righe mai viste sono "nuove"
      nuove = viste.size ? new Set(righe.filter((x) => !viste.has(x.k)).map((x) => x.k)) : new Set();
      for (const x of righe) viste.add(x.k);
      stato = "ok"; motivo = "";
    } catch (e) {
      righe = []; stato = "assente"; motivo = String((e && e.message) || "non raggiungibile"); err = motivo;
    }
    disegna();
    return err;
  }
  const rileggi = () => (V ? V.esegui("audit") : leggi());

  // scheletro con shimmer mentre il registro si carica
  function scheletro() {
    const w = el("div", "audit-scheletro");
    w.setAttribute("aria-busy", "true");
    w.setAttribute("aria-label", "Lettura del registro");
    for (let i = 0; i < 7; i++) {
      const r = el("div", "sk-riga");
      for (let c = 0; c < 6; c++) r.appendChild(el("i"));
      w.appendChild(r);
    }
    return w;
  }

  function selettore(etichetta, chiave, valori) {
    const l = el("label", null, etichetta);
    const s = el("select");
    const tutti = el("option", null, "tutti"); tutti.value = ""; s.appendChild(tutti);
    for (const v of valori) { const o = el("option", null, v); o.value = v; s.appendChild(o); }
    s.value = valori.includes(filtri[chiave]) ? filtri[chiave] : "";
    s.addEventListener("change", () => { filtri[chiave] = s.value; disegna(); });
    l.appendChild(s);
    return l;
  }
  const distinti = (k) => [...new Set(righe.map((x) => x[k]).filter(Boolean))].sort();

  function disegna() {
    const radice = document.getElementById("audit-radice");
    if (!radice) return;
    if (V) {
      const h2 = document.querySelector("#box-audit h2");
      const ind = V.indicatore("audit");
      if (h2 && ind.parentNode !== h2) h2.appendChild(ind);
    }
    const f0 = stato + "|" + motivo + "|" + JSON.stringify(filtri) + "|" + righe.map((x) => x.k).join(",");
    if (f0 === firma && radice.firstChild) return;
    firma = f0;
    radice.replaceChildren();
    if (stato === "attesa") { radice.appendChild(scheletro()); return; }
    if (stato === "assente") {
      const p = el("div", "audit-vuoto");
      p.appendChild(el("b", null, "Registro non disponibile. "));
      p.appendChild(document.createTextNode("Il server non ha ancora il registro delle azioni (" + motivo + "). Quando sara' attivo, qui compariranno quando, chi, cosa, banca, esito e dettaglio di ogni azione."));
      const b = el("button", "piccolo", "Riprova"); b.type = "button"; b.addEventListener("click", rileggi);
      p.appendChild(document.createElement("br")); p.appendChild(b);
      radice.appendChild(p);
      return;
    }
    const f = el("div", "audit-filtri");
    f.appendChild(selettore("Agente", "agente", distinti("chi")));
    f.appendChild(selettore("Banca", "banca", distinti("banca")));
    f.appendChild(selettore("Tipo", "tipo", distinti("tipo")));
    const lc = el("label", "audit-chk");
    const c = el("input"); c.type = "checkbox"; c.checked = filtri.errori;
    c.addEventListener("change", () => { filtri.errori = c.checked; disegna(); });
    lc.appendChild(c); lc.appendChild(document.createTextNode("solo errori"));
    f.appendChild(lc);
    if (V) f.appendChild(V.bottoneRileggi("audit"));
    else { const r = el("button", "piccolo", "Rileggi"); r.type = "button"; r.addEventListener("click", rileggi); f.appendChild(r); }
    radice.appendChild(f);

    const vis = righe.filter((x) => (!filtri.agente || x.chi === filtri.agente) && (!filtri.banca || x.banca === filtri.banca)
      && (!filtri.tipo || x.tipo === filtri.tipo) && (!filtri.errori || eErrore(x)));
    if (!vis.length) { radice.appendChild(el("p", "audit-vuoto", righe.length ? "Nessuna azione con questi filtri." : "Il registro e' vuoto: nessuna azione registrata finora.")); return; }
    const wrap = el("div", "audit-scorri");
    const t = el("table", "audit-tab");
    const tr0 = el("tr");
    for (const h of ["Quando", "Chi", "Cosa", "Banca", "Esito", "Dettaglio"]) tr0.appendChild(el("th", null, h));
    const th = el("thead"); th.appendChild(tr0); t.appendChild(th);
    const tb = el("tbody");
    for (const x of vis.slice(0, 500)) {
      const cl = [];
      if (eErrore(x)) cl.push("errore");
      if (nuove.has(x.k)) cl.push("nuova");
      if (eBloccata(x)) { cl.push("bloccata"); if (!tremate.has(x.k)) { tremate.add(x.k); cl.push("tremola"); } }   // trema una volta sola
      const tr = el("tr", cl.join(" "));
      for (const v of [x.quando, x.chi, x.cosa, x.banca, x.esito]) tr.appendChild(el("td", null, v || "-"));
      const td = el("td");
      const d = txt(x.dettaglio);
      if (d) {
        const det = el("details"); det.appendChild(el("summary", null, "apri"));
        det.appendChild(el("pre", null, typeof x.dettaglio === "object" ? JSON.stringify(x.dettaglio, null, 2) : d));
        td.appendChild(det);
      } else td.textContent = "-";
      tr.appendChild(td); tb.appendChild(tr);
    }
    t.appendChild(tb); wrap.appendChild(t); radice.appendChild(wrap);
    nuove = new Set();
    radice.appendChild(el("p", "audit-conta", vis.length + " azioni" + (vis.length > 500 ? " (prime 500 mostrate)" : "") + " su " + righe.length));
  }

  function avvia() {
    if (V) V.collega("audit", leggi);
    disegna();
    rileggi();
    window.addEventListener("hashchange", () => { if (location.hash === "#audit") rileggi(); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia); else avvia();
})();
