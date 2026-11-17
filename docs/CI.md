# CI (GitHub Actions)

## Objetivo
Executar a suíte completa (`python -m unittest discover -s tests -v`) em cada PR e em `main`,
sem GPU, sem pesos de modelos e sem acesso ao servidor municipal.

## Gatilhos
- `pull_request` (todas as bases): cobre a cadeia de PRs #2–#8 e PRs futuras.
- `push` em `main`.
- `push` no branch `chore/transcrita-011-ci-governance` (validação da governança sem exigir PR).
- Concorrência agrupada pelo SHA do head (`pull_request.head.sha` ou `sha`), cancelando duplicatas.

## Segurança
- `permissions: contents: read`.
- Sem `pull_request_target`, sem segredos, sem deploy, sem escrita no repositório.
- Actions oficiais apenas (`checkout`, `setup-python`).

## Dependências
- `pip install -e ".[web,test]" -c .github/ci-constraints.txt`.
- `[web]`: FastAPI/Uvicorn/python-multipart.
- `[test]`: `httpx2` (TestClient do Starlette 1.10) e `soundfile` (import do motor Parakeet).
- Versões fixadas em `.github/ci-constraints.txt`, espelhando o ambiente validado localmente.

## O que o CI NÃO faz
- Não baixa pesos Whisper/Parakeet (testes mockam os modelos; `Transcriber` é lazy).
- Não executa integração real com Parakeet (isso é do piloto isolado, com áudio autorizado).
- Não substitui homologação de qualidade ASR.

## Reprodução local
```bash
python3.12 -m venv .venv-ci
.venv-ci/bin/pip install -e ".[web,test]" -c .github/ci-constraints.txt
.venv-ci/bin/python -m unittest discover -s tests -v
```

## Evidência exigida
- Execução do GitHub Actions no SHA do head da PR (URL registrada).
- Job `testes (Python 3.12, CPU)` concluído com sucesso.
- GitGuardian é apenas verificação de segredos; não conta como CI de testes.
