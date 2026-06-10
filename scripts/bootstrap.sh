#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "Instalando uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

uv venv .venv --python 3.10
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

"$PYTHON_BIN" -m pip install --upgrade pip
uv pip install --python "$PYTHON_BIN" -e .

if ! command -v espeak-ng >/dev/null 2>&1; then
  echo
  echo "Aviso: espeak-ng nao foi encontrado no PATH."
  echo "No Ubuntu/Debian/WSL, instale com: sudo apt install espeak-ng"
  echo "No Windows, instale o eSpeak NG e informe o caminho do executavel na app."
fi

echo
echo "Ambiente pronto. Execute: ./scripts/run.sh"
