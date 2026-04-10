import os
import json
import threading

from PyQt6.QtCore import QObject, pyqtSignal

from downloader import baixar_jogo


# =========================
# PATHS
# =========================
base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
GAMES_DIR = os.path.join(base_dir, "PrimeX", "games")
JSON_INSTALLED = os.path.join(GAMES_DIR, "instalados.json")


# =========================
# HELPERS
# =========================
def save_installed(data: dict):
    os.makedirs(GAMES_DIR, exist_ok=True)
    with open(JSON_INSTALLED, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_installed():
    if not os.path.exists(JSON_INSTALLED):
        return {}

    try:
        with open(JSON_INSTALLED, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

        if isinstance(data, list):
            converted = {}
            for item in data:
                if not isinstance(item, dict):
                    continue

                nome = (item.get("nome") or item.get("title") or "").strip()
                if not nome:
                    continue

                converted[nome] = {
                    "install_dir": item.get("install_dir", ""),
                    "exe": item.get("exe", ""),
                    "exe_enc": item.get("exe_enc", ""),
                    "capa_url": item.get("capa_url", ""),
                    "genero": item.get("genero", []),
                    "descricao": item.get("descricao", "")
                }

            save_installed(converted)
            return converted

        return {}

    except Exception:
        return {}


def _normalize_exe_name(name: str) -> str:
    import re
    name = os.path.splitext(name)[0]
    name = name.lower().strip()
    name = re.sub(r'[\s_\-]+', '', name)
    return name


def find_best_exe_by_folder_name(install_dir: str) -> str:
    ignore_keywords = [
        "unins", "uninstall", "setup", "install", "installer",
        "dxsetup", "directx", "vcredist", "redist", "redistributable",
        "crashreport", "launcher", "updater", "rockstar", "socialclub",
        "unitycrashhandler", "ucrt"
    ]

    folder_name = os.path.basename(os.path.normpath(install_dir))
    folder_name_norm = _normalize_exe_name(folder_name)

    exact_candidates = []
    fallback_candidates = []

    for root, _, files in os.walk(install_dir):
        for fn in files:
            if not fn.lower().endswith(".exe"):
                continue

            low = fn.lower()
            if any(k in low for k in ignore_keywords):
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
            exe_name_norm = _normalize_exe_name(fn)

            item = (depth, size, rel)

            if exe_name_norm == folder_name_norm:
                exact_candidates.append(item)
            else:
                fallback_candidates.append(item)

    if exact_candidates:
        exact_candidates.sort(key=lambda x: (x[0], -x[1]))
        return exact_candidates[0][2]

    if fallback_candidates:
        fallback_candidates.sort(key=lambda x: (x[0], -x[1]))
        return fallback_candidates[0][2]

    return ""


def exe_saved_is_suspicious(exe_rel: str) -> bool:
    if not exe_rel:
        return True

    low = exe_rel.lower().replace("\\", "/")

    # launchers que a PrimeX escolheu de propósito são válidos
    allowed_launchers = (
        "launcher.exe",
        "launcher1.exe",
    )

    if low.endswith(allowed_launchers):
        return False

    bad_keywords = [
        "rockstar", "socialclub", "setup", "install",
        "unins", "uninstall", "updater", "crashreport",
        "dxsetup", "vcredist", "redistributable"
    ]
    return any(k in low for k in bad_keywords)
# =========================
# DOWNLOAD MANAGER
# =========================
class DownloadManager(QObject):
    download_updated = pyqtSignal(str, dict)   # game_name, dados
    download_finished = pyqtSignal(str)
    download_error = pyqtSignal(str, str)
    queue_updated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.downloads = {}
        self.queue = []
        self.current_download = None
        self.current_signals = None
        self._lock = threading.Lock()

    def enqueue_download(self, game_name: str, download_url: str, image_url: str = "", genres=None, descricao=""):
        with self._lock:
            # evita duplicar se já está em andamento/fila
            if game_name in self.downloads:
                status = self.downloads[game_name].get("status")
                if status in ("na_fila", "baixando", "extraindo", "instalando"):
                    return

            # se já estava concluído e quer baixar de novo, reseta
            self.downloads[game_name] = {
                "game_name": game_name,
                "download_url": download_url,
                "image_url": image_url,
                "genres": genres or [],
                "descricao": descricao or "",
                "progress": 0,
                "status": "na_fila",
                "error": "",
                "install_dir": "",
                "exe": "",
                "exe_enc": "",
            }

            if game_name not in self.queue:
                self.queue.append(game_name)

        self.queue_updated.emit()
        self._process_queue()

    def _process_queue(self):
        with self._lock:
            if self.current_download is not None:
                return

            if not self.queue:
                return

            game_name = self.queue.pop(0)
            item = self.downloads.get(game_name)

            if not item:
                self.current_download = None
                self.queue_updated.emit()
                return

            self.current_download = game_name
            item["status"] = "baixando"
            item["progress"] = int(item.get("progress", 0) or 0)
            current_item = dict(item)

        self.queue_updated.emit()
        self.download_updated.emit(game_name, current_item)

        try:
            signals = baixar_jogo(game_name, current_item["download_url"])
        except Exception as e:
            self._on_error(game_name, f"Erro ao iniciar download: {e}")
            return
        self.current_signals = signals

        signals.progress.connect(lambda pct, g=game_name: self._on_progress(g, pct))
        signals.finished.connect(lambda g=game_name, s=signals: self._on_finished(g, s))
        signals.error.connect(lambda msg, g=game_name: self._on_error(g, msg))
        signals.status.connect(lambda status, g=game_name: self._on_status(g, status))

    def _on_progress(self, game_name: str, pct: int):
        with self._lock:
            if game_name not in self.downloads:
                return

            self.downloads[game_name]["progress"] = max(0, min(100, int(pct)))

            # só força "baixando" se ainda estiver em fila ou já baixando;
            # não sobrescreve "extraindo" / "finalizando"
            current_status = self.downloads[game_name].get("status", "")
            if current_status in ("", "na_fila", "baixando"):
                self.downloads[game_name]["status"] = "baixando"

            item = dict(self.downloads[game_name])

        self.download_updated.emit(game_name, item)

    def _on_status(self, game_name: str, status: str):
        with self._lock:
            if game_name not in self.downloads:
                return

            self.downloads[game_name]["status"] = status
            item = dict(self.downloads[game_name])

        self.download_updated.emit(game_name, item)

    def _save_finished_install(self, game_name: str, signals):
        install_dir = os.path.normpath(signals.install_dir or os.path.join(GAMES_DIR, game_name))

        exe_rel = getattr(signals, "exe_relpath", "") or ""
        exe_enc = getattr(signals, "exe_enc_path", "") or ""

        low = exe_rel.lower().replace("\\", "/")

        # se o downloader escolheu launcher explícito, respeita
        launcher_escolhido = low.endswith("launcher.exe") or low.endswith("launcher1.exe")

        if not launcher_escolhido:
            if not exe_rel or exe_saved_is_suspicious(exe_rel):
                fixed_exe_rel = find_best_exe_by_folder_name(install_dir)
                if fixed_exe_rel:
                    exe_rel = fixed_exe_rel
                    exe_enc = ""

        current = self.downloads.get(game_name, {})

        data = load_installed()
        data[game_name] = {
            "install_dir": install_dir,
            "exe": exe_rel,
            "exe_enc": exe_enc,
            "capa_url": current.get("image_url", "") or "",
            "genero": current.get("genres", []) or [],
            "descricao": current.get("descricao", "") or ""
        }
        save_installed(data)

        return install_dir, exe_rel, exe_enc

    def _on_finished(self, game_name: str, signals):
        with self._lock:
            item = self.downloads.get(game_name, {})
            if game_name in self.downloads:
                self.downloads[game_name]["status"] = "instalando"
                self.downloads[game_name]["progress"] = 100
                item = dict(self.downloads[game_name])

        self.download_updated.emit(game_name, item)

        try:
            install_dir, exe_rel, exe_enc = self._save_finished_install(game_name, signals)

            with self._lock:
                if game_name in self.downloads:
                    self.downloads[game_name]["install_dir"] = install_dir
                    self.downloads[game_name]["exe"] = exe_rel
                    self.downloads[game_name]["exe_enc"] = exe_enc
                    self.downloads[game_name]["progress"] = 100
                    self.downloads[game_name]["status"] = "concluido"
                    self.downloads[game_name]["error"] = ""
                    item = dict(self.downloads[game_name])
                else:
                    item = {}

                self.current_download = None
                self.current_signals = None

            self.download_updated.emit(game_name, item)
            self.download_finished.emit(game_name)
            self.queue_updated.emit()
            self._process_queue()

        except Exception as e:
            self._on_error(game_name, f"Falha ao finalizar instalação: {e}")

    def _on_error(self, game_name: str, msg: str):
        with self._lock:
            if game_name in self.downloads:
                self.downloads[game_name]["status"] = "erro"
                self.downloads[game_name]["error"] = str(msg)
                item = dict(self.downloads[game_name])
            else:
                item = {}

            self.current_download = None
            self.current_signals = None

        self.download_updated.emit(game_name, item)
        self.download_error.emit(game_name, str(msg))
        self.queue_updated.emit()
        self._process_queue()

    def get_download(self, game_name: str) -> dict:
        with self._lock:
            return dict(self.downloads.get(game_name, {}))

    def get_all_downloads(self) -> list:
        with self._lock:
            return [dict(v) for v in self.downloads.values()]

    def get_queue(self) -> list:
        with self._lock:
            return list(self.queue)

    def is_downloading(self, game_name: str) -> bool:
        with self._lock:
            if game_name not in self.downloads:
                return False
            return self.downloads[game_name].get("status") in (
                "na_fila", "baixando", "extraindo", "finalizando", "instalando"
            )

    def remove_download(self, game_name: str):
        with self._lock:
            if game_name == self.current_download:
                return

            if game_name in self.queue:
                self.queue.remove(game_name)

            if game_name in self.downloads:
                del self.downloads[game_name]

        self.queue_updated.emit()

    def retry_download(self, game_name: str):
        with self._lock:
            item = self.downloads.get(game_name)
            if not item:
                return

            if game_name == self.current_download:
                return

            item["status"] = "na_fila"
            item["error"] = ""
            item["progress"] = 0

            if game_name not in self.queue:
                self.queue.append(game_name)

        self.queue_updated.emit()
        self._process_queue()


download_manager = DownloadManager()