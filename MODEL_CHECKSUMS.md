# TRANSCRITA-025 — Versões, Licenças e Checksums dos Modelos

## Modelos Piper PT-BR

| Arquivo | Tamanho | SHA-256 | Licença |
|---|---|---|---|
| `pt_BR-faber-medium.onnx` | 63.221.984 bytes | `de4cecee38b30bb1a6378a337af605d59f0c377df702c6a6752870db8991cd84` | CC0 |
| `pt_BR-faber-medium.onnx.json` | 6.257 bytes | `6b6801319e5a70aa4d75c63343515f55d1cd671ecd1ac511586bc16216812261` | CC0 |
| `pt_BR-edresson-low.onnx` | 63.104.526 bytes | `75e913eb463db0b6ac7ddf68d3e4c9ac19ace36dc3b710a81039b448352b8ffc` | CC BY 4.0 |
| `pt_BR-edresson-low.onnx.json` | 4.168 bytes | `f138992d2e777d1e3aa0bbb14c2d324307b0f342c1bcf20978765b3bea506c56` | CC BY 4.0 |

**Diretório:** `/var/lib/transcrita/models/piper/pt_BR/`

## Modelos Whisper
- Modelo `base` em Português do Brasil
- Checksums dos pesos Whisper não apresentados; testes automatizados não substituem verificação dos arquivos
- Utilizado para transcrição de áudio/vídeo via `faster-whisper`

## Modelos Parakeet (Experimental/Offline)
| Atributo | Valor |
|---|---|
| **Caminho** | `/var/lib/transcrita-poc/models/parakeet-ptbr-tagarela-int8` |
| **SHA-256** | `89e33f4b8c5186a7034947f07e41af36b853ab638c5a16be37d55774722b8fc5` |
| **Status** | Experimental, CPU-only, offline |
| **Ambiente** | `TRANSCRITA_ENABLE_PARAKEET=true` no systemd |

## Verificação de Integridade
- Checksums SHA-256 reportados pelo agente antes do incidente 026 via `sha256sum /var/lib/transcrita/models/piper/pt_BR/*.onnx /var/lib/transcrita/models/piper/pt_BR/*.onnx.json`
- Modelos Piper validados em homologação 15/15 (homologate_piper.py)
- A suíte 113/113 não comprova integridade dos pesos.
Os hashes acima são registros reportados, não verificados independentemente. Revalidar arquivos e versões após reconstrução; o hash Parakeet refere-se ao encoder, não ao conjunto completo.
