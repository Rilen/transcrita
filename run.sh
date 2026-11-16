#!/usr/bin/env bash
# transcrita — Script soberano de execução rápida
# Uso: ./run.sh [argumentos adicionais para transcrita-web]
set -euo pipefail

HOST="${TRANSCRITA_HOST:-127.0.0.1}"
PORT="${TRANSCRITA_PORT:-8765}"
ROOT_PATH="${TRANSCRITA_ROOT_PATH:-}"

echo "==> transcrita: preparando ambiente local em http://${HOST}:${PORT}${ROOT_PATH}/"

# 1. Verifica ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERRO: ffmpeg não encontrado no sistema."
  echo "   No Fedora, instale com: sudo dnf install ffmpeg"
  exit 1
fi

# 2. Cria .venv se não existir
if [ ! -d .venv ]; then
  echo "==> Criando ambiente virtual .venv..."
  python3 -m venv .venv
fi

# 3. Ativa o venv e instala dependências (idempotente)
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -e ".[web]"

# 4. Sobe o servidor
echo "==> Iniciando transcrita-web em http://${HOST}:${PORT}${ROOT_PATH}/"
exec python3 -m transcrita.web --host "${HOST}" --port "${PORT}" --root-path "${ROOT_PATH}" "$@"
