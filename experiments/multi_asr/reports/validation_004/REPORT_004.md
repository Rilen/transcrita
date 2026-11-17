# TRANSCRITA-004 — Validação representativa multimotor (CPU-only)

**Data:** 2026-11-17 · **Host:** 10.0.0.88 · **Base:** `exp/multi-asr-cpu-poc` (`e1e0ebe`) · **Produção:** `main` (`95bdf68`, intocada)

**Estado:** `TRANSCRITA_004_EXPLORATORY_ONLY`
(métricas reais e reprodutíveis, porém o corpus público não representa reuniões institucionais com sobreposição de fala e diarização; sem homologação institucional)

---

## 1. Reconhecimento e auditoria metodológica (003 → 004)

Confirmados: serviço `transcrita.service` ativo, `main` limpa em `95bdf68`, PR #2 aberta (`exp/multi-asr-cpu-poc`, `e1e0ebe`), venvs e pesos presentes.

Correções de rastreabilidade aplicadas antes dos novos benchmarks:
1. **Revisões e licenças pinadas** em `reports/METADATA.json` (repos, `sha` do HF, licença, versões de runtime).
2. **Semântica de tempo de carga documentada**: `load_time_s` inclui download na 1ª execução; tempos a quente (sem inferência) medidos por `warm_load.py`.
3. **Normalização/agregação auditadas**: WER/CER com acentos preservados; agregação ponderada por palavras (testes unitários).
4. **Licenças do corpus**: NURC-SP é **CC-BY-NC-ND** → nenhuma transformação de áudio aplicada; mTEDx é **CC-BY-NC** → uso interno.
5. **Lacuna registrada**: corpus público disponível não contém reuniões institucionais com múltiplos falantes sobrepostos.

## 2. Corpus 004
Ver [`CORPUS_004.md`](CORPUS_004.md). 24 clipes (133,3 s): 16 espontâneos (NURC-SP, diálogos/entrevistas/talks) + 8 preparados (TEDx pt-BR). Áudio bruto, sem derivados; manifesto local com hashes; nada de áudio/transcrição versionado.

## 3. Resultados

| Modelo | WER | CER | RTF | Load (s) | RAM (MB) |
|---|---:|---:|---:|---:|---:|
| **parakeet-ptbr-tagarela-int8** | **0,1078** | **0,0538** | **0,059** | 2,6 | **1 749** |
| whisper-large-v3-turbo | 0,1527 | 0,0911 | 0,588 | 3,7 | 2 098 |
| whisper-large-v3 | 0,1737 | 0,1013 | 1,119 | 5,7 | 3 982 |
| qwen3-asr-0.6b | 0,1946 | 0,1053 | 0,307 | 4,1 | 6 015 |

### Por cenário (WER)
| Modelo | espontâneo | preparado |
|---|---:|---:|
| parakeet-ptbr-tagarela-int8 | **0,1023** | **0,1176** |
| whisper-large-v3-turbo | 0,1628 | 0,1345 |
| whisper-large-v3 | 0,1907 | 0,1429 |
| qwen3-asr-0.6b | 0,2186 | 0,1513 |

### Erros por tipo (por palavra de referência)
| Modelo | Substituições | Deleções | Inserções |
|---|---:|---:|---:|
| parakeet | 0,0571 | **0,0240** | 0,0270 |
| turbo | 0,0541 | 0,0661 | 0,0330 |
| large-v3 | 0,0721 | 0,0661 | 0,0360 |
| qwen | 0,0991 | 0,0661 | 0,0300 |

Whisper tem **2,8× mais deleções** que o Parakeet na fala espontânea (omissões de trechos), o que explica a diferença de WER apesar de substituições semelhantes.

### Termos raros e números
Recall de termos raros (freq. 1, ≥4 letras): **parakeet 95,7%** · turbo 93,0% · large-v3 91,3% · qwen 87,8%.
O corpus não contém tokens numéricos → **avaliação de números/datas não realizada** (lacuna).

### Timestamps
- Whisper (turbo e large-v3): segmentos em 24/24 clipes, 1,2 segmento/clipe, cobertura média **0,88–0,89**.
- Parakeet (via `onnx-asr`) e Qwen3-ASR: **sem timestamps** nesta integração → não utilizáveis para SRT/segmentação.

### Estabilidade (3 repetições, subconjunto de 8 clipes, 44,7 s)
| Modelo | WER médio | dp | Tempo médio | dp | Saídas idênticas |
|---|---:|---:|---:|---:|---|
| parakeet | 0,1416 | 0,0000 | 2,6 s | 0,08 | sim |
| turbo | 0,2301 | 0,0000 | 28,1 s | 1,32 | sim |

Decodificação determinística; dispersão de tempo ≈ 3–5%.

## 4. Diagnóstico

1. Em **fala espontânea** (mais próxima de reuniões), o Parakeet pt-BR INT8 supera o turbo em WER (10,2% vs 16,3%) e é ~10× mais rápido, com menos RAM.
2. Em **fala preparada**, a diferença reduz (11,8% vs 13,5%), mas a ordem se mantém.
3. O turbo continua sendo o único caminho com **timestamps utilizáveis** (cobertura ~0,89).
4. Qwen3-ASR 0.6B é o mais fraco e mais caro em RAM (6 GB) neste cenário.
5. large-v3 não se justifica: pior WER e ~2× mais lento que o turbo.

## 5. Recomendação (direção, não integração)

| Categoria | Motor | Condição |
|---|---|---|
| **Qualidade em fala espontânea** | Parakeet pt-BR INT8 | Requer solução de timestamps (ex.: chunking por VAD) antes de substituir o caminho atual |
| **Melhor equilíbrio com timestamps** | Whisper large-v3-turbo | Manter como motor padrão atual |
| **Alta velocidade** | Parakeet pt-BR INT8 | RTF 0,059; bom para pré-transcrição de gravações longas |
| **Não recomendado** | Qwen3-ASR 0.6B, Whisper large-v3 | Sem vantagem demonstrada neste cenário |

**Proposta:** arquitetura de dois modos atrás de feature flag — Parakeet para pré-passagem rápida e turbo para versão final com timestamps — validada antes com gravações autorizadas de reuniões reais. Não executar integração sem nova autorização.

## 6. Limitações e impedimentos
- Sem corpus público de **reuniões** com sobreposição/diarização; NURC é espontâneo, mas entrevistas/talks.
- Amostra pequena (24 clipes) e curta (133 s) → variância; resultados comparativos.
- Licenças NC/ND impedem redistribuição e derivados do áudio; uso restrito a avaliação interna.
- Sem números/datas/siglas no corpus → termos críticos institucionais não avaliados.
- Parakeet/Qwen sem timestamps na integração avaliada.
- Estabilidade medida em subconjunto (8 clipes), 3 repetições.

## 7. Governança
- Branch: `exp/multi-asr-cpu-validation-004` (a partir de `exp/multi-asr-cpu-poc`).
- PR experimental alvo: base `exp/multi-asr-cpu-poc`; **produção não tocada** (sem merge/deploy).
- Testes: 11/11 na PoC (métricas, S/D/I, números, raros, contrato, manifesto) + 41/41 operacionais inalterados.
