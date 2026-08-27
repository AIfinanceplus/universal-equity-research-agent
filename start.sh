#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  ./setup_mac.sh
fi

source .venv/bin/activate

if [ ! -f ".env" ]; then
  cp .env.example .env
  chmod 600 .env
fi

if ! grep -Eq '^OPENAI_API_KEY=.+$' .env; then
  echo
  echo "OPENAI_API_KEY is missing."
  echo "Edit: $(pwd)/.env"
  exit 1
fi

echo
echo "Starting:"
echo "  http://127.0.0.1:8765"
echo

python -m uvicorn ui_server:app \
  --host 127.0.0.1 \
  --port 8765
