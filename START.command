#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  ./setup_mac.sh
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  chmod 600 .env
fi

if ! grep -Eq '^OPENAI_API_KEY=.+$' .env; then
  echo
  echo "OPENAI_API_KEY is not configured."
  echo "Edit: $(pwd)/.env"
  echo
  read -p "Press Enter to close..."
  exit 1
fi

if ! grep -Eq '^SEC_USER_AGENT=.+@.+$' .env; then
  echo
  echo "SEC_USER_AGENT is not configured."
  echo
  echo "Add a real contact to .env, for example:"
  echo "SEC_USER_AGENT=YourName your.email@example.com"
  echo
  read -p "Press Enter to close..."
  exit 1
fi

source .venv/bin/activate

URL="http://127.0.0.1:8765"

(
  sleep 2
  open "$URL"
) &

echo
echo "Starting Universal Equity Research Agent V8.4 Data Foundation ..."
echo
echo "$URL"
echo
echo "Keep this window open while using the app."
echo

python -m uvicorn ui_server:app \
  --host 127.0.0.1 \
  --port 8765
