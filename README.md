# transcrita

CLI para transcrição local de áudio e vídeo em português usando [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

## Requisitos

- Python 3.12+
- ffmpeg (para extração de áudio de vídeos)
- faster-whisper

## Instalação

```bash
pip install -e .
```

Com suporte à interface web:

```bash
pip install -e ".[web]"
```

Ou instale apenas as dependências e execute o módulo diretamente:

```bash
pip install -r requirements.txt
python -m transcrita.cli <arquivo>
```

## Uso rápido — `run.sh` (recomendado)

Após `git clone` ou `git pull`, suba a aplicação em qualquer estação Linux/Fedora:

```bash
git clone https://github.com/Rilen/transcrita.git && cd transcrita
./run.sh
```

Para atualizar depois:

```bash
git pull && ./run.sh
```

O servidor ficará disponível em `http://127.0.0.1:8765/` (variáveis `TRANSCRITA_HOST`, `TRANSCRITA_PORT` e `TRANSCRITA_ROOT_PATH` para sobrescrever).

Para usar em um subpath (ex: atrás de proxy reverso):

```bash
TRANSCRITA_HOST=0.0.0.0 TRANSCRITA_PORT=3005 TRANSCRITA_ROOT_PATH=/transcrita ./run.sh
```

## Uso — CLI

```bash
transcrita entrada.mp4 -m base -l pt -o saida.txt -s saida.srt
```

### Argumentos da CLI

| Argumento | Descrição | Padrão |
|-----------|-----------|--------|
| `input` | Caminho do arquivo de áudio ou vídeo | (obrigatório) |
| `-m, --model` | Modelo Whisper (tiny, base, small, medium, large-v3, large-v3-turbo) | `base` |
| `-l, --language` | Código do idioma (ISO 639-1) | `pt` |
| `-o, --output-txt` | Arquivo de saída em texto (.txt) | — |
| `-s, --output-srt` | Arquivo de saída em legendas (.srt) | — |
| `--device` | Dispositivo (auto, cpu, cuda) | `auto` |
| `--compute-type` | Tipo de computação (auto, int8, float16, float32) | `auto` |
| `--beam-size` | Tamanho do feixe de decodificação | `5` |
| `--vad` | Ativa detecção de atividade de voz (requer onnxruntime) | false |
| `--version` | Mostra a versão | — |

Se nenhum arquivo de saída for informado, o texto é impresso no stdout.

## Uso — Interface Web

Inicie o servidor local:

```bash
transcrita-web
```

O servidor fica disponível em `http://127.0.0.1:8765/` e o navegador é aberto automaticamente.

### Argumentos do servidor web

| Argumento | Descrição | Padrão |
|-----------|-----------|--------|
| `--host` | Host do servidor | `127.0.0.1` |
| `--port` | Porta do servidor | `8765` |
| `--root-path` | Caminho base para deploy atrás de subpath, ex: `/transcrita` | `""` |
| `--no-browser` | Não abre o navegador automaticamente | false |

### Deploy atrás de subpath reverso

Para executar atrás de um proxy reverso (ex: Nginx/Caddy) em um subpath, defina `TRANSCRITA_ROOT_PATH`:

```bash
# Servidor 10.0.0.88, porta 3005, subpath /transcrita
TRANSCRITA_HOST=0.0.0.0 TRANSCRITA_PORT=3005 TRANSCRITA_ROOT_PATH=/transcrita ./run.sh
```

A aplicação ficará disponível em `http://10.0.0.88:3005/transcrita/`.

**Exemplo Nginx** (habilite `proxy_buffering off` para SSE em tempo real):

```nginx
location /transcrita/ {
    proxy_pass http://127.0.0.1:3005/transcrita/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_cache off;
}
```

**Exemplo Caddy**:

```caddy
10.0.0.88:3005

handle_path /transcrita/* {
    reverse_proxy http://127.0.0.1:3005/transcrita* {
        header_up Host {upstream_hostport}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
    header /transcrita/* Cache-Control "no-cache"
}
```

A interface permite:
- Arraste e solte ou selecione um arquivo de áudio/vídeo.
- Escolha modelo, idioma, beam size e opcionalmente ative VAD.
- Transcreva e visualize o resultado em abas (Texto / SRT).
- Copie o conteúdo ou baixe os arquivos `.txt` e `.srt`.

## Exemplos

Transcrever um áudio e salvar texto + legendas:

```bash
transcrita audio.mp3 -m base -l pt -o transcricao.txt -s transcricao.srt
```

Transcrever um vídeo usando modelo maior e GPU:

```bash
transcrita video.mp4 -m large-v3 -l pt --device cuda --compute-type float16 -o saida.txt
```

Transcrever e exibir direto no terminal:

```bash
transcrita audio.wav -l pt
```

Iniciar a interface web em outra porta:

```bash
transcrita-web --port 8080
```

## Formatos de entrada suportados

Áudio: `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`

Vídeo: `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`, `.flv`, `.wmv`, `.m4v`
