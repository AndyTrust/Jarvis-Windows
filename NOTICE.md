# Avvisi e licenze di terzi

Il codice scritto per questo progetto è distribuito con licenza GNU GPL versione 3 (file `LICENSE`).
Qui sotto le parti di altri che il progetto include o scarica, con la loro licenza e la compatibilità con la GPL-3.0.
Verifica fatta il 2026-10-10 dai metadati di PyPI (campo licenza e classificatori), dai file LICENSE dei repository e
dalle schede dei modelli. Le versioni sono quelle di `requirements.txt` o, dove non è fissata, l'ultima su PyPI quel giorno.

## Incluse nel repository

| Parte | Dove | Licenza | Con GPL-3.0 |
|---|---|---|---|
| Cinque skill da Superpowers 6.3.0 (Jesse Vincent) | `claude-config/skills/brainstorming`, `writing-plans`, `systematic-debugging`, `verification-before-completion`, `writing-skills` | MIT (`claude-config/skills/LICENSE-superpowers.txt`) | compatibile: resta l'avviso MIT su quei file |
| Personaggi «Dots» di OpenDots / CopilotKit (Atai Barkai) e varianti derivate | `app/command-center/static/dots/` | MIT (`LICENSE-OpenDots.txt`, `ATTRIBUZIONE-nuovi-dots.txt`) | compatibile: resta l'avviso MIT sulle immagini |

## Librerie Python (le installa `INSTALLA.ps1` da PyPI, non sono nel repository)

| Libreria | Uso | Licenza | Con GPL-3.0 |
|---|---|---|---|
| claude-agent-sdk | missioni e agenti | MIT | compatibile |
| faster-whisper 1.2.1 | trascrizione locale | MIT | compatibile |
| kokoro-onnx 0.4.7 | voce locale | MIT (repository thewh1teagle/kokoro-onnx) | compatibile |
| misaki 0.7.4 | fonemi per Kokoro | Apache-2.0 | compatibile con GPL-3.0 (non con GPL-2.0) |
| onnxruntime | esecuzione dei modelli | MIT | compatibile |
| numpy | calcolo | BSD-3-Clause, 0BSD, MIT, Zlib, CC0-1.0 | compatibile |
| scipy | filtro dei bassi | BSD-3-Clause | compatibile |
| noisereduce | filtro del rumore | MIT (classificatore BSD su PyPI) | compatibile |
| soundfile | lettura e scrittura audio | BSD-3-Clause | compatibile |
| sounddevice | microfono e casse | MIT | compatibile |
| pynput | tasto Shift destro | LGPL-3.0 | compatibile |
| pillow | orb e icone | MIT-CMU | compatibile |
| edge-tts | voce in rete (facoltativa) | LGPL-3.0 | compatibile; usa un servizio online di Microsoft con i suoi termini |

## Modelli e programmi scaricati

| Parte | Da dove | Licenza | Con GPL-3.0 |
|---|---|---|---|
| Modello vocale Kokoro-82M (file `kokoro-v1.0.onnx`, `voices-v1.0.bin`) | release di kokoro-onnx su GitHub, pesi di hexgrad/Kokoro-82M | Apache-2.0 | compatibile |
| Modello Whisper «small» per faster-whisper | Hugging Face, Systran/faster-whisper-small (conversione dei pesi OpenAI Whisper) | MIT | compatibile |
| eSpeak NG | winget `eSpeak-NG.eSpeak-NG`, programma separato | GPL-3.0 | compatibile; non è incluso, si installa a parte |
| Python, Git for Windows | winget, programmi separati | PSF; GPL-2.0 | non inclusi, usati come programmi di sistema |

## Programmi esterni non inclusi

- **Claude Code** è un prodotto di Anthropic con i suoi termini d'uso. Non è incluso né ridistribuito: lo installi tu
  dal sito ufficiale. Jarvis lo lancia come programma esterno.
- **WSL, OpenSSH, tmate** (solo per l'assistenza a distanza facoltativa): installati a parte, ognuno con la sua licenza.

## Esito

Nessuna dipendenza incompatibile con la GPL-3.0. Due note:
- Apache-2.0 (misaki, pesi di Kokoro) è compatibile con la GPL-3.0 ma non con la GPL-2.0: il progetto va distribuito
  come GPL-3.0 (o successiva), non come GPL-2.0.
- edge-tts e Claude Code usano servizi in rete con termini propri: la licenza del codice non li cambia.

Il testo di questo file va aggiornato quando cambia `requirements.txt` o quando si aggiunge un modello.
