// Modo approvazione: sotto ogni risposta dell'assistente una barra con "Approva ed esegui" e "Rifiuta".
// Non tocca la chat: osserva #messaggi e #modo-chat e rimette la barra dopo ogni ridisegno (una per risposta).
// Usa le funzioni di app.js (azione, invia, salvaFili, disegnaMessaggi, disegnaModoChat, THREADS, chatCon).
// Il testo va sempre nel DOM con textContent. Il token non viene mai letto qui.
(function () {
  "use strict";
  const CHIAVE_DEC = "cc_appr_decisioni";     // esiti scelti, per sopravvivere al ridisegno e al ricaricamento
  const CHIAVE_RIP = "cc_appr_ripristina";    // modo da rimettere dopo l'invio forzato in "lavoro"
  const PREFISSO = "Il piano e approvato. Eseguilo ora, un passo alla volta, e dimmi cosa hai fatto. Piano:";
  const RIFIUTO = "Piano rifiutato, non ho eseguito niente.";
  const MAX_PIANO = 6000;
  const MAX_ATTESA = 30 * 60 * 1000;

  const leggiLS = (k, def) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : def; } catch (e) { return def; } };
  const scriviLS = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* niente */ } };
  const togliLS = (k) => { try { localStorage.removeItem(k); } catch (e) { /* niente */ } };
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };

  function hash(s) { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0; return h.toString(36); }
  const chiave = (k, m) => k + "|" + (m.ora || "") + "|" + (m.testo || "").length + "|" + hash(String(m.testo || "").slice(0, 400));

  let decisioni = leggiLS(CHIAVE_DEC, {});
  function ricorda(key, esito) {
    decisioni[key] = esito;
    const chiavi = Object.keys(decisioni);
    if (chiavi.length > 300) for (const c of chiavi.slice(0, chiavi.length - 300)) delete decisioni[c];
    scriviLS(CHIAVE_DEC, decisioni);
  }

  const modoAttuale = () => { const b = document.getElementById("modo-chat"); return b ? b.dataset.modo || "" : ""; };
  const filoCorrente = () => { try { return { k: chatCon, t: THREADS[chatCon] }; } catch (e) { return null; } };

  // la risposta e' una risposta vera da approvare?
  function daApprovare(t, i) {
    const m = t.messaggi[i];
    if (!m || m.chi !== "lui" || m.errore || m.tipo === "comando") return false;
    if (!m.testo || m.testo === "(nessuna risposta)" || m.testo.charAt(0) === "■") return false;   // niente per risposte vuote o fermate
    const prima = t.messaggi[i - 1];
    if (prima && prima.chi === "io" && String(prima.testo).indexOf(PREFISSO) === 0) return false;       // e' gia' la risposta all'esecuzione
    return true;
  }
  function richiestaDi(t, i) {
    const prima = t.messaggi[i - 1];
    return prima && prima.chi === "io" ? String(prima.testo).slice(0, 2000) : "";
  }
  function nomeAgente(k) {
    try { const a = AGENTI.get(k); return a ? String(a.nome || k) : "jarvis"; } catch (e) { return "jarvis"; }
  }

  // disegno idempotente: se la barra giusta c'e' gia' non cambia niente nel DOM
  let inCorso = false;
  function disegna() {
    if (inCorso) return;
    const f = filoCorrente();
    const box = document.getElementById("messaggi");
    if (!f || !f.t || !box || !f.t.messaggi.length) return;
    inCorso = true;
    try {
      const attivo = modoAttuale() === "approvazione";
      const figli = box.children;
      for (let i = 0; i < f.t.messaggi.length && i < figli.length; i++) {
        const nodo = figli[i];
        if (!nodo.classList.contains("msg") || nodo.classList.contains("mio")) continue;
        const corpo = nodo.querySelector(":scope > .corpo");
        if (!corpo) continue;
        const esistente = corpo.querySelector(":scope > .appr-barra");
        if (!daApprovare(f.t, i)) { if (esistente) esistente.remove(); continue; }
        const m = f.t.messaggi[i], key = chiave(f.k, m), esito = decisioni[key] || "";
        if (!attivo && !esito) { if (esistente) esistente.remove(); continue; }
        if (esistente && esistente.dataset.key === key && esistente.dataset.esito === esito) continue;
        if (esistente) esistente.remove();
        corpo.appendChild(creaBarra(f.k, key, esito));
      }
    } finally { inCorso = false; }
  }

  function creaBarra(k, key, esito) {
    const barra = el("div", "appr-barra" + (esito ? " " + esito : ""));
    barra.dataset.key = key; barra.dataset.esito = esito;
    barra.setAttribute("role", "group"); barra.setAttribute("aria-label", "Decisione sul piano");
    const si = el("button", "appr-si", "Approva ed esegui"); si.type = "button";
    const no = el("button", "appr-no", "Rifiuta"); no.type = "button";
    if (esito) {
      si.disabled = true; no.disabled = true;
      barra.append(el("span", "appr-esito", esito === "approvata" ? "Approvato: eseguito in modo lavoro" : "Rifiutato"), si, no);
    } else {
      barra.append(el("span", "appr-et", "Piano da approvare"), si, no);
      si.addEventListener("click", () => approva(k, key, si, no));
      no.addEventListener("click", () => rifiuta(k, key, si, no));
    }
    return barra;
  }

  function trova(k, key) {
    try {
      const t = THREADS[k];
      if (!t) return null;
      for (let i = 0; i < t.messaggi.length; i++) if (chiave(k, t.messaggi[i]) === key) return { t, i };
    } catch (e) { /* niente */ }
    return null;
  }

  // ---- Rifiuta
  async function rifiuta(k, key, si, no) {
    const r = trova(k, key);
    if (!r) return;
    si.disabled = no.disabled = true;
    const d = await azione({ tipo: "decisione_chat", decisione: "rifiutata", richiesta: richiestaDi(r.t, r.i), agente: nomeAgente(k) }, null);
    if (!d) { si.disabled = no.disabled = false; return; }
    ricorda(key, "rifiutata");
    r.t.messaggi.push({ chi: "lui", testo: RIFIUTO, ora: oraBreve(), tipo: "comando", titolo: "piano" });
    salvaFili();
    if (k === chatCon) disegnaMessaggi();
    disegna();
  }

  // ---- Approva ed esegui
  // La richiesta di chat non porta il campo "modo": il server usa quello salvato. Quindi solo per questo invio
  // si passa a "lavoro", si invia e si rimette "approvazione" appena la risposta e' arrivata.
  async function approva(k, key, si, no) {
    const r = trova(k, key);
    if (!r) return;
    if (r.t.attesa) { toast("Aspetta la risposta in corso", true); return; }
    if (k !== chatCon) { toast("Apri la chat di questo interlocutore per approvare", true); return; }
    si.disabled = no.disabled = true;
    const piano = String(r.t.messaggi[r.i].testo || "").slice(0, MAX_PIANO);
    const d1 = await azione({ tipo: "decisione_chat", decisione: "approvata", richiesta: richiestaDi(r.t, r.i), agente: nomeAgente(k) }, null);
    if (!d1) { si.disabled = no.disabled = false; return; }
    ricorda(key, "approvata");
    scriviLS(CHIAVE_RIP, { modo: "approvazione", k, da: Date.now() });
    const dm = await azione({ tipo: "modo_chat", modo: "lavoro" }, null);
    if (!dm || dm.modo !== "lavoro") {
      togliLS(CHIAVE_RIP);
      toast("Non riesco a passare al modo lavoro: il piano non e stato eseguito", true);
      disegna();
      return;
    }
    firme.modoChat = undefined; disegnaModoChat(dm.modo);
    const campo = document.getElementById("chiedi-testo"), bozza = campo.value;
    campo.value = PREFISSO + "\n\n" + piano;
    await invia();
    campo.value = bozza; autoAltezza();
    const t = THREADS[k];
    if (!t || !t.attesa) await ripristina();      // l'invio non e' partito: si torna subito al modo di prima
    else attendiRipristino();
    disegna();
  }

  async function ripristina() {
    const rip = leggiLS(CHIAVE_RIP, null);
    if (!rip) return;
    const d = await azione({ tipo: "modo_chat", modo: rip.modo || "approvazione" }, null);
    if (d && d.modo) { togliLS(CHIAVE_RIP); firme.modoChat = undefined; disegnaModoChat(d.modo); disegna(); }
  }
  let giro = null;
  function attendiRipristino() {
    if (giro) return;
    giro = setInterval(async () => {
      const rip = leggiLS(CHIAVE_RIP, null);
      if (!rip) { clearInterval(giro); giro = null; return; }
      let attesa = false;
      try { attesa = !!(THREADS[rip.k] && THREADS[rip.k].attesa); } catch (e) { /* niente */ }
      if (attesa && Date.now() - rip.da < MAX_ATTESA) return;
      clearInterval(giro); giro = null;
      await ripristina();
    }, 1500);
  }

  function avvia() {
    const box = document.getElementById("messaggi"), modo = document.getElementById("modo-chat");
    if (box) new MutationObserver(disegna).observe(box, { childList: true });
    if (modo) new MutationObserver(disegna).observe(modo, { attributes: true, attributeFilter: ["data-modo"] });
    disegna();
    if (leggiLS(CHIAVE_RIP, null)) attendiRipristino();    // pagina ricaricata durante un invio in "lavoro"
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia); else avvia();
})();
