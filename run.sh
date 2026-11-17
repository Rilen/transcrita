#!/usr/bin/env bash
# transcrita — Script soberano de execução rápida
# Uso: ./run.sh [argumentos adicionais para transcrita-web, ex: --no-browser]
set -euo pipefail

HOST="${TRANSCRITA_HOST:-127.0.0.1}"
PORT="${TRANSCRITA_PORT:-8765}"
ROOT_PATH="${TRANSCRITA_ROOT_PATH:-}"

echo "==> transcrita: preparando ambiente local em http://${HOST}:${PORT}${ROOT_PATH}/"

# 1. Verifica Python (projeto requer >= 3.12)
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "==> Python detectado: ${PYTHON_VERSION}"

# 2. Verifica ffmpeg (obrigatório para extração de áudio via CLI)
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERRO: ffmpeg não encontrado no sistema."
  echo "   No Fedora/RHEL, instale com: sudo dnf install ffmpeg"
  echo "   No Debian/Ubuntu, instale com: sudo apt install ffmpeg"
  exit 1
fi

# 3. Cria .venv se não existir
if [ ! -d .venv ]; then
  echo "==> Criando ambiente virtual .venv..."
  python3 -m venv .venv
fi

# 4. Ativa o venv
# shellcheck disable=SC1091
source .venv/bin/activate

# 5. Atualiza pip
pip install --quiet --upgrade pip

# 6. Instala dependências Python (sem compilar av/PyAV)
echo "==> Instalando dependências Python..."
if ! pip install --quiet -e ".[web]" 2>/dev/null; then
  echo "AVISO: instalação padrão falhou (provavelmente av/PyAV requer ffmpeg-devel). Usando instalação alternativa sem compilação nativa..."
  # Dependências web individualmente (wheels prontos, sem compilação)
  pip install --quiet fastapi uvicorn python-multipart
  # Pacote transcrita sem puxar dependências (evita av/onnxruntime de build)
  pip install --quiet -e . --no-deps
fi

# 7. Garante stub mínimo de av se import falhar (ambiente sem ffmpeg-devel)
if ! python3 -c "import av" 2>/dev/null; then
  echo "==> Criando stub mínimo de av (PyAV não disponível, usando ffmpeg CLI)..."
  SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
  AV_DIR="${SITE_PACKAGES}/av"
  mkdir -p "${AV_DIR}"
  cat > "${AV_DIR}/__init__.py" << 'PYEOF'
"""Stub mínimo do módulo av (PyAV) para ambientes sem ffmpeg-devel.

transcrita não usa PyAV: extrai áudio via ffmpeg CLI e lê WAV com o módulo
padrão wave. Este stub existe apenas para evitar ImportError em pacotes
que importam av opcionalmente.
"""
PYEOF
  cat > "${AV_DIR}/__main__.py" << 'PYEOF'
def main():
    raise SystemExit("Stub av: não execute diretamente.")

if __name__ == "__main__":
    main()
PYEOF
  echo "==> Stub de av criado em ${AV_DIR}"
fi

# 8. Verificação rápida de importação do pacote
python3 -c "from transcrita.core import Transcriber; print('==> transcrita importado com sucesso')"

# 9. Sobe o servidor (repasse flags adicionais como --no-browser)
echo "==> Iniciando transcrita-web em http://${HOST}:${PORT}${ROOT_PATH}/"
exec python3 -m transcrita.web --host "${HOST}" --port "${PORT}" --root-path "${ROOT_PATH}" "$@"
