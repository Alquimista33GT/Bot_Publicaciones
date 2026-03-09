#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$HOME/cm_bot"
VENV_DIR="$APP_DIR/.venv"
ENV_FILE="$APP_DIR/.env"

BOT_FILE="$APP_DIR/borrador_bot.py"
GUI_FILE="$APP_DIR/gui_borradores.py"

LOG_DIR="$APP_DIR/logs"
BOT_LOG="$LOG_DIR/bot.log"
BOT_PID_FILE="$APP_DIR/borrador_bot.pid"

mkdir -p "$LOG_DIR"

msg() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
  msg "ERROR: $*"
  exit 1
}

require_file() {
  local file="$1"
  [[ -f "$file" ]] || die "No existe el archivo: $file"
}

is_pid_running() {
  local pid="$1"
  [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null
}

start_bot() {
  if [[ -f "$BOT_PID_FILE" ]]; then
    local old_pid
    old_pid="$(cat "$BOT_PID_FILE" 2>/dev/null || true)"

    if is_pid_running "$old_pid"; then
      msg "borrador_bot.py ya está corriendo con PID $old_pid"
      return 0
    else
      msg "PID guardado inválido o proceso caído. Limpiando PID anterior."
      rm -f "$BOT_PID_FILE"
    fi
  fi

  msg "Iniciando bot..."
  nohup python -u "$BOT_FILE" >> "$BOT_LOG" 2>&1 &
  local new_pid=$!
  echo "$new_pid" > "$BOT_PID_FILE"

  sleep 1

  if is_pid_running "$new_pid"; then
    msg "BOT iniciado correctamente con PID $new_pid"
    msg "Log: $BOT_LOG"
  else
    rm -f "$BOT_PID_FILE"
    die "El bot no logró iniciar. Revisa el log: $BOT_LOG"
  fi
}

run_gui() {
  msg "Abriendo GUI..."
  exec python -u "$GUI_FILE"
}

main() {
  cd "$APP_DIR" || die "No se pudo entrar a $APP_DIR"

  [[ -d "$VENV_DIR" ]] || die "No existe el entorno virtual: $VENV_DIR"
  require_file "$BOT_FILE"
  require_file "$GUI_FILE"

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  else
    die "No existe el archivo .env en $ENV_FILE"
  fi

  [[ -n "${TG_BOT_TOKEN:-}" ]] || die "Falta TG_BOT_TOKEN en $ENV_FILE"

  start_bot
  run_gui
}

main "$@"
