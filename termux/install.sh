#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

HUB_DIR="${OFFTEC_HUB_DIR:-$HOME/HUB}"
STATE_DIR="$HOME/.local/state/offtec-hub"
VENV="$HOME/.local/share/offtec-hub/venv"
mkdir -p "$STATE_DIR" "$HOME/.local/share/offtec-hub" "$HUB_DIR/backend/data/uploads"
if [ ! -f "$HUB_DIR/backend/main.py" ]; then
  printf '%s\n' "OFFTEC HUB não encontrado em $HUB_DIR" "Defina OFFTEC_HUB_DIR para a pasta deste projeto e execute novamente."
  exit 2
fi
if ! command -v python >/dev/null 2>&1; then
  pkg install -y python
fi
python -m venv "$VENV"
"$VENV/bin/python" -m pip install -r "$HUB_DIR/backend/requirements.txt"
cat > "$STATE_DIR/start.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
HUB_DIR="${OFFTEC_HUB_DIR:-$HOME/HUB}"
VENV="$HOME/.local/share/offtec-hub/venv"
cd "$HUB_DIR"
exec "$VENV/bin/python" -m backend
EOF
chmod 700 "$STATE_DIR/start.sh"
PID_FILE="$STATE_DIR/server.pid"
if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
    old_cmd="$(ps -p "$old_pid" -o args= 2>/dev/null || true)"
    if [[ "$old_cmd" == *"backend"* ]]; then kill "$old_pid"; fi
  fi
fi
nohup "$STATE_DIR/start.sh" > "$STATE_DIR/server.log" 2>&1 &
server_pid="$!"
echo "$server_pid" > "$PID_FILE"
chmod 600 "$PID_FILE" "$STATE_DIR/server.log"
printf '%s\n' 'OFFTEC HUB configurado. Aguardando o backend local ficar disponível…'
if ! "$VENV/bin/python" - "$server_pid" <<'PY'
import sys, time, urllib.error, urllib.request
pid = sys.argv[1]
url = 'http://127.0.0.1:8765/api/v1/health'
for _ in range(30):
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            if response.status == 200:
                print('Backend confirmado pelo endpoint /api/v1/health.')
                raise SystemExit(0)
    except (OSError, urllib.error.URLError):
        pass
    time.sleep(1)
print(f'Backend não respondeu em 30 segundos (PID inicial {pid}). Últimas linhas do log:')
raise SystemExit(1)
PY
then
  tail -n 40 "$STATE_DIR/server.log" 2>/dev/null || true
  exit 1
fi
