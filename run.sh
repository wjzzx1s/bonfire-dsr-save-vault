#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$APP_DIR"

if [ ! -x .venv/bin/python ]; then
    echo "Creating Bonfire virtual environment…"
    python3 -m venv .venv
    ./.venv/bin/pip install --disable-pip-version-check -q --upgrade pip
fi

if ! ./.venv/bin/python -c "import PySide6" >/dev/null 2>&1; then
    echo "Installing Bonfire dependencies…"
    ./.venv/bin/pip install --disable-pip-version-check -q -r requirements.txt
fi

exec ./.venv/bin/python -m bonfire "$@"
