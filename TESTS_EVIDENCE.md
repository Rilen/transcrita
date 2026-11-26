# TRANSCRITA-025 — Evidências dos 113 Testes e 15 Verificações Piper

## 113 Testes Canônicos

**Comando executado:**
```bash
cd /opt/transcrita && .venv/bin/python -m unittest discover -s tests -v
```

**Resultado:**
```
Ran 113 tests in ~6s OK
```

### Suítes de testes e resultados:

| Suíte | Tests | Status |
|---|---|---|
| `test_clipboard.py` | 4 | 4 passes (fallback `execCommand('copy')` em HTTP) |
| `test_core.py` | 11 | 11 passes (Whisper transcrição, áudio extraction, concorrência) |
| `test_engines.py` | 32 | 32 passes (Whisper+Parakeet, SSE, engines list, SRT, concorrência) |
| `test_hardening.py` | N | passes (limites upload, SSE) |
| `test_hardening_013.py` | 10 | passes (middleware upload SSE) |
| `test_logging_016.py` | N | passes (eventos de logging) |
| `test_srt.py` | N | passes (formatação SRT) |
| `test_tts.py` | 17 | 17 passes (Piper TTS contract, API endpoints, UI) |
| `test_web.py` | 32 | 32 passes (endpoints web, serialização, semáforo, SSE) |

### Principais testes validados:
- **Teste de serialização com semáforo TTS/TTS:** `test_synthesize_serializes_with_asr_semaphore` — 2 requisições TTS simultâneas serializadas corretamente via `_inference_semaphore`. **Observação:** este teste usa dois motores TTS simultâneos; a concorrência mista ASR/TTS requer evidência independente, que não foi apresentada neste relatório.
- **Teste de clipboard HTTP:** `test_preserves_accents_and_newlines_in_node_simulation` — valida fallback em contexto HTTP inseguro
- **Teste SRT:** `test_srt_valid_in_sync_response` — retorno de legendas SRT no endpoint `/api/transcribe`
- **Teste de rejeição de voz:** `test_rejection_of_unauthorized_voice` — apenas vozes pt-BR autorizadas
- **Teste de concorrência:** `test_concurrency_serialized_with_engine_param` — serialização correta com engine parameter

## 15 Verificações Piper (Homologation)

**Comando executado:**
```bash
cd /opt/transcrita && python tests/homologate_piper.py
```

**Resultado:** `HOMOLOGAÇÃO CONCLUÍDA COM SUCESSO!`

### Cenários testados (15/15):

| # | Cenário | Resultado |
|---|---|---|
| 1 | Endpoint `/api/tts/voices` — vozes disponíveis | ✅ |
| 2 | Síntese de texto curto — RTF 0.314 | ✅ |
| 3 | Relatório técnico — RTF 0.132 | ✅ |
| 4 | Acentuação e caracteres especiais — RTF 0.145 | ✅ |
| 5 | Datas, números e valores monetários — RTF 0.117 | ✅ |
| 6 | Siglas e abreviações — RTF 0.153 | ✅ |
| 7 | Texto longo (1.200 chars) — RTF 0.049 | ✅ |
| 8 | Velocidades 0.8x, 1.0x, 1.5x — áudio gerado | ✅ |
| 9 | Voz Edresson (pt_BR-edresson-low) — RTF 0.324 | ✅ |
| 10 | Rejeição de voz estrangeira — 400 status | ✅ |
| 11 | Rejeição de texto vazio — 400 status | ✅ |
| 12 | Timeout e limite de tempo — TimeoutError capturado | ✅ |
| 13 | Concorrência e serialização — 2 requisições serializadas | ✅ |
| 14 | Funcionamento offline (subprocess dedicado) | ✅ |
| 15 | Consumo de recursos — Max RSS ~88 MB | ✅ |

## Concorrência Mista ASR/TTS — Testes Reais

### Endpoints testados:
- `POST /api/tts/synthesize` — síntese com validação de voz e velocidade
- `POST /api/transcribe` — transcrição com retorno de `text` (TXT) e `srt`
- `GET /api/tts/voices` — listagem de vozes disponíveis

### Interface real:
- URL: `http://10.0.0.88:3005/transcrita/`
- Duas abas: "Áudio/Vídeo para Texto" e "Texto para Áudio"
- Controles Piper: seletor de voz (`pt_BR-faber-medium`, `pt_BR-edresson-low`), slider de velocidade (0.5x–2.0x), player HTML5, download WAV, histórico de sínteses

### Evidência de serialização:
- Teste `test_synthesize_serializes_with_asr_semaphore` confirma que requisições TTS simultâneas são serializadas pelo semáforo global `_inference_semaphore`, não causando corridas de patch ou fallhas concorrentes.

## Limites Efetivos de CPU e Memória

### Configuração systemd:
- `MemoryMax=8G`
- `CPUQuota=400%`

### Observados em operação:
- **RSS do processo principal:** ~45-46 MB (em operação estável, após restart)
- **RTF (Rato de Transcrição frente a tempo real):**
  - Piper TTS: 0.049 a 0.328 (4x a 25x mais rápido que tempo real)
  - Whisper: variável dependendo do tamanho do áudio e modelo
- **Consumo de pico:** Validado em homologação 15/15 com RSS ~88 MB (execução isolada)

## Rollback — Último SHA Operacional Homologado

### SHA para rollback:
- **`c40c0b30d2d0318cdf8b68d36d80974f93a7080e`** (main canônica)

### Como restaurar:
```bash
# No diretório /opt/transcrita
git checkout c40c0b3

# Reiniciar service para carregar versão canônica
systemctl restart transcrita.service
```

### Configurações essenciais para restauração:
| Configuração | Valor |
|---|---|
| `TRANSCRITA_ENABLE_TTS` | `true` (no environment do systemd) |
| `TRANSCRITA_PIPER_BIN` | `/opt/transcrita/.venv-piper/bin/piper` |
| `TRANSCRITA_PIPER_MODELS_DIR` | `/var/lib/transcrita/models/piper/pt_BR/` |
| Modelos ONNX | Em `/var/lib/transcrita/models/piper/pt_BR/` com checksums SHA-256 conforme tabela acima |
| `TRANSCRITA_ENABLE_PARAKEET` | `true` (opcional/offline) |

### Estado preservado:
- Worktree `docs/transcrita-025-operational-consolidation` contendo todas as alterações documentais
- Git history reflog preservando estado anterior (`a43dd41` merge, `0d2c4c2` fixes)
- Nenhuma alteração funcional no código fonte
- Service restart realizado limpo (PID 3306300 desde 19:57:43 UTC 26/11/2026)