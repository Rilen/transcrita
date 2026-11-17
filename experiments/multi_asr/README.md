# PoC multimotor ASR (CPU-only) — TRANSCRITA-003

Comparação reproduzível de motores de transcrição em português, executando **integralmente em CPU**,
sem alterar o serviço operacional e sem publicar áudio/transcrições.

## Arquitetura

```
experiments/multi_asr/
  adapters/base.py                 # contrato ASRAdapter + resultado normalizado
  adapters/faster_whisper_adapter.py
  adapters/parakeet_onnx_adapter.py
  benchmark/run_benchmark.py       # executor (faster-whisper, onnx-asr)
  benchmark/run_qwen.py            # executor isolado (venv torch)
  benchmark/metrics.py             # normalização + WER/CER + agregação
  benchmark/summarize.py           # tabelas por cenário + proxy de alucinação
  benchmark/warm_load.py           # tempo de carga com cache quente
  corpus/build_corpus.py           # MLS Portuguese → cenários (clean/noisy/distant/multi/long)
  configs/models.json
  tests/                           # testes sem rede/modelos
  reports/                         # resultados sanitizados (sem áudio/transcrição)
```

## Dados e privacidade

- Corpus: **MLS Portuguese** (`facebook/multilingual_librispeech`, CC-BY-4.0), áudio LibriVox + transcrição humana.
- Nenhuma gravação municipal foi utilizada ou publicada.
- Áudio, pesos e caches ficam **fora do repositório** (`/var/lib/transcrita-poc`).
- Relatórios versionados contêm apenas métricas agregadas (sem textos).

## Reprodução

```bash
python3 -m venv .venv-poc
.venv-poc/bin/pip install -r experiments/multi_asr/requirements-poc.txt

# corpus (~5 min, 12 itens, 4,5 min de áudio)
.venv-poc/bin/python -m experiments.multi_asr.corpus.build_corpus --out /var/lib/transcrita-poc/corpus

# um modelo por execução (isolamento e limite de memória)
OMP_NUM_THREADS=12 HF_HOME_POC=/var/lib/transcrita-poc/hf \
taskset -c 0-11 nice -n 15 .venv-poc/bin/python -m experiments.multi_asr.benchmark.run_benchmark \
  --model whisper-large-v3-turbo \
  --manifest /var/lib/transcrita-poc/corpus/manifest.json \
  --out /var/lib/transcrita-poc/results/whisper-large-v3-turbo.json

# sumarização
.venv-poc/bin/python -m experiments.multi_asr.benchmark.summarize \
  --results-dir /var/lib/transcrita-poc/results \
  --manifest /var/lib/transcrita-poc/corpus/manifest.json \
  --out-json experiments/multi_asr/reports/results_summary.json \
  --out-md experiments/multi_asr/reports/RESULTS.md
```

Qwen3-ASR exige ambiente separado (torch CPU):

```bash
python3 -m venv .venv-qwen
.venv-qwen/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch
.venv-qwen/bin/pip install qwen-asr==0.0.6 jiwer
PYTHONPATH=$PWD .venv-qwen/bin/python -m experiments.multi_asr.benchmark.run_qwen \
  --manifest /var/lib/transcrita-poc/corpus/manifest.json \
  --out /var/lib/transcrita-poc/results/qwen3-asr-0.6b.json
```

## Testes

```bash
.venv-poc/bin/python -m unittest discover -s experiments/multi_asr/tests -t . -v
```
