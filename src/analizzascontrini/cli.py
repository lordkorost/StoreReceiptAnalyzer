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

# import sys
# import os
# import subprocess
# from pathlib import Path

# # La cartella che contiene questo file è 'src/analizzascontrini'
# BASE_DIR = Path(__file__).parent

# def run_worker():
#     """Avvia il worker di elaborazione"""
#     worker_path = BASE_DIR / "scripts" / "worker.py"
    
#     # Costruiamo il comando: python worker.py [eventuali argomenti extra]
#     cmd = [sys.executable, str(worker_path)] + sys.argv[1:]
    
#     # Eseguiamo il processo e mostriamo l'output a schermo
#     subprocess.run(cmd)

# def run_webui():
#     """Avvia il server Django (manage.py)"""
#     webui_dir = BASE_DIR / "webui"
#     manage_py = webui_dir / "manage.py"
    
#     # Cambiamo la directory di lavoro in webui, esattamente come fa Django
#     os.chdir(webui_dir)
    
#     # Costruiamo il comando: python manage.py [argomenti passati, es: runserver 0.0.0.0:8000]
#     # sys.argv[0] è 'as-webui', quindi prendiamo sys.argv[1:] per passare il resto
#     cmd = [sys.executable, str(manage_py)] + sys.argv[1:]
    
#     # Eseguiamo il processo e mostriamo l'output a schermo
#     subprocess.run(cmd)