# Validação 004 — resultados (fala espontânea e preparada)

## Visão geral

| Modelo | WER | CER | RTF | Load (s) | RAM (MB) |
|---|---:|---:|---:|---:|---:|
| parakeet-ptbr-tagarela-int8 | 0.1078 | 0.0538 | 0.059 | 2.6 | 1749 |
| whisper-large-v3-turbo | 0.1527 | 0.0911 | 0.588 | 3.7 | 2098 |
| whisper-large-v3 | 0.1737 | 0.1013 | 1.119 | 5.7 | 3982 |
| qwen3-asr-0.6b | 0.1946 | 0.1053 | 0.307 | 4.1 | 6015 |

## WER por cenário

| Modelo | espontâneo | preparado |
|---|---:|---:|
| parakeet-ptbr-tagarela-int8 | 0.1023 | 0.1176 |
| qwen3-asr-0.6b | 0.2186 | 0.1513 |
| whisper-large-v3 | 0.1907 | 0.1429 |
| whisper-large-v3-turbo | 0.1628 | 0.1345 |

## Erros por tipo (por palavra de referência)

| Modelo | Subst. | Del. | Ins. |
|---|---:|---:|---:|
| parakeet-ptbr-tagarela-int8 | 0.0571 | 0.0240 | 0.0270 |
| qwen3-asr-0.6b | 0.0991 | 0.0661 | 0.0300 |
| whisper-large-v3 | 0.0721 | 0.0661 | 0.0360 |
| whisper-large-v3-turbo | 0.0541 | 0.0661 | 0.0330 |

## Números e termos raros

| Modelo | Recall números | Nº espúrios | Recall raros |
|---|---:|---:|---:|
| parakeet-ptbr-tagarela-int8 | 0.000 (0 refs) | 0 | 0.957 (115) |
| qwen3-asr-0.6b | 0.000 (0 refs) | 0 | 0.878 (115) |
| whisper-large-v3 | 0.000 (0 refs) | 0 | 0.913 (115) |
| whisper-large-v3-turbo | 0.000 (0 refs) | 0 | 0.930 (115) |

## Timestamps

| Modelo | Clipes com segmentos | Segmentos (média) | Cobertura média |
|---|---:|---:|---:|
| parakeet-ptbr-tagarela-int8 | 0 | 0.0 | 0.00 |
| qwen3-asr-0.6b | 0 | 0.0 | 0.00 |
| whisper-large-v3 | 24 | 1.2 | 0.88 |
| whisper-large-v3-turbo | 24 | 1.2 | 0.89 |

## Estabilidade (3 repetições, 8 clipes)

| Modelo | WER médio | dp WER | Tempo médio (s) | dp tempo | Saídas idênticas |
|---|---:|---:|---:|---:|---|
| parakeet-ptbr-tagarela-int8 | 0.1416 | 0.0000 | 2.6 | 0.08 | sim |
| whisper-large-v3-turbo | 0.2301 | 0.0000 | 28.1 | 1.32 | sim |
