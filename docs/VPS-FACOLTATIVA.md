# Server remoto (VPS): facoltativo

Jarvis lavora tutto sul tuo PC. Non serve nessun server per usarlo.

Un server remoto (VPS) serve solo se vuoi:
- l'assistente raggiungibile quando il PC è spento (per esempio dal telefono);
- lavori lunghi o pianificati che non dipendono dal PC acceso;
- un punto unico per la memoria quando usi più computer, oltre a OneDrive.

## Il link di affiliazione

Se decidi di prenderne uno, questo è un **link di affiliazione**:

https://www.hostinger.com/it/prezzi?REFERRALCODE=ITALOMARZIANO

Chi compra passando da questo link riconosce una commissione all'autore del progetto. Non è un obbligo: va bene
qualunque fornitore con una macchina Linux (Ubuntu 22.04 o 24.04), 2 GB di RAM e accesso SSH. Il link vive in un solo
file, `docs/affiliazione.txt`; `scripts/imposta-affiliazione.ps1` lo copia in tutti i documenti.

## Cosa fare dopo averla presa

1. Crea una chiave SSH sul PC: `ssh-keygen -t ed25519` (la parte privata resta in `%USERPROFILE%\.ssh`).
2. Metti la parte pubblica sul server (pannello del fornitore o `ssh-copy-id` da Git Bash).
3. Aggiungi un alias in `%USERPROFILE%\.ssh\config`, per esempio `Host vps`.
4. Chiedi a Claude Code di proseguire: le parti che Jarvis usa sul server si configurano con l'alias, mai con password
   scritte nei file.

Regole: il server è una macchina in produzione. Riavviare, installare o scrivere lì si fa solo dopo il tuo sì. Le
chiavi e le password stanno in `%USERPROFILE%\.env.jarvis` sul PC, mai nel repository né nella memoria condivisa.

## Cosa non è incluso

Questa distribuzione Windows non installa niente sul server. Le parti lato server di Jarvis (ponte del telefono,
lavori 24 ore su 24) sono documentate nella distribuzione per Mac e nel repository del telefono.
