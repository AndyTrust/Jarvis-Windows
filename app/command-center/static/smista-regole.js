// Regole dello smistamento (smista.js): nome dell'agente in minuscolo -> [[espressione, peso]].
// Sono dati del progetto: smista.js non conosce nessun nome di agente. Qui un esempio: si adatta ai nomi dei propri agenti.
window.CC_SMISTA_REGOLE = {
  "analista-finanziario": [["cassa", 1], ["liquidit", 2], ["debit", 2], ["rate\\b|rateal", 1], ["margine", 1], ["pareggio|break.?even", 2], ["bilancio", 1], ["in banca", 1], ["flusso di cassa", 2]],
  "analista-previsionale": [["previsio", 2], ["forecast", 2], ["scenari", 2], ["trend", 1], ["kpi", 1], ["cosa succede se", 2], ["simulaz", 2], ["stagional", 1], ["rischio", 1]],
  "cambusa": [["fornitor", 2], ["merci", 1], ["scorte", 2], ["magazzin", 2], ["rincar", 2], ["food ?cost", 2], ["ingredient", 1], ["ricett", 1], ["consumo", 1], ["prezzo d.acquisto", 2]],
  "commerciale": [["incass", 1], ["venduto", 2], ["scontrino", 2], ["coperti", 2], ["\\bmenu\\b", 1], ["recension", 2], ["clienti", 1], ["vendite", 1], ["promozion", 1], ["delivery|deliveroo|glovo", 1], ["camerier", 1]],
  "commercialista": [["\\biva\\b", 2], ["\\bf24\\b", 2], ["dichiaraz", 2], ["imposte|tasse", 1], ["irap|ires", 2], ["fattura elettronica|\\bsdi\\b", 2], ["commercialista", 2], ["scadenz\\w* fiscal", 2], ["ritenut", 1]],
  "consulente-lavoro": [["buste? paga|cedolin", 2], ["dipendent", 1], ["assunzion|dimission", 2], ["contratt\\w* di lavoro", 2], ["ccnl", 2], ["part.?time", 2], ["ferie|permess", 1], ["\\btfr\\b", 2], ["\\bturni\\b", 1], ["ore lavorate", 2], ["costo del personale", 2], ["inps|inail", 2]],
  "cruscotto-bi": [["dashboard", 2], ["power ?bi", 2], ["grafic", 1], ["cruscotto", 2], ["schema bi", 2]],
  "fiscalista-patrimonio": [["patrimonio", 2], ["holding", 2], ["successione", 2], ["donazion", 2], ["agevolaz", 2], ["credito d.imposta", 2], ["tutela", 1], ["immobil", 1]],
  "garante-dati": [["dati mancanti", 2], ["qualit\\w* dei dati", 2], ["quadratura|\\bquadra\\b", 1], ["duplicat", 2], ["anomali", 1], ["non torna", 2], ["affidabil", 1], ["buchi", 1]],
  "legale-societario": [["s\\.?r\\.?l\\b|societ", 1], ["statuto", 2], ["verbale", 2], ["\\bsoci\\b", 1], ["responsabilit", 1], ["contratto d.affitto|locazione", 2], ["avvocat|legale", 2], ["privacy|gdpr", 2]],
  "manutentore-dati": [["correggi|correggere", 1], ["sistema(re)?\\b", 1], ["da sistemare", 2], ["ricarica", 1], ["ripara", 1], ["reimporta|rifai il giro", 2]],
  "revisore-contabile": [["\\brevision|\\brevisor", 2], ["riconcilia", 2], ["scritture", 2], ["partita doppia", 2], ["controllo contabil", 2], ["note di credito", 2], ["coerenza", 1]],
};
