#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
STATE_DIR="$HOME/.local/state/offtec-hub"
PID_FILE="$STATE_DIR/server.pid"
if [ ! -f "$PID_FILE" ]; then echo 'Servidor OFFTEC HUB não está em execução.'; exit 0; fi
pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
  cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  if [[ "$cmd" == *"backend"* ]]; then kill "$pid"; fi
fi
rm -f "$PID_FILE"
echo 'Servidor OFFTEC HUB encerrado.'
