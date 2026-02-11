# downloader.py
import os
import zipfile
import requests
import threading
import hashlib
from PyQt6.QtCore import QObject, pyqtSignal


# =========================
# PASTAS (mesmo padrão do explore_page.py)
# =========================
BASE_DIR = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
GAMES_DIR = os.path.join(BASE_DIR, "PrimeX", "games")
os.makedirs(GAMES_DIR, exist_ok=True)


# =========================
# SIGNALS
# =========================
class DownloadSignals(QObject):
    progress = pyqtSignal(int)   # 0..100
    finished = pyqtSignal()
    error = pyqtSignal(str)

    # Informações do resultado (preenchidas ao finalizar com sucesso)
    install_dir: str = ""
    exe_relpath: str = ""
    exe_enc_path: str = ""


# =========================
# UTIL: chave simples por máquina (obfuscation)
# =========================
def _machine_key() -> bytes:
    """
    Gera uma chave baseada no usuário/máquina.
    Não é DRM "forte", mas impede executar o jogo fora do launcher
    porque o .exe não fica disponível em claro.
    """
    base = (os.getenv("COMPUTERNAME", "") + "|" + os.getenv("USERNAME", "") + "|PrimeX_v1").encode("utf-8", "ignore")
    return hashlib.sha256(base).digest()


def _xor_crypt(data: bytes, key: bytes) -> bytes:
    out = bytearray(len(data))
    klen = len(key)
    for i, b in enumerate(data):
        out[i] = b ^ key[i % klen]
    return bytes(out)


def encrypt_file_to(src_path: str, dst_path: str) -> None:
    key = _machine_key()
    with open(src_path, "rb") as f:
        raw = f.read()
    enc = _xor_crypt(raw, key)
    with open(dst_path, "wb") as f:
        f.write(enc)


def decrypt_file_to(src_path: str, dst_path: str) -> None:
    # XOR é simétrico
    key = _machine_key()
    with open(src_path, "rb") as f:
        enc = f.read()
    raw = _xor_crypt(enc, key)
    with open(dst_path, "wb") as f:
        f.write(raw)


# =========================
# UTIL: detectar exe principal
# =========================
def find_main_exe(install_dir: str) -> str:
    """
    Procura o .exe principal pelo maior tamanho.
    Ignora executáveis comuns que não são o jogo.
    Retorna caminho absoluto do exe encontrado ou "".
    """
    ignore_prefixes = (
        "unins", "uninstall", "setup", "installer", "install",
        "vcredist", "dxsetup", "crashreport", "ucrt", "unitycrashhandler"
    )
    ignore_exact = {"launcher.exe", "steam.exe", "epicgameslauncher.exe"}

    candidates = []

    for root, _, files in os.walk(install_dir):
        for fn in files:
            if not fn.lower().endswith(".exe"):
                continue

            low = fn.lower()
            if low in ignore_exact:
                continue
            if any(low.startswith(p) for p in ignore_prefixes):
                continue

            full = os.path.join(root, fn)
            try:
                size = os.path.getsize(full)
            except Exception:
                continue

            # ignora exe muito pequeno
            if size < 200 * 1024:
                continue

            candidates.append((size, full))

    if not candidates:
        return ""

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


# =========================
# DOWNLOAD + EXTRACT
# =========================
def baixar_jogo(game_name: str, download_url: str, card=None) -> DownloadSignals:
    """
    Baixa e instala o jogo (ZIP) em:
      %LOCALAPPDATA%\\PrimeX\\games\\<game_name>\\

    Depois:
      - detecta exe principal
      - remove o exe original
      - cria arquivo criptografado .primexenc no lugar

    Retorna signals:
      - progress(int)
      - finished()
      - error(str)

    No sucesso, preenche:
      signals.install_dir
      signals.exe_relpath
      signals.exe_enc_path
    """
    signals = DownloadSignals()

    def run():
        try:
            safe_name = "".join(c for c in game_name if c not in r'\/:*?"<>|').strip()
            if not safe_name:
                raise Exception("Nome do jogo inválido.")

            install_dir = os.path.join(GAMES_DIR, safe_name)
            os.makedirs(install_dir, exist_ok=True)

            temp_zip = os.path.join(GAMES_DIR, f"{safe_name}.zip")

            # --- download ---
            with requests.get(download_url, stream=True, timeout=120) as r:
                r.raise_for_status()

                total_length = int(r.headers.get("content-length") or 0)
                downloaded = 0
                last_pct = -1

                with open(temp_zip, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_length > 0:
                            pct = int(downloaded * 100 / total_length)
                            if pct != last_pct:
                                last_pct = pct
                                signals.progress.emit(pct)

            # --- valida zip e extrai ---
            with zipfile.ZipFile(temp_zip, "r") as zf:
                zf.extractall(install_dir)

            # --- remove zip temporário ---
            try:
                os.remove(temp_zip)
            except Exception:
                pass

            # --- detectar exe principal ---
            main_exe = find_main_exe(install_dir)
            if not main_exe:
                # Não trava o jogo se não achar exe (pode ser emulador, etc)
                # mas devolve infos vazias
                signals.install_dir = install_dir
                signals.exe_relpath = ""
                signals.exe_enc_path = ""
                signals.progress.emit(100)
                signals.finished.emit()
                return

            # --- criptografar e remover exe original ---
            exe_rel = os.path.relpath(main_exe, install_dir)
            exe_enc_path = os.path.join(install_dir, exe_rel + ".primexenc")

            # garante diretório (se exe estiver em subpasta)
            os.makedirs(os.path.dirname(exe_enc_path), exist_ok=True)

            encrypt_file_to(main_exe, exe_enc_path)

            # remove exe original
            try:
                os.remove(main_exe)
            except Exception:
                # se não conseguir remover, pelo menos não quebra o fluxo
                pass

            # --- preencher infos ---
            signals.install_dir = install_dir
            signals.exe_relpath = exe_rel
            signals.exe_enc_path = exe_enc_path

            signals.progress.emit(100)
            signals.finished.emit()

        except Exception as e:
            signals.error.emit(str(e))

    threading.Thread(target=run, daemon=True).start()
    return signals
