#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/python" ]; then
  echo "Ambiente nao encontrado. Execute ./scripts/bootstrap.sh primeiro." >&2
  exit 1
fi

exec "$ROOT_DIR/.venv/bin/python" -m kokoro_ptbr_desktop
