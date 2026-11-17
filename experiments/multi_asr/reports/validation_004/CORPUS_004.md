# Corpus 004 — proveniência e instruções (sem áudio/transcrições versionados)

## Fontes públicas
| Fonte | Split/shard | Revisão | Licença | Uso |
|---|---|---|---|---|
| `nilc-nlp/CORAA-NURC-SP-Audio-Corpus` | `data/original/validation-00001.parquet`, `data/original/test-00002.parquet`, `data/original/validation-00000.parquet` | `c02be121ec191fe35fc5808209c346b59fe7e3e9` | **CC-BY-NC-ND-4.0** | fala espontânea pt-BR (NURC-SP) |
| `dominguesm/mTEDx-ptbr` | `data/test-00000-of-00003-ef95547d8377e9f8.parquet` | `ff48b897e2f6049feb50c9d4ff41581c04792f0e` | **CC-BY-NC-4.0** | fala preparada (TEDx pt-BR) |

## Seleção
- 16 clipes espontâneos: `variety=pt-br`, `quality=high`, 3–15 s, texto ≥ 25 caracteres, máx. 3 por gravação.
- 8 clipes preparados: 3–20 s, texto ≥ 25 caracteres.
- Total: 24 clipes, 133,3 s. Áudio mantido **sem transformação** (NURC é ND).

## Reprodutibilidade
- Download: `hf_hub_download(..., repo_type="dataset")` dos shards acima.
- Extração: bytes do campo `audio` gravados como WAV; `ffprobe` registra duração/amostragem.
- Integridade: `audio_sha256` e `text_sha256` por item no manifesto local
  (`/var/lib/transcrita-poc/corpus004/manifest.json`), que **não é versionado** por conter referências NC.
- Nenhum áudio, transcrição integral ou dado municipal é publicado no repositório.

## Uso permitido nesta missão
Avaliação interna, não comercial, sem redistribuição de áudio nem criação de obras derivadas do NURC-SP.
Resultados publicados apenas como métricas agregadas.
