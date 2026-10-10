// Dettatura nella chat: un microfono accanto a "invia" che scrive nel campo quello che dici, in italiano.
// Il messaggio NON parte da solo: lo rileggi e premi invio.
//
// Due modi, scelti da soli:
//  - LOCALE (preferito): il browser registra, il server del Command Center trascrive sul PC con Whisper
//    (/api/trascrivi) e torna solo il testo. L'audio non esce dal computer.
//  - BROWSER (ripiego, se la trascrizione sul PC non e' disponibile): il riconoscimento vocale del browser;
//    in Chrome l'audio passa dal servizio vocale di Chrome.
// Accende anche la chiamata a voce (chiamata.js) mettendo la classe "chiamata-ok" sul body; la chiamata usa
// il riconoscimento del browser (serve il testo man mano che parli).
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const MIC = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/></svg>';
  const Riconoscimento = window.SpeechRecognition || window.webkitSpeechRecognition;
  const PUO_REGISTRARE = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  const MAX_SECONDI = 120;
  const TITOLO_LOCALE = "Detta il messaggio: la voce si trascrive su questo PC (non parte da solo: rileggi e premi invio)";
  const TITOLO_BROWSER = "Detta il messaggio (non parte da solo: rileggi e premi invio)";
  let mic = null, nota = null, modo = "nessuno";            // modo: locale | browser | nessuno
  let ascolto = null;                                         // browser: l'oggetto di riconoscimento
  let reg = null;                                             // locale: { rec, flusso, pezzi, timer, base }
  let occupato = false;                                       // locale: sto trascrivendo
  let scrivoIo = false;

  function dici(testo, errore) {
    if (!nota) return;
    nota.textContent = testo || "";
    nota.hidden = !testo;
    nota.classList.toggle("errore", !!errore);
    clearTimeout(dici.t);
    if (testo && errore) dici.t = setTimeout(() => { nota.hidden = true; }, 12000);
  }

  function segnaMic(stato) {                                   // stato: "ascolta" | "pensa" | ""
    if (!mic) return;
    mic.classList.toggle("ascolta", stato === "ascolta");
    mic.classList.toggle("pensa", stato === "pensa");
    mic.disabled = stato === "pensa";
    mic.setAttribute("aria-pressed", String(stato === "ascolta"));
    mic.setAttribute("aria-label", stato === "ascolta" ? "Ferma il dettato" : stato === "pensa" ? "Sto trascrivendo" : "Detta il messaggio");
    if (!stato && nota && !nota.classList.contains("errore")) dici("");
  }

  function scriviNelCampo(base, testo) {
    const campo = $("chiedi-testo");
    if (!campo) return;
    scrivoIo = true;
    campo.value = (base + testo).replace(/\s+/g, " ").replace(/^\s/, "");
    campo.dispatchEvent(new Event("input", { bubbles: true }));       // app.js rifa' l'altezza del campo
    scrivoIo = false;
    try { campo.focus(); } catch (e) { /* niente */ }
  }

  // ------------------------------------------------------------------ modo LOCALE
  function formatoRegistrazione() {
    const scelte = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
    for (const f of scelte) { try { if (MediaRecorder.isTypeSupported(f)) return f; } catch (e) { /* niente */ } }
    return "";
  }

  async function avviaLocale() {
    if (reg || occupato) return;
    const campo = $("chiedi-testo");
    if (!campo) return;
    let flusso;
    try {
      flusso = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    } catch (e) {
      const nome = e && e.name;
      dici(nome === "NotAllowedError" || nome === "SecurityError"
        ? "Il microfono è bloccato per questo sito: consentilo nelle impostazioni del browser (il lucchetto accanto all'indirizzo) e riprova."
        : nome === "NotFoundError" ? "Nessun microfono trovato: usa il microfono della tastiera."
        : "Non riesco ad aprire il microfono: riprova.", true);
      return;
    }
    const formato = formatoRegistrazione();
    let rec;
    try { rec = formato ? new MediaRecorder(flusso, { mimeType: formato }) : new MediaRecorder(flusso); }
    catch (e) { flusso.getTracks().forEach((t) => t.stop()); dici("La registrazione non è partita: riprova.", true); return; }
    const base = campo.value.trim() ? campo.value.replace(/\s*$/, " ") : "";
    reg = { rec, flusso, pezzi: [], base, timer: null, tipo: rec.mimeType || formato || "audio/webm" };
    rec.ondataavailable = (ev) => { if (ev.data && ev.data.size) reg.pezzi.push(ev.data); };
    rec.onstop = () => finisciLocale();
    rec.start(250);
    reg.timer = setTimeout(() => fermaLocale(), MAX_SECONDI * 1000);
    segnaMic("ascolta");
    dici("Ti ascolto… tocca di nuovo il microfono per fermare. Si trascrive su questo PC; il messaggio non parte da solo.", false);
  }

  function fermaLocale() {
    if (!reg) return;
    clearTimeout(reg.timer);
    try { if (reg.rec.state !== "inactive") reg.rec.stop(); else finisciLocale(); } catch (e) { finisciLocale(); }
  }

  async function finisciLocale() {
    const r = reg;
    if (!r || r.finito) return;
    r.finito = true;
    reg = null;
    try { r.flusso.getTracks().forEach((t) => t.stop()); } catch (e) { /* niente */ }
    const blob = new Blob(r.pezzi, { type: r.tipo });
    if (blob.size < 800) { segnaMic(""); dici("Non ho sentito niente: tocca il microfono e riprova.", false); return; }
    occupato = true;
    segnaMic("pensa");
    dici("Trascrivo sul PC… (la prima volta ci mette qualche secondo in più)", false);
    try {
      const ris = await fetch("/api/trascrivi", { method: "POST", headers: { "X-Token": window.CC_TOKEN || "", "Content-Type": r.tipo.split(";")[0] }, body: blob });
      const dati = await ris.json().catch(() => ({}));
      if (!ris.ok) throw new Error(dati.errore || "La trascrizione non è riuscita.");
      if (!dati.testo) { dici("Non ho capito parole: tocca il microfono e riprova.", false); }
      else { scriviNelCampo(r.base, dati.testo); dici("Fatto. Rileggi e premi invio: il messaggio non parte da solo.", false); }
    } catch (e) {
      dici((e && e.message) || "La trascrizione non è riuscita: riprova o scrivi a mano.", true);
    } finally {
      occupato = false;
      segnaMic("");
    }
  }

  // ------------------------------------------------------------------ modo BROWSER (ripiego)
  function avviaBrowser() {
    if (!Riconoscimento || ascolto) return;
    const campo = $("chiedi-testo");
    if (!campo) return;
    const r = new Riconoscimento();
    r.lang = "it-IT";
    r.interimResults = true;
    r.continuous = true;
    r.maxAlternatives = 1;
    const base = campo.value.trim() ? campo.value.replace(/\s*$/, " ") : "";
    r.onresult = (ev) => {
      let fissa = "", provvisoria = "";
      for (let i = 0; i < ev.results.length; i++) {
        const x = ev.results[i][0] ? ev.results[i][0].transcript : "";
        if (ev.results[i].isFinal) fissa += x; else provvisoria += x;
      }
      scriviNelCampo(base, fissa + provvisoria);
    };
    r.onerror = (ev) => {
      const e = ev && ev.error;
      const testi = {
        "not-allowed": "Il microfono è bloccato per questo sito: consentilo nelle impostazioni del browser (il lucchetto accanto all'indirizzo) e riprova.",
        "service-not-allowed": "Il dettato non è permesso in questo browser: usa il microfono della tastiera.",
        "audio-capture": "Nessun microfono trovato: usa il microfono della tastiera.",
        "no-speech": "Non ho sentito niente: tocca il microfono e riprova.",
        network: "Il dettato ha bisogno della rete: riprova quando la connessione torna.",
        "language-not-supported": "Il dettato in italiano non è disponibile su questo browser.",
      };
      if (e !== "aborted") dici(testi[e] || "Il dettato si è fermato: riprova.", e !== "no-speech");
    };
    r.onend = () => { ascolto = null; segnaMic(""); };
    try { r.start(); } catch (e) { dici("Il dettato non è partito: riprova.", true); return; }
    ascolto = r;
    segnaMic("ascolta");
    dici("Ti ascolto… tocca di nuovo il microfono per fermare. Il messaggio non parte da solo.", false);
  }

  function fermaBrowser() {
    if (!ascolto) return;
    try { ascolto.stop(); } catch (e) { /* gia' fermo */ }
  }

  // ------------------------------------------------------------------ comune
  function clic() {
    if (modo === "locale") { if (reg) fermaLocale(); else avviaLocale(); }
    else if (modo === "browser") { if (ascolto) fermaBrowser(); else avviaBrowser(); }
  }
  function ferma() { if (reg) fermaLocale(); if (ascolto) fermaBrowser(); }
  const inCorso = () => !!(reg || ascolto);

  async function scegliModo() {
    if (PUO_REGISTRARE) {
      try {
        const r = await fetch("/api/trascrivi/stato", { headers: { "X-Token": window.CC_TOKEN || "" }, cache: "no-store" });
        const d = r.ok ? await r.json() : null;
        if (d && d.disponibile) return "locale";
      } catch (e) { /* server vecchio o rete giu': si prova il browser */ }
    }
    return Riconoscimento ? "browser" : "nessuno";
  }

  async function monta() {
    const form = $("form-chiedi"), invia = $("btn-invia");
    if (!form || !invia || $("btn-detta")) return;
    nota = document.createElement("small");
    nota.className = "dettatura-nota";
    nota.setAttribute("role", "status");
    nota.setAttribute("aria-live", "polite");
    nota.hidden = true;
    form.after(nota);
    modo = await scegliModo();
    if (modo !== "nessuno") {
      mic = document.createElement("button");
      mic.type = "button";
      mic.id = "btn-detta";
      mic.className = "ponte-mic";                       // il nome che chiamata.js cerca per mettere il telefono dopo il microfono
      mic.dataset.modo = modo;
      mic.title = modo === "locale" ? TITOLO_LOCALE : TITOLO_BROWSER;
      mic.setAttribute("aria-label", "Detta il messaggio");
      mic.setAttribute("aria-pressed", "false");
      mic.innerHTML = MIC;
      mic.addEventListener("click", clic);
      invia.before(mic);
      form.addEventListener("submit", ferma, true);
    } else {
      dici("Il dettato vocale non è disponibile in questo browser: usa il microfono della tastiera.", true);
    }
    document.body.classList.add("chiamata-ok");          // accende la chiamata a voce (chiamata.js)
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", monta); else monta();
  window.CCDettatura = { ferma, attivo: inCorso, modo: () => modo };
})();
