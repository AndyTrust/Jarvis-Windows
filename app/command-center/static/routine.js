// La pagina «Routine» del Command Center (2026-10-05, l'utente): tutti i lavori automatici di VPS (systemd e cron) e Mac
// (launchd), con «Avvia ora» (senza conferma), «Log», «Modifica» e «Nuova» (doppio passo: «Prepara» mostra il comando
// esatto, «Conferma ed esegui» lo lancia). In più, sulla lavagna, i comandi rapidi per gruppo «Controlli» e «Scarica
// dati». Dati: GET/POST /api/routine, GET /api/routine/log (server.py → routine.py).
// Come piani.js: si aggancia da sola al menu, a TITOLI e alla barra della lavagna. Testi sempre con textContent.
(function routine() {
  "use strict";
  const S = { dati: null, errore: "", filtro: "tutte", gruppo: "", occupato: false, timer: null, attivo: false,
    log: {}, modifica: null, prep: null, esito: null, nuova: null, rapidi: null,
    bozza: null, erroreForm: null };   // bozza: quello che l'utente ha scritto nel modulo; erroreForm: {chiave, campo, testo}
  // 2026-10-05 sera (verificatore): l'effetto della routine, letto negli script (routine-gruppi.json)
  const EFFETTO = { scrive: ["scrive in produzione", "ro-eff-scrive"], invia: ["manda messaggi", "ro-eff-invia"],
    "": ["effetto da verificare", "ro-eff-ignoto"] };
  const etichettaEffetto = (r) => r.effetto === "lettura" ? null :
    el("span", { class: "ro-eff " + (EFFETTO[r.effetto || ""] || EFFETTO[""])[1] }, (EFFETTO[r.effetto || ""] || EFFETTO[""])[0]);
  // il campo a cui appartiene un errore del server, dalle prime parole del messaggio
  function campoDiErrore(msg) {
    const m = (msg || "").toLowerCase();
    if (/^(orario|l'orario|campo cron|valore cron|passo cron|intervallo)/.test(m)) return "orario";
    for (const c of ["comando", "descrizione", "nome", "tipo", "gruppo", "attivo"]) if (m.startsWith(c)) return c;
    return "";
  }
  const N = {};
  const token = () => window.CC_TOKEN || "";
  function el(tag, attrs, ...figli) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v; else if (k.startsWith("on")) n.addEventListener(k.slice(2), v); else n.setAttribute(k, String(v));
    }
    for (const f of figli) if (f != null && f !== false) n.append(f instanceof Node ? f : document.createTextNode(String(f)));
    return n;
  }
  async function chiama(metodo, percorso, corpo) {
    const r = await fetch(percorso, { method: metodo, cache: "no-store", credentials: "same-origin",
      headers: Object.assign({ "X-Token": token(), Accept: "application/json" }, corpo ? { "Content-Type": "application/json" } : {}),
      body: corpo ? JSON.stringify(corpo) : undefined });
    let d = null;
    try { d = await r.json(); } catch (e) { /* non JSON */ }
    return { stato: r.status, d: d && typeof d === "object" ? d : {} };
  }
  const ora = (t) => t ? new Date(t * 1000).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }) : "";
  const durata = (s) => s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
  const nomeGruppo = (g) => ((S.dati && S.dati.nomi_gruppi) || {})[g] || g;
  const SEGNO = { ok: "✅", errore: "❌", in_corso: "⏳" };

  // ---------------------------------------------------------------- voce di menu e vista
  function creaVoceMenu() {
    const menu = document.querySelector(".schede.menu");
    if (menu && !menu.querySelector('a[data-vista="routine"]')) {
      const a = el("a", { href: "#routine", "data-vista": "routine", title: "I lavori automatici di VPS (CRM) e PC: avvia, log, modifica" },
        el("i", { class: "spia grigia" }), "Routine");
      const dopo = menu.querySelector('a[data-vista="scadenze"]');
      if (dopo) dopo.parentNode.insertBefore(a, dopo.nextSibling); else menu.append(a);   // Windows: «Scadenze» sta nel menu «Altro»
    }
    const griglia = document.querySelector("#m-foglio .m-foglio-griglia");
    if (griglia && !griglia.querySelector('a[data-vista="routine"]')) {
      const b = el("a", { href: "#routine", "data-vista": "routine" },
        el("i", { class: "spia grigia", "aria-hidden": "true" }), el("span", { class: "m-ico", "aria-hidden": "true" }, "⏱"),
        el("span", {}, "Routine"), el("b", { class: "conta" }));
      const largo = griglia.querySelector(".m-foglio-largo");
      if (largo) griglia.insertBefore(b, largo); else griglia.append(b);
    }
    try { if (typeof TITOLI === "object" && TITOLI && !TITOLI.routine) TITOLI.routine = "Routine"; } catch (e) { /* app.js vecchio */ } // eslint-disable-line no-undef
  }
  function segnaSpia() {
    const rr = (S.dati && S.dati.routine) || [];
    const errori = rr.filter((r) => r.esito === "errore" && r.attivo).length;
    const lavora = (S.dati && S.dati.esecuzioni || []).some((e) => e.stato === "in_corso" || e.stato === "partenza");
    for (const sp of document.querySelectorAll('.menu a[data-vista="routine"] .spia, #m-foglio a[data-vista="routine"] .spia'))
      sp.className = "spia " + (lavora ? "lavora" : errori ? "attenzione" : "ok");
  }

  function spia(r) {
    if (r.in_corso || r.esito === "in_corso") return "lavora";
    if (!r.attivo) return "grigia";
    if (r.esito === "errore") return "guasto";
    return r.esito === "ok" ? "ok" : "grigia";
  }
  function orarioBreve(r) {
    const o = r.orario || "";
    return o.startsWith("ogni giorno ") && o.length < 22 ? `${r.dove} ${o.slice(12)}` : `${r.dove} · ${o}`;
  }
  function ultimaEsec(id) {
    return ((S.dati && S.dati.esecuzioni) || []).find((e) => e.id === id) || null;
  }
  function testoEsec(e) {
    if (!e) return null;
    const fine = e.finito || Date.now() / 1000;
    if (e.stato === "partenza" || e.stato === "in_corso") return el("span", { class: "ro-esec ro-lavora" }, `⏳ avviata alle ${ora(e.partito)}, in corso da ${durata(fine - e.partito)}`);
    if (e.stato === "lunga") return el("span", { class: "ro-esec ro-lavora" }, `⏳ ${e.esito}`);
    return el("span", { class: "ro-esec " + (e.stato === "ok" ? "ro-ok" : "ro-ko") },
      `${e.stato === "ok" ? "✅" : "❌"} avvio a mano delle ${ora(e.partito)}: ${e.esito} (${durata(fine - e.partito)})`);
  }

  // ---------------------------------------------------------------- azioni
  async function avvia(r, bottone) {
    if (bottone) bottone.disabled = true;
    S.errore = "";
    try {
      const x = await chiama("POST", "/api/routine", { azione: "avvia", id: r.id });
      if (x.stato === 200) {
        S.dati.esecuzioni = [x.d, ...((S.dati.esecuzioni || []).filter((e) => e.eid !== x.d.eid))];
      } else S.errore = x.d.errore || ("errore " + x.stato);
    } catch (e) { S.errore = "Rete assente: la routine non è partita."; }
    disegna(); segnaSpia(); pianifica();
  }
  async function apriLog(r) {
    if (S.log[r.id] !== undefined) { delete S.log[r.id]; disegna(); return; }
    S.log[r.id] = "Leggo il log…"; disegna();
    try {
      const x = await chiama("GET", "/api/routine/log?id=" + encodeURIComponent(r.id));
      S.log[r.id] = x.stato === 200 ? (x.d.testo || "(vuoto)") : (x.d.errore || ("errore " + x.stato));
    } catch (e) { S.log[r.id] = "Rete assente."; }
    disegna();
    const pre = N.lista && N.lista.querySelector(`li[data-id="${CSS.escape(r.id)}"] .ro-log`);
    if (pre) pre.scrollTop = pre.scrollHeight;
  }
  async function prepara(corpo, chiave) {
    S.occupato = true; S.errore = ""; S.esito = null; S.erroreForm = null; disegna();
    try {
      const x = await chiama("POST", "/api/routine", Object.assign({ azione: "prepara" }, corpo));
      if (x.stato === 200) S.prep = x.d;
      else {
        const testo = x.d.errore || ("errore " + x.stato);
        // l'errore resta dentro la scheda, vicino al campo; il modulo tiene quello che l'utente ha scritto (S.bozza)
        if (chiave) S.erroreForm = { chiave, campo: campoDiErrore(testo), testo }; else S.errore = testo;
      }
    } catch (e) { if (chiave) S.erroreForm = { chiave, campo: "", testo: "Rete assente: niente preparato." }; else S.errore = "Rete assente: niente preparato."; }
    S.occupato = false; disegna();
    const box = document.querySelector(".ro-prep");
    if (box) box.scrollIntoView({ block: "nearest" });
  }
  async function conferma() {
    const p = S.prep;
    if (!p) return;
    S.occupato = true; S.errore = ""; disegna();
    try {
      const x = await chiama("POST", "/api/routine", { azione: "conferma", prep: p.prep, codice: p.codice, conferma: true });
      if (x.stato === 200) {
        S.esito = { ok: x.d.ok, testo: x.d.uscita || "", id: x.d.id };
        S.prep = null;
        if (x.d.ok) { S.modifica = null; S.nuova = null; }
      } else S.errore = x.d.errore || ("errore " + x.stato);
    } catch (e) { S.errore = "Rete assente: non so se è partito. Rileggi l'elenco prima di riprovare."; }
    S.occupato = false;
    await aggiorna(true);
  }
  async function annullaPrep() {
    const p = S.prep;
    S.prep = null; disegna();
    if (p) { try { await chiama("POST", "/api/routine", { azione: "annulla", prep: p.prep }); } catch (e) { /* niente */ } }
  }

  // ---------------------------------------------------------------- moduli
  const AIUTO_ORARIO = {
    vps: "«07:30», «*-*-* 07:00:00», «Mon..Fri 08:30» (ora di Roma) oppure «ogni 15 min». Controllato con systemd-analyze sulla VPS.",
    cron: "5 campi di cron in ora della VPS (UTC): «40 3 * * *» = 05:40 a Roma con l'ora legale. Il % nel comando si scrive \\%.",
    mac: "«07:30», più orari «07:00, 19:00», oppure «ogni 15 min».",
    win: "«07:30» (ogni giorno) oppure «ogni 15 min». Per un\'attività che c\'è già si cambia solo l\'ora di partenza.",
  };
  function orarioDiPartenza(r) {
    if (r.fonte === "cron") return r.cron || "";
    if (r.fonte === "vps") {
      if ((r.calendario || []).length === 1) return r.calendario[0].replace(/\s+Europe\/Rome$/, "");
      const iv = (r.intervallo || {}).OnUnitActiveSec;
      return iv ? "ogni " + iv : "";
    }
    const o = r.orario || "";
    if (o.startsWith("ogni giorno ")) return o.slice(12);
    if (/^ogni \d+ (min|h)$/.test(o)) return o;
    return "";
  }
  function erroreDi(chiave, nome) {
    const e = S.erroreForm;
    return e && e.chiave === chiave && e.campo === nome ? el("small", { class: "ro-errore-campo", role: "alert" }, e.testo) : null;
  }
  function campo(etichetta, input, aiuto, errore) {
    if (errore) input.setAttribute("aria-invalid", "true");
    return el("label", { class: "ro-campo" + (errore ? " ro-campo-ko" : "") }, el("span", { class: "ro-et" }, etichetta), input,
      aiuto ? el("small", { class: "ro-aiuto" }, aiuto) : null, errore);
  }
  function moduloModifica(r) {
    const m = r.modifica || {};
    const iniz = { descrizione: r.descrizione || "", orario: orarioDiPartenza(r), comando: r.comando_modifica || r.comando || "" };
    const b = S.bozza && S.bozza.id === r.id ? S.bozza : null;      // quello che l'utente aveva scritto, se c'è
    const descr = el("input", { type: "text", maxlength: "120", disabled: m.descrizione ? null : "" });
    descr.value = b ? b.descrizione : iniz.descrizione;
    const orario = el("input", { type: "text", maxlength: "80", disabled: m.orario ? null : "", placeholder: r.fonte === "cron" ? "*/10 * * * *" : "07:30" });
    orario.value = b ? b.orario : iniz.orario;
    const cmd = el("textarea", { rows: "2", maxlength: "600", disabled: m.comando ? null : "", spellcheck: "false" });
    cmd.value = b ? b.comando : iniz.comando;
    const attivo = el("input", { type: "checkbox", disabled: m.attivo ? null : "" });
    attivo.checked = b ? b.attivo : !!r.attivo;
    const salva = () => { S.bozza = { id: r.id, descrizione: descr.value, orario: orario.value, comando: cmd.value, attivo: attivo.checked }; };
    for (const x of [descr, orario, cmd, attivo]) x.addEventListener("input", salva);
    const mascherato = /mascherato|riga nascosta|…\[nascosto\]/.test(iniz.comando);
    const f = el("form", { class: "ro-form", onsubmit: (ev) => {
      ev.preventDefault();
      const corpo = { id: r.id };
      if (descr.value.trim() !== iniz.descrizione) corpo.descrizione = descr.value;
      if (orario.value.trim() !== iniz.orario) corpo.orario = orario.value;
      if (cmd.value.trim() !== iniz.comando.trim()) corpo.comando = cmd.value;
      if (attivo.checked !== !!r.attivo) corpo.attivo = attivo.checked;
      salva();
      if (Object.keys(corpo).length === 1) { S.erroreForm = { chiave: r.id, campo: "", testo: "Niente da cambiare." }; disegna(); return; }
      prepara(corpo, r.id);
    } },
      campo("Descrizione", descr, m.descrizione ? null : "Sul PC la descrizione non si cambia da qui.", erroreDi(r.id, "descrizione")),
      campo("Orario", orario, AIUTO_ORARIO[r.fonte], erroreDi(r.id, "orario")),
      campo("Comando", cmd, mascherato ? "Il comando contiene un valore nascosto: se lo cambi, riscrivilo per intero." : (r.fonte === "vps" ? "Va in un drop-in ExecStart (50-routine.conf); il file originale resta." : null), erroreDi(r.id, "comando")),
      el("label", { class: "ro-spunta" }, attivo, el("span", {}, "Attiva (togli la spunta per metterla in pausa)")),
      erroreDi(r.id, "attivo") || erroreDi(r.id, ""),
      el("div", { class: "ro-azioni" },
        el("button", { type: "submit", class: "ro-btn ro-si", disabled: S.occupato ? "" : null }, "Prepara"),
        el("button", { type: "button", class: "ro-btn", onclick: () => { S.modifica = null; S.prep = null; S.bozza = null; S.erroreForm = null; disegna(); } }, "Chiudi")),
      el("p", { class: "ro-nota" }, "«Prepara» non tocca niente: mostra il comando esatto. Si esegue solo con «Conferma ed esegui»."));
    return f;
  }
  function moduloNuova() {
    const n = S.nuova || {};
    const gruppi = Object.entries((S.dati && S.dati.nomi_gruppi) || {});
    for (const g of (S.dati && S.dati.gruppi) || []) if (!gruppi.some(([id]) => id === g.id)) gruppi.push([g.id, g.nome]);
    const fonte = el("select", {}, ...[["win", "PC · Utilità di pianificazione"]]
      .map(([v, t]) => el("option", { value: v, selected: (n.fonte || "win") === v ? "" : null }, t)));
    const nome = el("input", { type: "text", maxlength: "40", pattern: "[a-z0-9-]{1,40}", required: "", value: n.nome || "", placeholder: "giro-controllo" });
    const descr = el("input", { type: "text", maxlength: "120", value: n.descrizione || "" });
    const orario = el("input", { type: "text", maxlength: "80", required: "", value: n.orario || "", placeholder: "07:30" });
    const cmd = el("textarea", { rows: "2", maxlength: "600", required: "", spellcheck: "false" });
    cmd.value = n.comando || "";
    const gruppo = el("select", {}, ...gruppi.map(([id, t]) => el("option", { value: id, selected: n.gruppo === id ? "" : null }, t)));
    const tipo = el("select", {}, ...[["", "nessuno"], ["controllo", "controllo"], ["dati", "scarica dati"]]
      .map(([v, t]) => el("option", { value: v, selected: (n.tipo || "") === v ? "" : null }, t)));
    const attivo = el("input", { type: "checkbox" });
    attivo.checked = n.attivo !== false;
    const leggi = () => ({ fonte: fonte.value, nome: nome.value.trim(), descrizione: descr.value, orario: orario.value,
      comando: cmd.value, gruppo: gruppo.value, tipo: tipo.value, attivo: attivo.checked });
    for (const x of [fonte, nome, descr, orario, cmd, gruppo, tipo, attivo]) x.addEventListener("input", () => { S.nuova = leggi(); });
    fonte.addEventListener("change", () => { S.nuova = leggi(); const a = orario.parentNode.querySelector(".ro-aiuto"); if (a) a.textContent = AIUTO_ORARIO[fonte.value]; });
    return el("form", { class: "ro-form ro-nuova", onsubmit: (ev) => {
      ev.preventDefault();
      S.nuova = leggi();
      prepara(Object.assign({ nuova: true }, S.nuova), "nuova");
    } },
      el("h3", { class: "ro-titolo" }, "Nuova routine"),
      campo("Dove", fonte), campo("Nome", nome, "Minuscole, cifre e trattini. Sul PC diventa \\Jarvis\\<nome> nell'Utilità di pianificazione.", erroreDi("nuova", "nome")),
      campo("Descrizione", descr, null, erroreDi("nuova", "descrizione")),
      campo("Orario", orario, AIUTO_ORARIO[fonte.value], erroreDi("nuova", "orario")),
      campo("Comando", cmd, "Una riga di shell. Sulla VPS l'uscita va in /var/log/jarvis-<nome>.log.", erroreDi("nuova", "comando")),
      el("div", { class: "ro-riga2" }, campo("Gruppo", gruppo), campo("Tipo", tipo, "«controllo» compare nei comandi rapidi solo se la routine è di sola lettura (deciso in routine-gruppi.json dopo aver letto lo script).", erroreDi("nuova", "tipo"))),
      el("label", { class: "ro-spunta" }, attivo, el("span", {}, "Attiva subito")),
      erroreDi("nuova", "") || erroreDi("nuova", "attivo") || erroreDi("nuova", "gruppo"),
      el("div", { class: "ro-azioni" },
        el("button", { type: "submit", class: "ro-btn ro-si", disabled: S.occupato ? "" : null }, "Prepara"),
        el("button", { type: "button", class: "ro-btn", onclick: () => { S.nuova = null; S.prep = null; S.erroreForm = null; disegna(); } }, "Chiudi")));
  }
  function riquadroPrep() {
    const p = S.prep;
    return el("div", { class: "ro-prep", role: "group", "aria-label": "Conferma il comando" },
      el("h4", {}, `Sto per eseguire su ${p.dove}:`),
      el("ul", { class: "ro-riep" }, ...(p.riepilogo || []).map((x) => el("li", {}, x))),
      el("pre", { tabindex: "0" }, p.comando),
      el("p", { class: "ro-nota" }, `Vale 10 minuti. Il registro attività segna chi conferma e l'esito.`),
      el("div", { class: "ro-azioni" },
        el("button", { type: "button", class: "ro-btn ro-si", disabled: S.occupato ? "" : null, onclick: conferma }, "Conferma ed esegui"),
        el("button", { type: "button", class: "ro-btn", onclick: annullaPrep }, "Annulla")));
  }
  function riquadroEsito() {
    const e = S.esito;
    return el("div", { class: "ro-esito " + (e.ok ? "ro-ok" : "ro-ko") },
      el("h4", {}, e.ok ? `✅ Fatto: ${e.id}` : `❌ Non riuscito: ${e.id}`),
      e.testo ? el("pre", { tabindex: "0" }, e.testo) : null,
      el("button", { type: "button", class: "ro-btn", onclick: () => { S.esito = null; disegna(); } }, "Chiudi"));
  }

  // ---------------------------------------------------------------- disegno
  function scheda(r) {
    const e = ultimaEsec(r.id);
    const inCorso = e && (e.stato === "partenza" || e.stato === "in_corso");
    const testa = el("div", { class: "ro-testa" },
      el("i", { class: "spia " + (inCorso ? "lavora" : spia(r)), "aria-hidden": "true" }),
      el("h3", { class: "ro-titolo", title: r.nome }, r.descrizione || r.nome),
      el("span", { class: "ro-dove", title: r.orario_grezzo ? `${r.orario}\n${r.orario_grezzo}` : r.orario }, orarioBreve(r)));
    const ultimo = r.ultimo_testo ? `ultimo ${r.ultimo_testo} ${SEGNO[r.esito] || (r.fonte === "cron" ? "" : "")}`.trim() : (r.fonte === "cron" ? "" : "mai partita");
    const sotto = el("p", { class: "ro-sotto" },
      el("span", { class: "ro-nome" }, `${r.nome} · ${nomeGruppo(r.gruppo)}${r.tipo ? " · " + (r.tipo === "dati" ? "scarica dati" : "controllo") : ""}`),
      etichettaEffetto(r),
      !r.attivo ? el("span", { class: "ro-fermo" }, r.fonte === "mac" && !r.caricato ? "(fermo: non caricato)" : "(in pausa)") : null,
      ultimo ? el("span", {}, ultimo + (r.fonte === "cron" ? " (da orario)" : "")) : null,
      r.fonte === "cron" && r.log_aggiornato ? el("span", {}, `log scritto ${ora(r.log_aggiornato)}`) : null,
      r.esito === "errore" && r.codice != null ? el("span", { class: "ro-ko" }, `codice ${r.codice}${r.risultato && r.risultato !== "success" ? " · " + r.risultato : ""}`) : null,
      r.prossimo_testo ? el("span", {}, `prossimo ${r.prossimo_testo}`) : null);
    const azioni = el("div", { class: "ro-azioni" },
      el("button", { type: "button", class: "ro-btn ro-avvia", disabled: !r.avviabile || inCorso ? "" : null,
        title: r.avviabile ? "Parte subito, senza conferma" : r.perche_no, onclick: (ev) => avvia(r, ev.currentTarget) }, inCorso ? "⏳ In corso" : "▶ Avvia ora"),
      el("button", { type: "button", class: "ro-btn", "aria-expanded": S.modifica === r.id ? "true" : "false",
        onclick: () => { S.modifica = S.modifica === r.id ? null : r.id; S.prep = null; S.esito = null; S.bozza = null; S.erroreForm = null; disegna(); } }, "✎ Modifica"),
      (r.modifica || {}).attivo ? el("button", { type: "button", class: "ro-btn", disabled: S.occupato ? "" : null,
        title: r.attivo ? "Prepara la pausa (chiede conferma)" : "Prepara la riattivazione (chiede conferma)",
        onclick: () => { S.modifica = r.id; S.bozza = null; prepara({ id: r.id, attivo: !r.attivo }, r.id); } }, r.attivo ? "⏸ Pausa" : "▶ Riattiva") : null,
      el("button", { type: "button", class: "ro-btn", "aria-expanded": S.log[r.id] !== undefined ? "true" : "false", onclick: () => apriLog(r) }, "Log"));
    const li = el("li", { class: "ro-scheda" + (r.attivo ? "" : " ro-spenta"), "data-id": r.id }, testa, sotto,
      el("div", { class: "ro-vivo", "data-esec": r.id }, testoEsec(e)), azioni);
    if (S.log[r.id] !== undefined) li.append(el("pre", { class: "ro-log", tabindex: "0" }, S.log[r.id]));
    if (S.modifica === r.id) {
      li.append(moduloModifica(r));
      if (S.prep && S.prep.id === r.id && !S.prep.nuova) li.append(riquadroPrep());
      if (S.esito && S.esito.id === r.id) li.append(riquadroEsito());
    }
    return li;
  }
  function filtrate() {
    const rr = (S.dati && S.dati.routine) || [];
    return rr.filter((r) => (S.filtro === "tutte" || (S.filtro === "vps" && r.dove === "VPS") || (S.filtro === "mac" && r.dove === "PC") ||
      (S.filtro === "errori" && r.esito === "errore")) && (!S.gruppo || r.gruppo === S.gruppo));
  }
  function disegnaFiltri() {
    const rr = (S.dati && S.dati.routine) || [];
    const n = { tutte: rr.length, vps: rr.filter((r) => r.dove === "VPS").length, mac: rr.filter((r) => r.dove === "PC").length,
      errori: rr.filter((r) => r.esito === "errore").length };
    const etich = { tutte: "Tutte", vps: "VPS", mac: "PC", errori: "⚠ errori" };
    N.filtri.textContent = "";
    for (const k of Object.keys(etich)) N.filtri.append(el("button", { type: "button", class: "ro-filtro", "aria-pressed": S.filtro === k ? "true" : "false",
      onclick: () => { S.filtro = k; disegna(); } }, `${etich[k]} (${n[k]})`));
    const gruppi = [...new Set(rr.map((r) => r.gruppo))].sort((a, b) => nomeGruppo(a).localeCompare(nomeGruppo(b)));
    const sel = el("select", { class: "ro-sel-gruppo", "aria-label": "Gruppo", onchange: (ev) => { S.gruppo = ev.target.value; disegna(); } },
      el("option", { value: "" }, "tutti i gruppi"), ...gruppi.map((g) => el("option", { value: g, selected: S.gruppo === g ? "" : null }, nomeGruppo(g))));
    N.filtri.append(sel);
  }
  function disegna() {
    if (!N.lista) return;
    N.errore.textContent = S.errore; N.errore.hidden = !S.errore;
    const d = S.dati;
    N.stato.textContent = d ? `lette alle ${ora(d.letto)} · ${Object.entries(d.conta || {}).map(([k, v]) => `${v} ${k === "vps" ? "timer VPS" : k === "cron" ? "cron VPS" : "PC"}`).join(", ")}` : "carico…";
    N.avvisi.textContent = "";
    for (const a of (d && d.avvisi) || []) N.avvisi.append(el("p", { class: "ro-errore" }, a));
    N.nuova.textContent = "";
    if (S.nuova) {
      N.nuova.append(moduloNuova());
      if (S.prep && S.prep.nuova) N.nuova.append(riquadroPrep());
      if (S.esito && !S.modifica) N.nuova.append(riquadroEsito());
    } else if (S.esito && !S.modifica) N.nuova.append(riquadroEsito());
    if (!d) { N.lista.textContent = ""; N.lista.append(el("li", { class: "ro-nota" }, "Carico le routine di VPS (CRM) e PC…")); return; }
    disegnaFiltri();
    N.lista.textContent = "";
    const voci = filtrate();
    if (!voci.length) N.lista.append(el("li", { class: "ro-nota" }, "Nessuna routine con questo filtro."));
    for (const r of voci) N.lista.append(scheda(r));
    N.registro.textContent = "";
    for (const x of (d.registro || []).slice(0, 20)) N.registro.append(el("li", {},
      el("span", { class: "ro-et" }, new Date(x.ts * 1000).toLocaleString("it-IT", { timeZone: "Europe/Rome", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })),
      el("span", {}, `${x.azione} · ${x.id} · ${x.esito}${x.chi ? " · " + x.chi : ""}${x.riepilogo ? " · " + x.riepilogo : ""}${x.motivo ? " · " + x.motivo : ""}`)));
  }
  function aggiornaVivi() {        // solo le righe «in corso», senza ridisegnare i moduli aperti
    for (const box of document.querySelectorAll(".ro-vivo[data-esec]")) {
      box.textContent = "";
      const t = testoEsec(ultimaEsec(box.dataset.esec));
      if (t) box.append(t);
    }
  }
  function creaVista() {
    const main = document.querySelector("main");
    if (!main || document.querySelector('section[data-vista="routine"]')) return false;
    N.lista = el("ul", { class: "ro-lista" });
    N.errore = el("p", { class: "ro-errore", role: "alert", hidden: "" });
    N.avvisi = el("div", {});
    N.filtri = el("div", { class: "ro-filtri", role: "group", "aria-label": "Filtro" });
    N.stato = el("small", { class: "ro-stato", "aria-live": "polite" }, "carico…");
    N.nuova = el("div", { class: "ro-nuova-box" });
    N.registro = el("ol", { class: "ro-registro" });
    N.vista = el("section", { class: "vista vista-routine", "data-vista": "routine", "aria-labelledby": "ro-titolo-pagina" },
      el("div", { class: "ro-intro" },
        el("div", { class: "ro-intro-testa" }, el("h2", { id: "ro-titolo-pagina", class: "ro-pagina" }, "Routine"),
          el("button", { type: "button", class: "ro-btn", onclick: () => aggiorna(true), title: "Rilegge VPS (CRM) e PC adesso" }, "⟳ Rileggi"),
          el("button", { type: "button", class: "ro-btn ro-si", onclick: () => { apriNuova({}); } }, "+ Nuova")),
        el("p", { class: "ro-sotto-titolo" }, "I lavori automatici di VPS (timer e cron) e del PC. «Avvia ora» parte subito; modifiche e routine nuove mostrano il comando e aspettano la tua conferma. Ore di Roma."),
        N.stato),
      N.filtri, N.errore, N.avvisi, N.nuova, N.lista,
      el("details", { class: "ro-reg" }, el("summary", {}, "Registro delle routine (ultime 20)"), N.registro));
    main.append(N.vista);
    disegna();
    return true;
  }
  function apriNuova(pre) {
    S.nuova = Object.assign({ fonte: "win" }, pre || {});
    S.prep = null; S.esito = null; S.modifica = null;
    disegna();
    if (N.nuova) N.nuova.scrollIntoView({ block: "start" });
  }

  // ---------------------------------------------------------------- dati e tempi
  async function aggiorna(forza) {
    try {
      const x = await chiama("GET", "/api/routine" + (forza ? "?forza=1" : ""));
      if (x.stato === 200) { S.dati = x.d; if (S.errore.startsWith("Rete")) S.errore = ""; } else S.errore = x.d.errore || ("errore " + x.stato);
    } catch (e) { S.errore = "Rete assente."; }
    // con un modulo aperto si aggiornano solo gli stati vivi: non si perde quello che l'utente sta scrivendo
    if (S.modifica || S.nuova) { aggiornaVivi(); if (!N.lista.childElementCount) disegna(); } else disegna();
    segnaSpia(); disegnaRapidi(); pianifica();
  }
  const attiva = () => location.hash.startsWith("#routine") && !document.hidden;
  const inCorso = () => ((S.dati && S.dati.esecuzioni) || []).some((e) => e.stato === "partenza" || e.stato === "in_corso");
  function pianifica() {
    clearTimeout(S.timer);
    const ms = inCorso() ? 2000 : attiva() ? 30000 : 120000;
    S.timer = setTimeout(() => aggiorna(false), ms);
  }
  function cambio() {
    if (location.hash.startsWith("#routine/nuova")) {
      const pre = window.ccRoutineNuova || {};
      window.ccRoutineNuova = null;
      history.replaceState(null, "", "#routine");
      apriNuova(pre);
    }
    if (attiva() && !S.attivo) { S.attivo = true; aggiorna(false); }
    else if (!attiva() && S.attivo) { S.attivo = false; }
  }

  // ---------------------------------------------------------------- comandi rapidi sulla lavagna
  function menuRapido(tipo, etichetta) {
    const lista = el("div", { class: "ro-menu-lista", role: "menu" });
    const d = el("details", { class: "ro-menu" }, el("summary", { class: "piccolo", title: etichetta + " per gruppo" }, etichetta + " ▾"), lista);
    d.addEventListener("toggle", () => { if (d.open) riempi(); });
    function riempi() {
      lista.textContent = "";
      const gruppi = (S.dati && S.dati.gruppi) || [];
      const tutti = gruppi.flatMap((g) => g[tipo] || []);
      for (const g of gruppi) {
        const ids = g[tipo] || [];
        if (ids.length) {
          lista.append(el("button", { type: "button", role: "menuitem", class: "ro-voce", title: ids.join(", "),
            onclick: () => { d.open = false; lanciaRapido(ids, `${etichetta} · ${g.nome}`); } }, `${g.nome} (${ids.length})`,
          tipo === "dati" ? el("span", { class: "ro-eff ro-eff-scrive" }, "scrive in produzione") : null));
        } else {
          lista.append(el("a", { href: "#routine/nuova", role: "menuitem", class: "ro-voce ro-voce-vuota", title: "Nessuna routine di questo tipo: apre «Nuova» già compilata",
            onclick: () => { d.open = false; window.ccRoutineNuova = { gruppo: g.id, tipo, fonte: "win", nome: `${g.id}-${tipo === "dati" ? "dati" : "controllo"}`.slice(0, 40) }; } },
          el("span", {}, g.nome), el("small", {}, " nessuna routine: creala")));
        }
      }
      lista.append(el("button", { type: "button", role: "menuitem", class: "ro-voce ro-voce-tutti", disabled: tutti.length ? null : "",
        onclick: () => { d.open = false; lanciaRapido(tutti, `${etichetta} · tutti`); } }, `Tutti, in sequenza (${tutti.length})`,
        tipo === "dati" ? el("span", { class: "ro-eff ro-eff-scrive" }, "scrive in produzione") : el("span", { class: "ro-eff ro-eff-lettura" }, "solo lettura")));
      if (!S.dati) lista.append(el("p", { class: "ro-nota" }, "Carico le routine…"));
    }
    return d;
  }
  async function lanciaRapido(ids, titolo) {
    S.rapidi = { ids, titolo, da: Date.now() / 1000 - 2, errore: "" };
    disegnaRapidi();
    try {
      const x = await chiama("POST", "/api/routine", { azione: "avvia-molte", ids });
      if (x.stato !== 200) S.rapidi.errore = x.d.errore || ("errore " + x.stato);
    } catch (e) { S.rapidi.errore = "Rete assente: non partito."; }
    setTimeout(() => aggiorna(false), 800);
  }
  function disegnaRapidi() {
    const box = document.getElementById("ro-rapidi-stato");
    if (!box || !S.rapidi) return;
    const r = S.rapidi;
    if (r.errore) { box.textContent = `${r.titolo}: ${r.errore}`; box.className = "lav-stato ro-ko"; return; }
    const es = ((S.dati && S.dati.esecuzioni) || []).filter((e) => r.ids.includes(e.id) && e.partito >= r.da);
    const ok = es.filter((e) => e.stato === "ok").length, ko = es.filter((e) => e.stato === "errore").length;
    const vive = es.filter((e) => e.stato === "in_corso" || e.stato === "partenza");
    const finito = ok + ko === r.ids.length;
    box.className = "lav-stato " + (finito ? (ko ? "ro-ko" : "ro-ok") : "");
    box.textContent = `${r.titolo}: ${ok + ko}/${r.ids.length} finite` + (ko ? `, ${ko} con errore` : "") +
      (vive.length ? ` · in corso: ${vive.map((e) => e.nome).join(", ")}` : finito ? (ko ? " ❌" : " ✅") : " · in coda");
    box.title = es.map((e) => `${e.nome}: ${e.esito}`).join("\n");
  }
  function creaRapidi() {
    const barra = document.querySelector(".lavagna-barra");
    if (!barra || document.getElementById("ro-rapidi")) return;
    const box = el("span", { class: "ro-rapidi", id: "ro-rapidi", role: "group", "aria-label": "Comandi rapidi per gruppo" },
      menuRapido("controllo", "✔ Controlli"), menuRapido("dati", "⬇ Scarica dati"),
      el("small", { id: "ro-rapidi-stato", class: "lav-stato", "aria-live": "polite" }));
    const accanto = document.getElementById("lav-aggiorna-ultime") || document.getElementById("lav-aggiorna-agenti");
    if (accanto && accanto.parentNode === barra) barra.insertBefore(box, accanto.nextSibling); else barra.append(box);
    document.addEventListener("click", (ev) => {
      for (const d of box.querySelectorAll("details[open]")) if (!d.contains(ev.target)) d.open = false;
    });
  }

  (async function avvio() {
    if (document.readyState === "loading") await new Promise((ok) => document.addEventListener("DOMContentLoaded", ok, { once: true }));
    let r;
    try { r = await chiama("GET", "/api/routine"); } catch (e) { return; }
    if (r.stato !== 200) return;                    // dal sito senza la rotta o con un server vecchio: niente voce
    S.dati = r.d;
    creaVoceMenu();
    if (!creaVista()) return;
    creaRapidi();
    segnaSpia();
    window.addEventListener("hashchange", cambio);
    document.addEventListener("visibilitychange", cambio);
    if (location.hash.startsWith("#routine") && typeof mostraVista === "function") { try { mostraVista(); } catch (e) { /* niente */ } } // eslint-disable-line no-undef
    cambio();
    pianifica();
  })();
})();
