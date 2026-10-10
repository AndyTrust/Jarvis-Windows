// Regole dello smistamento (smista.js): nome dell'agente in minuscolo -> [[espressione, peso]].
// Si parte da zero: nessuna regola. Senza regole smista.js usa le parole della missione («description») di ogni agente,
// quindi gli agenti creati con crea_agente.py vengono suggeriti da soli. Per affinare, aggiungi qui righe come:
//   "<nome-agente>": [["parola", 2], ["altra parola", 1]],
window.CC_SMISTA_REGOLE = {};
