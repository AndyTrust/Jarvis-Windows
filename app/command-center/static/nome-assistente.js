// Il nome dell'assistente in tutta la pagina (2026-10-10, si parte da zero): il pannello nasce con la parola «Jarvis»
// nei testi; qui la si sostituisce con il nome scelto dal proprietario (utente.json → window.CC_ASSISTENTE, messo dal
// server nella pagina). Tocca solo testi visibili e gli attributi title, placeholder, aria-label e alt, più il titolo
// della scheda del browser. Non tocca codice, campi in cui si scrive, messaggi della chat (#messaggi) né i diari.
(function nomeAssistente() {
  "use strict";
  const nome = String(window.CC_ASSISTENTE || "").trim();
  if (!nome || nome === "Jarvis") return;
  const RE = /(?<![\/\\~.\w-])Jarvis\b(?!App|[\/\\-]|\.\w)/g;   // mai dentro un percorso (~/Jarvis, C:\\Jarvis) o un nome di file
  const ATTR = ["title", "placeholder", "aria-label", "alt", "content"];
  const SALTA = new Set(["SCRIPT", "STYLE", "TEXTAREA", "INPUT", "CODE", "PRE"]);
  const fuori = (n) => n.closest && n.closest("#messaggi, .pg-diario, .pg-stato, [contenteditable]");
  function sistema(n) {
    if (n.nodeType === 3) {
      const p = n.parentElement;
      if (p && !SALTA.has(p.tagName) && !fuori(p) && RE.test(n.nodeValue)) n.nodeValue = n.nodeValue.replace(RE, nome);
      RE.lastIndex = 0;
      return;
    }
    if (n.nodeType !== 1 || n.tagName === "SCRIPT" || n.tagName === "STYLE" || fuori(n)) return;
    for (const a of ATTR) {
      const v = n.getAttribute && n.getAttribute(a);
      if (v && RE.test(v)) n.setAttribute(a, v.replace(RE, nome));
      RE.lastIndex = 0;
    }
    if (SALTA.has(n.tagName)) return;
    for (const c of n.childNodes) sistema(c);
  }
  function titolo() { if (RE.test(document.title)) document.title = document.title.replace(RE, nome); RE.lastIndex = 0; }
  new MutationObserver((cambi) => {
    for (const c of cambi) {
      if (c.type === "characterData") sistema(c.target);
      else if (c.type === "attributes") sistema(c.target);
      else for (const n of c.addedNodes) sistema(n);
    }
    titolo();
  }).observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTR });
  const tutto = () => { sistema(document.documentElement); titolo(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", tutto); else tutto();
})();
