# Avisos de terceiros — Transcrita

## Dependências de runtime
| Componente | Licença | Observação |
|---|---|---|
| faster-whisper | MIT | runtime Whisper (CTranslate2) |
| CTranslate2 | MIT | inferência CPU |
| onnx-asr | MIT (`License-Expression`) | runtime ONNX para Parakeet |
| onnxruntime | MIT | execução ONNX |
| soundfile | BSD-3-Clause | leitura de WAV |
| Silero VAD (embutido no faster-whisper) | MIT | detecção de fala |
| FastAPI / Uvicorn / python-multipart | MIT / BSD | camada web |
| Piper TTS (OHF-Voice/piper1-gpl) | GPL-3.0 / MIT | motor neural TTS local isolado |

## Pesos do modelo Parakeet PT-BR (experimental)
- Checkpoint: `calneymgp/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx-int8`
- Licença: **CC-BY-4.0** (atribuição obrigatória).
- Linhagem: NVIDIA Parakeet TDT 0.6B v3 (CC-BY-4.0) → fine-tune pt-BR TAGARELA
  (`alexandreacff/parakeet-tdt-0.6b-v3-ptBR-plus`, `alefiury/...-onnx`) →
  quantização INT8 dinâmica (comunidade). A quantização **não foi reavaliada**
  formalmente pelo autor original; trate como experimental.
- Atribuição recomendada em publicações/derivados: NVIDIA NeMo/Parakeet,
  TAGARELA (dataset), Alefiury e Alexandre Acff (fine-tune/export), autor da
  quantização.

## Integridade dos pesos
- Opcional: defina `TRANSCRITA_PARAKEET_SHA256` com o SHA-256 de
  `encoder-model.int8.onnx`. Se definido, o motor recusa carregar em caso de
  divergência (log interno registra esperado/atual).

## Modelos de Voz Piper TTS (Português do Brasil)

### 1. Faber (`pt_BR-faber-medium`)
- **Arquivo ONNX:** `pt_BR-faber-medium.onnx`
- **SHA-256:** `75e913eb463db0b6ac7ddf68d3e4c9ac19ace36dc3b710a81039b448352b8ffc`
- **Arquivo Config:** `pt_BR-faber-medium.onnx.json`
- **SHA-256:** `6b6801319e5a70aa4d75c63343515f55d1cd671ecd1ac511586bc16216812261`
- **Licença do Dataset:** **CC0 1.0 Universal** (Domínio Público).
- **Origem:** Open Home Foundation (`OHF-Voice/voice-datasets`).
- **Taxa de Amostragem:** 22.050 Hz (16-bit mono PCM).

### 2. Edresson (`pt_BR-edresson-low`)
- **Arquivo ONNX:** `pt_BR-edresson-low.onnx`
- **SHA-256:** `de4cecee38b30bb1a6378a337af605d59f0c377df702c6a6752870db8991cd84`
- **Arquivo Config:** `pt_BR-edresson-low.onnx.json`
- **SHA-256:** `f138992d2e777d1e3aa0bbb14c2d324307b0f342c1bcf20978765b3bea506c56`
- **Licença do Dataset:** **CC-BY-4.0** (Edresson TTS-Portuguese-Corpus).
- **Atribuição:** Edresson Silva (`https://github.com/Edresson/TTS-Portuguese-Corpus`).
- **Taxa de Amostragem:** 16.000 Hz (16-bit mono PCM).
