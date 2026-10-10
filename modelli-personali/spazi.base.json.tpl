{
  "_nota": "Modello personale: l'installatore lo rende in command-center/spazi.json solo se manca già.",
  "spazi": [
    {
      "id": "agenti-utente",
      "nome": "Agenti di @@UTENTE@@",
      "memoria": "@@JARVIS_DIR@@/.claude/memoria-@@UTENTE_SLUG@@",
      "report": "@@JARVIS_DIR@@/report-missioni",
      "progetti": [
        {
          "id": "jarvis",
          "nome": "Jarvis di @@UTENTE@@",
          "cartella": "@@JARVIS_DIR@@",
          "capogruppo": null,
          "sezioni_memoria": [],
          "memoria_propria": [
            "@@JARVIS_DIR@@/.claude/memoria-@@UTENTE_SLUG@@"
          ]
        }
      ]
    },
    {
      "id": "memoria",
      "nome": "Memoria",
      "memoria": "@@JARVIS_DIR@@/.claude/memoria-@@UTENTE_SLUG@@",
      "report": "@@JARVIS_DIR@@/report-missioni",
      "progetti": [
        {
          "id": "memoria",
          "nome": "Memoria di @@UTENTE@@",
          "cartella": "@@JARVIS_DIR@@/.claude/memoria-@@UTENTE_SLUG@@",
          "capogruppo": "archivista",
          "sezioni_memoria": [],
          "memoria_propria": [
            "@@JARVIS_DIR@@/.claude/memoria-@@UTENTE_SLUG@@"
          ]
        }
      ]
    }
  ]
}
