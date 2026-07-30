#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$PROJECT_ROOT/venv"

cd "$PROJECT_ROOT"

echo "========================================"
echo " StoreReceiptAnalyzer"
echo "========================================"

# ==========================================
# CHECK VIRTUAL ENVIRONMENT
# ==========================================

if [ ! -d "$VENV" ]; then
    echo "[FAIL] Virtual environment not found."
    echo "[INFO] Run ./install.sh first."
    exit 1
fi

if [ ! -x "$VENV/bin/as-webui" ]; then
    echo "[FAIL] Command as-webui not found."
    echo "[INFO] Run ./install.sh first."
    exit 1
fi

if [ ! -x "$VENV/bin/as-worker" ]; then
    echo "[FAIL] Command as-worker not found."
    echo "[INFO] Run ./install.sh first."
    exit 1
fi

# ==========================================
# LOAD CONFIGURATION
# ==========================================

AS_PORT=$("$VENV/bin/python" - <<'PY'
from dotenv import load_dotenv, find_dotenv
import os
import sys

env_path = find_dotenv(usecwd=True)

if not env_path:
    print("[FAIL] File .env not found.", file=sys.stderr)
    sys.exit(1)

load_dotenv(env_path)

print(os.getenv("AS_PORT", "8000"))
PY
)

echo "[OK] WebUI Port: $AS_PORT"

# ==========================================
# DEBUG MODE
# ==========================================

DEBUG=$("$VENV/bin/python" - <<'PY'
from dotenv import load_dotenv, find_dotenv
import os
import sys

env_path = find_dotenv(usecwd=True)

if not env_path:
    sys.exit(1)

load_dotenv(env_path)

print(os.getenv("DEBUG", "False").lower())
PY
)

if [[ "$DEBUG" == "true" || "$DEBUG" == "1" || "$DEBUG" == "yes" || "$DEBUG" == "on" ]]; then
    echo
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo " WARNING: DEBUG MODE IS ENABLED"
    echo " Do not use DEBUG=True in production."
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo
else
    echo "[OK] DEBUG mode disabled"
fi
# ==========================================
# FUNCTIONS
# ==========================================

start_worker() {
    echo "[INFO] Starting worker..."
    exec "$VENV/bin/as-worker"
}

start_web() {
    echo "[INFO] Starting WebUI on port $AS_PORT..."
    exec "$VENV/bin/as-webui" runserver "0.0.0.0:$AS_PORT"
}

cleanup() {
    echo
    echo "[INFO] Stopping StoreReceiptAnalyzer..."

    kill "$WORKER_PID" 2>/dev/null || true
    kill "$WEBUI_PID" 2>/dev/null || true

    wait "$WORKER_PID" 2>/dev/null || true
    wait "$WEBUI_PID" 2>/dev/null || true

    echo "[OK] StoreReceiptAnalyzer stopped"
}

start_all() {
    echo "[INFO] Starting worker..."
    "$VENV/bin/as-worker" &

    WORKER_PID=$!

    echo "[INFO] Starting WebUI on port $AS_PORT..."

    (
        cd "$PROJECT_ROOT/src/analizzascontrini/webui"
        exec "$VENV/bin/python" -u manage.py runserver --noreload "0.0.0.0:$AS_PORT"
    ) &

    WEBUI_PID=$!

    trap cleanup SIGINT SIGTERM

    echo
    echo "[OK] StoreReceiptAnalyzer started"
    echo

    wait
}
# ==========================================
# COMMAND
# ==========================================

case "${1:-all}" in

    worker)
        start_worker
        ;;

    web)
        start_web
        ;;

    all)
        start_all
        ;;

    *)
        echo "Uso:"
        echo "  ./run.sh              Start worker e WebUI"
        echo "  ./run.sh worker       Start only the worker"
        echo "  ./run.sh web          Start only the WebUI"
        exit 1
        ;;

esac