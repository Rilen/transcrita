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
