# downloader.py
import os
import zipfile
import requests
import threading
import hashlib
from PyQt6.QtCore import QObject, pyqtSignal
import shutil
from http.client import IncompleteRead
from urllib3.exceptions import ProtocolError
from requests.exceptions import ChunkedEncodingError, ConnectionError
import json
import time
from urllib.parse import urlsplit, urlunsplit, quote
import requests


import requests.adapters

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
session.mount("http://", adapter)
session.mount("https://", adapter)


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
    progress = pyqtSignal(int)
    speed = pyqtSignal(str)
    eta = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.pause_event = threading.Event()
        self.cancel_event = threading.Event()

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


def find_launcher_exe(install_dir: str) -> str:
    launcher_names = ("launcher.exe", "launcher1.exe")

    for root, _, files in os.walk(install_dir):
        for fn in files:
            if fn.lower() in launcher_names:
                return os.path.join(root, fn)

    return ""

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
def _normalize_name(name: str) -> str:
    import re
    name = os.path.splitext(name)[0]  # remove extensão se vier
    name = name.lower().strip()
    name = re.sub(r'[\s_\-]+', '', name)
    return name

def validate_game_files(install_dir: str) -> None:
    exe_found = False

    for root, _, files in os.walk(install_dir):
        for f in files:
            if f.lower().endswith(".exe"):
                exe_found = True
                break

    if not exe_found:
        raise Exception(
            "A instalação do jogo está incompleta.\n\n"
            "Nenhum executável foi encontrado.\n"
            "Tente baixar novamente."
        )

def find_main_exe(install_dir: str) -> str:
    ignore_keywords = (
        "unins", "uninstall", "setup", "installer", "install",
        "vcredist", "dxsetup", "crashreport", "ucrt",
        "unitycrashhandler", "launcher", "socialclub", "rockstar"
    )
    ignore_exact = {"steam.exe", "epicgameslauncher.exe"}

    folder_name = os.path.basename(os.path.normpath(install_dir))
    folder_name_norm = _normalize_name(folder_name)

    exact_match_candidates = []
    fallback_candidates = []
    launcher_candidates = []

    for root, _, files in os.walk(install_dir):
        for fn in files:
            if not fn.lower().endswith(".exe"):
                continue

            low = fn.lower()

            if low in ignore_exact:
                continue

            full = os.path.join(root, fn)

            try:
                size = os.path.getsize(full)
            except Exception:
                size = 0

            if size < 20 * 1024:
                continue

            rel = os.path.relpath(full, install_dir)
            depth = rel.count(os.sep)
            exe_name_norm = _normalize_name(fn)

            item = (depth, size, full)

            # 1) prioridade máxima: nome do exe = nome da pasta
            if exe_name_norm == folder_name_norm:
                exact_match_candidates.append(item)
                continue

            # 2) launchers / socialclub / rockstar ficam como último recurso
            if any(k in low for k in ignore_keywords):
                launcher_candidates.append(item)
                continue

            # 3) exe normal vira fallback padrão
            fallback_candidates.append(item)

    # prioridade 1: nome igual ao da pasta
    if exact_match_candidates:
        exact_match_candidates.sort(key=lambda x: (x[0], -x[1]))
        return exact_match_candidates[0][2]

    # prioridade 2: exe normal mais próximo da raiz e maior
    if fallback_candidates:
        fallback_candidates.sort(key=lambda x: (x[0], -x[1]))
        return fallback_candidates[0][2]

    # prioridade 3: launcher como último recurso
    if launcher_candidates:
        launcher_candidates.sort(key=lambda x: (x[0], -x[1]))
        return launcher_candidates[0][2]

    return ""


# =========================
# DOWNLOAD + EXTRACT
# =========================

def _normalize_download_url(url: str) -> str:
    parts = urlsplit(url)
    safe_path = quote(parts.path, safe="/-_.()")
    return urlunsplit((parts.scheme, parts.netloc, safe_path, parts.query, parts.fragment))

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


def _meta_path_for(temp_zip_path: str) -> str:
    return temp_zip_path + ".meta"


def _load_meta(meta_path: str) -> dict:
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_meta(meta_path: str, data: dict) -> None:
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _delete_file_silent(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _server_supports_resume(url: str) -> bool:
    try:
        r = session.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Encoding": "identity",
                "Range": "bytes=0-0"
            },
            stream=True,
            timeout=(15, 30),
            allow_redirects=True
        )
        try:
            content_range = r.headers.get("Content-Range", "")
            accept_ranges = r.headers.get("Accept-Ranges", "")
            return (
                r.status_code == 206
                or "bytes" in accept_ranges.lower()
                or content_range.startswith("bytes ")
            )
        finally:
            r.close()
    except Exception:
        return False

def wait_file_ready(path: str, timeout=10):
    import time

    for _ in range(timeout):
        try:
            with open(path, 'rb'):
                return True
        except:
            time.sleep(1)

    return False

def check_required_files(install_dir: str, required_files: list):
    missing = []

    for f in required_files:
        full = os.path.join(install_dir, f)
        if not os.path.exists(full):
            missing.append(f)

    if missing:
        raise Exception(
            "Arquivos essenciais não encontrados:\n\n" +
            "\n".join(missing) +
            "\n\nTente reinstalar o jogo."
        )

def clear_install_dir(install_dir: str) -> None:
    if not os.path.exists(install_dir):
        return

    for name in os.listdir(install_dir):
        full = os.path.join(install_dir, name)
        try:
            if os.path.isdir(full):
                shutil.rmtree(full)
            else:
                os.remove(full)
        except Exception:
            pass

def _format_eta(seconds: float) -> str:
    try:
        seconds = int(seconds)
    except Exception:
        return "calculando..."

    if seconds <= 0:
        return "menos de 1 min"

    minutes = seconds // 60
    hours = minutes // 60

    if hours > 0:
        rem_min = minutes % 60
        return f"{hours}h {rem_min}min"

    if minutes > 0:
        return f"{minutes} min"

    return "menos de 1 min"

class DownloadCancelled(Exception):
    pass

def resolve_exe_principal(install_dir: str, exe_principal: str) -> str:
    exe_principal = (exe_principal or "").strip()
    if not exe_principal:
        return ""

    exe_manual = os.path.normpath(exe_principal)
    exe_manual_path = os.path.normpath(os.path.join(install_dir, exe_manual))

    if os.path.exists(exe_manual_path):
        return exe_manual_path

    target_name = os.path.basename(exe_manual).lower()

    for root, _, files in os.walk(install_dir):
        for fn in files:
            if fn.lower() == target_name:
                return os.path.join(root, fn)

    return ""

def baixar_jogo(game_name: str, download_url: str, card=None, exe_principal="") -> DownloadSignals:
    signals = DownloadSignals()
    signals.pause_event.clear()
    signals.cancel_event.clear()
    download_url = _normalize_download_url(download_url)

    def _current_games_dir() -> str:
        path = get_install_root()
        os.makedirs(path, exist_ok=True)
        return path

    def run():
        max_attempts = 5

        try:
            safe_name = "".join(c for c in game_name if c not in r'\/:*?"<>|').strip()
            if not safe_name:
                raise Exception("Nome do jogo inválido.")

            games_dir = _current_games_dir()

            install_dir = os.path.join(games_dir, safe_name)
            os.makedirs(install_dir, exist_ok=True)

            try:
                os.system(f'attrib +h "{games_dir}"')
            except Exception:
                pass

            try:
                os.system(f'attrib +h "{install_dir}"')
            except Exception:
                pass

            temp_zip = os.path.join(games_dir, f"{safe_name}.zip.part")
            final_zip = os.path.join(games_dir, f"{safe_name}.zip")
            meta_path = _meta_path_for(temp_zip)

            def cleanup_cancelled_files():
                time.sleep(0.2)

                _delete_file_silent(temp_zip)
                _delete_file_silent(final_zip)
                _delete_file_silent(meta_path)

                try:
                    if os.path.isdir(install_dir):
                        shutil.rmtree(install_dir, ignore_errors=True)
                except Exception:
                    pass

            resume_supported = _server_supports_resume(download_url)

            for attempt in range(1, max_attempts + 1):
                try:
                    meta = _load_meta(meta_path)
                    total_length_meta = int(meta.get("total_size", 0) or 0)

                    downloaded_existing = 0
                    if os.path.exists(temp_zip):
                        downloaded_existing = os.path.getsize(temp_zip)

                    headers = {
                        "User-Agent": "Mozilla/5.0",
                        "Accept-Encoding": "identity"
                    }

                    if resume_supported and downloaded_existing > 0:
                        headers["Range"] = f"bytes={downloaded_existing}-"

                    signals.status.emit("baixando")

                    with session.get(
                            download_url,
                            stream=True,
                            timeout=(30, 3600),
                            headers=headers,
                            allow_redirects=True
                    ) as r:
                        r.raise_for_status()

                        is_partial = (r.status_code == 206)
                        content_length = int(r.headers.get("content-length") or 0)

                        # Se já existe parcial e o servidor não respondeu como parcial,
                        # NÃO zerar nem sobrescrever.
                        if downloaded_existing > 0 and not is_partial:
                            raise Exception(
                                "O servidor não aceitou retomar o download.\n\n"
                                "O progresso parcial foi mantido, mas este link não suportou continuação agora."
                            )

                        if is_partial:
                            total_length = downloaded_existing + content_length
                        else:
                            total_length = content_length

                        if total_length <= 0:
                            if total_length_meta > 0:
                                total_length = total_length_meta
                            else:
                                raise Exception("Não foi possível verificar o tamanho do arquivo.")

                        required_space = total_length * 2
                        if not has_enough_disk_space(install_dir, required_space):
                            free_space = shutil.disk_usage(install_dir).free
                            raise Exception(
                                f"Espaço insuficiente para instalar o jogo.\n\n"
                                f"Necessário: {required_space / (1024 ** 3):.2f} GB\n"
                                f"Disponível: {free_space / (1024 ** 3):.2f} GB"
                            )

                        _save_meta(meta_path, {
                            "game_name": safe_name,
                            "url": download_url,
                            "total_size": total_length,
                            "resume_supported": resume_supported,
                            "updated_at": int(time.time())
                        })

                        downloaded = downloaded_existing
                        last_pct = -1
                        write_mode = "ab" if (resume_supported and downloaded_existing > 0) else "wb"

                        last_speed_time = time.time()
                        last_speed_bytes = downloaded
                        speed_text = ""

                        with open(temp_zip, write_mode) as f:
                            flush_counter = 0

                            for chunk in r.iter_content(chunk_size=1024 * 1024):
                                if signals.cancel_event.is_set():
                                    signals.status.emit("cancelado")
                                    raise DownloadCancelled()

                                while signals.pause_event.is_set():
                                    signals.status.emit("pausado")
                                    time.sleep(0.3)

                                    if signals.cancel_event.is_set():
                                        signals.status.emit("cancelado")
                                        raise DownloadCancelled()

                                signals.status.emit("baixando")

                                if not chunk:
                                    continue

                                f.write(chunk)
                                downloaded += len(chunk)
                                flush_counter += len(chunk)

                                now = time.time()
                                elapsed = now - last_speed_time

                                if elapsed >= 1:
                                    bytes_diff = downloaded - last_speed_bytes
                                    speed_bps = bytes_diff / elapsed

                                    remaining_bytes = max(0, total_length - downloaded)

                                    if speed_bps > 0:
                                        eta_seconds = remaining_bytes / speed_bps
                                        eta_text = _format_eta(eta_seconds)
                                    else:
                                        eta_text = "calculando..."

                                    if speed_bps >= 1024 * 1024:
                                        speed_text = f"{speed_bps / (1024 * 1024):.1f} MB/s"
                                    else:
                                        speed_text = f"{speed_bps / 1024:.0f} KB/s"

                                    signals.speed.emit(speed_text)
                                    signals.eta.emit(eta_text)

                                    last_speed_time = now
                                    last_speed_bytes = downloaded

                                if flush_counter >= 16 * 1024 * 1024:
                                    f.flush()
                                    flush_counter = 0

                                pct = min(100, int(downloaded * 100 / total_length))
                                if pct != last_pct:
                                    last_pct = pct
                                    signals.progress.emit(pct)

                            f.flush()

                    real_size = os.path.getsize(temp_zip)

                    if real_size < total_length:
                        if attempt < max_attempts:
                            time.sleep(2)
                            continue

                        raise Exception(
                            "O download não foi concluído ainda, mas o progresso foi mantido.\n\n"
                            "Abra novamente o download para continuar de onde parou."
                        )

                    if real_size > total_length:
                        _delete_file_silent(temp_zip)
                        _delete_file_silent(meta_path)
                        raise Exception(
                            f"Arquivo parcial inválido: esperado {total_length} bytes, mas recebeu {real_size} bytes."
                        )

                    if os.path.exists(final_zip):
                        _delete_file_silent(final_zip)
                    os.replace(temp_zip, final_zip)

                    signals.speed.emit("")
                    signals.eta.emit("")
                    signals.status.emit("extraindo")

                    if not zipfile.is_zipfile(final_zip):
                        raise Exception("O arquivo baixado não é um ZIP válido ou está corrompido.")

                    clear_install_dir(install_dir)

                    with zipfile.ZipFile(final_zip, "r") as zf:
                        members = zf.infolist()
                        total_uncompressed = sum((m.file_size or 0) for m in members) or 1
                        extracted_bytes = 0
                        last_extract_pct = -1

                        for member in members:
                            zf.extract(member, install_dir)
                            extracted_bytes += (member.file_size or 0)

                            extract_pct = min(100, int(extracted_bytes * 100 / total_uncompressed))
                            if extract_pct != last_extract_pct:
                                last_extract_pct = extract_pct
                                signals.progress.emit(extract_pct)

                    signals.speed.emit("")
                    signals.speed.emit("")
                    signals.eta.emit("")
                    signals.status.emit("finalizando")

                    validate_game_files(install_dir)

                    required_files = []
                    check_required_files(install_dir, required_files)

                    _delete_file_silent(final_zip)
                    _delete_file_silent(meta_path)

                    # PRIORIDADE: exe_principal do admin
                    if exe_principal:
                        main_exe = resolve_exe_principal(install_dir, exe_principal)

                        if not main_exe:
                            raise Exception(
                                "Executável principal não encontrado.\n\n"
                                f"Cadastrado no admin:\n{exe_principal}\n\n"
                                f"Pasta instalada:\n{install_dir}"
                            )
                    else:
                        main_exe = find_main_exe(install_dir)

                        if main_exe and os.path.getsize(main_exe) < 500 * 1024:
                            raise Exception("Executável inválido detectado.")

                    launcher_exe = find_launcher_exe(install_dir)

                    if not main_exe:
                        signals.install_dir = install_dir
                        signals.exe_relpath = ""
                        signals.exe_enc_path = ""
                        signals.progress.emit(100)
                        signals.finished.emit()
                        return

                    exe_rel = os.path.relpath(main_exe, install_dir)

                    if launcher_exe:
                        signals.install_dir = install_dir
                        signals.exe_relpath = os.path.relpath(launcher_exe, install_dir)
                        signals.exe_enc_path = ""
                    else:
                        exe_enc_path = os.path.join(install_dir, exe_rel + ".primexenc")
                        os.makedirs(os.path.dirname(exe_enc_path), exist_ok=True)

                        encrypt_file_to(main_exe, exe_enc_path)

                        try:
                            os.remove(main_exe)
                        except Exception:
                            pass

                        signals.install_dir = install_dir
                        signals.exe_relpath = exe_rel
                        signals.exe_enc_path = exe_enc_path

                    signals.progress.emit(100)
                    signals.finished.emit()
                    return

                except DownloadCancelled:
                    signals.speed.emit("")
                    signals.eta.emit("")
                    cleanup_cancelled_files()
                    return

                except (IncompleteRead, ProtocolError, ChunkedEncodingError, ConnectionError):
                    if attempt < max_attempts:
                        time.sleep(2)
                        continue
                    raise Exception(
                        "O download foi interrompido antes de terminar.\n\n"
                        "A conexão com o servidor foi encerrada durante a transferência.\n"
                        "Abra novamente o download para continuar de onde parou."
                    )

                except Exception as e:
                    msg = str(e)

                    if "IncompleteRead" in msg or "Connection broken" in msg:
                        if attempt < max_attempts:
                            time.sleep(2)
                            continue
                        raise Exception(
                            "O download foi interrompido antes de terminar.\n\n"
                            "A conexão com o servidor foi encerrada durante a transferência.\n"
                            "Abra novamente o download para continuar de onde parou."
                        )

                    raise

        except Exception as e:
            signals.error.emit(str(e))

    threading.Thread(target=run, daemon=True).start()
    return signals
