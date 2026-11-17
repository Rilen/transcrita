# TRANSCRITA-006 — Integridade textual (Parakeet + VAD)

**Data:** 2026-11-17 · **Host:** 10.0.0.88 · **Base:** `exp/multi-asr-timestamps-005` (`3da28c7`) · **Produção:** `main` (`95bdf68`, intocada)

**Estado:** `TRANSCRITA_006_VALIDATED_VERIFIED`
Critérios experimentais comprovados no corpus público (16 clipes, referência humana). Homologação institucional permanece pendente (sem reuniões reais autorizadas).

---

## 1. Diagnóstico da perda (A005, pad=150 ms)

| Métrica | Valor |
|---|---|
| Clipes / tokens de referência | 16 / 265 |
| WER passe integral | 0,1069 |
| WER A005 (segmentado) | 0,1227 |
| Integridade A005 (vs integral) | 0,978 |
| **Palavras de referência perdidas** | **3** |
| Duplicações (bigramas) integral / A005 | 3 / 3 |
| Fala não coberta (proxy) | 0,69% |

Classificação: a diferença concentra-se em **corte de palavras nas fronteiras** (padding insuficiente + ausência de fusão de pausas curtas), **não** em remoção de regiões de fala (proxy de fala não coberta < 1%) nem em duplicações (inalteradas).

## 2. Estratégias avaliadas

| Estratégia | Descrição | Resultado |
|---|---|---|
| **A005 (baseline)** | th 0,35 · pad 150 ms · sem merge | perda de 3 tokens; integridade 0,978 |
| **A2 (A3)** | th 0,30 · pad 250 ms · min_silence 550 ms · min_speech 150 ms · merge 0,35 s | **integridade 1,0000; 0 perda; WER = integral** |
| A2b (equilíbrio) | pad 200 ms | integridade 0,997 (máx 4,8% em 1 clipe); WER 0,1039; recall@250 100% |
| **C (reconciliação)** | texto do passe integral + tempos estimados (Whisper); nenhuma palavra inventada | texto **idêntico** ao integral em 16/16 e no controlado |
| B (MMS_FA) | alinhamento por palavra (005) | não necessário para corrigir perda; mantido como opção de precisão |

## 3. Resultados comparativos

| Estratégia | WER | Integridade | Perda (tokens) | SRT válido | RTF | RAM pico* |
|---|---:|---:|---:|---:|---:|---:|
| Integral (referência) | 0,1069 | — | — | — | 0,046 | 3 658 MB |
| A005 | 0,1227 | 0,978 | 3/265 | 100% | 0,053 | 3 658 MB |
| **A2/A3** | **0,1069** | **1,0000** | **0/265** | **100%** | **0,051** | 3 658 MB |
| A2b (pad 200) | 0,1039 | 0,997 | 1/265 (1 clipe) | 100% | ~0,05 | 3 658 MB |
| C (reconciliado) | 0,1069 | 1,0000 | 0/265 | 100% | 0,554 | 3 830 MB |

\*RSS do processo com Parakeet + Whisper carregados; Parakeet isolado ≈1,7 GB (missão 004).

## 4. Integridade temporal (conjunto controlado, 6 fronteiras)

| Estratégia | Recall@250 ms | Recall@500 ms | MAE | Segmentos |
|---|---:|---:|---:|---:|
| A005 | 100% | 100% | 93 ms | 9 |
| A2/A3 (pad 250) | 67% | **100%** | 182 ms | 8 (ref. 6) |
| C (reconciliado) | 67% | 100% | 182 ms | 8 |

O padding de 250 ms desloca o início ~para antes do onset (proteção contra corte). Em tolerância de 500 ms o recall é 100% — o viés é sistemático e **a favor** da integridade (nunca corta o início da fala).

## 5. Loops executados (5 ciclos, limites respeitados)
1. **Diagnóstico**: A005 perde 3 tokens (fronteiras), integridade 0,978.
2. **VAD**: adicionada fusão de pausas curtas e varredura de `pad` (150/200/250) + limiar 0,30/0,35.
3. **Escolha**: `pad=250` elimina a perda (integridade 1,000); `pad=200` melhora onset com 0,3% residual.
4. **Reconciliação**: texto integral + tempos estimados; verificado texto idêntico ao integral (controlado e 16/16).
5. **Consolidação**: SRT válido, testes determinísticos, métricas de RTF/RAM.

## 6. Testes
- **32/32** na PoC: merge de segmentos (gap/clamp/inválido), reconciliação (preservação/ordem/sem invenção), SRT (clamp, sobreposição, vazio), fronteiras, áudio curto e longo, falha de alinhamento (`ValueError`) e contrato de métricas.
- **41/41** operacionais, inalterados; nenhum arquivo do pacote `transcrita` tocado.

## 7. Limitações
- Corpus público (16 clipes/103 s) sem reuniões com sobreposição; resultados comparativos, não homologação.
- Integridade medida contra o passe integral **e** referência humana; “100%” refere-se a este corpus/metodologia.
- Viés de onset ≈ padding (250 ms) — adequado a legendas, mas não é alinhamento por palavra.
- Reconciliação garante texto, mas herda precisão temporal estimada e custo (RTF 0,554).
- Sem avaliação de números/siglas (corpus sem tokens numéricos).

## 8. Recomendação técnica
1. **Adotar A2/A3 (`th 0,30 · pad 250 ms · merge 0,35 s`)** como configuração experimental padrão do Parakeet com VAD: elimina a perda textual observada, mantém RTF ~0,05 e SRT válido, sem dependências novas.
2. Expor o viés de início (~250 ms antes) na documentação de integração; se a precisão de onset for prioritária, usar `pad 200 ms` (integridade 99,7%, onset 100% em 250 ms).
3. Manter **reconciliação** como caminho de segurança para áudio difícil (baixa energia/VAD agressivo), por garantir texto idêntico ao integral, ao custo de RTF ~0,55 (uma passada extra do Whisper).
4. Não integrar ao serviço operacional nesta missão; próximos passos exigem reuniões autorizadas e validação temporal humana.

## 9. Governança
Branch `exp/multi-asr-integrity-006`; PR alvo: base `exp/multi-asr-timestamps-005`; sem merge/deploy. Produção intocada.
