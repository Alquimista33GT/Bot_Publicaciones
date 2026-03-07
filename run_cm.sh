#!/bin/bash
set -euo pipefail

cd "$HOME/cm_bot"
source .venv/bin/activate

if [ -f "$HOME/cm_bot/.env" ]; then
  set -a
  source "$HOME/cm_bot/.env"
  set +a
fi

if [ -z "${TG_BOT_TOKEN:-}" ]; then
  echo "Falta TG_BOT_TOKEN en ~/cm_bot/.env"
  exit 1
fi

if pgrep -f "$HOME/cm_bot/borrador_bot.py" >/dev/null 2>&1; then
  echo "borrador_bot.py ya está corriendo."
else
  nohup python -u "$HOME/cm_bot/borrador_bot.py" > "$HOME/cm_bot/bot.log" 2>&1 &
  echo "BOT iniciado. Log: $HOME/cm_bot/bot.log"
fi

python -u "$HOME/cm_bot/gui_borradores.py"
