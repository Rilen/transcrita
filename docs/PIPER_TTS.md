# Integração do Piper TTS Local (MISSÃO TRANSCRITA-022)

Este documento descreve a arquitetura, governança, modelos, endpoints e procedimentos operacionais do motor de síntese de fala local **Piper TTS** no Transcrita.

---

## 1. Visão Geral e Arquitetura

O Transcrita evolui para suportar duas modalidades operacionais independentes:
1. **ASR (Áudio/Vídeo para Texto):** Motores Whisper (estável) e Parakeet PT-BR (experimental).
2. **TTS (Texto para Áudio):** Motor neural local Piper TTS.

```
+-----------------------------------------------------------------------+
|                             Nginx Gateway                             |
|               (http://10.0.0.88:3005/transcrita/ -> Uvicorn)          |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                         Transcrita FastAPI                            |
|             (Interface Web de 2 Abas: ASR e Piper TTS)                |
+-----------------------------------------------------------------------+
              |                                          |
              v                                          v
+---------------------------+              +----------------------------+
|      Fila de ASR          |              |       Fila de TTS          |
|  (Whisper / Parakeet)     |              |       (Piper TTS)          |
+---------------------------+              +----------------------------+
              \                                          /
               \                                        /
                v                                      v
+-----------------------------------------------------------------------+
|             Semáforo Global de Inferência (_inference_semaphore)      |
|             (Capacidade: 1 inferência por vez; teto de 16 waiters)    |
+-----------------------------------------------------------------------+
              |                                          |
              v                                          v
+---------------------------+              +----------------------------+
|   Venv ASR (.venv)        |              |   Venv TTS (.venv-piper)   |
|   - faster-whisper        |              |   - piper-tts 1.8.0        |
|   - ffmpeg subprocess     |              |   - Subprocesso isolado    |
+---------------------------+              +----------------------------+
```

### Isolamento Técnico e Constituição do Agente (.kilorules)
- **Isolamento de dependências:** O Piper e seu runtime ONNX são instalados em um ambiente virtual dedicado (`/opt/transcrita/.venv-piper`), sem modificar o ambiente `.venv` principal do ASR.
- **Subprocesso desacoplado:** A invocação do sintetizador ocorre via `subprocess.run([piper_bin, ...], shell=False)`, garantindo que dependências nativas e memória alocada pelo runtime C++ sejam liberadas imediatamente para o sistema operacional ao término da síntese.
- **Respeito ao orçamento global:** TTS e ASR compartilham o mesmo semáforo de inferência (`_inference_semaphore`), impedindo concorrência simultânea entre sintetização e transcrição e garantindo que o servidor permaneça estritamente dentro dos limites do systemd (`MemoryMax=8G`, `CPUQuota=400%`).
- **Segurança de dados e conformidade:** Não há retenção desnecessária de textos ou áudios temporários. Textos nunca são registrados em arquivos de log. Processamento 100% offline.

---

## 2. Modelos e Governança de Vozes (pt-BR)

Em cumprimento à política de governança do Transcrita, apenas vozes em Português do Brasil (pt-BR) são autorizadas. É estritamente vedado o download ou uso de vozes estrangeiras.

Diretório persistente:
`/var/lib/transcrita/models/piper/pt_BR/`

### 1. Voz Principal (Obrigatória): `pt_BR-faber-medium`
- **Identificador:** `pt_BR-faber-medium`
- **Arquivo ONNX:** `pt_BR-faber-medium.onnx`
  - **SHA-256:** `75e913eb463db0b6ac7ddf68d3e4c9ac19ace36dc3b710a81039b448352b8ffc`
- **Arquivo de Configuração:** `pt_BR-faber-medium.onnx.json`
  - **SHA-256:** `6b6801319e5a70aa4d75c63343515f55d1cd671ecd1ac511586bc16216812261`
- **Qualidade / Frequência:** Média · 22.050 Hz (16-bit PCM mono).
- **Licença do Dataset:** **CC0 1.0 Universal** (Domínio Público).
- **Origem:** Open Home Foundation (`OHF-Voice/voice-datasets`).

### 2. Voz Secundária: `pt_BR-edresson-low`
- **Identificador:** `pt_BR-edresson-low`
- **Arquivo ONNX:** `pt_BR-edresson-low.onnx`
  - **SHA-256:** `de4cecee38b30bb1a6378a337af605d59f0c377df702c6a6752870db8991cd84`
- **Arquivo de Configuração:** `pt_BR-edresson-low.onnx.json`
  - **SHA-256:** `f138992d2e777d1e3aa0bbb14c2d324307b0f342c1bcf20978765b3bea506c56`
- **Qualidade / Frequência:** Baixa · 16.000 Hz (16-bit PCM mono).
- **Licença do Dataset:** **CC-BY-4.0** (Edresson Silva / TTS-Portuguese-Corpus).
- **Origem:** HuggingFace `rhasspy/piper-voices`.

---

## 3. Endpoints da API

Os endpoints operam sob o contexto da aplicação (compatíveis com subcaminho reverso `/transcrita`).

### `GET /api/tts/voices`
Retorna a lista de vozes pt-BR registradas, seu status de disponibilidade física no servidor e a voz padrão.

**Exemplo de Resposta (HTTP 200):**
```json
{
  "enabled": true,
  "default_voice": "pt_BR-faber-medium",
  "voices": [
    {
      "id": "pt_BR-faber-medium",
      "name": "Faber (Médio, pt-BR)",
      "language": "pt-BR",
      "quality": "medium",
      "sample_rate": 22050,
      "default": true,
      "available": true,
      "unavailable_reason": "",
      "license": "CC0"
    },
    {
      "id": "pt_BR-edresson-low",
      "name": "Edresson (Baixo, pt-BR)",
      "language": "pt-BR",
      "quality": "low",
      "sample_rate": 16000,
      "default": false,
      "available": true,
      "unavailable_reason": "",
      "license": "CC BY 4.0"
    }
  ]
}
```

### `POST /api/tts/synthesize`
Sintetiza um texto em áudio e retorna diretamente o arquivo WAV PCM.

**Corpo da Requisição (JSON):**
```json
{
  "text": "Texto a ser falado em português brasileiro.",
  "voice": "pt_BR-faber-medium",
  "speed": 1.0
}
```

**Parâmetros:**
- `text` *(obrigatório)*: Texto UTF-8 a sintetizar (limite padrão: 10.000 caracteres).
- `voice` *(opcional, padrão: `pt_BR-faber-medium`)*: Identificador da voz autorizada na allowlist.
- `speed` *(opcional, padrão: 1.0)*: Velocidade da fala entre 0.5 e 2.0.

**Resposta:**
- `Content-Type: audio/wav`
- `Content-Disposition: attachment; filename="sintese_pt_BR-faber-medium.wav"`
- `Cache-Control: no-cache`

**Validações e Códigos de Retorno:**
- `200 OK`: Áudio sintetizado com sucesso.
- `400 Bad Request`: Texto vazio, texto acima de 10.000 caracteres, voz não permitida ou velocidade fora do intervalo.
- `503 Service Unavailable`: Módulo desabilitado administrativamente (`TRANSCRITA_ENABLE_TTS=false`) ou servidor ocupado por inferência concorrente após esgotamento de fila.
- `504 Gateway Timeout`: Tempo limite esgotado durante processamento do subprocesso.

---

## 4. Interface com 2 Abas

A interface do usuário (`transcrita/static/index.html`) foi estruturada em duas abas principais acessíveis via mouse ou teclado (suporte a ARIA tabs e atalhos de seta):

1. **Aba 1 — Áudio/Vídeo para Texto (ASR):**
   - Preserva integralmente todas as funções existentes: upload, seleção de motores Whisper/Parakeet, streaming SSE, cancelamento, barra de progresso, download de texto e SRT.
2. **Aba 2 — Texto para Áudio (TTS):**
   - Seletor de vozes pt-BR com Faber como padrão.
   - Slider de velocidade contínuo de 0.5x a 2.0x com indicação visual.
   - Campo de texto multilinha com contador em tempo real (`0 / 10.000 caracteres`).
   - Botões de Ação: "Gerar áudio" e "Limpar".
   - Indicador de processamento (spinner animado com status).
   - Player nativo HTML5 `<audio controls>` para reprodução imediata.
   - Botão para download direto do arquivo `.wav`.
   - Painel lateral com histórico de áudios gerados na sessão atual (com play rápido e download).

Alternar entre abas preserva 100% dos estados, textos digitados, filas e áudios gerados.

---

## 5. Configuração por Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `TRANSCRITA_ENABLE_TTS` | `false` | Feature flag administrativa para ativação do motor TTS. |
| `TRANSCRITA_PIPER_BIN` | `/opt/transcrita/.venv-piper/bin/piper` | Caminho do executável Piper. |
| `TRANSCRITA_PIPER_MODELS_DIR` | `/var/lib/transcrita/models/piper/pt_BR` | Diretório de modelos `.onnx` e `.onnx.json`. |
| `TRANSCRITA_TTS_MAX_CHARS` | `10000` | Limite máximo de caracteres por requisição de síntese. |
| `TRANSCRITA_TTS_TIMEOUT` | `60.0` | Timeout máximo em segundos para execução da síntese. |

---

## 6. Resultados de Homologação em CPU (Intel Xeon Gold 5317)

Testes executados no ambiente isolado do servidor:

| Cenário de Teste | Caracteres | Duração Áudio | Tempo Síntese | RTF | Tamanho WAV |
|---|---|---|---|---|---|
| Texto curto | 33 | 2,83 s | 0,70 s | 0,248 | 122 KB |
| Relatório técnico | 124 | 7,60 s | 0,82 s | 0,108 | 327 KB |
| Acentos e especiais | 88 | 6,64 s | 0,90 s | 0,135 | 286 KB |
| Datas e valores | 113 | 10,19 s | 0,94 s | 0,092 | 439 KB |
| Siglas e siglas pt-BR | 86 | 6,54 s | 0,89 s | 0,136 | 281 KB |
| Texto longo institucional | 1.668 | 89,15 s | 3,47 s | 0,039 | 3.840 KB |
| Voz Edresson (baixa) | 51 | 3,07 s | 0,75 s | 0,245 | 96 KB |

- **Velocidade:** RTF médio entre **0,039 e 0,248** (geração de 4x a 25x mais rápida que o tempo real).
- **Consumo de Memória:** RSS máximo de ~398 MB durante a execução do processo.
- **Concorrência:** Serialização estrita verificada entre requisições simultâneas sem vazamento de vagas.

---

## 7. Procedimentos Operacionais

### Procedimento de Ativação em Produção (Pós-Aprovação)

Quando autorizado, a ativação em produção é realizada ajustando a feature flag no serviço systemd:

1. Editar as configurações de ambiente do serviço:
   ```bash
   systemctl edit transcrita.service
   ```
2. Adicionar o bloco com a flag ativada:
   ```ini
   [Service]
   Environment="TRANSCRITA_ENABLE_TTS=true"
   ```
3. Recarregar o systemd e reiniciar o serviço:
   ```bash
   systemctl daemon-reload
   systemctl restart transcrita.service
   ```
4. Validar o funcionamento:
   ```bash
   curl -s http://127.0.0.1:3005/transcrita/api/tts/voices | grep '"enabled":true'
   ```

### Procedimento de Rollback Imediato

Caso haja qualquer instabilidade ou necessidade de desativação do TTS:

1. Desativar a flag de ambiente:
   ```bash
   systemctl edit transcrita.service
   # Definir: Environment="TRANSCRITA_ENABLE_TTS=false"
   ```
2. Reiniciar o serviço:
   ```bash
   systemctl daemon-reload
   systemctl restart transcrita.service
   ```
3. O endpoint de síntese passará imediatamente a rejeitar requisições com HTTP 503 e a interface desabilitará os controles de geração de áudio, mantendo o ASR em pleno funcionamento.
