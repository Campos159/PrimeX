import os
import shutil
import threading
import requests
import zipfile
from PyQt6.QtWidgets import QMessageBox

# Pasta base dos jogos
GAMES_DIR = os.path.join(os.getcwd(), "games")
os.makedirs(GAMES_DIR, exist_ok=True)

def baixar_jogo(game_name: str, download_url: str, card=None):
    """
    Baixa e instala o jogo a partir de arquivo ZIP.
    game_name: nome do jogo (será nome da pasta)
    download_url: link do backend para download
    card: GameCard opcional para atualizar botão
    """
    try:
        os.makedirs(GAMES_DIR, exist_ok=True)
        temp_zip = os.path.join(GAMES_DIR, f"{game_name}.zip")

        # Download do jogo
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(temp_zip, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    f.write(chunk)

        # Pasta do jogo
        install_dir = os.path.join(GAMES_DIR, game_name)
        os.makedirs(install_dir, exist_ok=True)

        # Extrai o ZIP
        try:
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                zip_ref.extractall(install_dir)
        except Exception as e:
            # Move o zip mesmo que falhe
            shutil.move(temp_zip, os.path.join(install_dir, f"{game_name}.zip"))
            raise e

        # Remove ZIP temporário
        if os.path.exists(temp_zip):
            os.remove(temp_zip)

        # Atualiza botão para JOGAR
        if card:
            card.set_playable()

        print(f"Jogo '{game_name}' instalado com sucesso!")

    except Exception as e:
        print(f"Erro ao baixar/instalar jogo '{game_name}': {e}")
        if card:
            QMessageBox.warning(card, "Erro", f"Falha ao instalar o jogo:\n{e}")

from PyQt6.QtCore import QObject, pyqtSignal

class DownloadSignals(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

def baixar_jogo(game_name: str, download_url: str, card=None):
    signals = DownloadSignals()

    def run():
        try:
            import requests, os, zipfile, shutil

            pasta_jogo = os.path.join(GAMES_DIR, game_name)
            os.makedirs(pasta_jogo, exist_ok=True)
            temp_zip = os.path.join(GAMES_DIR, f"{game_name}.zip")

            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                total_length = int(r.headers.get("content-length", 0))
                downloaded = 0

                with open(temp_zip, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_length > 0:
                                signals.progress.emit(int(downloaded / total_length * 100))

            with zipfile.ZipFile(temp_zip, "r") as zip_ref:
                zip_ref.extractall(pasta_jogo)

            if os.path.exists(temp_zip):
                os.remove(temp_zip)

            signals.finished.emit()

        except Exception as e:
            signals.error.emit(str(e))

    import threading
    threading.Thread(target=run, daemon=True).start()
    return signals
