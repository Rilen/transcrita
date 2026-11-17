# Matriz de elegibilidade — candidatos ASR (CPU-only)

Avaliação documental (fonte oficial, licença, runtime, suporte a pt-BR) antes de qualquer download.

| Candidato | Identidade / fonte | Licença | pt-BR | Runtime CPU verificado | Status | Justificativa |
|---|---|---|---|---|---|---|
| Whisper small | `Systran/faster-whisper-small` (CT2) | MIT (pesos OpenAI) | Sim (multilíngue) | faster-whisper 1.2.1 / CTranslate2 4.9.0 | **ELEGÍVEL** | Runtime já em produção; int8 CPU |
| Whisper medium | `Systran/faster-whisper-medium` (CT2) | MIT | Sim | idem | **ELEGÍVEL** | Avaliado para curva precisão/custo |
| Whisper large-v3-turbo | `deepdml/faster-whisper-large-v3-turbo-ct2` | MIT | Sim | idem | **ELEGÍVEL** | turbo = decoder reduzido; melhor equilíbrio observado |
| Whisper large-v3 | `Systran/faster-whisper-large-v3` (CT2) | MIT | Sim | idem | **ELEGÍVEL** | Referência de qualidade máxima da família |
| Parakeet TDT 0.6B v3 (pt-BR TAGARELA, ONNX INT8) | `calneymgp/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx-int8` | CC-BY-4.0 | Sim (fine-tune pt-BR) | onnx-asr 0.12.0 + onnxruntime 1.32.0 | **ELEGÍVEL (condicionado a atribuição)** | Fine-tune comunitário (não oficial NVIDIA) e quantização INT8 não reavaliada formalmente; base NVIDIA v3 é CC-BY-4.0 |
| NVIDIA Parakeet TDT 0.6B v3 (oficial, multilíngue) | `nvidia/parakeet-tdt-0.6b-v3` | CC-BY-4.0 | Sim (`pt` nos metadados) | Exige NeMo/PyTorch (não homologado nesta PoC) | **CONDICIONAL** | Runtime oficial pesado; não avaliado nesta rodada por limite de escopo/recursos |
| Qwen3-ASR 0.6B | `Qwen/Qwen3-ASR-0.6B` | Apache-2.0 | Sim (52 idiomas incl. pt) | qwen-asr 0.0.6 + torch 2.15 CPU | **ELEGÍVEL** | Avaliado em venv separado (`.venv-qwen`) |
| Qwen3-ASR 1.7B | `Qwen/Qwen3-ASR-1.7B` | Apache-2.0 | Sim | qwen-asr + torch CPU | **CONDICIONAL** | Viável, porém com maior custo de RAM/tempo; não executado nesta rodada |
| TAGARELA (fine-tunes comunitários) | ex.: `alexandreacff/distil-whisper-tagarela-v2`, `alefiury/parakeet-tdt-tagarela-v2` | varia (CC-BY-4.0 nos disponíveis) | Sim | Whisper→CT2 requer conversão (transformers+torch); Parakeet→NeMo/ONNX | **CONDICIONAL** | Exige conversão/validação adicional; o representante pt-BR do Parakeet via ONNX já foi avaliado |
| Voxtral | — | — | — | sem runtime CPU homologado identificado | **INELEGÍVEL (nesta fase)** | Sem evidência reproduzível de execução CPU offline |

> Critério de elegibilidade: pesos públicos + licença compatível + runtime CPU disponível e documentado + suporte declarado a português.
> Nenhum peso de candidato INELEGÍVEL foi baixado.
