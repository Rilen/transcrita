# Constituição Técnica e Guia de Maturação Contínua — `transcrita`

Este documento estabelece as invariantes arquiteturais, os critérios de qualidade e o protocolo de evolução iterativa do projeto **`transcrita`**. Qualquer agente de código (Kilo CLI, Aider, etc.) ou desenvolvedor humano deve respeitar estas diretrizes antes de propor ou aplicar alterações.

---

## 1. Constituição do Projeto (Invariantes Inegociáveis)

1. **Compatibilidade Estrita com Python 3.15+ (Linux/Fedora):**
   - Não introduzir dependências que exijam compilação nativa frágil ou rodas binárias indisponíveis no Python 3.15 (ex.: `av`/PyAV ou `onnxruntime` obrigatório).
   - A decodificação de mídia deve permanecer delegada ao binário `ffmpeg` do sistema via `subprocess`.
   - O filtro VAD (`vad_filter`) deve permanecer **desativado por padrão** (`False`).

2. **Eficiência de Hardware (Single-Model & Fila Sequencial):**
   - Manter o cache *single-model* em memória/VRAM no `Transcriber`: carregar um novo modelo deve descarregar explicitamente o modelo anterior (`gc.collect()` / liberação CUDA quando aplicável).
   - O processamento em lote deve ocorrer **estritamente de forma sequencial** (um arquivo por vez) para evitar contenção de threads de CPU/GPU e picos de memória.

3. **Frontend 100% Autocontido (Zero Build / Zero CDN):**
   - Toda a interface web reside exclusivamente em `transcrita/static/index.html` usando HTML5, CSS3 e Vanilla JavaScript puro.
   - Proibido adicionar React, Vue, Tailwind via CDN, bundlers (Vite/Webpack) ou fontes externas.

4. **Cancelamento Resiliente e Limpeza de Recursos:**
   - Todo arquivo temporário criado durante uploads ou extração de áudio deve ser removido em blocos `try...finally`.
   - O endpoint SSE (`/api/transcribe/stream`) deve monitorar `request.is_disconnected()` e propagar `cancel_event` (`threading.Event`) para interromper imediatamente o loop de inferência no `core.py`.

5. **Contrato de Testes Obrigatório:**
   - Nenhuma alteração pode ser concluída sem passar 100% em `python3 -m unittest discover -s tests -v`.
   - Toda nova funcionalidade ou correção no backend (`core.py`, `web.py`, `cli.py`, `srt.py`) exige cobertura correspondente em `tests/`.

---

## 2. Arquitetura de Referência

```text
transcrita/
├── __init__.py
├── cli.py              # Ponto de entrada CLI (transcrita / transcrita-web)
├── core.py             # Núcleo Transcriber, cache single-model, ffmpeg, RTF e cancel_event
├── srt.py              # Formatação de legendas SRT
├── web.py              # API FastAPI, upload multipart e streaming SSE com detecção de desconexão
└── static/
    └── index.html      # UI SPA autocontida (fila lateral, filtro por seleção, edição inline, temas)
tests/
├── test_core.py
├── test_srt.py
└── test_web.py
```

---

## 3. Eixos de Auditoria e Melhoria Contínua

Ao executar um ciclo de maturação, avalie o repositório na seguinte ordem de prioridade:

### Eixo 1 — Estabilidade, Resiliência & Cancelamento
- Garantir ausência de vazamento de descritores/arquivos temporários mesmo sob falha abrupta de `ffmpeg` ou desconexão do cliente SSE.
- Validar tratamento seguro do `sessionStorage` no frontend (proteção contra JSON corrompido ou `QuotaExceededError`).
- Assegurar isolamento de eventos DOM na UI (cliques em botões de ação nunca devem disparar acidentalmente o `<input type="file">`).

### Eixo 2 — Ergonomia & Fluxo de Uso (UI/UX)
- **Layout:** Área central focada no texto consolidado (editável via `contenteditable` antes de exportar) e sidebar direita dedicada ao controle da fila e filtro por seleção (`checkbox`, todos marcados por padrão).
- **Produtividade:** Manter atalhos rápidos (`Ctrl+Enter` para iniciar fila, feedback visual instantâneo ao copiar/baixar, dropzone compacta quando a fila já contém itens).
- **Contraste e Temas:** Garantir legibilidade total tanto no tema escuro (padrão) quanto no tema claro.

### Eixo 3 — Observabilidade & Qualidade de Código
- Manter logs estruturados no backend com duração do áudio, tempo de processamento, **RTF (*Real-Time Factor*)** e contagem de segmentos.
- Manter funções pequenas, coesas e tipadas.

### Eixo 4 — Operação Local & Empacotamento (Fedora / Podman / systemd)
- Evoluir os artefatos de implantação local sem poluir o núcleo Python:
  - `Containerfile` otimizado para **Podman** (com `ffmpeg`, usuário não-root e volume persistente para cache do Hugging Face/Whisper).
  - Unit `systemd --user` (`transcrita-web.service`) para execução contínua em segundo plano no Fedora.

---

## 4. Protocolo de Entrega para Agentes de Código

Ao finalizar qualquer ciclo de trabalho neste repositório:

1. Execute `python3 -m unittest discover -s tests -v` e confirme **100% de aprovação**.
2. Apresente um resumo objetivo em formato de tabela:
   `| Arquivo | Problema/Oportunidade | Melhoria Aplicada | Impacto |`
3. Liste até **3 próximos incrementos de alto valor** e aguarde aprovação explícita antes de iniciar o próximo ciclo.