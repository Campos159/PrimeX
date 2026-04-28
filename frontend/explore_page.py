import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QGridLayout, QSizePolicy, QMessageBox, QDialog, QTextEdit
)
from PyQt6.QtCore import Qt, QSize, QRunnable, QThreadPool, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QPainter, QPainterPath
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtGui import QPixmap, QIcon, QColor, QLinearGradient
from PyQt6.QtCore import QRectF
from PyQt6.QtCore import Qt, QSize
from profile import ProfilePage
from navbar import NavBar
from downloader import decrypt_file_to, wait_file_ready
from filter_bar import FilterBar
from PyQt6.QtGui import QFontDatabase
from api_config import API_BASE
import hashlib
import requests
from PyQt6.QtWidgets import QGraphicsOpacityEffect
from PyQt6.QtCore import QPropertyAnimation
from PyQt6.QtWidgets import QScrollArea
from utils import resource_path
from session import load_session
from PyQt6.QtGui import QFont
from download_manager import download_manager
import platform
import shutil
import subprocess
import re
import psutil
from PyQt6.QtGui import QShortcut, QKeySequence



FONT_PATH = resource_path(os.path.join("fonts", "VT323-Regular.ttf"))


# Pastas/arquivos
base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
GAMES_DIR = os.path.join(base_dir, "PrimeX", "games")
JSON_INSTALLED = os.path.join(GAMES_DIR, "instalados.json")


def save_installed(data: dict):
    os.makedirs(GAMES_DIR, exist_ok=True)
    with open(JSON_INSTALLED, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def mark_installed(game_title: str, install_dir: str, exe_name: str = "", capa_url: str = "", genero=None):
    data = load_installed()
    data[game_title] = {
        "install_dir": install_dir,
        "exe": exe_name,
        "capa_url": capa_url or "",
        "genero": genero or []
    }
    save_installed(data)


def find_best_exe(install_dir: str) -> str:
    """
    Encontra automaticamente o melhor .exe dentro da pasta do jogo e retorna o CAMINHO RELATIVO.
    Regras:
    - ignora uninstall/installer/setup/redistributable
    - prioriza exe na raiz
    - prioriza exe maior (geralmente é o jogo)
    """
    ignore_keywords = [
        "unins", "uninstall", "setup", "install", "installer",
        "dxsetup", "directx", "vcredist", "redist", "redistributable",
        "crashreport", "launcher", "updater"
    ]

    candidates = []
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

            rel = os.path.relpath(full, install_dir)

            # score: exe na raiz ganha bônus
            depth = rel.count(os.sep)
            root_bonus = 2 if depth == 0 else 0

            candidates.append((root_bonus, size, rel))

    if not candidates:
        return ""

    # maior root_bonus, depois maior tamanho
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


import re


def _normalize_exe_name(name: str) -> str:
    name = os.path.splitext(name)[0]
    name = name.lower().strip()
    name = re.sub(r'[\s_\-]+', '', name)
    return name


def find_best_exe_by_folder_name(install_dir: str) -> str:
    """
    Procura primeiro um .exe com nome igual ao da pasta do jogo.
    Se não achar, usa fallback inteligente.
    Retorna CAMINHO RELATIVO ao install_dir.
    """
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

            # prioridade máxima: nome do exe = nome da pasta
            if exe_name_norm == folder_name_norm:
                exact_candidates.append(item)
            else:
                fallback_candidates.append(item)

    if exact_candidates:
        # mais perto da raiz, depois maior
        exact_candidates.sort(key=lambda x: (x[0], -x[1]))
        return exact_candidates[0][2]

    if fallback_candidates:
        # mais perto da raiz, depois maior
        fallback_candidates.sort(key=lambda x: (x[0], -x[1]))
        return fallback_candidates[0][2]

    return ""


def exe_saved_is_suspicious(exe_rel: str) -> bool:
    if not exe_rel:
        return True

    low = exe_rel.lower().replace("\\", "/")

    # ✅ launchers válidos (NÃO são suspeitos)
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


def user_can_download(user_info: dict) -> bool:
    if not user_info:
        return False

    # se você salva isso no profile/session:
    if user_info.get("plan_active") is True:
        return True

    # fallback: se vier um campo texto do backend
    plano = str(user_info.get("plan", "")).upper().strip()
    return plano in ("ATIVO", "PERMANENTE")



def load_installed():
    if not os.path.exists(JSON_INSTALLED):
        return {}

    try:
        with open(JSON_INSTALLED, "r", encoding="utf-8") as f:
            data = json.load(f)

        # formato certo
        if isinstance(data, dict):
            return data

        # formato antigo: lista -> converte
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
            save_installed(converted)  # salva convertido
            return converted

        return {}

    except Exception:
        return {}




# =========================
# GAME CARD
# =========================

class ImageLoaderSignals(QObject):
    finished = pyqtSignal(str, bytes)


class ImageLoaderTask(QRunnable):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = ImageLoaderSignals()

    def run(self):
        data = b""

        if not self.url:
            self.signals.finished.emit(self.url, data)
            return

        try:
            base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
            cache_dir = os.path.join(base_dir, "PrimeX", "cache", "covers")
            os.makedirs(cache_dir, exist_ok=True)

            h = hashlib.md5(self.url.encode("utf-8")).hexdigest()
            cache_path = os.path.join(cache_dir, f"{h}.img")

            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                with open(cache_path, "rb") as f:
                    data = f.read()
            else:
                r = requests.get(self.url, timeout=8)
                r.raise_for_status()
                data = r.content

                with open(cache_path, "wb") as f:
                    f.write(data)

        except Exception as e:
            print("Erro ao carregar capa:", e)

        self.signals.finished.emit(self.url, data)

class GameCard(QWidget):
    def __init__(self, image_url, title_top, title_bottom, download_url, genres=None, user_info=None, descricao="", requisitos=None, exe_principal=""):

        super().__init__()

        self.requisitos = requisitos or {}

        # estado do usuário (vem do MainWindow)
        self.user_info = dict(user_info or {})

        # mescla sessão salva por cima (persistência)
        sess = load_session()
        if isinstance(sess, dict):
            self.user_info.update(sess)

        self.download_url = download_url
        self.game_title = f"{title_top} {title_bottom}".strip()
        self.image_url = image_url
        self.genres = genres or []
        self.descricao = descricao
        self.exe_principal = (exe_principal or "").strip()

        download_manager.download_updated.connect(self._on_global_download_updated)
        download_manager.download_finished.connect(self._on_global_download_finished)
        download_manager.download_error.connect(self._on_global_download_error)



        self.setFixedSize(260, 485)

        # ===== CARD ROOT =====
        self.setStyleSheet("""
        QWidget {
            background-color: #120f2a;
            border-radius: 16px;
            border: 2px solid #2a245f;
        }

        QWidget:hover {
            border: 2px solid #836FFF;
            background-color: #18134a;
        }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ===== IMAGE =====
        self.image_label = QLabel()
        self.image_label.setFixedSize(260, 210)
        self.image_label.setFixedHeight(210)
        self.image_label.setScaledContents(False)
        self.image_label.setStyleSheet("""
        QLabel {
            border-top-left-radius: 16px;
            border-top-right-radius: 16px;
        }
        """)

        self._original_pixmap = QPixmap()

        # placeholder leve enquanto a capa carrega
        self.image_label.setText("CARREGANDO...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
        QLabel {
            border-top-left-radius: 16px;
            border-top-right-radius: 16px;
            color: #836FFF;
            font-size: 18px;
            background-color: #120f2a;
        }
        """)



        root.addWidget(self.image_label)
        # ===== TITLE =====

        self.title_label = QLabel(self.game_title.upper())
        self.title_label.setFixedHeight(64)  # 2 linhas
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label.setStyleSheet("""
            color: #e0d9ff;
            font-size: 20px;
            letter-spacing: 1px;
            padding: 10px 12px;
            background-color: rgba(0,0,0,0.30);
        """)

        root.addWidget(self.title_label)

        # aplica texto com "..." se ficar grande
        self._update_title_text()

        # ===== BUTTONS =====
        btns = QVBoxLayout()
        btns.setContentsMargins(12, 10, 12, 14)
        btns.setSpacing(8)

        self.btn_install = QPushButton("INSTALAR")
        self.btn_install.setStyleSheet("""
        QPushButton {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #836FFF,
                stop:1 #4cc3ff
            );
            color: #0d0b1f;
            font-size: 18px;
            font-weight: bold;
            border-radius: 12px;
            padding: 12px;
        }

        QPushButton:hover {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #9a7dff,
                stop:1 #6fd4ff
            );
            box-shadow: 0 0 20px #836FFF;
        }
        """)

        self.btn_install.clicked.connect(self.install_game)

        self.btn_req = QPushButton("REQUISITOS")
        self.btn_req.setStyleSheet("""
        QPushButton {
            background-color: rgba(131,111,255,0.08);
            border: 1px solid #836FFF;
            color: #b9a9ff;
            font-size: 15px;
            border-radius: 10px;
            padding: 10px;
        }

        QPushButton:hover {
            background-color: #836FFF;
            color: #0d0b1f;
        }
        """)

        self.btn_req.clicked.connect(self.show_requirements)

        self.btn_uninstall = QPushButton("DESINSTALAR")
        self.btn_uninstall.setStyleSheet("""
        QPushButton {
            background-color: rgba(255, 85, 85, 0.12);
            border: 1px solid #ff5555;
            color: #ffb3b3;
            font-size: 15px;
            border-radius: 10px;
            padding: 10px;
        }
        QPushButton:hover {
            background-color: #ff5555;
            color: #0d0b1f;
        }
        """)
        self.btn_uninstall.clicked.connect(self.uninstall_game)

        btns.addWidget(self.btn_install)
        btns.addWidget(self.btn_req)
        btns.addWidget(self.btn_uninstall)

        # ✅ NÃO deixar o layout mudar:
        self.btn_uninstall.setEnabled(False)
        self.btn_uninstall.setText("DESINSTALAR")
        self.btn_uninstall.setEnabled(False)
        self.btn_uninstall.setStyleSheet("""
        QPushButton {
            background-color: rgba(255, 85, 85, 0.12);
            border: 1px solid #ff5555;
            color: #ffb3b3;
            font-size: 15px;
            border-radius: 10px;
            padding: 10px;
        }
        QPushButton:hover {
            background-color: #ff5555;
            color: #0d0b1f;
        }
        QPushButton:disabled {
            background-color: rgba(255, 85, 85, 0.06);
            border: 1px solid rgba(255, 85, 85, 0.35);
            color: rgba(255, 179, 179, 0.55);
        }
        """)

        root.addLayout(btns)


        dl = download_manager.get_download(self.game_title)
        if dl:
            self._on_global_download_updated(self.game_title, dl)

        if self.is_installed():
            self.set_playable()


    # =========================
    # MÉTODOS AUXILIARES
    # =========================

    def _get_pc_specs(self):
        specs = {
            "cpu": platform.processor() or "",
            "ram_gb": 0,
            "gpu": "",
            "system": platform.system(),
            "release": platform.release(),
        }

        try:
            specs["ram_gb"] = round(psutil.virtual_memory().total / (1024 ** 3))
        except Exception:
            specs["ram_gb"] = 0

        # CPU fallback
        if not specs["cpu"]:
            try:
                specs["cpu"] = platform.uname().processor or ""
            except Exception:
                pass

        # GPU via WMIC / PowerShell no Windows
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["wmic", "path", "win32_VideoController", "get", "name"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
                lines = [l for l in lines if l.lower() != "name"]
                if lines:
                    specs["gpu"] = lines[0]
        except Exception:
            pass

        return specs

    def _extract_drive_from_install_path(self):
        data = load_installed()
        info = data.get(self.game_title) or {}
        install_dir = (info.get("install_dir") or "").strip()

        if install_dir:
            drive = os.path.splitdrive(install_dir)[0]
            if drive:
                return drive + "\\"

        # fallback: pasta padrão atual do launcher
        if GAMES_DIR:
            drive = os.path.splitdrive(GAMES_DIR)[0]
            if drive:
                return drive + "\\"

        return os.path.abspath(os.sep)

    def _get_free_disk_gb(self):
        try:
            target_path = self._extract_drive_from_install_path()
            usage = shutil.disk_usage(target_path)
            return round(usage.free / (1024 ** 3))
        except Exception:
            return 0

    def _normalize_text(self, text):
        text = (text or "").lower().strip()
        text = re.sub(r"[\s_\-]+", "", text)
        return text

    def _basic_cpu_match(self, user_cpu: str, required_cpu: str):
        if not required_cpu:
            return None

        u = self._normalize_text(user_cpu)
        r = self._normalize_text(required_cpu)

        if not u:
            return None

        if r in u:
            return True

        cpu_order = ["i3", "i5", "i7", "i9", "ryzen3", "ryzen5", "ryzen7", "ryzen9"]

        def get_rank(text):
            for idx, item in enumerate(cpu_order):
                if item in text:
                    return idx
            return None

        user_rank = get_rank(u)
        req_rank = get_rank(r)

        if user_rank is not None and req_rank is not None:
            return user_rank >= req_rank

        return None

    def _basic_gpu_match(self, user_gpu: str, required_gpu: str):
        if not required_gpu:
            return None

        u = self._normalize_text(user_gpu)
        r = self._normalize_text(required_gpu)

        if not u:
            return None

        if r in u:
            return True

        # comparação simples por famílias comuns
        def extract_series(text):
            nums = re.findall(r"\d{3,4}", text)
            return int(nums[0]) if nums else None

        user_series = extract_series(u)
        req_series = extract_series(r)

        nvidia_family = any(x in u for x in ["gtx", "rtx"]) and any(x in r for x in ["gtx", "rtx"])
        amd_family = any(x in u for x in ["rx", "radeon"]) and any(x in r for x in ["rx", "radeon"])

        if user_series and req_series and (nvidia_family or amd_family):
            return user_series >= req_series

        return None

    def _analyze_pc_for_game(self):
        req = self.requisitos or {}
        min_req = req.get("min") or {}
        rec_req = req.get("rec") or {}

        specs = self._get_pc_specs()
        free_disk_gb = self._get_free_disk_gb()

        checks = []

        # RAM mínima
        min_ram = min_req.get("ram")
        if isinstance(min_ram, int) and min_ram > 0:
            checks.append({
                "label": "RAM mínima",
                "required": f"{min_ram} GB",
                "current": f"{specs['ram_gb']} GB",
                "ok": specs["ram_gb"] >= min_ram
            })

        # Armazenamento mínimo
        min_storage = min_req.get("storage")
        if isinstance(min_storage, int) and min_storage > 0:
            checks.append({
                "label": "Espaço livre",
                "required": f"{min_storage} GB",
                "current": f"{free_disk_gb} GB livres",
                "ok": free_disk_gb >= min_storage
            })

        # CPU mínima
        min_cpu = (min_req.get("cpu") or "").strip()
        if min_cpu:
            cpu_match = self._basic_cpu_match(specs["cpu"], min_cpu)
            checks.append({
                "label": "CPU mínima",
                "required": min_cpu,
                "current": specs["cpu"] or "Não detectada",
                "ok": cpu_match
            })

        # GPU mínima
        min_gpu = (min_req.get("gpu") or "").strip()
        if min_gpu:
            gpu_match = self._basic_gpu_match(specs["gpu"], min_gpu)
            checks.append({
                "label": "GPU mínima",
                "required": min_gpu,
                "current": specs["gpu"] or "Não detectada",
                "ok": gpu_match
            })

        failed = [c for c in checks if c["ok"] is False]
        unknown = [c for c in checks if c["ok"] is None]

        # Resultado geral
        if not checks:
            status = "uncertain"
            headline = "⚠️ Este jogo ainda não possui requisitos mínimos cadastrados."
        elif failed:
            status = "below_minimum"
            headline = "❌ Seu PC pode não rodar este jogo corretamente."
        elif unknown:
            status = "uncertain"
            headline = "⚠️ Não foi possível confirmar tudo com precisão, mas seu PC pode rodar."
        else:
            status = "ok"
            headline = "✅ Seu PC atende aos requisitos mínimos."

        # Recomendados
        recommendation_lines = []

        rec_ram = rec_req.get("ram")
        if isinstance(rec_ram, int) and rec_ram > 0:
            recommendation_lines.append(f"RAM recomendada: {rec_ram} GB")

        rec_storage = rec_req.get("storage")
        if isinstance(rec_storage, int) and rec_storage > 0:
            recommendation_lines.append(f"Espaço recomendado: {rec_storage} GB")

        rec_gpu = (rec_req.get("gpu") or "").strip()
        if rec_gpu:
            recommendation_lines.append(f"GPU recomendada: {rec_gpu}")

        rec_cpu = (rec_req.get("cpu") or "").strip()
        if rec_cpu:
            recommendation_lines.append(f"CPU recomendada: {rec_cpu}")

        rec_os = (rec_req.get("os") or "").strip()
        if rec_os:
            recommendation_lines.append(f"Sistema recomendado: {rec_os}")

        rec_dx = (rec_req.get("dx") or "").strip()
        if rec_dx:
            recommendation_lines.append(f"DirectX recomendado: {rec_dx}")

        return {
            "status": status,
            "headline": headline,
            "checks": checks,
            "specs": specs,
            "free_disk_gb": free_disk_gb,
            "recommendations": recommendation_lines,
        }

    def _build_pc_check_text(self, analysis: dict):
        lines = [analysis["headline"], ""]

        specs = analysis["specs"]
        lines.append("🖥 Seu PC:")
        lines.append(f"CPU: {specs.get('cpu') or 'Não detectada'}")
        lines.append(f"RAM: {specs.get('ram_gb', 0)} GB")
        lines.append(f"GPU: {specs.get('gpu') or 'Não detectada'}")
        lines.append(f"Espaço livre: {analysis.get('free_disk_gb', 0)} GB")
        lines.append("")

        if analysis["checks"]:
            lines.append("🔍 Comparação com os requisitos mínimos:")
            for item in analysis["checks"]:
                ok = item["ok"]
                if ok is True:
                    icon = "✅"
                elif ok is False:
                    icon = "❌"
                else:
                    icon = "⚠️"

                lines.append(
                    f"{icon} {item['label']}: atual {item['current']} | exigido {item['required']}"
                )
            lines.append("")

        if analysis["recommendations"]:
            lines.append("⭐ Recomendado pelo jogo:")
            for rec in analysis["recommendations"]:
                lines.append(f"- {rec}")
            lines.append("")

        if analysis["status"] == "below_minimum":
            lines.append("Você ainda pode tentar instalar, mas há risco de travamentos ou de o jogo não abrir.")
        elif analysis["status"] == "uncertain":
            lines.append("Alguns itens não puderam ser validados com precisão. Você pode continuar se quiser.")
        else:
            lines.append("Seu PC parece apto para instalar este jogo.")

        return "\n".join(lines)

    def _confirm_pc_check_before_install(self):
        analysis = self._analyze_pc_for_game()
        message = self._build_pc_check_text(analysis)

        msg = QMessageBox(self)
        msg.setWindowTitle("Verificação do PC")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("Análise concluída")
        msg.setInformativeText(message)
        continuar = msg.addButton("Continuar instalação", QMessageBox.ButtonRole.AcceptRole)
        cancelar = msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(continuar)
        msg.exec()

        return msg.clickedButton() == continuar

    def _update_title_text(self):
        txt = self.game_title.upper()

        fm = QFontMetrics(self.title_label.font())
        # largura útil: remove padding (12 + 12)
        max_w = max(10, self.title_label.width() - 24)

        elided = fm.elidedText(txt, Qt.TextElideMode.ElideRight, max_w)
        self.title_label.setText(elided)

    def _plano_ativo(self) -> bool:
        """
        1) Usa o estado salvo em sessão (plan_active + expires_at).
        2) Se tiver token, tenta confirmar no backend.
        3) Se o backend falhar (endpoint/timeout), NÃO derruba a sessão.
        """

        # -------- 1) valida sessão local --------
        plan_active = bool((self.user_info or {}).get("plan_active"))
        expires_at = (self.user_info or {}).get("expires_at")

        if plan_active and expires_at:
            try:
                from datetime import datetime, timezone
                exp_str = str(expires_at).replace("Z", "+00:00")
                exp = datetime.fromisoformat(exp_str)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if exp <= now:
                    # expirou
                    self.user_info["plan_active"] = False
                    return False
            except Exception:
                # se der erro no parse, não mata o acesso
                pass

        if plan_active and not expires_at:
            # permanente
            return True

        # se sessão diz que não está ativo, ainda podemos confirmar no backend
        token = (self.user_info or {}).get("token", "").strip()
        if not token:
            return False

        # -------- 2) confirma backend (flexível) --------
        try:
            r = requests.get(
                f"{API_BASE}/token/status",  # ✅ TROQUE aqui para o endpoint real do seu backend
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )

            if r.status_code != 200:
                # se backend não confirmar, mantém sessão como estava (não bloqueia por erro)
                return plan_active

            data = r.json() if "application/json" in (r.headers.get("content-type", "")) else {}

            # ✅ tenta achar qualquer formato comum
            if data.get("plan_active") is True:
                self.user_info["plan_active"] = True
                self.user_info["plan"] = data.get("plan", self.user_info.get("plan"))
                self.user_info["expires_at"] = data.get("expires_at", self.user_info.get("expires_at"))
                return True

            if data.get("ativo") is True:
                self.user_info["plan_active"] = True
                return True

            if str(data.get("status", "")).upper() == "ATIVO":
                self.user_info["plan_active"] = True
                return True

            # se backend disser não ativo:
            self.user_info["plan_active"] = False
            return False

        except Exception:
            # se cair a internet/endpoint errado: usa o que está salvo
            return plan_active

    def get_image_data(self, url):
        if not url:
            return b""

        if url.startswith("data:image") and "base64," in url:
            import base64
            try:
                b64 = url.split("base64,", 1)[1]
                return base64.b64decode(b64)
            except Exception as e:
                print("Erro ao decodificar imagem base64:", e)
                return b""

        try:
            # ===== CACHE LOCAL (não ocupa VPS) =====
            base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
            cache_dir = os.path.join(base_dir, "PrimeX", "cache", "covers")
            os.makedirs(cache_dir, exist_ok=True)

            # nome do arquivo baseado na URL (evita conflito e não precisa ID)
            h = hashlib.md5(url.encode("utf-8")).hexdigest()
            cache_path = os.path.join(cache_dir, f"{h}.img")

            # se já existe, usa do disco
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                with open(cache_path, "rb") as f:
                    return f.read()

            # se não existe, baixa e salva
            response = requests.get(url, timeout=8)
            response.raise_for_status()
            data = response.content

            with open(cache_path, "wb") as f:
                f.write(data)

            return data

        except Exception as e:
            print("Erro ao carregar imagem (cache):", e)
            return b""

    def _set_progress(self, pct: int):
        pct = max(0, min(100, int(pct)))
        self.btn_install.setText(f"BAIXANDO... {pct}%")
        self.btn_install.setEnabled(False)

    def _apply_cover_pixmap(self):
        if self._original_pixmap.isNull():
            return

        target_w = self.image_label.width()
        target_h = self.image_label.height()
        if target_w <= 0 or target_h <= 0:
            return

        # 1) escala "cover"
        pm = self._original_pixmap.scaled(
            target_w, target_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )

        # 2) crop central
        x = max(0, (pm.width() - target_w) // 2)
        y = max(0, (pm.height() - target_h) // 2)
        pm = pm.copy(x, y, target_w, target_h)

        # 3) clip arredondado (só topo)
        from PyQt6.QtGui import QPainter, QPainterPath
        from PyQt6.QtCore import QRectF

        out = QPixmap(target_w, target_h)
        out.fill(Qt.GlobalColor.transparent)

        r = 16.0  # mesmo radius do card
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, target_w, target_h), r, r)

        painter = QPainter(out)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pm)
        painter.end()

        self.image_label.setPixmap(out)

    def _show_requirements_dialog(self, title: str, text: str):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setFixedSize(760, 520)
        dlg.setStyleSheet("""
            QDialog {
                background-color: #0d0b1f;
                color: #b9a9ff;
                border: 2px solid #2a245f;
                border-radius: 18px;
            }
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Caixa de texto com scroll
        box = QTextEdit()
        box.setReadOnly(True)
        box.setText(text)
        box.setFont(QFont("VT323", 18))
        box.setStyleSheet("""
            QTextEdit {
                background-color: #120f2a;
                border: 2px solid #2a245f;
                border-radius: 14px;
                padding: 12px;
                color: #e0d9ff;
            }
            QScrollBar:vertical {
                border: none;
                background: #0d0b1f;
                width: 12px;
                margin: 8px 4px 8px 4px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #836FFF;
                min-height: 30px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9a7dff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        layout.addWidget(box)

        # Botão OK
        ok_btn = QPushButton("OK")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setFixedHeight(46)
        ok_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #836FFF,
                    stop:1 #4cc3ff
                );
                color: #0d0b1f;
                font-size: 20px;
                border-radius: 14px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9a7dff,
                    stop:1 #6fd4ff
                );
            }
        """)
        ok_btn.clicked.connect(dlg.accept)
        layout.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignRight)

        dlg.exec()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_cover_pixmap()
        if hasattr(self, "title_label"):
            self._update_title_text()

    def _on_global_download_updated(self, game_name: str, data: dict):
        if game_name != self.game_title:
            return

        status = data.get("status", "")
        progress = int(data.get("progress", 0))

        if status == "na_fila":
            self.btn_install.setText("NA FILA")
            self.btn_install.setEnabled(False)

        elif status == "baixando":
            self.btn_install.setText(f"BAIXANDO... {progress}%")
            self.btn_install.setEnabled(False)

        elif status == "extraindo":
            self.btn_install.setText("EXTRAINDO...")
            self.btn_install.setEnabled(False)

        elif status == "finalizando":
            self.btn_install.setText("FINALIZANDO...")
            self.btn_install.setEnabled(False)

        elif status == "concluido":
            # se já instalou no JSON, vira jogável
            if self.is_installed():
                self.set_playable()
            else:
                self.btn_install.setText("INSTALAR")
                self.btn_install.setEnabled(True)

        elif status == "erro":
            self.btn_install.setText("INSTALAR")
            self.btn_install.setEnabled(True)

    def _on_global_download_finished(self, game_name: str):
        if game_name != self.game_title:
            return

        if self.is_installed():
            self.set_playable()
        else:
            self.btn_install.setText("INSTALAR")
            self.btn_install.setEnabled(True)

    def _on_global_download_error(self, game_name: str, msg: str):
        if game_name != self.game_title:
            return

        self.btn_install.setText("INSTALAR")
        self.btn_install.setEnabled(True)

    def install_game(self):
        uid = (self.user_info or {}).get("id")
        if not uid:
            QMessageBox.warning(self, "Sessão inválida", "Usuário sem ID válido. Faça login novamente.")
            return

        # se já está instalado: jogar
        if self.is_installed():
            self.play_game()
            return

        # bloqueia se não tiver plano/token ativo
        if not user_can_download(self.user_info):
            QMessageBox.warning(
                self,
                "Acesso negado",
                "Seu plano/token não está ATIVO. Ative seu acesso para baixar jogos."
            )
            return

        # se já está na fila / baixando, não adiciona de novo
        if download_manager.is_downloading(self.game_title):
            QMessageBox.information(
                self,
                "Download em andamento",
                f"{self.game_title} já está na fila ou em download."
            )
            return

        # 🔥 NOVO: verificação do PC antes de instalar
        if not self._confirm_pc_check_before_install():
            return

        download_manager.enqueue_download(
            game_name=self.game_title,
            download_url=self.download_url,
            image_url=self.image_url,
            genres=self.genres,
            exe_principal=self.exe_principal
        )

        self.btn_install.setText("NA FILA")
        self.btn_install.setEnabled(False)

    def _on_install_finished(self, signals):
        install_dir = os.path.normpath(signals.install_dir or os.path.join(GAMES_DIR, self.game_title))

        # aqui o downloader já tentou detectar exe e proteger
        exe_rel = getattr(signals, "exe_relpath", "") or ""
        exe_enc = getattr(signals, "exe_enc_path", "") or ""

        if self.exe_principal:
            exe_manual = os.path.normpath(self.exe_principal)
            exe_manual_path = os.path.normpath(os.path.join(install_dir, exe_manual))

            if os.path.exists(exe_manual_path):
                exe_rel = exe_manual
                exe_enc = ""

        # segurança extra: se vier exe suspeito, recalcula localmente
        if not exe_rel or exe_saved_is_suspicious(exe_rel):
            fixed_exe_rel = find_best_exe_by_folder_name(install_dir)
            if fixed_exe_rel:
                exe_rel = fixed_exe_rel
                exe_enc = ""
        print("install_dir:", signals.install_dir)
        print("exe_relpath:", signals.exe_relpath)
        print("exe_enc_path:", signals.exe_enc_path)

        # salva no instalados.json
        data = load_installed()
        data[self.game_title] = {
            "install_dir": install_dir,
            "exe": self.exe_principal or exe_rel,
            "exe_enc": exe_enc,
            "capa_url": self.image_url or "",
            "genero": self.genres or [],
            "descricao": self.descricao or "",  # ✅
            "exe_principal": self.exe_principal or "",
        }
        save_installed(data)

        self.set_playable()
        self.btn_uninstall.setVisible(True)
        QMessageBox.information(self, "Sucesso", f"{self.game_title} instalado com sucesso!")
        self.btn_uninstall.setVisible(True)

    def uninstall_game(self):
        import shutil
        import stat

        data = load_installed()
        info = data.get(self.game_title) or {}
        install_dir = os.path.normpath((info.get("install_dir") or "").strip())

        resp = QMessageBox.question(
            self,
            "Confirmar desinstalação",
            f"Deseja desinstalar '{self.game_title}'?\nIsso removerá os arquivos do jogo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        # trava botões enquanto desinstala
        self.btn_install.setEnabled(False)
        self.btn_req.setEnabled(False)
        self.btn_uninstall.setEnabled(False)

        def _on_rm_error(func, path, exc_info):
            # tenta remover read-only e repetir
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        try:
            # remove pasta do jogo
            if install_dir and os.path.isdir(install_dir):
                shutil.rmtree(install_dir, onerror=_on_rm_error)  # ✅ sem ignore_errors

                # se ainda existir, falhou (mostra)
                if os.path.isdir(install_dir):
                    raise PermissionError(f"Não foi possível remover completamente:\n{install_dir}")

            # remove do instalados.json
            if self.game_title in data:
                del data[self.game_title]
                save_installed(data)

            # volta botão principal para instalar
            self.btn_install.setText("INSTALAR")
            self.btn_install.setEnabled(True)
            try:
                self.btn_install.clicked.disconnect()
            except Exception:
                pass
            self.btn_install.clicked.connect(self.install_game)

            # requisitos volta normal
            self.btn_req.setEnabled(True)

            # desinstalar: volta desativado
            self.btn_uninstall.setEnabled(False)
            self.btn_uninstall.setCursor(Qt.CursorShape.ArrowCursor)
            self.btn_uninstall.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 85, 85, 0.06);
                border: 1px solid rgba(255, 85, 85, 0.35);
                color: rgba(255, 179, 179, 0.55);
                font-size: 15px;
                border-radius: 10px;
                padding: 10px;
            }
            """)

            QMessageBox.information(self, "Concluído", f"{self.game_title} foi desinstalado.")

        except PermissionError:
            # reabilita botões
            self.btn_install.setEnabled(True)
            self.btn_req.setEnabled(True)
            self.btn_uninstall.setEnabled(True)

            QMessageBox.warning(
                self,
                "Permissão negada",
                "Não consegui remover os arquivos do jogo.\n\n"
                "Feche o jogo/patch e execute o PrimeX como Administrador, depois tente novamente."
            )

        except Exception as e:
            # se falhar, reabilita tudo
            self.btn_install.setEnabled(True)
            self.btn_req.setEnabled(True)

            if self.is_installed():
                self.set_playable()
            else:
                self.btn_uninstall.setEnabled(False)
                self.btn_uninstall.setCursor(Qt.CursorShape.ArrowCursor)

            QMessageBox.warning(self, "Erro", f"Não foi possível desinstalar:\n{e}")

    def play_game(self):
        import subprocess
        import time
        import threading
        import os

        if not self._plano_ativo():
            QMessageBox.warning(self, "Acesso negado", "Seu acesso não está ativo.")
            return

        data = load_installed()
        info = data.get(self.game_title) or {}

        install_dir = os.path.normpath((info.get("install_dir") or "").strip()).rstrip("\\/")
        if not install_dir or not os.path.isdir(install_dir):
            QMessageBox.warning(self, "Erro", f"Pasta do jogo não encontrada:\n{install_dir}")
            return

        exe_rel = (info.get("exe") or "").strip()
        low = exe_rel.lower().replace("\\", "/")
        launcher_escolhido = low.endswith("launcher.exe") or low.endswith("launcher1.exe")
        exe_enc = (info.get("exe_enc") or "").strip()

        # recalcula se:
        # - não existe exe salvo
        # - ou o exe salvo parece suspeito (launcher/setup/rockstar/etc)
        # - ou o arquivo salvo não existe mais
        need_recalculate = False

        if not exe_rel:
            need_recalculate = True
        elif not launcher_escolhido and exe_saved_is_suspicious(exe_rel):
            need_recalculate = True
        else:
            exe_path_test = os.path.normpath(os.path.join(install_dir, exe_rel))
            if not os.path.exists(exe_path_test) and not exe_enc:
                need_recalculate = True

        if need_recalculate:
            new_exe_rel = find_best_exe_by_folder_name(install_dir)
            if new_exe_rel:
                exe_rel = new_exe_rel

                # salva correção no instalados.json
                data.setdefault(self.game_title, {})
                data[self.game_title]["exe"] = exe_rel
                save_installed(data)

                # se existia exe_enc antigo, limpa referência para não apontar errado
                if exe_saved_is_suspicious((info.get("exe") or "").strip()):
                    data.setdefault(self.game_title, {})
                    data[self.game_title]["exe_enc"] = ""
                    save_installed(data)
                    exe_enc = ""

        if not exe_rel:
            QMessageBox.warning(self, "Erro", "Não encontrei o executável do jogo (exe).")
            return

        exe_path = os.path.normpath(os.path.join(install_dir, exe_rel))
        exe_dir = os.path.dirname(exe_path)

        def _run_exe(real_exe_path: str):
            import subprocess
            import os
            import ctypes

            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200

            try:
                return subprocess.Popen(
                    [real_exe_path],
                    cwd=os.path.dirname(real_exe_path),  # ✅ CWD correto
                    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                    close_fds=True
                )

            except OSError as e:
                # ✅ WinError 740 = requer elevação (admin)
                if getattr(e, "winerror", None) == 740:
                    ctypes.windll.shell32.ShellExecuteW(
                        None,
                        "runas",  # pede UAC
                        real_exe_path,  # exe
                        None,  # argumentos (se tiver, eu ajusto)
                        os.path.dirname(real_exe_path),  # pasta
                        1
                    )
                    return None

                raise

        # ✅ 1) Se tem exe protegido: descriptografa SEM trocar nome (Unity precisa do nome certo)
        # ✅ 1) Se tem exe protegido: descriptografa para o exe real e executa
        if exe_enc and os.path.exists(exe_enc):
            try:
                decrypt_file_to(exe_enc, exe_path)

                if not wait_file_ready(exe_path, timeout=10):
                    raise Exception("O executável não ficou pronto para uso a tempo.")

                p = _run_exe(exe_path)

                def _cleanup_when_exit():
                    try:
                        if p is not None:
                            p.wait()
                        else:
                            # caso tenha aberto via runas/UAC, espera um pouco
                            time.sleep(20)
                    finally:
                        try:
                            if os.path.exists(exe_path):
                                os.remove(exe_path)
                        except Exception:
                            pass

                threading.Thread(target=_cleanup_when_exit, daemon=True).start()
                return

            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Não foi possível iniciar o jogo (protegido):\n{e}")
                return
        # ✅ 2) Sem proteção (modo antigo): roda exe normal
        if os.path.exists(exe_path):
            try:
                if not wait_file_ready(exe_path, timeout=10):
                    raise Exception("O executável está indisponível ou bloqueado.")
                _run_exe(exe_path)
                return
            except Exception as e:
                QMessageBox.warning(self, "Erro ao iniciar", f"Falhou ao abrir:\n{exe_path}\n\nErro:\n{e}")
                return

        QMessageBox.warning(self, "Erro", f"Executável não encontrado:\n{exe_path}")

    def show_requirements(self):
        req = self.requisitos or {}

        def format_block(title, data):
            if not data:
                return ""

            lines = [f"🎮 {title}:\n"]

            if data.get("os"):
                lines.append(f"Sistema: {data['os']}")
            if data.get("cpu"):
                lines.append(f"CPU: {data['cpu']}")
            if data.get("ram"):
                lines.append(f"RAM: {data['ram']} GB")
            if data.get("gpu"):
                lines.append(f"GPU: {data['gpu']}")
            if data.get("dx"):
                lines.append(f"DirectX: {data['dx']}")
            if data.get("storage"):
                lines.append(f"Espaço: {data['storage']} GB")

            if data.get("notes"):
                lines.append(f"\nObs: {data['notes']}")

            return "\n".join(lines)

        min_block = format_block("MÍNIMOS", req.get("min"))
        rec_block = format_block("RECOMENDADOS", req.get("rec"))

        texto_final = ""

        if min_block or rec_block:
            texto_final = f"{min_block}\n\n{rec_block}".strip()
        else:
            # fallback antigo
            texto_final = (self.descricao or "").strip() or "Requisitos não informados."

        self._show_requirements_dialog("Requisitos do Sistema", texto_final)

    def is_installed(self):
        data = load_installed()
        info = data.get(self.game_title)
        if not info:
            return False

        install_dir = info.get("install_dir", "")
        return bool(install_dir) and os.path.isdir(install_dir)

    def set_playable(self):
        # ===== BOTÃO PRINCIPAL: JOGAR =====
        self.btn_install.setText("JOGAR")
        self.btn_install.setEnabled(True)
        self.btn_install.setStyleSheet("""
        QPushButton {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #4cc3ff,
                stop:1 #00ffaa
            );
            color: #0d0b1f;
            font-size: 18px;
            font-weight: bold;
            border-radius: 12px;
            padding: 12px;
        }
        QPushButton:hover {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #6fd4ff,
                stop:1 #33ffbb
            );
        }
        """)

        # garante que clique vai para play_game (sem acumular sinais)
        try:
            self.btn_install.clicked.disconnect()
        except Exception:
            pass
        self.btn_install.clicked.connect(self.play_game)

        # ===== DESINSTALAR: ATIVADO (SEM MEXER EM VISIBILIDADE) =====
        self.btn_uninstall.setEnabled(True)
        self.btn_uninstall.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_uninstall.setStyleSheet("""
        QPushButton {
            background-color: rgba(255, 85, 85, 0.12);
            border: 1px solid #ff5555;
            color: #ffb3b3;
            font-size: 15px;
            border-radius: 10px;
            padding: 10px;
        }
        QPushButton:hover {
            background-color: #ff5555;
            color: #0d0b1f;
        }
        QPushButton:pressed {
            background-color: #ff7777;
        }
        """)



class DestaqueWidget(QWidget):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


    def __init__(self, width, height, title="", image_data=None, big=False, show_title=True):
        super().__init__()
        self.is_new = False
        self.setFixedSize(width, height)
        self.title = title
        self.image = QPixmap()
        self.big = big
        self.show_title = show_title
        self.game_data = {}
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if image_data:
            self.image.loadFromData(image_data)

    def set_image(self, data):
        pix = QPixmap()
        pix.loadFromData(data)
        self.image = pix
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.rect()
        radius = 16 if self.big else 14

        # recorte arredondado
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)

        painter.save()
        painter.setClipPath(path)

        if not self.image.isNull():
            pm = self.image.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )

            x = max(0, (pm.width() - rect.width()) // 2)
            y = max(0, (pm.height() - rect.height()) // 2)

            painter.drawPixmap(0, 0, pm.copy(x, y, rect.width(), rect.height()))
        else:
            painter.fillRect(rect, QColor("#000000"))

        # overlay só se tiver texto
        if self.show_title:
            overlay_top = int(rect.height() * 0.80)

            gradient = QLinearGradient(0, overlay_top, 0, rect.height())
            gradient.setColorAt(0, QColor(0, 0, 0, 0))
            gradient.setColorAt(1, QColor(0, 0, 0, 180))

            painter.fillRect(rect, gradient)

        painter.restore()

        # borda por cima
        pen = painter.pen()
        pen.setWidth(2)
        pen.setColor(QColor("#2a245f"))
        painter.setPen(pen)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)

        if self.show_title and self.title:
            painter.setPen(QColor("#ffffff"))

            font = painter.font()
            font.setPointSize(28 if self.big else 18)
            font.setBold(True)
            painter.setFont(font)

            painter.drawText(
                rect.adjusted(20, 0, -20, -20),
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                self.title.upper()
            )
            if self.is_new:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#836FFF"))

                badge_rect = QRectF(10, 10, 180, 36)
                painter.drawRoundedRect(badge_rect, 10, 10)

                painter.setPen(QColor("#0d0b1f"))

                font = painter.font()
                font.setPointSize(12 if self.big else 10)
                font.setBold(True)
                painter.setFont(font)

                painter.drawText(
                    badge_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    "NOVO NA PRIMEX"
                )




# =========================
# MAIN WINDOW
# =========================
class MainWindow(QWidget):
    def __init__(self, usuario_info=None):
        super().__init__()
        self.setWindowTitle("PrimeX")
        self.setStyleSheet("""
            QWidget {
                background-color: #0d0b1f;
                color: #b9a9ff;
                font-family: 'VT323';
            }
        """)
        self.user_info = dict(usuario_info or {})

        self._navigating = False
        self.thread_pool = QThreadPool.globalInstance()

        # ✅ mescla sessão persistida por cima
        sess = load_session()
        if isinstance(sess, dict):
            self.user_info.update(sess)

        # ✅ garante chaves mínimas sem inventar id fake
        self.user_info.setdefault("id", "")
        self.user_info.setdefault("nome", "Usuário")
        self.user_info.setdefault("is_admin", False)
        self.user_info.setdefault("token", "")

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(8)

        # =========================
        # HEADER
        # =========================
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addStretch()

        user_btn = QPushButton(self.user_info.get("nome", "Usuário"))
        user_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        user_btn.setFixedHeight(46)
        user_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid #836FFF;
                border-radius: 18px;
                color: #e0d9ff;
                font-size: 17px;
                font-weight: bold;
                padding: 6px 14px 6px 10px;
                text-align: left;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(131, 111, 255, 0.12);
            }
        """)

        avatar_pix = self._make_round_avatar(self.user_info.get("avatar_url", ""), 28)
        if not avatar_pix.isNull():
            user_btn.setIcon(QIcon(avatar_pix))
            user_btn.setIconSize(QSize(28, 28))

        user_btn.clicked.connect(self.open_profile)
        header.addWidget(user_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.main_layout.addLayout(header)

        # NavBar
        nav_callbacks = {
            "EXPLORAR": self.open_explorar,
            "INSTALADOS": self.open_instalados,
            "DOWNLOADS": self.open_downloads
        }
        self.nav_bar = NavBar(parent=self, callbacks=nav_callbacks)
        self.main_layout.addWidget(self.nav_bar)

        # <<< NOVO: Barra de filtros fixa (igual do installed.py, porém via componente reutilizável)
        self.filter_bar = FilterBar(on_filter_change=self.apply_filters)
        self.filter_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.main_layout.addWidget(self.filter_bar)

        # Botão de atualizar / F5
        refresh_row = QHBoxLayout()
        refresh_row.setContentsMargins(0, 0, 0, 0)
        refresh_row.addStretch()

        self.refresh_btn = QPushButton("🔄 Atualizar")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setFixedHeight(42)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a245f;
                color: #e0d9ff;
                border: 1px solid #836FFF;
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #836FFF;
                color: #0d0b1f;
            }
        """)
        self.refresh_btn.clicked.connect(self.reload_games)

        refresh_row.addWidget(self.refresh_btn)
        self.main_layout.addLayout(refresh_row)

        # Grid
        # ===== SCROLL + GRID =====
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                border: none;
                background: #0d0b1f;
                width: 12px;
                margin: 8px 4px 8px 4px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #836FFF;
                min-height: 30px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover { background: #9a7dff; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")

        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 25)
        self.scroll_layout.setSpacing(24)

        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background: transparent;")

        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setHorizontalSpacing(20)
        self.grid_layout.setVerticalSpacing(50)
        self.grid_layout.setContentsMargins(0, 5, 0, 25)

        self.scroll_layout.addWidget(self.grid_widget)

        self.scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll_area)

        self.setLayout(self.main_layout)
        self.setMinimumSize(720, 480)
        self.showMaximized()

        # Atalho F5 para recarregar
        self.shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        self.shortcut_refresh.activated.connect(self.reload_games)

        self.cards = []

        self.novos_jogos = []
        self.destaque_index = 0
        self.destaque_main = None
        self.destaque_side_widgets = []
        self.destaque_timer = QTimer(self)
        self.destaque_timer.timeout.connect(self.next_destaque)

        self.load_games()
        # aplica filtros atuais (mantém layout consistente mesmo sem jogos)
        self.apply_filters()

    def open_explorar(self):
        # Já estou no Explorar, então não abro outra janela
        if self._navigating:
            return

        self.reload_games()

    def animate_fade(self, widget, on_mid=None):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        fade_out = QPropertyAnimation(effect, b"opacity")
        fade_out.setDuration(200)
        fade_out.setStartValue(1)
        fade_out.setEndValue(0)

        fade_in = QPropertyAnimation(effect, b"opacity")
        fade_in.setDuration(200)
        fade_in.setStartValue(0)
        fade_in.setEndValue(1)

        # 🔥 GUARDA referência (ESSENCIAL)
        self._anim = (fade_out, fade_in)

        def after_fade_out():
            if on_mid:
                on_mid()
            fade_in.start()

        fade_out.finished.connect(after_fade_out)
        fade_out.start()

    def load_card_image_async(self, card):
        if not card.image_url:
            return

        task = ImageLoaderTask(card.image_url)

        def on_finished(url, data):
            if not data:
                return

            if not hasattr(card, "image_label"):
                return

            pix = QPixmap()
            pix.loadFromData(data)

            if pix.isNull():
                return

            card._original_pixmap = pix
            card._apply_cover_pixmap()

        task.signals.finished.connect(on_finished)
        self.thread_pool.start(task)

    def reload_games(self):
        try:
            self.refresh_btn.setText("ATUALIZANDO...")
            self.refresh_btn.setEnabled(False)

            self.load_games()
            self.apply_filters()

        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Falha ao atualizar jogos:\n{e}")

        finally:
            self.refresh_btn.setText("🔄 Atualizar")
            self.refresh_btn.setEnabled(True)

    def _pixmap_from_source(self, source: str, size: int = 36):
        pixmap = QPixmap()

        if not source:
            return pixmap

        if source.startswith("http://") or source.startswith("https://"):
            try:
                r = requests.get(source, timeout=8)
                if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
                    pixmap.loadFromData(r.content)
            except Exception:
                return QPixmap()
        else:
            pixmap = QPixmap(source)

        if pixmap.isNull():
            return QPixmap()

        return pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )

    def _make_round_avatar(self, source: str, size: int = 36):
        pix = self._pixmap_from_source(source, size)

        if pix.isNull():
            default_avatar = resource_path("assets/profile_default.png")
            pix = self._pixmap_from_source(default_avatar, size)

        if pix.isNull():
            return QPixmap()

        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pix)
        painter.end()

        return rounded

    def open_downloads(self):
        if self._navigating:
            return

        self._navigating = True

        from downloads import DownloadsPage
        self.downloads_window = DownloadsPage(usuario_info=self.user_info)
        self.downloads_window.show()
        self.hide()
        QTimer.singleShot(300, self.close)

    def open_profile(self):
        if self._navigating:
            return

        self._navigating = True

        self.profile_window = ProfilePage(user_info=self.user_info)
        self.profile_window.show()
        self.hide()
        QTimer.singleShot(300, self.close)

    def refresh_page(self):
        if self._navigating:
            return

        self.reload_games()

    def open_instalados(self):
        if self._navigating:
            return

        self._navigating = True

        try:
            if hasattr(self, "nav_bar"):
                self.nav_bar.setEnabled(False)

            from installed import InstaladosPage
            self.installed_window = InstaladosPage(usuario_info=self.user_info)
            self.installed_window.show()

            self.hide()
            QTimer.singleShot(300, self.close)

        except Exception as e:
            self._navigating = False
            if hasattr(self, "nav_bar"):
                self.nav_bar.setEnabled(True)

            QMessageBox.warning(self, "Erro", f"Não foi possível abrir Instalados:\n{e}")

    def _make_destaque_image_label(self, jogo, width, height, big=False):
        label = QLabel()
        label.setFixedSize(width, height)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        nome = jogo.get("nome", "Jogo")
        capa_url = jogo.get("capa_url", "")

        label.setText(nome.upper())
        label.setStyleSheet(f"""
            QLabel {{
                background-color: #120f2a;
                border-radius: {'16px' if big else '14px'};
                border: 2px solid #2a245f;
                color: #ffffff;
                font-size: {'30px' if big else '20px'};
                font-weight: bold;
                padding: {'22px' if big else '14px'};
            }}
            QLabel:hover {{
                border: 2px solid #836FFF;
                background-color: #18134a;
            }}
        """)

        if capa_url:
            task = ImageLoaderTask(capa_url)

            def on_finished(url, data):
                if not data:
                    return

                pix = QPixmap()
                pix.loadFromData(data)

                if pix.isNull():
                    return

                pm = pix.scaled(
                    width,
                    height,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )

                x = max(0, (pm.width() - width) // 2)
                y = max(0, (pm.height() - height) // 2)
                pm = pm.copy(x, y, width, height)

                # escurece um pouco para o texto aparecer
                dark = QPixmap(width, height)
                dark.fill(Qt.GlobalColor.transparent)

                painter = QPainter(dark)
                painter.drawPixmap(0, 0, pm)
                painter.fillRect(0, 0, width, height, Qt.GlobalColor.transparent)
                painter.end()

                label.setPixmap(pm)
                label.setScaledContents(True)

            task.signals.finished.connect(on_finished)
            self.thread_pool.start(task)

        return label

    def _load_image_into_destaque(self, widget, url):
        if not url:
            return

        task = ImageLoaderTask(url)

        def on_finished(_, data, w=widget):
            if data:
                w.set_image(data)

        task.signals.finished.connect(on_finished)
        self.thread_pool.start(task)

    def update_destaque_content(self):
        if not self.novos_jogos or not self.destaque_main:
            return


        total = len(self.novos_jogos)

        jogo_principal = self.novos_jogos[self.destaque_index % total]
        self.destaque_main.title = jogo_principal.get("nome", "")
        nome_norm = (jogo_principal.get("nome") or "").strip().lower()
        self.destaque_main.is_new = nome_norm in self.novos_ids
        self.destaque_main.game_data = jogo_principal
        self.destaque_main.image = QPixmap()
        banner = jogo_principal.get("banner_url") or jogo_principal.get("capa_url")

        self._load_image_into_destaque(
            self.destaque_main,
            banner
        )
        self.destaque_main.update()

        screens = [
            jogo_principal.get("screenshot_1_url"),
            jogo_principal.get("screenshot_2_url")
        ]

        for i, side in enumerate(self.destaque_side_widgets):
            img_url = screens[i] if i < len(screens) and screens[i] else banner

            side.title = ""
            side.game_data = jogo_principal
            side.is_new = nome_norm in getattr(self, "novos_ids", set())
            side.image = QPixmap()

            self._load_image_into_destaque(side, img_url)
            side.update()

    def on_destaque_click(self, jogo):
        if not jogo:
            return

        nome = jogo.get("nome", "")
        download = (jogo.get("dropbox_token") or "").strip()
        descricao = (jogo.get("descricao") or "Sem descrição cadastrada.").strip()

        requisitos = {
            "min": {
                "os": jogo.get("min_os"),
                "cpu": jogo.get("min_cpu"),
                "ram": jogo.get("min_ram_gb"),
                "gpu": jogo.get("min_gpu"),
                "dx": jogo.get("min_directx"),
                "storage": jogo.get("min_storage_gb"),
                "notes": jogo.get("min_notes"),
            },
            "rec": {
                "os": jogo.get("rec_os"),
                "cpu": jogo.get("rec_cpu"),
                "ram": jogo.get("rec_ram_gb"),
                "gpu": jogo.get("rec_gpu"),
                "dx": jogo.get("rec_directx"),
                "storage": jogo.get("rec_storage_gb"),
                "notes": jogo.get("rec_notes"),
            }
        }

        def format_block(title, data):
            if not data:
                return ""

            lines = [f"🎮 {title}:\n"]

            if data.get("os"):
                lines.append(f"Sistema: {data['os']}")
            if data.get("cpu"):
                lines.append(f"CPU: {data['cpu']}")
            if data.get("ram"):
                lines.append(f"RAM: {data['ram']} GB")
            if data.get("gpu"):
                lines.append(f"GPU: {data['gpu']}")
            if data.get("dx"):
                lines.append(f"DirectX: {data['dx']}")
            if data.get("storage"):
                lines.append(f"Espaço: {data['storage']} GB")
            if data.get("notes"):
                lines.append(f"\nObs: {data['notes']}")

            return "\n".join(lines)

        min_block = format_block("MÍNIMOS", requisitos.get("min"))
        rec_block = format_block("RECOMENDADOS", requisitos.get("rec"))

        requisitos_texto = f"{min_block}\n\n{rec_block}".strip()

        if not requisitos_texto:
            requisitos_texto = "Requisitos não informados."

        dlg = QDialog(self)
        dlg.setWindowTitle(nome)
        dlg.setFixedSize(760, 560)
        dlg.setStyleSheet("""
            QDialog {
                background-color: #0d0b1f;
                color: #e0d9ff;
                border-radius: 18px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        title = QLabel(nome.upper())
        title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 34px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title)

        desc = QTextEdit()
        desc.setReadOnly(True)
        desc.setText(f"{descricao}\n\n━━━━━━━━━━━━━━━━━━━━\n\n{requisitos_texto}")
        desc.setStyleSheet("""
            QTextEdit {
                background-color: #120f2a;
                color: #e0d9ff;
                border: 2px solid #2a245f;
                border-radius: 14px;
                padding: 12px;
                font-size: 20px;
            }
        """)
        layout.addWidget(desc)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancelar = QPushButton("CANCELAR")
        btn_cancelar.setFixedHeight(46)
        btn_cancelar.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #836FFF;
                color: #b9a9ff;
                border-radius: 12px;
                font-size: 18px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: rgba(131,111,255,0.15);
            }
        """)

        btn_instalar = QPushButton("INSTALAR")
        btn_instalar.setFixedHeight(46)
        btn_instalar.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #836FFF,
                    stop:1 #4cc3ff
                );
                color: #0d0b1f;
                border-radius: 12px;
                font-size: 20px;
                font-weight: bold;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9a7dff,
                    stop:1 #6fd4ff
                );
            }
        """)

        btn_cancelar.clicked.connect(dlg.reject)
        btn_instalar.clicked.connect(dlg.accept)

        btn_row.addWidget(btn_cancelar)
        btn_row.addWidget(btn_instalar)
        layout.addLayout(btn_row)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        if not nome or not download:
            QMessageBox.warning(self, "Erro", "Este jogo não possui link de download cadastrado.")
            return

        if download_manager.is_downloading(nome):
            QMessageBox.information(
                self,
                "Download em andamento",
                f"{nome} já está na fila ou em download."
            )
            return

        if not user_can_download(self.user_info):
            QMessageBox.warning(
                self,
                "Acesso negado",
                "Seu plano/token não está ATIVO. Ative seu acesso para baixar jogos."
            )
            return

        download_manager.enqueue_download(
            game_name=nome,
            download_url=download,
            image_url=jogo.get("capa_url", ""),
            genres=jogo.get("genero", [])
        )

    def next_destaque(self):
        if not self.novos_jogos:
            return

        def trocar():
            self.destaque_index = (self.destaque_index + 1) % len(self.novos_jogos)
            self.update_destaque_content()

        # anima só UMA vez
        self.animate_fade(self.destaque_main, on_mid=trocar)

        # anima laterais (sem trocar)
        for side in self.destaque_side_widgets:
            self.animate_fade(side)

    def load_games(self):
        uid = self.user_info.get("id")
        if not uid:
            QMessageBox.warning(
                self,
                "Sessão inválida",
                "Seu login não está carregando o ID do usuário.\nFaça login novamente."
            )
            return

        try:
            response = requests.get(f"{API_BASE}/admin/listar_jogos", timeout=10)
            response.raise_for_status()
            todos_jogos = response.json().get("jogos", [])

            novos_jogos = list(reversed(todos_jogos))[:8]
            self.novos_jogos = novos_jogos
            self.destaque_index = 0

            self.novos_ids = {
                (j.get("nome") or "").strip().lower()
                for j in novos_jogos[:3]
            }

            jogos_data = sorted(
                todos_jogos,
                key=lambda j: (j.get("nome") or "").lower().strip()
            )
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Falha ao carregar lista de jogos:\n{e}")
            jogos_data = []

        # limpa grid
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            w = item.widget() if item else None
            if w:
                self.grid_layout.removeWidget(w)
                w.setParent(None)

        self.cards.clear()

        # =========================
        # REMOVE DESTAQUE ANTIGO
        # =========================
        if hasattr(self, "destaque_widget"):
            self.destaque_timer.stop()
            self.scroll_layout.removeWidget(self.destaque_widget)
            self.destaque_widget.deleteLater()

        # =========================
        # DESTAQUES
        # =========================
        if novos_jogos:
            destaque_widget = QWidget()
            destaque_layout = QHBoxLayout(destaque_widget)
            destaque_layout.setSpacing(12)
            destaque_layout.setContentsMargins(0, 0, 0, 20)

            # ===== JOGO PRINCIPAL =====
            self.destaque_main = DestaqueWidget(
                790,
                340,
                title="",
                big=True,
                show_title=True
            )

            self.destaque_main.clicked.connect(
                lambda: self.on_destaque_click(self.destaque_main.game_data)
            )

            destaque_layout.addWidget(self.destaque_main, stretch=3)

            # ===== LADO DIREITO =====
            side_layout = QVBoxLayout()
            side_layout.setSpacing(10)

            self.destaque_side_widgets = []

            for _ in range(2):
                side = DestaqueWidget(
                    290,
                    160,
                    title="",
                    big=False,
                    show_title=False
                )

                side.clicked.connect(
                    lambda w=side: self.on_destaque_click(w.game_data)
                )

                self.destaque_side_widgets.append(side)
                side_layout.addWidget(side)

            destaque_layout.addLayout(side_layout, stretch=1)

            wrapper = QHBoxLayout()
            wrapper.setContentsMargins(0, 0, 0, 0)
            wrapper.addStretch()
            wrapper.addWidget(destaque_widget)
            wrapper.addStretch()

            container = QWidget()
            container.setLayout(wrapper)

            self.destaque_widget = container
            destaque_widget.setFixedSize(1100, 360)

            self.scroll_layout.insertWidget(0, container)

            self.update_destaque_content()

            if len(self.novos_jogos) > 1:
                self.destaque_timer.start(5000)
            else:
                self.destaque_timer.stop()

        for idx, jogo in enumerate(jogos_data):
            requisitos = {
                "min": {
                    "os": jogo.get("min_os"),
                    "cpu": jogo.get("min_cpu"),
                    "ram": jogo.get("min_ram_gb"),
                    "gpu": jogo.get("min_gpu"),
                    "dx": jogo.get("min_directx"),
                    "storage": jogo.get("min_storage_gb"),
                    "notes": jogo.get("min_notes"),
                },
                "rec": {
                    "os": jogo.get("rec_os"),
                    "cpu": jogo.get("rec_cpu"),
                    "ram": jogo.get("rec_ram_gb"),
                    "gpu": jogo.get("rec_gpu"),
                    "dx": jogo.get("rec_directx"),
                    "storage": jogo.get("rec_storage_gb"),
                    "notes": jogo.get("rec_notes"),
                }
            }

            card = GameCard(
                image_url=jogo.get("capa_url", ""),
                title_top=jogo.get("nome", ""),
                title_bottom="",
                download_url=jogo.get("dropbox_token", "").strip(),
                genres=jogo.get("genero", []),
                user_info=self.user_info,
                descricao=jogo.get("descricao", ""),
                requisitos=requisitos,
                exe_principal=jogo.get("exe_principal", "")
            )

            self.cards.append(card)
            self.load_card_image_async(card)

            row = idx // 5
            col = idx % 5
            self.grid_layout.addWidget(card, row, col, alignment=Qt.AlignmentFlag.AlignTop)

            self.cards.append(card)
            self.load_card_image_async(card)
            row = idx // 5
            col = idx % 5
            self.grid_layout.addWidget(card, row, col, alignment=Qt.AlignmentFlag.AlignTop)

        total_slots = max(5, len(jogos_data))
        for idx in range(len(jogos_data), total_slots):
            row = idx // 5
            col = idx % 5
            placeholder = QLabel()
            placeholder.setFixedSize(260, 485)
            placeholder.setStyleSheet("background-color: transparent; border: none;")
            self.grid_layout.addWidget(placeholder, row, col)

    # <<< NOVO: filtros (texto + gêneros) sem quebrar layout
    def apply_filters(self, search_text=None, active_genres=None):
        # quando chamado manualmente, lê do componente
        if search_text is None or active_genres is None:
            search_text, active_genres = self.filter_bar.get_filters()

        search_text = (search_text or "").lower().strip()

        filtered_cards = []

        # 1) filtra os cards
        for card in self.cards:
            title = card.game_title.lower()

            genre_match = True
            if active_genres:
                genre_match = any(g in card.genres for g in active_genres)

            text_match = search_text in title
            visible = text_match and genre_match

            card.setVisible(visible)

            if visible:
                filtered_cards.append(card)

        # 2) limpa o grid atual
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        # 3) adiciona os cards filtrados em sequência
        for idx, card in enumerate(filtered_cards):
            row = idx // 5
            col = idx % 5
            self.grid_layout.addWidget(card, row, col, alignment=Qt.AlignmentFlag.AlignTop)

        # 4) placeholders para manter alinhamento visual
        total_slots = max(5, len(filtered_cards))
        for idx in range(len(filtered_cards), total_slots):
            row = idx // 5
            col = idx % 5
            placeholder = QLabel()
            placeholder.setFixedSize(260, 485)
            placeholder.setStyleSheet("background-color: transparent; border: none;")
            self.grid_layout.addWidget(placeholder, row, col)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont(FONT_PATH)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
