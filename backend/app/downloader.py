# downloader.py
import os
import zipfile
import requests
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


# =========================
# DOWNLOAD + EXTRACT
# =========================
def baixar_jogo(game_name: str, download_url: str, card=None) -> DownloadSignals:
    """
    Baixa e instala o jogo (ZIP) em:
      %LOCALAPPDATA%\\PrimeX\\games\\<game_name>\\

    Retorna signals:
      - progress(int)
      - finished()
      - error(str)

    Obs: se o servidor mandar .rar/.7z/.exe etc, vai dar erro ao extrair (não é zip).
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
            with requests.get(download_url, stream=True, timeout=60) as r:
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

            # --- valida zip ---
            # se não for zip, zipfile vai estourar
            with zipfile.ZipFile(temp_zip, "r") as zf:
                zf.extractall(install_dir)

            # --- cleanup ---
            try:
                os.remove(temp_zip)
            except Exception:
                pass

            # botão mudar pra JOGAR (opcional)
                try:
                    card.set_playable()
                except Exception:
                    pass

            signals.progress.emit(100)
            signals.finished.emit()

        except Exception as e:
            signals.error.emit(str(e))

    # thread simples (sem travar UI)
    import threading
    threading.Thread(target=run, daemon=True).start()
    return signals
