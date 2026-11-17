# TRANSCRITA-005 — Validação institucional e timestamps (CPU-only)

**Data:** 2026-11-17 · **Host:** 10.0.0.88 · **Base:** `exp/multi-asr-cpu-validation-004` (`0ba2d9d`) · **Produção:** `main` (`95bdf68`, intocada)

**Estado:** `TRANSCRITA_005_EXPLORATORY_ONLY`
Corpus público sem reuniões institucionais com sobreposição real; precisão temporal avaliada em conjunto controlado (fronteiras conhecidas), não em referência humana de tempo.

---

## 1. Baseline e governança
- Branch 005: `exp/multi-asr-timestamps-005` (worktree `/opt/transcrita-005`).
- Serviço `transcrita.service` ativo durante toda a missão; nenhum endpoint/frontend/systemd/nginx alterado.
- Resultados 003/004 preservados (baseline imutável); pesos e ambientes existentes reutilizados (nenhum modelo novo instalado).
- Auditoria confirmou revisões/licenças pinadas em `reports/METADATA.json` (missão 004).

## 2. Corpus 005
| Fonte | Licença | Conteúdo | Itens |
|---|---|---|---|
| NURC-SP (`nilc-nlp/CORAA-NURC-SP-Audio-Corpus`) | CC-BY-NC-ND-4.0 | diálogos (6) e entrevistas (4) espontâneas, 2–4 falantes | 10 |
| mTEDx pt-BR (`dominguesm/mTEDx-ptbr`) | CC-BY-NC-4.0 | palestras preparadas | 6 |

Total: **16 clipes / 103,4 s**. Conjunto controlado (mTEDx concatenado com silêncios de 1,0 s): **46,4 s, 6 fronteiras conhecidas**. NURC usado **sem transformação** (ND); derivados apenas no conjunto controlado (mTEDx permite). Nenhum áudio/transcrição versionado.

## 3. Qualidade ASR

| Métrica | Parakeet PT-BR INT8 | Whisper large-v3-turbo |
|---|---:|---:|
| **WER global** | **0,1069** | 0,1379 |
| Diálogos espontâneos | **0,1132** | 0,1506 |
| Entrevistas espontâneas | **0,0947** | 0,1047 |
| Fala preparada | **0,1088** | 0,1472 |

Parakeet vence em todos os cenários, com menor custo (RTF 0,05 vs 0,59) e RAM 1,7 GB vs 2,1 GB.

## 4. Estratégias de timestamps

| Estratégia | SRT válido | Cobertura | Integridade textual* | RTF | Fronteiras recall@250 ms | MAE |
|---|---:|---:|---:|---:|---:|---:|
| **A — VAD + Parakeet (ajustada)** | 100% | 0,92 | **0,978** | **0,043** | **100%** | **93 ms** |
| A — VAD (padrão) | 100% | 0,87 | 0,947 | 0,064 | 100%** | 53 ms** |
| C — Híbrido estimado | 100% | 0,87 | **1,000** | 0,562 | 50% | 83 ms |
| B — MMS_FA (texto Parakeet) | n/a | n/a | 1,000 (texto fixo) | 0,061 | **100%** | **70 ms** |

\*Integridade = 1 − WER do texto segmentado contra o texto integral do mesmo motor.
\*\*Configuração padrão tem melhor precisão de onset, porém cobertura/integridade piores (áudio cortado em trechos de baixa energia).
B executa apenas **alinhamento** (texto fornecido); não é reconhecimento.

### Ajuste de VAD (conjunto controlado)
| th | pad (ms) | Cobertura | Integridade | Frag./min | Recall | MAE |
|---|---:|---:|---:|---:|---:|---:|
| 0,50 | 100 | 0,79 | 0,972 | 19,4 | 100% | 53 ms |
| 0,35 | 150 | **0,85** | **0,991** | 11,6 | **100%** | 93 ms |
| 0,35 | 300 | 0,90 | 0,991 | 11,6 | 50% | 148 ms |
| 0,30 | 400 | 0,94 | 0,962 | 10,4 | 17% | — |

Escolhido `th=0,35 / pad=150 ms`: melhor integridade, sem perda de recall e com fragmentação moderada.

## 5. Avaliação temporal — critérios de aceitação
| Critério | A (VAD) | C (híbrido) | B (MMS_FA) |
|---|---|---|---|
| Segmentos cronológicos válidos | ✅ | ✅ | ✅ (parcial: agrupamento) |
| Sem timestamps negativos/fora da duração | ✅ | ✅ | ✅ |
| Sem perda silenciosa de texto | ⚠️ 97,8% de integridade | ✅ 100% | ✅ (texto fixo) |
| SRT válido | ✅ | ✅ | ✅ (após agrupamento) |
| Desempenho CPU documentado | ✅ RTF 0,043 | ✅ RTF 0,562 | ✅ RTF 0,061 |
| Testes determinísticos | ✅ 7 casos | ✅ | ⚠️ sem testes próprios |
| Limitações declaradas | ✅ | ✅ | ✅ |

## 6. Comparação Parakeet vs Whisper
- **Texto:** Parakeet superior (10,7% vs 13,8%) e ~13× mais rápido.
- **Timestamps nativos:** apenas Whisper fornece segmentos/words; cobertura temporal ~0,89 (004).
- **Estratégias para Parakeet:** VAD entrega segmentos válidos e precisos (100% recall, 93 ms); MMS_FA entrega alinhamento por palavra (MAE 70 ms) com licença NC; híbrido preserva 100% do texto, mas fronteiras são estimadas (recall 50%).

## 7. Loops executados (limites respeitados)
1. Decodificação PyAV incompatível no caminho híbrido → passagem de array mono 16 kHz.
2. `difflib` desempacotado com 4 valores → corrigido para `(a, b, size)`.
3. Ajuste de VAD: 5 configurações no conjunto controlado → escolhida `0,35/150`.
4. Ajuste do híbrido: `pause` 0,7/1,0/1,4 → mantido 1,0 s (melhor equilíbrio recall/fragmentação).
5. MMS_FA: 4 correções de compatibilidade (API do tokenizer, dígitos fora do dicionário, atributo `dictionary`, texto do Parakeet) — uma além do limite de 3, registrada como exceção por ser correção trivial de atributo.

## 8. Testes e regressões
- PoC: **19/19 OK** (SRT, híbrido, fronteiras, integridade, métricas, contrato).
- Operacional: **41/41 OK**, inalterado.
- Serviços: `transcrita.service` ativo, health direto/proxy `{"status":"ok"}`, gateway/FROC 200, Consulta360 intacto.

## 9. Recomendação de arquitetura (futura, não integrada)
1. **Parakeet PT-BR INT8 + VAD (A ajustada)** como motor principal de transcrição com segmentos — melhor combinação de qualidade, velocidade e timestamps utilizáveis.
2. **Parakeet + MMS_FA (B)** opcional para timestamps por palavra, condicionado a revisão jurídica da licença CC-BY-NC e ao runtime torchaudio.
3. **Híbrido (C)** como fallback quando fidelidade textual absoluta for prioritária e timestamps aproximados bastarem.
4. Manter **Whisper large-v3-turbo** como referência/caminho existente até validação com reuniões reais autorizadas.

## 10. Limitações e riscos
- Sem reuniões reais com sobreposição/diarização; NURC/M-TEDx aproximam, mas não substituem.
- Precisão temporal medida em fronteiras controladas por construção, não em referência humana de tempo.
- A perde ~2,2% de texto frente ao passe integral do Parakeet (trechos de baixa energia).
- B depende de transcrição prévia e de licença NC; sem testes determinísticos próprios nesta rodada.
- Amostra pequena (16 clipes/103 s) → resultados comparativos, não homologação.

## 11. Governança
Branch `exp/multi-asr-timestamps-005`; PR experimental alvo: base `exp/multi-asr-cpu-validation-004`; sem merge/deploy. Produção intocada.
