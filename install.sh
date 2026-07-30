#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$PROJECT_ROOT/venv"

cd "$PROJECT_ROOT"

echo "========================================"
echo " StoreReceiptAnalyzer - Installation"
echo "========================================"

# ==========================================
# PYTHON
# ==========================================

if ! command -v python3 >/dev/null 2>&1; then
    echo "[FAIL] Python 3 non trovato."
    exit 1
fi

PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')

PYTHON_VERSION=$(python3 --version)

if [ "$PYTHON_MAJOR" -lt 3 ] || {
    [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 12 ];
}; then
    echo "[FAIL] Python 3.12 or higher required."
    echo "[INFO] Version found: $PYTHON_VERSION"
    exit 1
fi

echo "[OK] $PYTHON_VERSION"
# ==========================================
# REQUIREMENTS
# ==========================================

if [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo "[FAIL] requirements.txt not found."
    exit 1
fi

echo "[OK] requirements.txt found"

# ==========================================
# VIRTUAL ENVIRONMENT
# ==========================================

if [ ! -d "$VENV" ]; then
    echo "[INFO] Creating virtual environment..."

    python3 -m venv "$VENV"

    echo "[OK] Virtual environment created"
else
    echo "[OK] Virtual environment already exists"
fi

# ==========================================
# DEPENDENCIES
# ==========================================

echo "[INFO] Installing/verifying dependencies..."

"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r "$PROJECT_ROOT/requirements.txt"
"$VENV/bin/python" -m pip install "$PROJECT_ROOT"
echo "[OK] Dependencies installed"

# ==========================================
# ENVIRONMENT
# ==========================================

ENV_PATH=$("$VENV/bin/python" - <<'PY'
from dotenv import find_dotenv

env_path = find_dotenv(usecwd=True)

if env_path:
    print(env_path)
PY
)

if [ -z "$ENV_PATH" ]; then
    echo "[FAIL] File .env not found"
    echo "[INFO] Create a .env file from .env.example."
    exit 1
fi

echo "[OK] .env found: $ENV_PATH"

# ==========================================
# ENVIRONMENT VARIABLES
# ==========================================

ENV_PATH="$ENV_PATH" "$VENV/bin/python" - <<'PY'

from dotenv import load_dotenv
import os
import sys

env_path = os.environ["ENV_PATH"]

load_dotenv(env_path)

required = [
    "SECRET_KEY",
    "AS_HOST",
    "AS_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "OLLAMA_HOST",
    "REDIS_URL",
]

missing = []

for variable in required:
    if not os.getenv(variable):
        missing.append(variable)

if missing:
    print("[FAIL] Variabili mancanti nel .env:")
    for variable in missing:
        print(f"       - {variable}")
    sys.exit(1)

print("[OK] Variabili .env presenti")
PY

# ==========================================
# POSTGRESQL
# ==========================================

echo "[INFO] Checking PostgreSQL..."

"$VENV/bin/python" - <<'PY'
from dotenv import load_dotenv, find_dotenv
import os
import sys
import psycopg2
from psycopg2 import sql

env_path = find_dotenv(usecwd=True)

if not env_path:
    print("[FAIL] File .env not found.")
    sys.exit(1)

load_dotenv(env_path)

db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")

# ==========================================
# Test connection to the configured database
# ==========================================

try:

    connection = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
        connect_timeout=5
    )

    connection.close()

    print(f"[OK] PostgreSQL database '{db_name}' reachable.")

except psycopg2.OperationalError as error:

    error_message = str(error)

    # Non-existent database
    if "does not exist" not in error_message:

        print("[FAIL] Unable to connect to PostgreSQL.")
        print(f"       {error_message}")
        sys.exit(1)

    print(f"[INFO] Database '{db_name}' does not exist.")
    print("[INFO] I'll try to create it...")

    # ==========================================
    # Connection to the administrative database
    # ==========================================

    try:

        connection = psycopg2.connect(
            dbname="postgres",
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            connect_timeout=5
        )

        connection.autocommit = True

        cursor = connection.cursor()

        cursor.execute(
            sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(db_name)
            )
        )

        cursor.close()
        connection.close()

        print(f"[OK] Database '{db_name}' created.")

    except psycopg2.OperationalError as error:

        print("[FAIL] Unable to connect to the PostgreSQL administrative database.")
        print(f"       {error}")
        sys.exit(1)

    except psycopg2.errors.InsufficientPrivilege:

        print("[FAIL] The PostgreSQL user cannot create databases.")
        print("       Create the database manually or use a user with the CREATE DATABASE permission.")
        sys.exit(1)

    except Exception as error:

        print("[FAIL] Error creating the database.")
        print(f"       {error}")
        sys.exit(1)

PY


# ==========================================
# REDIS
# ==========================================

echo "[INFO] Checking Redis..."

"$VENV/bin/python" - <<'PY'
from dotenv import load_dotenv, find_dotenv
import os
import sys
import redis

env_path = find_dotenv(usecwd=True)

if not env_path:
    print("[FAIL] File .env not found.")
    sys.exit(1)

load_dotenv(env_path)

redis_url = os.getenv("REDIS_URL")

try:

    client = redis.from_url(
        redis_url,
        socket_connect_timeout=5,
        socket_timeout=5
    )

    if not client.ping():
        print("[FAIL] Redis did not respond to the PING.")
        sys.exit(1)

    print("[OK] Redis is reachable.")

except Exception as error:

    print("[FAIL] Unable to connect to Redis.")
    print(f"       {error}")
    sys.exit(1)

PY

# ==========================================
# OLLAMA
# ==========================================

echo "[INFO] Checking Ollama..."

"$VENV/bin/python" - <<'PY'
from dotenv import load_dotenv, find_dotenv
import os
import sys
import requests

env_path = find_dotenv(usecwd=True)

if not env_path:
    print("[FAIL] File .env not found")
    sys.exit(1)

load_dotenv(env_path)

ollama_host = os.getenv("OLLAMA_HOST").rstrip("/")

try:

    response = requests.get(
        f"{ollama_host}/api/tags",
        timeout=5
    )

    if response.status_code != 200:
        print(
            f"[FAIL] Ollama responded with HTTP "
            f"{response.status_code}."
        )
        sys.exit(1)

    data = response.json()
    models = data.get("models", [])

    print(
        f"[OK] Ollama reachable "
        f"({len(models)} available models)."
    )

except requests.exceptions.RequestException as error:

    print("[FAIL] Unable to reach Ollama.")
    print(f"       {error}")
    sys.exit(1)

except ValueError:

    print("[FAIL] Ollama returned an invalid response.")
    sys.exit(1)

PY

# ==========================================
# DJANGO CHECK
# ==========================================

echo "[INFO] Checking Django configuration..."

"$VENV/bin/python" \
    "$PROJECT_ROOT/src/analizzascontrini/webui/manage.py" \
    check

echo "[OK] Valid Django configuration"

# ==========================================
# DATABASE MIGRATIONS
# ==========================================

echo "[INFO] I am applying the migrations..."

"$VENV/bin/python" \
    "$PROJECT_ROOT/src/analizzascontrini/webui/manage.py" \
    migrate

echo "[OK] Applied migrations"

# ==========================================
# STATIC FILES
# ==========================================

echo "[INFO] Collecting static files..."

"$VENV/bin/python" \
    "$PROJECT_ROOT/src/analizzascontrini/webui/manage.py" \
    collectstatic --noinput

echo "[OK] Collected static files"


echo
echo "========================================"
echo " Installation complete"
echo "========================================"
echo
echo "To launch StoreReceiptAnalyzer:"
echo
echo "    ./run.sh"
echo