// La pagina «Progetti» del Command Center (2026-10-10, si parte da zero): l'elenco dei progetti che esistono, letto da
// GET /api/progetti (spazi.json + cartelle + schede: una sola fonte), e per ogni progetto la sua pagina: cartella e
// file caricati (con caricamento), indice dei file, agenti con missione, modello, strumenti, limiti e diario
// modificabili, Stato.md dello spazio. Ogni modifica passa da POST /api/progetto/azione, che usa gli stessi script
// dell'assistente (crea_progetto.py, crea_agente.py) e scrive i file veri con copia di sicurezza.
// Si aggiorna da sola: app.js rilancia gli eventi del flusso come «cc:flusso» e qui si rilegge su «progetti» e «spazi».
// Con zero progetti mostra lo stato vuoto anche su Lavagna, Squadra e Missioni. Aggiunge il diario dell'agente nella
// sua scheda della lavagna. Testi sempre con textContent.
(function progetti() {
  "use strict";
  const S = { elenco: null, archiviati: [], scelto: "", dati: null, vuoto: "", attesa: null, modificando: false };
  const token = () => window.CC_TOKEN || "";
  function el(tag, attrs, ...figli) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v; else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (k === "value") n.value = v; else n.setAttribute(k, String(v));
    }
    for (const f of figli) if (f != null && f !== false) n.append(f instanceof Node ? f : document.createTextNode(String(f)));
    return n;
  }
  async function chiedi(percorso, corpo) {
    const r = await fetch(percorso, corpo === undefined ? { headers: { "X-Token": token() }, cache: "no-store" }
      : { method: "POST", headers: { "X-Token": token(), "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
    let d = {};
    try { d = await r.json(); } catch (e) { /* non JSON */ }
    if (!r.ok) throw new Error(d.errore || ("errore " + r.status));
    return d;
  }
  const N = {};
  function avviso(testo, errore) {
    if (N.nota) { N.nota.textContent = testo; N.nota.className = "pg-nota" + (errore ? " pg-errore" : ""); }
  }

  // ---------------------------------------------------------------- menu e vista
  function creaVoceMenu() {
    const menu = document.querySelector(".schede.menu");
    if (menu && !document.querySelector('a[data-vista="progetti"]')) {
      const a = el("a", { href: "#progetti", "data-vista": "progetti", title: "I progetti, i loro file e i loro agenti" },
        el("i", { class: "spia grigia" }), "Progetti");
      const dopo = menu.querySelector('a[data-vista="lavagna"]');
      if (dopo && dopo.nextSibling) dopo.parentNode.insertBefore(a, dopo.nextSibling); else menu.append(a);
    }
    const griglia = document.querySelector("#m-foglio .m-foglio-griglia");
    if (griglia && !griglia.querySelector('a[data-vista="progetti"]')) {
      griglia.prepend(el("a", { href: "#progetti", "data-vista": "progetti" }, el("span", { class: "m-ico", "aria-hidden": "true" }, "▦"), el("span", {}, "Progetti")));
    }
    try { if (typeof TITOLI === "object" && TITOLI && !TITOLI.progetti) TITOLI.progetti = "Progetti"; } catch (e) { /* app.js vecchio */ } // eslint-disable-line no-undef
  }
  function creaVista() {
    const main = document.querySelector("main");
    let sez = document.querySelector('.vista[data-vista="progetti"]');     // di solito c'è già in index.html (routing)
    if (!main || (sez && sez.childElementCount)) return;
    N.elenco = el("div", { class: "pg-elenco", role: "list" });
    N.archiviati = el("div", { class: "pg-archiviati" });
    N.pagina = el("div", { class: "pg-pagina" });
    N.nota = el("p", { class: "pg-nota", role: "status" });
    N.nuovo = el("form", { class: "pg-nuovo", onsubmit: nuovoProgetto },
      el("label", {}, "Nome ", el("input", { name: "nome", required: "required", maxlength: "60", placeholder: "<nome-progetto>" })),
      el("label", {}, "A cosa serve ", el("input", { name: "descrizione", maxlength: "300", placeholder: "una riga (facoltativa)" })),
      el("label", {}, "Cartella ", el("input", { name: "cartella", maxlength: "400", placeholder: "vuota = cartella nuova in Progetti" })),
      el("button", { type: "submit" }, "Crea il progetto"));
    N.nuovo.hidden = true;
    const testa = el("div", { class: "pg-testa" }, el("h2", {}, "Progetti"),
      el("button", { type: "button", class: "pg-bottone", onclick: () => { N.nuovo.hidden = !N.nuovo.hidden; } }, "＋ Nuovo progetto"));
    // chi scrive in un campo della pagina: gli aggiornamenti del flusso non ricreano i campi (si rinfrescano solo file e Stato.md)
    N.pagina.addEventListener("input", () => { S.modificando = true; });
    if (!sez) { sez = el("section", { class: "vista vista-progetti", "data-vista": "progetti" }); main.append(sez); }
    sez.append(testa, N.nuovo, N.nota, N.elenco, N.pagina, N.archiviati);
  }

  // ---------------------------------------------------------------- elenco
  async function leggiElenco() {
    try {
      const d = await chiedi("/api/progetti");
      S.elenco = d.progetti || []; S.vuoto = d.vuoto || ""; S.archiviati = d.archiviati || [];
      disegnaElenco();
      disegnaArchiviati();
      bannerVuoti();
      if (S.scelto && !S.elenco.some((p) => p.id === S.scelto)) S.scelto = "";
      if (!S.scelto && S.elenco.length) S.scelto = S.elenco[0].id;
      if (S.scelto) leggiProgetto(); else N.pagina.replaceChildren();
    } catch (e) { avviso("Progetti non letti: " + e.message, true); }
  }
  function disegnaElenco() {
    N.elenco.replaceChildren();
    if (!S.elenco.length) {
      N.elenco.append(el("div", { class: "pg-vuoto" },
        el("p", {}, S.vuoto || "Di' all'assistente di crearne uno (o /nuovo-progetto <nome> in Claude Code)."),
        el("p", {}, el("button", { type: "button", class: "pg-bottone", onclick: () => { N.nuovo.hidden = false; N.nuovo.querySelector("[name=nome]").focus(); } }, "Crea il tuo primo progetto"))));
      return;
    }
    for (const p of S.elenco) {
      N.elenco.append(el("button", { type: "button", role: "listitem", class: "pg-voce" + (p.id === S.scelto ? " pg-scelto" : ""),
        onclick: () => { S.scelto = p.id; S.modificando = false; disegnaElenco(); leggiProgetto(); } },
      el("b", {}, p.nome), el("small", {}, `${p.spazio} · ${p.agenti} agenti · ${p.file} file${p.esiste ? "" : " · cartella mancante"}`)));
    }
  }
  async function nuovoProgetto(ev) {
    ev.preventDefault();
    const f = new FormData(N.nuovo);
    try {
      const d = await chiedi("/api/progetto/azione", { cosa: "crea_progetto", nome: f.get("nome"), descrizione: f.get("descrizione"), cartella: f.get("cartella") });
      N.nuovo.reset(); N.nuovo.hidden = true; S.scelto = d.id || S.scelto;
      avviso("Progetto creato con il suo capogruppo"); leggiElenco();
    } catch (e) { avviso(e.message, true); }
  }

  // ---------------------------------------------------------------- pagina del progetto
  function disegnaArchiviati() {
    N.archiviati.replaceChildren();
    if (!S.archiviati.length) return;
    const lista = el("ul", { class: "pg-file" });
    for (const a of S.archiviati) {
      lista.append(el("li", {}, el("b", {}, a.nome), ` · archiviato ${a.archiviato || ""} · ${a.cartella || ""} `,
        el("button", { type: "button", onclick: () => azione({ cosa: "ripristina_progetto", progetto: a.id }, `«${a.nome}» ripristinato`) }, "Ripristina")));
    }
    N.archiviati.append(el("div", { class: "pg-blocco" }, el("h3", {}, "Progetti archiviati"),
      el("p", { class: "pg-piccolo" }, "Cartella, file e memoria sono rimasti dove erano: «Ripristina» li rimette fra i progetti attivi."), lista));
  }
  function fileLista(d) {
    const lista = el("ul", { class: "pg-file" });
    for (const f of d.file || []) lista.append(el("li", {}, el("code", {}, f.nome), ` · ${f.data} · ${Math.max(1, Math.round(f.byte / 1024))} KB`));
    if (!(d.file || []).length) lista.append(el("li", { class: "pg-piccolo" }, "Nessun file ancora: caricali qui o copiali in " + d.file_dir));
    return lista;
  }
  async function leggiProgetto() {
    if (!S.scelto) return;
    try {
      const d = await chiedi("/api/progetto?id=" + encodeURIComponent(S.scelto));
      if (S.modificando && S.dati && S.dati.id === d.id) {          // aggiornamento mirato: i campi in modifica restano
        S.dati = d;
        const vecchia = N.pagina.querySelector(".pg-file"); if (vecchia) vecchia.replaceWith(fileLista(d));
        const st = N.pagina.querySelector(".pg-stato"); if (st) st.textContent = d.stato || "(Stato.md non ancora scritto)";
        return;
      }
      S.dati = d; disegnaProgetto();
    }
    catch (e) { avviso("Progetto non letto: " + e.message, true); }
  }
  async function azione(corpo, fatto) {
    try { await chiedi("/api/progetto/azione", Object.assign({ progetto: S.scelto }, corpo)); avviso(fatto || "Salvato"); S.modificando = false; leggiElenco(); }
    catch (e) { avviso(e.message, true); }
  }
  function disegnaProgetto() {
    const d = S.dati;
    if (!d) return;
    const aperti = new Set([...N.pagina.querySelectorAll("details[open]")].map((x) => x.dataset.chiave));
    N.pagina.replaceChildren();
    const nomeIn = el("input", { value: d.nome, maxlength: "60", "aria-label": "Nome del progetto" });
    const cartIn = el("input", { value: d.cartella, maxlength: "400", "aria-label": "Cartella del progetto", class: "pg-largo" });
    N.pagina.append(el("div", { class: "pg-blocco" }, el("h3", {}, d.nome),
      el("p", { class: "pg-piccolo" }, `Spazio «${d.spazio}» · capogruppo ${d.capogruppo || "—"}`),
      el("div", { class: "pg-riga" }, nomeIn, el("button", { type: "button", onclick: () => azione({ cosa: "rinomina_progetto", nome: nomeIn.value }, "Nome cambiato") }, "Rinomina")),
      el("div", { class: "pg-riga" }, cartIn, el("button", { type: "button", onclick: () => azione({ cosa: "sposta_progetto", cartella: cartIn.value }, "Cartella spostata") }, "Sposta"),
        el("button", { type: "button", class: "pg-pericolo", onclick: () => { if (confirm(`Archiviare «${d.nome}»? Esce dai progetti attivi; cartella, file e memoria restano.`)) azione({ cosa: "archivia_progetto" }, "Progetto archiviato"); } }, "Archivia"))));
    const scegli = el("input", { type: "file", multiple: "multiple", class: "pg-file-in", onchange: (ev) => carica(ev.target.files) });
    const lista = fileLista(d);
    N.pagina.append(el("div", { class: "pg-blocco" }, el("h3", {}, "File del progetto"),
      el("p", { class: "pg-piccolo" }, `Cartella ${d.file_dir}. Indice-file.md si aggiorna da solo e il capogruppo lo legge.`),
      el("label", { class: "pg-bottone" }, "Carica file", scegli), lista));
    const blocco = el("div", { class: "pg-blocco" }, el("h3", {}, "Agenti"));
    for (const a of d.agenti || []) blocco.append(schedaAgente(a, aperti));
    const ruolo = el("input", { placeholder: "ruolo (es. ricerca)", maxlength: "40" });
    const miss = el("input", { placeholder: "missione: cosa fa, su quali file, cosa consegna", maxlength: "600", class: "pg-largo" });
    const mod = el("select", {}, ...["sonnet", "haiku", "opus"].map((m) => el("option", { value: m }, m)));
    blocco.append(el("div", { class: "pg-riga pg-nuovo-agente" }, ruolo, miss, mod,
      el("button", { type: "button", onclick: () => azione({ cosa: "crea_agente", ruolo: ruolo.value, missione: miss.value, modello: mod.value, programma: mod.value === "opus" }, "Specialista creato") }, "＋ Specialista")));
    N.pagina.append(blocco);
    N.pagina.append(el("div", { class: "pg-blocco" }, el("h3", {}, "Stato.md dello spazio"),
      el("pre", { class: "pg-stato" }, d.stato || "(Stato.md non ancora scritto)")));
  }
  function schedaAgente(a, aperti) {
    const det = el("details", { class: "pg-agente", "data-chiave": a.nome });
    if (aperti.has(a.nome)) det.open = true;
    const miss = el("textarea", { rows: "3", maxlength: "600" }); miss.value = a.descrizione || "";
    const mod = el("select", {}, ...["haiku", "sonnet", "opus"].map((m) => el("option", { value: m }, m))); mod.value = a.modello || "sonnet";
    const strum = el("input", { value: (a.strumenti || []).join(", "), placeholder: "vuoto = quelli di base" });
    const lim = el("input", { value: (a.limiti || "").replace(/^- /, "").split("\n")[0], placeholder: "cosa non fa", class: "pg-largo" });
    const nome = el("input", { value: a.nome, maxlength: "40" });
    const diario = el("textarea", { rows: "10", class: "pg-diario" }); diario.value = a.diario_testo || "";
    det.append(el("summary", {}, el("b", {}, a.nome), a.capogruppo ? " · capogruppo" : "", ` · ${a.modello}`),
      el("label", {}, "Missione", miss),
      el("div", { class: "pg-riga" }, el("label", {}, "Modello ", mod), el("label", {}, "Strumenti ", strum), el("label", {}, "Nome ", nome)),
      el("label", {}, "Limiti", lim),
      el("div", { class: "pg-riga" },
        el("button", { type: "button", onclick: () => azione({ cosa: "modifica_agente", nome: a.nome, missione: miss.value, modello: mod.value, strumenti: strum.value, limiti: lim.value, nuovo_nome: nome.value, programma: mod.value === "opus" }, "Scheda salvata") }, "Salva la scheda"),
        a.capogruppo ? null : el("button", { type: "button", class: "pg-pericolo", onclick: () => { if (confirm(`Togliere ${a.nome}? La scheda va in _archivio, il diario resta.`)) azione({ cosa: "togli_agente", nome: a.nome }, "Agente tolto"); } }, "Togli")),
      el("h4", {}, "Diario (Fatto · Da fare · Errori commessi da non ripetere)"), diario,
      el("button", { type: "button", onclick: () => azione({ cosa: "diario", nome: a.nome, testo: diario.value }, "Diario salvato") }, "Salva il diario"));
    return det;
  }
  async function carica(files) {
    for (const f of files) {
      if (f.size > 50 * 1024 * 1024) { avviso(`${f.name}: oltre 50 MB, copialo a mano nella cartella File`, true); continue; }
      const b64 = await new Promise((ok, ko) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(",")[1] || ""); r.onerror = ko; r.readAsDataURL(f); });
      try { await chiedi("/api/progetto/file", { progetto: S.scelto, nome: f.name, base64: b64 }); avviso(`${f.name} caricato`); }
      catch (e) { avviso(`${f.name}: ${e.message}`, true); }
    }
    leggiProgetto();
  }

  // ---------------------------------------------------------------- stato vuoto anche su lavagna, squadra e missioni
  function bannerVuoti() {
    const vuoto = Array.isArray(S.elenco) && !S.elenco.length;
    for (const sel of ["#lavagna", '.vista[data-vista="agenti"]', '.vista[data-vista="missioni"]']) {
      const sez = document.querySelector(sel);
      if (!sez) continue;
      let b = sez.querySelector(":scope > .pg-banner-vuoto");
      if (!vuoto) { if (b) b.remove(); continue; }
      if (!b) {
        b = el("div", { class: "pg-vuoto pg-banner-vuoto" + (sel === "#lavagna" ? " pg-banner-lavagna" : ""), role: "note" },
          el("p", {}, S.vuoto || "Di' all'assistente di crearne uno (o /nuovo-progetto <nome> in Claude Code)."),
          el("p", {}, el("button", { type: "button", class: "pg-bottone", onclick: () => {
            location.hash = "#progetti";
            setTimeout(() => { if (N.nuovo) { N.nuovo.hidden = false; const c = N.nuovo.querySelector("[name=nome]"); if (c) c.focus(); } }, 50);
          } }, "Crea il tuo primo progetto")));
        sez.prepend(b);
      }
    }
  }
  async function controllaVuoti() {
    try { const d = await chiedi("/api/progetti"); S.elenco = d.progetti || []; S.vuoto = d.vuoto || ""; bannerVuoti(); }
    catch (e) { /* il giro dopo riprova */ }
  }

  // ---------------------------------------------------------------- diario nella scheda della lavagna
  async function diarioNellaScheda() {
    const dlg = document.getElementById("scheda-agente");
    let k = "";
    try { k = typeof schedaKey === "string" ? schedaKey : ""; } catch (e) { k = ""; } // eslint-disable-line no-undef
    if (!dlg || !dlg.open || !k || !k.includes(":")) return;
    const [pid, nome] = k.split(":");
    let box = dlg.querySelector(".pg-diario-scheda");
    if (!box) { box = el("div", { class: "pg-diario-scheda" }); (dlg.querySelector("form") || dlg).append(box); }
    if (box.dataset.chiave === k && box.dataset.modificato === "1") return;     // testo in modifica: non si tocca
    try {
      const d = await chiedi("/api/progetto?id=" + encodeURIComponent(pid));
      const a = (d.agenti || []).find((x) => x.nome === nome);
      if (!a) { box.replaceChildren(); return; }
      const t = el("textarea", { rows: "8", class: "pg-diario" }); t.value = a.diario_testo || "";
      box.dataset.chiave = k; box.dataset.modificato = "0";
      t.addEventListener("input", () => { box.dataset.modificato = "1"; });
      const esito = el("small", { class: "pg-piccolo" });
      box.replaceChildren(el("h3", {}, "Diario dell'agente"), el("p", { class: "pg-piccolo" }, a.diario_file), t,
        el("button", { type: "button", onclick: async () => {
          try { await chiedi("/api/progetto/azione", { cosa: "diario", progetto: pid, nome, testo: t.value }); esito.textContent = "Diario salvato"; box.dataset.modificato = "0"; }
          catch (e) { esito.textContent = e.message; }
        } }, "Salva il diario"), esito);
    } catch (e) { box.replaceChildren(); }
  }

  // ---------------------------------------------------------------- avvio e aggiornamento da solo
  function aperta() { return location.hash.startsWith("#progetti"); }
  function rileggi() {
    clearTimeout(S.attesa);
    S.attesa = setTimeout(() => { if (aperta()) leggiElenco(); else controllaVuoti(); diarioNellaScheda(); }, 250);
  }
  function avvia() {
    creaVoceMenu(); creaVista();
    window.addEventListener("cc:flusso", (ev) => {
      const k = (ev && ev.detail) || [];
      if (!k.length || k.includes("progetti") || k.includes("spazi")) rileggi();
    });
    window.addEventListener("hashchange", () => { if (aperta()) leggiElenco(); });
    const dlg = document.getElementById("scheda-agente");
    if (dlg) new MutationObserver(() => { if (dlg.open) diarioNellaScheda(); }).observe(dlg, { attributes: true, attributeFilter: ["open"] });
    if (aperta()) leggiElenco(); else controllaVuoti();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia); else avvia();
})();
