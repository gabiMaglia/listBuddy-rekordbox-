#!/usr/bin/env bash
# Crea y activa un virtualenv en .venv e instala las dependencias
set -euo pipefail

PY=python3

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ERROR: $PY no está disponible. Instala Python 3 y vuelve a intentar." >&2
  exit 2
fi

echo "Creando virtual environment en .venv..."
$PY -m venv .venv
echo "Activando .venv..."
# shellcheck disable=SC1091
source .venv/bin/activate
echo "Actualizando pip..."
python -m pip install --upgrade pip
echo "Instalando dependencias desde requirements.txt..."
pip install -r requirements.txt
echo "Listo. Activá el venv con: source .venv/bin/activate" 
echo "Y ejecutá: python3 main.py"
