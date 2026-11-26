# TRANSCRITA-025 — Configuração Persistente de Ativação do Piper

## Flag Administrativa
- **Nome:** `TRANSCRITA_ENABLE_TTS`
- **Valor padrão:** `false` (desabilitado por padrão)
- **Valor ativo:** `true` (configurado no systemd e usado na homologação)

## Environment Variables Relacionadas
| Variável | Descrição | Padrão/Valor |
|---|---|---|
| `TRANSCRITA_ENABLE_TTS` | Feature flag administrativa para ativação do TTS | `false` |
| `TRANSCRITA_TTS_MAX_CHARS` | Limite máximo de caracteres para síntese | `10000` |
| `TRANSCRITA_TTS_TIMEOUT` | Tempo limite em segundos para síntese | `60.0` |
| `TRANSCRITA_PIPER_BIN` | Caminho binário do motor Piper | `/opt/transcrita/.venv-piper/bin/piper` |
| `TRANSCRITA_PIPER_MODELS_DIR` | Diretório de modelos Piper ONNX | `/var/lib/transcrita/models/piper/pt_BR/` |
| `TRANSCRITA_FFMPEG_TIMEOUT` | Timeout FFmpeg em segundos | `300` |

## Binário e Modelos Piper
- **Binário:** `/opt/transcrita/.venv-piper/bin/piper` (executável)
- **Modelos ONNX:**
  - `pt_BR-faber-medium.onnx` (63.2 MB, CC0 license)
  - `pt_BR-faber-medium.onnx.json` (6.3 KB, CC0 license)
  - `pt_BR-edresson-low.onnx` (63.1 MB, CC BY 4.0 license)
  - `pt_BR-edresson-low.onnx.json` (4.2 KB, CC BY 4.0 license)
- **Diretório:** `/var/lib/transcrita/models/piper/pt_BR/`

## Voices Autorizadas (Allowlist pt-BR)
| Voice ID | Nome | Língua | Qualidade | Sample Rate | License | Default |
|---|---|---|---|---|---|---|
| `pt_BR-faber-medium` | Faber (Médio, pt-BR) | pt-BR | medium | 22050 | CC0 | `True` |
| `pt_BR-edresson-low` | Edresson (Baixo, pt-BR) | pt-BR | low | 16000 | CC BY 4.0 | `False` |

## Validação de Voz
- Política de segurança estrita: apenas vozes em pt-BR autorizadas são aceitas
- Vozes fora da allowlist são rejeitadas com mensagem "Voz 'X' não autorizada pela governança pt-BR"
- Implementado em `transcrita.tts.voice_availability()` e `transcrita.tts.piper.synthesize()`
Após o incidente 026, o agente reportou reinstalação de piper-tts e ativação na unit. Versão exata instalada e configuração efetiva ainda requerem evidência local. Ver IP_DOCUMENTATION.md.
