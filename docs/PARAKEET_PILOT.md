# Piloto Parakeet PT-BR (autorização posterior)

## Pré-requisitos
- Modelo: `calneymgp/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx-int8` (INT8 dinâmico comunitário).
- Licença: **CC-BY-4.0** (atribuição obrigatória; ver `THIRD_PARTY_NOTICES.md`).
- Proveniência: NVIDIA Parakeet TDT 0.6B v3 → fine-tune TAGARELA → export ONNX → quantização INT8.
- Revisão HF do checkpoint: `7d84392553633a8e5bdca7eccb5ae25467e9572f`.
- Integridade: definir `TRANSCRITA_PARAKEET_SHA256` (SHA-256 de `encoder-model.int8.onnx`).
  Valor de referência do checkpoint acima: `89e33f4b8c5186a7034947f07e41af36b853ab638c5a16be37d55774722b8fc5`.
- Dependências: `pip install -e ".[web,parakeet]"` **somente no ambiente de piloto**.

## Configuração
- `TRANSCRITA_ENABLE_PARAKEET=true` (apenas no piloto).
- `TRANSCRITA_PARAKEET_MODEL=/caminho/dos/pesos`.
- VAD fixo: threshold 0,30; pad 250 ms; silêncio 550 ms; fala 150 ms; merge 0,35 s.

## Limites e isolamento
- CPU-only; concorrência serializada pelo semáforo global do produto.
- Orçamento sugerido: ≤4 vCPU e ≤4 GB RSS para o serviço em piloto.
- Não alterar nginx/systemd operacionais sem autorização.

## Áudio e critérios
- Apenas gravações **autorizadas**; nada de dados municipais privados sem consentimento.
- Referência humana revisada para WER/CER; avaliar nomes, siglas, números e datas.
- Timestamps: por segmento (VAD); início ~250 ms adiantado; sem nível de palavra.
- Critérios de aceite: WER ≤ baseline Whisper no mesmo corpus, SRT válido, sem perda textual
  (integridade ≥ 0,99 vs passe integral), estabilidade em 3 repetições.

## Reversão
- `TRANSCRITA_ENABLE_PARAKEET=false` + restart (imediato).
- Remover `[parakeet]` do venv do piloto, se necessário; manter `[web]`.
