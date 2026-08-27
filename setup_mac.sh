#!/bin/bash
set -e

cd "$(dirname "$0")"

echo
echo "======================================"
echo "Universal Equity Research Agent Setup"
echo "======================================"
echo

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 not found."
  echo "Install Python 3 first, then rerun."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "[1/4] Creating .venv ..."
  "$PYTHON_BIN" -m venv .venv
else
  echo "[1/4] .venv already exists."
fi

source .venv/bin/activate

echo "[2/4] Upgrading pip ..."
python -m pip install --upgrade pip

echo "[3/4] Installing dependencies ..."
python -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "[4/4] Creating .env ..."
  cp .env.example .env
  chmod 600 .env
else
  echo "[4/4] .env already exists."
fi

echo
echo "Syntax check ..."

python -m py_compile \
  main.py \
  ui_server.py \
  agent/config.py \
  agent/schemas.py \
  agent/search.py \
  agent/resolver.py \
  agent/valuation.py \
  agent/verification.py \
  agent/nodes.py \
  agent/graph.py \
  agent/state_factory.py

echo
echo "Setup complete."
echo
echo "If OPENAI_API_KEY is not yet in .env, edit:"
echo "  $(pwd)/.env"
echo
