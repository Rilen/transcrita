# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

## [Unreleased]

### Preparação Parakeet PT-BR (missão 019, branch `fix/transcrita-019-parakeet-readiness`)

- **Correção:** tokens especiais do decoder ONNX (`<unk>`, `<pad>` e padrão
  NeMo `<|...|>`) não vazam mais para o texto final; sequências legítimas
  entre `<` e `>` são preservadas. Aplicado em `ParakeetEngine.transcribe_file`,
  garantindo consistência entre texto, segmentos, JSON, SSE e SRT.
- **Correção:** rota `/` passa a enviar `Cache-Control: no-cache`
  (must-revalidate), eliminando HTML obsoleto servido de cache heurístico do
  navegador sem afetar conteúdo ou cache de modelos/áudio.
- **Validação isolada (TRANSCRITA-018/019):** modelo INT8 carrega offline em
  ~3 s, RSS ~1,5–2,3 GB, RTF ~0,04 (~25× tempo real); SSE, SRT, cancelamento,
  alternância Whisper↔Parakeet e rejeições explícitas verificados em instância
  de teste dedicada.
- **Documentado:** incompatibilidade `av 19.0.2` × `faster-whisper 1.2.1`
  afeta apenas decodificação por caminho de arquivo (não usada em produção,
  que decodifica via ffmpeg); recomendado pinar `av<19` se esse caminho for
  adotado.

### Publicado — hardening de upload e SSE (missão 013, PR #9)

- **Correção (H1):** o middleware de limite de upload agora normaliza o
  `root_path` efetivo antes de comparar com os endpoints de upload; o limite de
  512 MB (Content-Length e corpos chunked) passa a valer também sob
  `/transcrita/...`, sem afetar outras rotas.
- **Correção (H2):** o endpoint SSE ganhou watcher de `http.disconnect`,
  tratamento de `CancelledError` (ASGI 2.3) e logging de eventos terminais
  deduplicados (`sse_iniciado`, `sse_concluido`, `sse_cancelado` com motivo,
  `sse_falha`, `sse_worker_cancelado`), sem nome de arquivo, texto ou caminhos.
- Testes: `tests/test_hardening_013.py` (10 casos, ASGI 2.3/2.4 e `root_path`).
- Documentação: `docs/HARDENING_UPLOAD_SSE.md`.
- Deploy: merge `62bb3b6` em `main`; `transcrita.service` reiniciado em
  2026-11-18 13:27 UTC; rollback para `0369558` via `git checkout` + restart.

### Pendências conhecidas (backlog TRANSCRITA-016+)

- Logs `INFO` de `transcrita.web`/`transcrita.core` não chegam ao journald
  (ausência de `logging.basicConfig`/`dictConfig`; uvicorn só configure seus
  próprios loggers) — telemetria terminal SSE implementada mas invisível em
  produção.
- Endpoint `/api/health` minimalista (sem versão/SHA).
- UI não expõe exportação SRT (API já retorna `srt`).
- Sem autenticação nos endpoints (ver TRANSCRITA-014, risco P1).
