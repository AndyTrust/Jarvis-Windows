// Vista Memoria a tre colonne (personale, privata, condivisa del progetto agenti).
// Dati: GET /api/memoria-banche (puo' mancare: allora "non disponibile").
// Regole: la colonna privata mostra SOLO una spia ok/assente. Nessun pulsante copia tra banche.
// Tutto il testo entra nel DOM con textContent. Il token e' quello gia' usato da app.js.
(function () {
  "use strict";
  const BANCHE = [
    { id: "personale", nome: "Banca personale" },
    { id: "privata", nome: "Banca privata" },
    { id: "condivisa", nome: "Banca condivisa (progetto degli agenti)" },
  ];
  const ETICHETTE = { note: "note", ultimo_aggiornamento: "ultimo aggiornamento", aggiornata: "ultimo aggiornamento", indice: "indice",
    diario_oggi: "diario oggi", diario: "diario oggi", registro: "registro", da_allineare: "da allineare", messaggio: "nota" };
  const V = window.CCVivo || null;   // effetti vivi (vivo.js); senza, tutto funziona lo stesso
  let dati = null;          // ultima risposta valida
  let errore = "";          // motivo se non disponibile
  let colonnaAttiva = "personale";
  let entrata = true;       // la cascata e il count-up partono all'ingresso nella vista, non a ogni rilettura
  let firmaGriglia = "";    // se i dati non cambiano la griglia non si ridisegna (le spie non perdono il ritmo)
  let rif = null;           // pezzi fissi del blocco: tabs e griglia

  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };

  async function leggi() {
    let err = null;
    try {
      const r = await fetch("/api/memoria-banche", { headers: { "X-Token": window.CC_TOKEN }, cache: "no-store" });
      if (!r.ok) throw new Error(r.status === 404 ? "endpoint non presente" : "risposta " + r.status);
      const j = await r.json();
      if (!j || typeof j !== "object") throw new Error("risposta non valida");
      dati = j; errore = "";
    } catch (e) {
      dati = null; errore = String((e && e.message) || "non raggiungibile"); err = errore;
    }
    disegna();
    return err;
  }
  const rileggi = () => (V ? V.esegui("memoria") : leggi());

  // trova la banca nella risposta: oggetto {personale,privata,condivisa}, oppure {banche:{...}} o array con campo id/nome
  function banca(id) {
    if (!dati) return null;
    const radice = dati.banche || dati;
    if (Array.isArray(radice)) return radice.find((b) => b && String(b.id || b.nome || b.banca || "").toLowerCase().includes(id)) || null;
    return radice[id] != null ? radice[id] : null;
  }
  const OK = ["ok", "verde", "allineata", "presente", "true", "si"];
  const ATT = ["attenzione", "giallo", "da_allineare"];
  // spia normalizzata: ok | attenzione | guasto | grigia
  function spia(b) {
    if (b == null) return "grigia";
    if (typeof b === "boolean") return b ? "ok" : "guasto";
    if (typeof b === "string") b = { stato: b };
    if (b.presente !== false && String(b.indice_allineato).toLowerCase() === "no") return "attenzione";
    const v =b.spia != null ? b.spia : b.stato != null ? b.stato : b.ok != null ? b.ok : b.presente;
    const t = String(v).toLowerCase();
    if (OK.includes(t)) return "ok";
    if (ATT.includes(t)) return "attenzione";
    if (["assente", "false", "no", "guasto", "rosso", "errore"].includes(t)) return "guasto";
    return "grigia";
  }
  const TESTO = { ok: "ok", attenzione: "attenzione", guasto: "assente", grigia: "non disponibile" };

  const ISO = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/;
  const stessoGiorno = (x, y) => x.getFullYear() === y.getFullYear() && x.getMonth() === y.getMonth() && x.getDate() === y.getDate();
  // "oggi 10:19", "ieri 18:02", altrimenti data breve (con l'anno solo se non e' quello corrente)
  function formatoData(iso) {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    const hm = d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
    const oggi = new Date(); const ieri = new Date(oggi); ieri.setDate(oggi.getDate() - 1);
    if (stessoGiorno(d, oggi)) return "oggi " + hm;
    if (stessoGiorno(d, ieri)) return "ieri " + hm;
    const opz = { day: "2-digit", month: "2-digit" };
    if (d.getFullYear() !== oggi.getFullYear()) opz.year = "numeric";
    return d.toLocaleDateString("it-IT", opz) + " " + hm;
  }

  function riga(dl, k, v, anima) {
    if (v == null || typeof v === "object") return;
    dl.appendChild(el("dt", null, ETICHETTE[k] || k.replace(/_/g, " ")));
    const dd = el("dd");
    if (typeof v === "boolean" || v === "true" || v === "false") dd.textContent = (v === true || v === "true") ? "si" : "no";
    else if (typeof v === "number" && isFinite(v)) {
      dd.className = "num";
      if (anima && V) V.contaSu(dd, v, 600); else dd.textContent = String(v);
    } else if (typeof v === "string" && ISO.test(v)) {
      dd.className = "data"; dd.textContent = formatoData(v); dd.title = v;   // ISO completo nel title
    } else dd.textContent = String(v);
    dl.appendChild(dd);
  }

  // privata: ritorna solo ok | guasto | grigia, mai altro
  function spiaPrivata() {
    const s = spia(banca("privata"));
    return s === "ok" ? "ok" : s === "grigia" ? "grigia" : "guasto";
  }

  function colonna(def, anima) {
    const col = el("section", "mem3-col" + (def.id === colonnaAttiva ? " attiva" : ""));
    col.dataset.banca = def.id;
    const privata = def.id === "privata";
    const b = privata ? null : banca(def.id);     // il contenuto di privata non viene nemmeno letto qui
    const sp = !dati ? "grigia" : privata ? spiaPrivata() : spia(b);
    col.dataset.spia = sp;
    const h = el("h3");
    h.appendChild(el("i", "spia " + sp));
    h.appendChild(el("span", null, def.nome));
    col.appendChild(h);
    col.appendChild(el("div", "mem3-stato", "spia: " + (dati ? TESTO[sp] : "non disponibile")));
    if (privata) {
      col.appendChild(el("p", "mem3-nota", "Di questa banca si vede solo se c'e' (ok) o manca (assente)."));
      return col;
    }
    if (!dati) { col.appendChild(el("p", "mem3-nota", "Dati non disponibili.")); return col; }
    if (b && typeof b === "object") {
      const dl = el("dl");
      for (const k of Object.keys(b)) { if (k === "spia" || k === "stato" || k === "id" || k === "nome") continue; riga(dl, k, b[k], anima); }
      if (dl.children.length) col.appendChild(dl);
      const avv = b.avvisi || b.da_fare;
      if (Array.isArray(avv) && avv.length) {
        const ul = el("ul");
        for (const a of avv.slice(0, 8)) ul.appendChild(el("li", null, typeof a === "object" ? JSON.stringify(a) : String(a)));
        col.appendChild(ul);
      }
    } else if (b == null) col.appendChild(el("p", "mem3-nota", "Questa banca non e' nella risposta del server."));
    return col;
  }

  function sezione() { return document.querySelector('.vista[data-vista="memoria"]'); }

  // pezzi fissi del blocco: la testa (con indicatore e Rileggi) non si ricostruisce a ogni lettura
  function blocco() {
    const sez = sezione();
    if (!sez) return null;
    let b = document.getElementById("mem3");
    if (!b) {
      b = el("section", "pannello mem3"); b.id = "mem3"; sez.insertBefore(b, sez.firstChild);
      const testa = el("div", "mem3-testa");
      testa.appendChild(el("h2", null, "Le tre banche"));
      if (V) testa.appendChild(V.indicatore("memoria"));
      else testa.appendChild(el("span", "mem3-stato", ""));
      if (V) testa.appendChild(V.bottoneRileggi("memoria"));
      else { const r = el("button", "piccolo", "Rileggi"); r.type = "button"; r.addEventListener("click", rileggi); testa.appendChild(r); }
      b.appendChild(testa);
      rif = { tabs: el("div", "mem3-tabs"), griglia: el("div", "mem3-griglia") };
      b.appendChild(rif.tabs); b.appendChild(rif.griglia);
    }
    return b;
  }

  function disegna() {
    // vista Memoria: blocco in cima, il contenuto di prima resta sotto
    const b = blocco();
    if (!b) return;
    const vis = sezione().classList.contains("attiva");
    const anima = entrata && !!dati && vis;
    if (anima) entrata = false;
    rif.tabs.replaceChildren();
    for (const def of BANCHE) {
      const t = el("button", "piccolo" + (def.id === colonnaAttiva ? " attiva" : ""), def.nome.replace("Banca ", "").replace(" (condivisa)", ""));
      t.type = "button";
      t.addEventListener("click", () => { colonnaAttiva = def.id; disegna(); });
      rif.tabs.appendChild(t);
    }
    // la firma non contiene mai il contenuto di privata
    const firma = JSON.stringify([dati ? [banca("personale"), banca("condivisa"), spiaPrivata()] : null, errore, colonnaAttiva]);
    if (!anima && firma === firmaGriglia) return;
    firmaGriglia = firma;
    rif.griglia.className = "mem3-griglia" + (anima ? " mem3-anima" : "");
    rif.griglia.replaceChildren();
    for (const def of BANCHE) rif.griglia.appendChild(colonna(def, anima));
  }

  function avvia() {
    if (V) V.collega("memoria", leggi);
    disegna();
    rileggi();
    window.addEventListener("hashchange", () => {
      if (location.hash === "#memoria") { entrata = true; firmaGriglia = ""; disegna(); rileggi(); }
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia); else avvia();
})();
