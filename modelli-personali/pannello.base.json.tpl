{
 "gruppi": [
  {
   "id": "spazio-memoria",
   "nome": "Memoria",
   "chiuso": true,
   "agenti": [
    "memoria:archivista"
   ]
  },
  {
   "id": "spazio-agenti-utente",
   "nome": "Agenti di @@UTENTE@@",
   "chiuso": false,
   "agenti": [
    "jarvis:esecutore"
   ]
  }
 ],
 "aspetto": {},
 "lavagne": {
  "generale": {
   "nodi": [
    {
     "id": "n1",
     "tipo": "nota",
     "agente": "",
     "testo": "@@UTENTE@@",
     "x": 502.0,
     "y": 0.0
    },
    {
     "id": "n2",
     "tipo": "nota",
     "agente": "",
     "testo": "Jarvis — orchestratore, risponde a @@UTENTE@@",
     "x": 502.0,
     "y": 110.0
    },
    {
     "id": "n3",
     "tipo": "nota",
     "agente": "",
     "testo": "Memoria",
     "x": 815.0,
     "y": -74.0
    },
    {
     "id": "n4",
     "tipo": "agente",
     "agente": "memoria:archivista",
     "testo": "",
     "x": 815.0,
     "y": 12.0
    },
    {
     "id": "n5",
     "tipo": "agente",
     "agente": "jarvis:esecutore",
     "testo": "",
     "x": 815.0,
     "y": 110.0
    }
   ],
   "fili": [
    {
     "da": "n1",
     "a": "n2"
    },
    {
     "da": "n2",
     "a": "n1"
    },
    {
     "da": "n2",
     "a": "n3"
    },
    {
     "da": "n3",
     "a": "n4"
    },
    {
     "da": "n2",
     "a": "n4"
    },
    {
     "da": "n2",
     "a": "n5"
    },
    {
     "da": "n5",
     "a": "n4"
    }
   ],
   "vista": {
    "x": 0.0,
    "y": 156.0,
    "zoom": 0.9
   },
   "bolle": {}
  },
  "spazio-agenti-utente": {
   "nodi": [
    {
     "id": "n6",
     "tipo": "agente",
     "agente": "jarvis:esecutore",
     "testo": "",
     "x": -4.0,
     "y": 30.0
    }
   ],
   "fili": [],
   "vista": {
    "x": 580.0,
    "y": 359.5,
    "zoom": 1.0
   },
   "bolle": {}
  }
 },
 "aggiornato": "",
 "versione": 1
}
