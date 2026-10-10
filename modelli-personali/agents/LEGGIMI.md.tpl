# Gli agenti di @@NOME_ASSISTENTE@@ di @@UTENTE@@

Si parte da zero. Qui ci sono solo i due aiutanti generici dell'assistente (la chat master, che risponde a @@UTENTE@@):

- `esecutore.md` — esegue compiti già decisi, passo per passo; si ferma davanti all'irreversibile.
- `ricercatore-web.md` — cerca fonti su internet e riporta fatti con link e data.

I progetti e i loro agenti nascono quando servono: «crea il progetto …» a @@NOME_ASSISTENTE@@, oppure
`/nuovo-progetto <nome>` e `/nuovo-agente <progetto> <ruolo>` in Claude Code (script `strumenti\crea_progetto.py` e
`strumenti\crea_agente.py`). Ogni progetto ha il suo capogruppo `<id>-ceo` in `<cartella>\.claude\agents\`, che crea gli
specialisti uno alla volta. Un agente nuovo si invoca per nome dalla sessione di Claude Code successiva alla sua creazione.
Guida: `docs\wiki\Progetti-e-agenti.md`.
