# Hardening de upload e ciclo SSE (TRANSCRITA-013)

## H1 — Limite de upload sob `root_path`

### Causa
O middleware comparava `scope["path"]` diretamente com `/api/transcribe*`. Com o serviço
publicado em `/transcrita`, o caminho chega como `/transcrita/api/transcribe`; a comparação
falhava e o limite de 512 MB não era aplicado no backend (o nginx ainda bloqueava no caminho
público, mas o backend ficava dependente do proxy).

### Correção
`UploadSizeLimitMiddleware` normaliza o caminho removendo **apenas** o prefixo efetivo:
`scope["root_path"]` e/ou o `root_path` configurado na app (via `add_middleware(..., root_path=...)`).
Não há remoção de prefixos arbitrários; a rota normalizada é comparada com a lista exata de
endpoints de upload.

- `Content-Length` acima do limite → 413 imediato (sem ler o corpo).
- Sem `Content-Length` (chunked) → contagem no `receive`; 413 ao exceder, sem buffer integral.
- Rotas não relacionadas passam intactas.
- Uploads interrompidos não derrubam o serviço; temporários continuam sob `TemporaryDirectory`.

## H2 — Observabilidade do cancelamento SSE

### Causa
Com ASGI `spec_version 2.3` (uvicorn/httptools), o Starlette cancela a tarefa de streaming ao
detectar desconexão (`listen_for_disconnect`) — o cancelamento **funciona**, mas o código só
registrava quando `Request.is_disconnected()` retornava `True`, o que raramente ocorre porque o
`receive` já foi consumido pelo listener. Resultado: sem log de desconexão, embora o worker fosse
interrompido pelo `cancel_event`.

### Correção
- **Watcher dedicado** de desconexão (`_watch_disconnect`) concorre pelo `receive` e, ao receber
  `http.disconnect`, sinaliza `cancel_event` e registra o evento (cobrindo ASGI ≥ 2.4 e casos em
  que o watcher vence a corrida).
- Caminho de `CancelledError` (ASGI 2.3) registra `sse_cancelado` com `motivo="tarefa_cancelada"`.
- `Request.is_disconnected()` permanece como verificação best-effort.
- Eventos estruturados, **um terminal por requisição** (deduplicado por estado):
  `sse_iniciado`, `sse_concluido`, `sse_cancelado` (`cliente_desconectado` | `tarefa_cancelada` |
  `worker_cancelado`), `sse_falha`, `sse_worker_cancelado`.
- Logs sem nome de arquivo, texto transcrito ou caminhos; apenas motor, modelo, duração e nº de segmentos.
- Sem alteração da ordem dos eventos SSE nem do contrato da API.

### Limitação documentada
Em transporte/proxy que não propague `http.disconnect`, o servidor pode concluir normalmente sem
registrar desconexão; nesse caso não se declara cancelamento (evita falso positivo). A cobertura
de testes exercita ASGI 2.3 e 2.4 com desconexão real no nível ASGI.

## Testes
`tests/test_hardening_013.py` cobre: normalização de rota (com/sem `root_path`, configuração),
413 por `Content-Length` e chunked, rota não relacionada, integração ASGI com `root_path`,
conclusão normal (sem falso cancelamento), desconexão em 2.3 e 2.4, liberação do semáforo,
worker encerrado e ausência de nome/texto nos logs.
Os dois testes de serialização existentes foram endurecidos contra flutuação de relógio/carga
(tolerância de 20 ms e remoção de teto rígido), preservando a semântica.
