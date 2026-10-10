---
description: Domande di avvio in modalità piano, poi installazione di Jarvis per Windows dopo l'approvazione
---

Fai la procedura «Prima apertura» di `CLAUDE.md` di questo repository, dall'inizio, anche se
`%USERPROFILE%\.jarvis\installato.json` esiste già (in quel caso dillo e proponi le risposte attuali di
`%USERPROFILE%\.jarvis\risposte-avvio.json` come valori predefiniti).

1. Entra in modalità piano. Non modifichi niente finché la persona non approva il piano.
2. Fai le DOMANDE DI AVVIO di `CLAUDE.md`, una per volta, aspettando ogni risposta. Niente segreti.
3. Mostra il piano: il JSON delle risposte, cosa installa `INSTALLA.ps1`, cosa non tocca, come si torna indietro.
4. Chiedi «Approvi il piano?». Solo dopo un sì chiaro: esci dalla modalità piano, scrivi
   `%USERPROFILE%\.jarvis\risposte-avvio.json` (formato: `modelli-personali\risposte-avvio.esempio.json`), lancia
   `powershell -ExecutionPolicy Bypass -File .\INSTALLA.ps1 -DaRisposte`, poi `VERIFICA.ps1`, e riferisci con le righe
   vere dell'uscita.

$ARGUMENTS
