# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

## [Unreleased]

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
