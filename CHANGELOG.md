# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

## [Unreleased]

### Recuperação operacional — TRANSCRITA-026

- Reconstrução dos runtimes ASR e Piper, restauração do bind dedicado e recuperação do acesso institucional reportadas pelo agente; acesso confirmado pelo usuário.
- [Registro do incidente](IP_DOCUMENTATION.md), [recuperação](ROLLBACK_DOCUMENTATION.md) e [limites das evidências](TESTS_EVIDENCE.md). Nenhuma alteração funcional nesta consolidação documental.

### Integração do Piper TTS local (missão 022, branch `feat/transcrita-022-piper-tts`)

- **Funcionalidade:** adição de síntese neural de fala local (Texto para Áudio — TTS) utilizando o motor Piper mantido pela Open Home Foundation (`OHF-Voice/piper1-gpl`).
- **Governança de Vozes pt-BR:** allowlist estrita em Português do Brasil com voz principal `pt_BR-faber-medium` (CC0, 22.050 Hz) e secundária `pt_BR-edresson-low` (CC-BY-4.0, 16.000 Hz) armazenadas em `/var/lib/transcrita/models/piper/pt_BR/`. Rejeição sumária de vozes não autorizadas ou estrangeiras.
- **Isolamento de Ambiente e Hardware:** runtime ONNX e motor Piper instalados em venv dedicado (`/opt/transcrita/.venv-piper`), preservando a Constituição do projeto (`.kilorules`). Síntese executada em subprocesso sem `shell=True`, compartilhando o semáforo global de inferência (`_inference_semaphore`) com o ASR para cumprimento dos limites de `MemoryMax=8G` e `CPUQuota=400%`.
- **API:** endpoints `GET /api/tts/voices` e `POST /api/tts/synthesize` sob `root_path=/transcrita`, com validação de entrada, teto de 10.000 caracteres, timeout configurável e serialização de fila.
- **Interface Web:** reorganização da interface em duas abas (`Áudio/Vídeo para Texto` e `Texto para Áudio`) com suporte a ARIA tabs e atalhos de teclado, slider de velocidade (0.5x–2.0x), player nativo HTML5, download de áudio WAV e histórico de sínteses da sessão.
- **Homologação:** validado em CPU com RTF entre 0,039 e 0,248 (~4x a 25x mais rápido que tempo real), consumo de RSS de ~398 MB e integridade de acentuação, números, siglas e valores monetários.

### Correção de cópia do texto transcrito (missão 021, branch `fix/transcrita-021-clipboard`)

- **Correção:** suporte a cópia de texto em conexões HTTP sobre IP privado (`http://10.0.0.88:3005/transcrita/`), onde `navigator.clipboard` é indisponível por restrição de contexto seguro do navegador (Secure Context).
- **Fallback:** implementada estratégia resiliente com `document.execCommand('copy')` via elemento temporário selecionável com preservação integral de texto, quebras de linha e acentuação UTF-8, restauração do foco/seleção e feedback de sucesso condicionado à efetiva cópia. Em caso de bloqueio duplo do navegador, o texto é selecionado com instrução ao usuário para atalho do teclado (Ctrl+C).

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

- Endpoint `/api/health` minimalista (sem versão/SHA).
- Sem autenticação nos endpoints (ver TRANSCRITA-014, risco P1).
