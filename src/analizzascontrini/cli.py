import sys
import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent


def run_worker():
    """Avvia il worker di elaborazione"""
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "analizzascontrini.scripts.worker",
        *sys.argv[1:],
    ]

    subprocess.run(cmd, check=True)


def run_webui():
    """Avvia il server Django (manage.py)"""
    webui_dir = BASE_DIR / "webui"
    manage_py = webui_dir / "manage.py"

    os.chdir(webui_dir)

    cmd = [
        sys.executable,
        "-u",
        str(manage_py),
        *sys.argv[1:],
    ]

    subprocess.run(cmd, check=True)

