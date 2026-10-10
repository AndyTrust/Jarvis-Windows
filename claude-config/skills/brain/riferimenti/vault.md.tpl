# Il vault Obsidian (facoltativo)

Se usi Obsidian, il vault è il tuo «secondo cervello»: le stesse conclusioni della memoria, scritte come note
collegate e leggibili da te. **Non è obbligatorio**: senza vault la memoria in `.claude\memoria\` funziona lo stesso.

## Come si collega

In `@@JARVIS_DIR_WIN@@\utente.json` scrivi `"vault_dir": "C:\percorso\del\tuo\vault"` (la cartella che contiene
`.obsidian\`). In alternativa imposta la variabile d'ambiente `JARVIS_VAULT`. Se il percorso è vuoto o non esiste,
`salva.ps1` non scrive nulla nel vault.

## Cosa ci scrive Jarvis

```
<vault>\
└── <nome del progetto>\           <- una cartella per progetto, con lo stesso nome della cartella sul disco
    └── A che punto siamo.md       riscritta da salva.ps1 a ogni chiusura, non si corregge a mano
```

Il resto del vault è tuo: Jarvis non lo tocca. Per dare a un progetto una cartella con un nome diverso, aggiungilo a
`$PROGETTI` in `strumenti\comune.ps1`.

## Regole

- Il vault è la **cartella padre** che contiene `.obsidian\`: i `[[collegamenti]]` funzionano solo restando dentro.
- Se il vault sta su un cloud (OneDrive, iCloud, Dropbox) controlla che sia montato prima di scrivere: altrimenti
  nasce una copia locale che non arriva mai online.
- **Memoria e vault non sono la stessa cosa e non si copiano l'una nell'altra.** La memoria serve al modello ed è
  telegrafica; il vault serve a te ed è più discorsivo.
- Una nota che descrive dati non si scrive a mano se esiste uno strumento che la genera: si corregge lo strumento.
