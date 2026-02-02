import os
import sys
import time
import socket
import subprocess
import atexit

import httpx
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFontDatabase

# =========================================
# BASE DIR (DEV vs PyInstaller onefile)
# =========================================
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

# =========================================
# IMPORTANTÍSSIMO:
# Faz o Python enxergar /app como módulo
# (onde está downloader.py, main.py, etc)
# =========================================
APP_DIR = os.path.join(BASE_DIR, "app")
if os.path.isdir(APP_DIR) and APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Também mantém o BASE_DIR no path (assets, etc)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ✅ PRIMEIRA TELA (importa só depois do sys.path pronto)
from register import RegisterWindow
from api_config import API_BASE

# ===== Fonte =====
FONT_PATH = os.path.join(BASE_DIR, "assets", "fonts", "VT323-Regular.ttf")

# ===== Backend =====
HEALTH_URL = API_BASE


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def _kill_port_windows(port: int) -> bool:
    """
    Tenta matar o processo que está usando a porta (Windows).
    Retorna True se matou algo, False se não encontrou/não conseguiu.
    """
    if os.name != "nt":
        return False

    try:
        out = subprocess.check_output(
            ["cmd", "/c", f'netstat -ano | findstr :{port}'],
            text=True, errors="ignore"
        )
        pids = set()
        for line in out.splitlines():
            if "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit():
                    pids.add(int(pid))

        killed_any = False
        for pid in pids:
            subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            killed_any = True

        return killed_any
    except Exception:
        return False


def start_backend():
    """
    Sobe o uvicorn automaticamente.
    - No EXE: usa sys.executable (python embutido no PyInstaller)
    - Usa cwd=BASE_DIR (onde existe a pasta app/)
    """
    # Se a porta estiver ocupada, tenta matar no Windows (às vezes fica “preso”)
    if _is_port_open(BACKEND_HOST, BACKEND_PORT):
        _kill_port_windows(BACKEND_PORT)
        time.sleep(0.3)

    # Se ainda estiver ocupada, não inicia outro backend
    if _is_port_open(BACKEND_HOST, BACKEND_PORT):
        return None

    cmd = [
        sys.executable, "-m", "uvicorn",
        "main:app",                 # 👈 porque APP_DIR foi colocado no sys.path (app/main.py vira main)
        "--host", BACKEND_HOST,
        "--port", str(BACKEND_PORT),
        "--log-level", "warning",
    ]

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
        cwd=APP_DIR  # 👈 garante que o uvicorn acha main.py no diretório app
    )
    return proc


def wait_backend(timeout_sec=10):
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            r = httpx.get(HEALTH_URL, timeout=0.7)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def main():
    app = QApplication(sys.argv)

    # Fonte VT323
    if os.path.exists(FONT_PATH):
        QFontDatabase.addApplicationFont(FONT_PATH)

    backend_proc = start_backend()

    if backend_proc is not None:
        def _stop_backend(p):
            try:
                if os.name == "nt":
                    subprocess.call(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    p.terminate()
            except Exception:
                pass

        atexit.register(lambda: _stop_backend(backend_proc))

    if not wait_backend():
        # se o backend iniciou mas não respondeu, captura stderr para ajudar
        extra = ""
        if backend_proc is not None:
            try:
                err = backend_proc.stderr.read().decode(errors="ignore")[:1200]
                if err.strip():
                    extra = "\n\nDETALHES:\n" + err
            except Exception:
                pass

        QMessageBox.critical(
            None,
            "Erro",
            "Não foi possível iniciar o servidor interno (backend).\n"
            "Verifique se a porta 8000 está livre e tente novamente."
            + extra
        )

        if backend_proc is not None:
            try:
                backend_proc.terminate()
            except Exception:
                pass
        sys.exit(1)

    # ✅ Abre REGISTRO primeiro
    w = RegisterWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
