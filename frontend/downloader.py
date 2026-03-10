# downloader.py
import os
import zipfile
import requests
import threading
import hashlib
from PyQt6.QtCore import QObject, pyqtSignal
import shutil


# =========================
# PASTAS (mesmo padrão do explore_page.py)
# =========================
from install_config import get_install_root

GAMES_DIR = get_install_root()
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
                size = 0

            # ✅ NÃO descarta exe pequeno (só ignora lixo MUITO pequeno)
            if size < 20 * 1024:   # 20 KB
                continue

            candidates.append((size, full))

    if not candidates:
        return ""

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]



# =========================
# DOWNLOAD + EXTRACT
# =========================

def has_enough_disk_space(target_path: str, required_bytes: int) -> bool:
    """
    Verifica se há espaço livre suficiente no disco da pasta alvo.
    """
    base_path = target_path
    while base_path and not os.path.exists(base_path):
        parent = os.path.dirname(base_path)
        if parent == base_path:
            break
        base_path = parent

    if not base_path or not os.path.exists(base_path):
        base_path = os.path.abspath(os.sep)

    usage = shutil.disk_usage(base_path)
    return usage.free >= required_bytes

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

            try:
                os.system(f'attrib +h "{GAMES_DIR}"')
            except Exception:
                pass

            try:
                os.system(f'attrib +h "{install_dir}"')
            except Exception:
                pass

            temp_zip = os.path.join(GAMES_DIR, f"{safe_name}.zip")

            # --- download ---
            with requests.get(download_url, stream=True, timeout=(30, 600)) as r:
                r.raise_for_status()

                total_length = int(r.headers.get("content-length") or 0)

                # --- verifica espaço antes de baixar ---
                if total_length <= 0:
                    raise Exception(
                        "Não foi possível verificar o tamanho do arquivo. O servidor não enviou Content-Length.")

                required_space = total_length * 2
                if not has_enough_disk_space(install_dir, required_space):
                    free_space = shutil.disk_usage(install_dir).free
                    raise Exception(
                        f"Espaço insuficiente para instalar o jogo.\n\n"
                        f"Necessário: {required_space / (1024 ** 3):.2f} GB\n"
                        f"Disponível: {free_space / (1024 ** 3):.2f} GB"
                    )

                downloaded = 0
                last_pct = -1

                with open(temp_zip, "wb") as f:
                    for chunk in r.iter_content(chunk_size=4 * 1024 * 1024):
                        if not chunk:
                            continue

                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_length > 0:
                            pct = min(100, int(downloaded * 100 / total_length))
                            if pct != last_pct:
                                last_pct = pct
                                signals.progress.emit(pct)

            # --- valida tamanho do arquivo baixado ---
            if total_length > 0:
                real_size = os.path.getsize(temp_zip)
                if real_size != total_length:
                    raise Exception(
                        f"Download incompleto: esperado {total_length} bytes, recebido {real_size} bytes."
                    )

            # --- valida se o arquivo é ZIP válido ---
            if not zipfile.is_zipfile(temp_zip):
                raise Exception("O arquivo baixado não é um ZIP válido ou está corrompido.")

            # --- extrai ZIP ---
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
