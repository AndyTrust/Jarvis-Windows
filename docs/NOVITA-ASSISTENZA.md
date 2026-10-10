# Novità dell'assistenza a distanza (02/10/2026)

- Un tasto solo, «Attiva assistenza», nella pagina Stato. Si vede anche ad assistenza spenta. Crea o completa
  assistenza.json senza cambiare i valori che ci sono e, se manca qualcosa, apre la finestra che installa WSL,
  Ubuntu, openssh, tmux e tmate.
- Collegamento nuovo: tunnel ssh dentro WSL verso il server del tecnico. Il riquadro mostra una richiesta
  `jarvis-tunnel:` da copiare e mandare. tmate resta la riserva.
- Chiusura per STOP, credito finito, 8 ore, tunnel caduto o Linux che non risponde: i processi dentro WSL si
  fermano in modo esplicito e si controlla che siano fermi. Tunnel mai stabilito in 15 minuti: minuti a credito.
- Conteggio (regola del 2026-10-02): 12,50 € ogni 15 minuti, anticipati. All'avvio si scala solo il primo blocco
  da 15; ricarica minima 15 minuti; rimborso di 15 minuti se il tunnel non parte. Vale anche con un assistenza.json
  vecchio che porta 60.
- Senza dati di pagamento sul PC il riquadro non mostra ordini, coordinate o IBAN.
- ASSISTENZA.ps1 -SoloControlla stampa un riepilogo di poche righe da mandare al tecnico.
- Prove: app/strumenti/prova_assistenza.py (wsl.exe finto) e app/command-center/prova_assistenza_pannello.py
  (contro il pannello acceso).

## Schermo condiviso (02/10/2026, sera)

- Il tecnico può VEDERE e USARE lo schermo del PC (monitor, mouse, tastiera), non solo il terminale. Stesso credito a
  blocchi, un solo consenso, un solo STOP che chiude tutto. Il riquadro dice «Schermo condiviso attivo» quando il tecnico guarda.
- Serve TightVNC Server: «Attiva assistenza» lo installa con winget (senza servizio, senza aprire il firewall). Gira solo
  durante l'assistenza, solo su 127.0.0.1, con una password nuova a ogni sessione che il tecnico riceve cifrata.
- Senza TightVNC si usa il solo terminale, come prima. Prova: `app/strumenti/prova_assistenza_schermo.py`.
