# Missão 006 — integridade textual (resultados)

## Diagnóstico (A005 vs passe integral)

- Clipes: 16 · tokens de referência: 265
- WER: integral 0.1069 · A005 0.1227
- Integridade A005: 0.978
- Palavras de referência perdidas pela A005: **3**
- Duplicações (bigramas): integral 3 · A005 3
- Fala não coberta (proxy): 0.0069

## Correção A2 (VAD pad=250 ms, merge 0,35 s, th 0,30)

- WER: **0.1069** (igual ao passe integral)
- Integridade: **1.0000** · palavras perdidas: 0
- SRT válido: 100% · RTF: 0.051
- Fronteiras (controlado): recall@250 ms 67% · recall@500 ms 100% · MAE 182 ms

## Reconciliação (texto integral + tempos estimados)

- Clipes reconciliados: 16/16 · SRT válido: 100% · RTF: 0.554
- Texto igual ao integral (controlado): True

## Varredura de padding (16 clipes + controlado)

| pad (ms) | merge (s) | WER | Integridade média | Integridade máx. | Recall@250 | Recall@500 | MAE |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 150 | 0.35 | 0.1147 | 0.9732 | 0.5714 | 100% | 100% | 98 ms |
| 200 | 0.35 | 0.1039 | 0.9970 | 0.9524 | 100% | 100% | 140 ms |
| 250 | 0.35 | 0.1069 | 1.0000 | 1.0000 | 67% | 100% | 145 ms |
| 250 | 0.5 | 0.1093 | 0.9976 | 0.9615 | 50% | 50% | 125 ms |

Integridade = 1 − WER do texto segmentado contra o passe integral do próprio Parakeet.
Recall/MAE medidos no conjunto controlado contra onsets de fala conhecidos.
