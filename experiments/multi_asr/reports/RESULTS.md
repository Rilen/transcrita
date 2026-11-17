# Resultados do benchmark multimotor (CPU-only)

## Visão geral

| Modelo | WER | CER | RTF | Load (s) | RAM pico (MB) | OK |
|---|---:|---:|---:|---:|---:|---:|
| whisper-large-v3-turbo | 0.0521 | 0.0279 | 0.255 | 30.6 | 2648 | 12/12 |
| whisper-medium | 0.0741 | 0.0312 | 0.568 | 33.5 | 2951 | 12/12 |
| whisper-large-v3 | 0.0757 | 0.0315 | 0.751 | 54.9 | 5831 | 12/12 |
| parakeet-ptbr-tagarela-int8 | 0.1041 | 0.0441 | 0.041 | 2.6 | 2438 | 12/12 |
| qwen3-asr-0.6b | 0.1341 | 0.0526 | 0.321 | 5.5 | 6015 | 12/12 |
| whisper-small | 0.1404 | 0.0583 | 0.251 | 1.3 | 978 | 12/12 |

## WER por cenário

| Modelo | clean | distant | long | multi | noisy |
|---|---:|---:|---:|---:|---:|
| parakeet-ptbr-tagarela-int8 | 0.0850 | 0.1343 | 0.1265 | 0.0761 | 0.1290 |
| qwen3-asr-0.6b | 0.1215 | 0.0746 | 0.1747 | 0.0870 | 0.2097 |
| whisper-large-v3 | 0.0526 | 0.1343 | 0.1145 | 0.0217 | 0.0806 |
| whisper-large-v3-turbo | 0.0364 | 0.0448 | 0.0663 | 0.0326 | 0.1129 |
| whisper-medium | 0.0810 | 0.0448 | 0.0843 | 0.0326 | 0.1129 |
| whisper-small | 0.1700 | 0.0896 | 0.1145 | 0.1087 | 0.1935 |

## Proxy de alucinação (razão palavras hipótese/referência)

| Modelo | Clipes com razão > 1,5 | Razão máxima |
|---|---:|---:|
| parakeet-ptbr-tagarela-int8 | 0 | 1.04 |
| qwen3-asr-0.6b | 0 | 1.06 |
| whisper-large-v3 | 0 | 1.03 |
| whisper-large-v3-turbo | 0 | 1.03 |
| whisper-medium | 0 | 1.12 |
| whisper-small | 0 | 1.32 |
