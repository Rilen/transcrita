# Design Brief — transcrita

## 1. Objetivo & Proposta de Valor

**Aplicação:** Ferramenta local de transcrição de áudio e vídeo para texto e legendas (SRT), executada 100% no próprio computador do usuário, sem envio de arquivos para nuvem.

**Proposta de valor:** Transcrição privada, rápida e gratuita de arquivos de áudio/vídeo em português (e outros idiomas), com progresso em tempo real e download imediato dos resultados em .txt e .srt.

**Público-alvo:** Jornalistas, pesquisadores, estudantes, produtores de conteúdo e profissionais que precisam transcrição local de entrevistas, aulas, reuniões e vídeos sem depender de serviços online pagos ou com restrições de privacidade.

---

## 2. Lista de Telas Essenciais

A aplicação é uma página única (SPA-like) servida por FastAPI em `http://127.0.0.1:8000/`.

| Tela / Seção | Descrição | Fluxo-chave |
|--------------|-----------|-------------|
| **Início / Upload** | Área de drag-and-drop, seleção de arquivo, controles de modelo/idioma/beam size/VAD, botão Transcrever e barra de progresso SSE. | Selecionar arquivo → configurar opções → iniciar transcrição → acompanhar progresso por segmento. |
| **Resultado (Texto)** | Exibição do texto transcrito acumulado em tempo real, com botões Copiar e Baixar .txt. | Visualizar texto à medida que segmentos chegam → copiar ou baixar. |
| **Resultado (SRT)** | Exibição das legendas no formato SRT, com botão Baixar .srt. | Alternar aba para SRT → baixar legenda. |
| **Erro** | Mensagem de falha da API com opção de tentar novamente. | Exibir erro → usuário corrige arquivo/opções e reenvia. |

Não há telas de login, cadastro, dashboard ou listagem histórica (processamento é local e estateless por requisição).

---

## 3. Identidade Visual & Branding

### Paleta de cores (variáveis CSS já definidas no projeto)

| Função | Cor clara (light) | Cor escura (dark) | Uso |
|--------|-------------------|-------------------|-----|
| Background (`--bg`) | `#ffffff` | `#0f172a` | Fundo da página |
| Card (`--card`) | `#f5f5f5` | `#1e293b` | Drop-zone, barra de progresso, caixa de saída |
| Borda (`--border`) | `#d1d5db` | `#334155` | Divisórias e campos |
| Primária (`--primary`) | `#2563eb` | `#3b82f6` | Botão Transcrever, preenchimento da barra de progresso |
| Primária hover | `#1d4ed8` | `#2563eb` | Estado ativo do botão primário |
| Acento (`--accent`) | `#059669` | `#10b981` | Botões Baixar (sucesso) |
| Perigo (`--danger`) | `#dc2626` | `#ef4444` | Botão Cancelar, remover arquivo, erros |
| Muted (`--muted`) | `#6b7280` | `#94a3b8` | Texto secundário, dicas, rodapé |

### Tipografia
- Sistema nativo: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`
- Saída de texto/SRT: monoespaçado (`ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`)

### Tom visual
Minimalista, local-first, dark/light automático (`prefers-color-scheme`), sem CDN, sem build step, focado em legibilidade e feedback imediato.

---

## 4. Estrutura de Componentes & Conteúdo Real

### Menus / Controles
- **Modelo (select):** tiny, base, small, medium, large-v3, large-v3-turbo (rápido e preciso). Padrão: `base`.
- **Idioma (select):** Português Brasil (pt), Inglês (en), Espanhol (es), Detectar automaticamente (auto). Padrão: `pt`.
- **Beam Size (number input):** 1–10. Padrão: `5`.
- **Usar VAD (checkbox):** desmarcado por padrão.
- **Dispositivo / Compute type:** fixos no backend (`auto` / `default`), não expostos na UI atual.

### Cards
- **Drop-zone:** ícone de microfone, título "Solte o arquivo aqui ou clique para selecionar", hint "Áudio ou vídeo".
- **File-info:** nome do arquivo, tamanho formatado, botão remover (×).
- **Progress-card:** status (ex. "Carregando modelo…", "Extraindo áudio…"), barra de progresso 0–100%, tempo decorrido / total, botão Cancelar.

### Tabelas / Dados
- **Saída de texto:** bloco pré-formatado com rolagem, atualizado em tempo real via eventos SSE (`segment`).
- **Saída SRT:** bloco pré-formatado com numeração, timestamps e texto das legendas.

### CTAs (Chamadas para ação)
- **Transcrever** (primário): inicia o upload e transcrição via SSE.
- **Cancelar** (perigo): aborta o `AbortController` do stream SSE.
- **Copiar** (secundário): copia conteúdo da aba ativa (Texto ou SRT) para a área de transferência.
- **Baixar .txt** (sucesso): gera Blob e dispara download do arquivo `.txt`.
- **Baixar .srt** (sucesso): gera Blob e dispara download do arquivo `.srt`.

### Formatos de entrada suportados
Áudio: `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`  
Vídeo: `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`, `.flv`, `.wmv`, `.m4v`

---

## 5. Dispositivo / Formato Alvo

**Desktop (principal).** Interface otimizada para navegadores em `localhost`, largura máxima de 800px centralizada.  
**Mobile (secundário / responsivo):** grade de controles se adapta em coluna única (`grid-template-columns: repeat(auto-fit, minmax(140px, 1fr))`), botões empilhados, texto monoespaçado com quebra de linha.

---

## 6. Notas de Implementação

- HTML + CSS + Vanilla JS em arquivo único (`transcrita/static/index.html`), sem dependências externas.
- Comunicação com o backend via `POST /api/transcribe/stream` (SSE) e `POST /api/transcribe` (compatibilidade CLI).
- Progresso em tempo real calculado pelo backend: `progress = min(100, round(end / duration * 100, 1))`.
- Cancelamento via `AbortController` no cliente.
- Dark/light automático conforme preferência do sistema operacional.
