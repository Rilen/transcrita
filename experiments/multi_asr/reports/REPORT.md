# TRANSCRITA-003 — PoC multimotor ASR CPU-only (relatório)

**Data:** 2026-11-17 · **Host:** `srv-lnx-gpt-oss-120b` (10.0.0.88) · **Baseline:** `95bdf68`
**Estado:** `TRANSCRITA_003_POC_EVALUATED_VERIFIED` (escopo e limitações abaixo)

---

## 1. Inventário do ambiente

| Item | Valor |
|---|---|
| SO | Ubuntu 24.04.4 LTS |
| CPU | 2× Intel Xeon Gold 5317 (20 cores/socket, 40 threads lógicas) |
| RAM | 125 GiB (≈117 GiB livres durante a PoC) |
| Disco | 295 GB (68 GB livres após a PoC; uso da PoC: 9,4 GB) |
| GPU | ausente (CPU-only) |
| Runtime operacional | faster-whisper 1.2.1 + CTranslate2 4.9.0 (em `transcrita.service`) |
| PoC | `/opt/transcrita-003` (worktree isolada), venvs `.venv-poc` e `.venv-qwen` |
| Dados da PoC | `/var/lib/transcrita-poc` (corpus, pesos, resultados) — fora do Git |

Serviço operacional permaneceu ativo e saudável durante toda a execução; benchmarks limitados a 12 threads
(`taskset 0-11`, `nice 15`), execução sequencial, sem carga concorrente.

## 2. Elegibilidade dos motores

Ver [`ELIGIBILITY.md`](ELIGIBILITY.md). Resumo: 6 candidatos **ELEGÍVEIS** avaliados; Parakeet oficial (NeMo),
Qwen3-ASR 1.7B e fine-tunes TAGARELA adicionais **CONDICIONAIS** (não executados nesta rodada por custo de runtime);
Voxtral **INELEGÍVEL** nesta fase (sem runtime CPU reproduzível identificado).

## 3. Arquitetura implementada

Interface única `ASRAdapter` (`load`/`transcribe`/`unload`/`metadata`) + resultado normalizado
(`TranscriptionResult`) com campos opcionais explicitados em `capabilities` (segmentos, word timestamps, VAD, diarização).
Separação entre pré-processamento (WAV 16 kHz via `soundfile`/ffmpeg), execução do modelo, normalização textual,
métricas (WER/CER via `jiwer`), agregação e relatórios. Nenhum acoplamento ao frontend nem alteração do pacote `transcrita`.

Correções de compatibilidade durante o ciclo (cada uma com teste/validação):
1. Decodificação PyAV incompatível → leitura WAV via `soundfile` + array `float32` (com reamostragem linear).
2. `onnx-asr` 0.12 exige `path` + `quantization` para checkpoints INT8 → adaptador ajustado.
3. Ambiente Qwen separado sem `jiwer` → dependência instalada no venv dedicado.

## 4. Corpus e metodologia

- **Fonte:** MLS Portuguese (`facebook/multilingual_librispeech`, split `test`), **CC-BY-4.0**, áudio LibriVox
  com transcrição humana. Nenhum dado municipal utilizado.
- **Composição (12 itens, 272,8 s):** 6 `clean`, 2 `noisy`, 2 `distant`, 1 `multi` (3 falantes concatenados),
  1 `long` (4 clipes, ~93 s).
- **Degradações sintéticas:** ruído branco mixado (amplitude 0,05); distância = lowpass 3,5 kHz + eco + atenuação 0,55;
  multi/long = concatenação com 0,5 s de silêncio (sem sobreposição real).
- **Métrica:** WER/CER com normalização (minúsculas, sem pontuação, acentos preservados); WER agregado ponderado
  por palavras de referência. RTF = tempo de processamento / duração do áudio. RAM = pico RSS do processo.
- **Configuração comum:** CPU int8 (CT2) / INT8 (ONNX) / float32 (Qwen), 12 threads, sem VAD, beam 5 (Whisper),
  warm-up em 1 clipe, 1 execução por clipe, timeout 300 s/clipe.

## 5. Resultados (medições reais)

| Modelo | WER | CER | RTF | Load (s) | RAM pico (MB) | OK |
|---|---:|---:|---:|---:|---:|---:|
| whisper-large-v3-turbo | **0,0521** | **0,0279** | 0,255 | 30,6 | 2 648 | 12/12 |
| whisper-medium | 0,0741 | 0,0312 | 0,568 | 33,5 | 2 951 | 12/12 |
| whisper-large-v3 | 0,0757 | 0,0315 | 0,751 | 54,9 | 5 831 | 12/12 |
| parakeet-ptbr-tagarela-int8 | 0,1041 | 0,0441 | **0,041** | 2,6 | 2 438 | 12/12 |
| qwen3-asr-0.6b | 0,1341 | 0,0526 | 0,321 | 5,5 | 6 015 | 12/12 |
| whisper-small | 0,1404 | 0,0583 | 0,251 | 1,3 | 978 | 12/12 |

`Load` inclui download na primeira execução dos modelos Whisper (exceto small, já em cache). Carga a quente
(sem inferência): medium 2,4 s · turbo 2,6 s · large-v3 5,9 s · parakeet 1,6 s (small 14,2 s por incluir
imports iniciais do processo — outlier de medição).

### WER por cenário

| Modelo | clean | noisy | distant | multi | long |
|---|---:|---:|---:|---:|---:|
| whisper-large-v3-turbo | **0,0364** | 0,1129 | **0,0448** | 0,0326 | **0,0663** |
| whisper-medium | 0,0810 | 0,1129 | **0,0448** | 0,0326 | 0,0843 |
| whisper-large-v3 | 0,0526 | **0,0806** | 0,1343 | **0,0217** | 0,1145 |
| parakeet-ptbr-tagarela-int8 | 0,0850 | 0,1290 | 0,1343 | 0,0761 | 0,1265 |
| qwen3-asr-0.6b | 0,1215 | 0,2097 | 0,0746 | 0,0870 | 0,1747 |
| whisper-small | 0,1700 | 0,1935 | 0,0896 | 0,1087 | 0,1145 |

### Alucinações (proxy)

Razão palavras hipótese/referência: **nenhum** modelo apresentou clipe com razão > 1,5.
Máximos: turbo 1,04 · parakeet 1,04 · qwen 1,06 · medium/large/small ≤ 1,10. Sem inserções massivas neste corpus.

### Termos críticos

O corpus MLS é literário (leitura), **sem** nomes institucionais, siglas, datas ou números representativos.
A avaliação de termos críticos de reuniões municipais **não foi realizada** e permanece pendente com áudio autorizado.

## 6. Loops de otimização

| Ciclo | Problema | Ação | Resultado |
|---|---|---|---|
| 1 | `av`/PyAV incompatível na decodificação | Troca para `soundfile` + array float32 | 12/12 OK |
| 2 | Loader ONNX não encontrava `encoder-model.onnx` | `path` do snapshot + `quantization=int8` | 12/12 OK |
| 3 | Qwen sem `jiwer` no venv isolado | Instalação no `.venv-qwen` | 12/12 OK |

Nenhum ciclo adicional foi necessário; sem regressões de qualidade entre execuções.

## 7. Testes

- PoC: 7/7 (`experiments/multi_asr/tests`) — métricas, contrato de adaptador, agregação, forma do manifesto.
- Operacional: 41/41 (`tests/`) inalterado — pacote `transcrita` não foi modificado nesta missão.

## 8. Impacto operacional

- Nenhum serviço reiniciado; `transcrita.service` permaneceu `active` e `{"status":"ok"}`.
- Gateway, FROC Portal e Consulta360 preservados (200 / 200 / container `Up 11 days`).
- Benchmarks sequenciais, 12 threads, `nice 15`; pico de carga observado ~8,4 (decaindo), RAM do host folgada (117 GiB livres).

## 9. Limitações

1. Corpus pequeno (12 itens, 4,5 min) e de **fala lida** (audiolivro), não reuniões espontâneas.
2. Degradações são sintéticas; `multi` não contém sobreposição de fala real.
3. Sem avaliação de diarização e de termos institucionais.
4. `parakeet` (via onnx-asr) não fornece segmentos/timestamps nesta integração.
5. WER com n=12 tem variância alta; resultados são **comparativos**, não absolutos de campo.
6. Qwen executado em float32 (CPU), sem otimização de geração.

## 10. Recomendação

| Categoria | Modelo | Racional |
|---|---|---|
| **Qualidade máxima** | `whisper-large-v3-turbo` | Menor WER/CER no corpus; melhor em clean/distant/long; RAM 2,6 GB |
| **Melhor equilíbrio** | `whisper-large-v3-turbo` | Qualidade superior com RTF 0,26 e carga a quente ~2,6 s |
| **Execução rápida** | `parakeet-ptbr-tagarela-int8` | RTF 0,041 (~24× tempo real), 2,4 GB, carga 1,6 s; WER 10,4% |
| **Não recomendado (neste cenário)** | `whisper-large-v3`, `whisper-medium`, `qwen3-asr-0.6b` | Dominados por turbo (pior qualidade e/ou maior custo), sem vantagem demonstrada |
| **Uso restrito** | `whisper-small` | Apenas se memória for crítico (<1 GB), com perda clara de qualidade |

**Sugestão de arquitetura futura (não executada):** manter `faster-whisper large-v3-turbo int8` como motor padrão
e oferecer `parakeet pt-BR INT8` como modo "rápido" para gravações longas, adicionando segmentação por VAD
para compensar a ausência de timestamps. Integração deve ocorrer atrás de feature flag, com o contrato `ASRAdapter`
já validado nesta PoC, sem alterar o frontend ou o fluxo SSE existente.

## 11. Reprodução

Ver [`../README.md`](../README.md). Resultados sanitizados: [`RESULTS.md`](RESULTS.md) e
[`results_summary.json`](results_summary.json).


---

## Adendo 004 — correções metodológicas
- Revisões e licenças de pesos/runtime pinadas em `reports/METADATA.json`.
- Esclarecido que `load_time_s` inclui download na primeira execução (a quente: `warm_load.py`).
- Corpus 003 usou MLS (CC-BY-4.0), permitindo degradações sintéticas; o corpus 004 usa NURC-SP (CC-BY-NC-ND), **sem qualquer transformação de áudio**.
- Validação em fala espontânea/preparada: ver `reports/validation_004/REPORT_004.md`.
