# Validação 005 — qualidade e timestamps (CPU-only)

## Qualidade ASR (16 clipes, fala espontânea + preparada)

| Métrica | Parakeet PT-BR INT8 | Whisper large-v3-turbo |
|---|---:|---:|
| WER | **0.1069** | 0.1379 |

| Cenário | n | WER Parakeet | WER Whisper |
|---|---:|---:|---:|
| prepared | 6 | 0.1088 | 0.1472 |
| spontaneous_dialogue | 6 | 0.1132 | 0.1506 |
| spontaneous_interview | 4 | 0.0947 | 0.1047 |

## Estratégias de timestamps

| Estratégia | SRT válido | Cobertura | Integridade textual* | RTF | Fronteiras (recall@250ms) | MAE |
|---|---:|---:|---:|---:|---:|---:|
| A — VAD + Parakeet (ajustada) | 100% | 0.92 | 0.978 | 0.043 | 100% | 93 ms |
| A — VAD (padrão) | 100% | 0.87 | 0.947 | 0.064 | — | — |
| C — Híbrido estimado | 100% | 0.87 | 1.000 | 0.562 | 50% | 83 ms |
| B — MMS_FA (texto Parakeet) | n/a | n/a | 1.000 (texto fixo) | 0.061 | 100% | 70 ms |

*Integridade = 1 - WER do texto segmentado contra o texto integral do mesmo motor.

B executa apenas alinhamento (não reconhece); RTF mede alinhamento sobre 46,4 s.

## Ajuste de VAD (conjunto controlado, 6 fronteiras conhecidas)

| th | pad (ms) | Cobertura | Integridade | Frag./min | Recall | MAE |
|---|---:|---:|---:|---:|---:|---:|
| 0.5 | 100 | 0.79 | 0.028 | 19.4 | 100% | 53 ms |
| 0.35 | 300 | 0.90 | 0.009 | 11.6 | 50% | 148 ms |
| 0.3 | 400 | 0.94 | 0.038 | 10.4 | 17% | 0 ms |
| 0.35 | 150 | 0.85 | 0.009 | 11.6 | 100% | 93 ms |
| 0.4 | 150 | 0.83 | 0.019 | 16.8 | 100% | 93 ms |

## Limitações

- Corpus público sem reuniões com sobreposição real; NURC é espontâneo (diálogos/entrevistas) e mTEDx é preparado.
- Sem referência temporal humana; precisão de fronteira medida em conjunto controlado com silêncios inseridos.
- B (MMS_FA) exige transcrição prévia, licença CC-BY-NC-4.0 do bundle e runtime torchaudio.
- Estratégia C é estimada por alinhamento de sequência; não é alinhamento forçado por palavra.
