import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QGridLayout, QSizePolicy, QMessageBox
)
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from profile import ProfilePage
from navbar import NavBar
from downloader import baixar_jogo, decrypt_file_to
from filter_bar import FilterBar
from PyQt6.QtGui import QFontDatabase
from api_config import API_BASE
import hashlib
import requests
from PyQt6.QtWidgets import QScrollArea
from utils import resource_path
from session import load_session
from PyQt6.QtWidgets import QDialog, QTextEdit
from PyQt6.QtGui import QFont



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
class GameCard(QWidget):
    def __init__(self, image_url, title_top, title_bottom, download_url, genres=None, user_info=None, descricao=""):


        super().__init__()

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
        data = self.get_image_data(image_url)
        if data:
            self._original_pixmap.loadFromData(data)

        # aplica depois que o layout definir tamanhos
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._apply_cover_pixmap)



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

        if self.is_installed():
            self.set_playable()


    # =========================
    # MÉTODOS AUXILIARES
    # =========================

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

    def install_game(self):

        uid = (self.user_info or {}).get("id")
        if not uid:
            QMessageBox.warning(self, "Sessão inválida", "Usuário sem ID válido. Faça login novamente.")
            return
        # se já está instalado: jogar
        if self.is_installed():
            self.play_game()
            return

        # ✅ bloqueia se não tiver plano/token ativo
        if not user_can_download(self.user_info):
            QMessageBox.warning(self, "Acesso negado",
                                "Seu plano/token não está ATIVO. Ative seu acesso para baixar jogos.")
            return

        self.btn_install.setText("BAIXANDO... 0%")
        self.btn_install.setEnabled(False)

        signals = baixar_jogo(self.game_title, self.download_url, card=self)

        signals.progress.connect(self._set_progress)

        # MUITO IMPORTANTE: capture o signals aqui
        signals.finished.connect(lambda: self._on_install_finished(signals))

        def on_error(msg):
            self.btn_install.setText("INSTALAR")
            self.btn_install.setEnabled(True)
            QMessageBox.warning(self, "Erro no download", msg)

        signals.error.connect(on_error)

    def _on_install_finished(self, signals):
        install_dir = signals.install_dir or os.path.join(GAMES_DIR, self.game_title)

        # aqui o downloader já tentou detectar exe e proteger
        exe_rel = getattr(signals, "exe_relpath", "") or ""
        exe_enc = getattr(signals, "exe_enc_path", "") or ""
        print("install_dir:", signals.install_dir)
        print("exe_relpath:", signals.exe_relpath)
        print("exe_enc_path:", signals.exe_enc_path)

        # salva no instalados.json
        data = load_installed()
        data[self.game_title] = {
            "install_dir": install_dir,
            "exe": exe_rel,
            "exe_enc": exe_enc,
            "capa_url": self.image_url or "",
            "genero": self.genres or [],
            "descricao": self.descricao or ""  # ✅
        }
        save_installed(data)

        self.set_playable()
        self.btn_uninstall.setVisible(True)
        QMessageBox.information(self, "Sucesso", f"{self.game_title} instalado com sucesso!")
        self.btn_uninstall.setVisible(True)

    def uninstall_game(self):
        data = load_installed()
        info = data.get(self.game_title) or {}
        install_dir = info.get("install_dir", "")

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

        try:
            # remove pasta do jogo
            if install_dir and os.path.isdir(install_dir):
                import shutil
                shutil.rmtree(install_dir, ignore_errors=True)

            # remove do instalados.json
            if self.game_title in data:
                del data[self.game_title]
                save_installed(data)

            # ===== VOLTA BOTÃO PRINCIPAL PARA INSTALAR =====
            self.btn_install.setText("INSTALAR")
            self.btn_install.setEnabled(True)
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
            }
            """)

            try:
                self.btn_install.clicked.disconnect()
            except Exception:
                pass
            self.btn_install.clicked.connect(self.install_game)

            # ===== REQUISITOS VOLTA NORMAL =====
            self.btn_req.setEnabled(True)

            # ===== DESINSTALAR: VOLTA PARA "APAGADO" (SEM SUMIR) =====
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

        except Exception as e:
            # se falhar, reabilita tudo
            self.btn_install.setEnabled(True)
            self.btn_req.setEnabled(True)

            # tenta voltar desinstalar ao estado correto (se ainda estiver instalado)
            if self.is_installed():
                self.set_playable()
            else:
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

        exe_rel = (info.get("exe") or "").strip()  # ex: "Raft.exe" ou "Raft\\Raft.exe"
        exe_enc = (info.get("exe_enc") or "").strip()  # caminho do .enc

        if not exe_rel and exe_enc:
            # fallback se por algum motivo não salvou exe_rel
            exe_rel = find_best_exe(install_dir)

        if not exe_rel:
            QMessageBox.warning(self, "Erro", "Não encontrei o executável do jogo (exe).")
            return

        exe_path = os.path.normpath(os.path.join(install_dir, exe_rel))
        exe_dir = os.path.dirname(exe_path)

        def _run_exe(real_exe_path: str):
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200

            return subprocess.Popen(
                [real_exe_path],
                cwd=os.path.dirname(real_exe_path),  # ✅ CWD correto
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                close_fds=True
            )

        # ✅ 1) Se tem exe protegido: descriptografa SEM trocar nome (Unity precisa do nome certo)
        if exe_enc and os.path.exists(exe_enc):
            try:
                # ✅ Descriptografa para o exe real do jogo (ex: Raft.exe)
                decrypt_file_to(exe_enc, exe_path)

                p = _run_exe(exe_path)

                # ✅ Opcional recomendado: limpar/reproteger quando fechar
                def _cleanup_when_exit():
                    try:
                        p.wait()
                    finally:
                        try:
                            # aqui você escolhe: apagar exe descriptografado
                            # (ou recriptografar de volta se você tiver função)
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
                _run_exe(exe_path)
                return
            except Exception as e:
                QMessageBox.warning(self, "Erro ao iniciar", f"Falhou ao abrir:\n{exe_path}\n\nErro:\n{e}")
                return

        QMessageBox.warning(self, "Erro", f"Executável não encontrado:\n{exe_path}")

    def show_requirements(self):
        texto = (self.descricao or "").strip()
        if not texto:
            texto = "Descrição / requisitos não informados."

        # melhora a leitura: garante quebras e espaços
        texto = texto.replace("\\n", "\n").strip()

        self._show_requirements_dialog("Requisitos", texto)

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

        def load_installed():
            if not os.path.exists(JSON_INSTALLED):
                return {}

            try:
                with open(JSON_INSTALLED, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # ✅ formato correto
                if isinstance(data, dict):
                    return data

                # ✅ formato antigo: lista
                if isinstance(data, list):
                    converted = {}
                    for item in data:
                        if isinstance(item, dict):
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

                    save_installed(converted)  # ✅ salva convertido
                    return converted

                return {}

            except Exception:
                return {}




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

        self.main_layout.addLayout(header)

        user_btn = QPushButton(f"👤 {self.user_info.get('nome', 'Usuário')}")
        user_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        user_btn.setStyleSheet("""
            QPushButton {
    border: 2px solid #836FFF;
    border-radius: 15px;
    color: #b9a9ff;
    font-size: 18px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #836FFF;
    color: #0d0b1f;
    box-shadow: 0 0 10px #836FFF;
}
        """)
        user_btn.clicked.connect(self.open_profile)
        header.addWidget(user_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.main_layout.addLayout(header)

        # NavBar
        nav_callbacks = { "EXPLORAR": self.refresh_page, "INSTALADOS": self.open_instalados }
        self.nav_bar = NavBar(parent=self, callbacks=nav_callbacks)
        self.main_layout.addWidget(self.nav_bar)

        # <<< NOVO: Barra de filtros fixa (igual do installed.py, porém via componente reutilizável)
        self.filter_bar = FilterBar(on_filter_change=self.apply_filters)
        self.filter_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.main_layout.addWidget(self.filter_bar)

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

        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background: transparent;")

        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setHorizontalSpacing(20)
        self.grid_layout.setVerticalSpacing(50)  # seu espaçamento atual
        self.grid_layout.setContentsMargins(0, 5, 0, 25)  # um respiro embaixo

        self.scroll_area.setWidget(self.grid_widget)
        self.main_layout.addWidget(self.scroll_area)

        self.setLayout(self.main_layout)
        self.setMinimumSize(720, 480)
        self.showMaximized()

        self.cards = []
        self.load_games()
        # aplica filtros atuais (mantém layout consistente mesmo sem jogos)
        self.apply_filters()

    def open_profile(self):
        self.profile_window = ProfilePage(user_info=self.user_info)
        self.profile_window.show()
        self.close()

    def refresh_page(self):
        self.new_window = MainWindow(usuario_info=self.user_info)
        self.new_window.show()
        self.close()

    def open_instalados(self):
        from installed import InstaladosPage
        self.installed_window = InstaladosPage(usuario_info=self.user_info)
        self.installed_window.show()
        self.close()

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
            jogos_data = response.json().get("jogos", [])
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

        for idx, jogo in enumerate(jogos_data):
            card = GameCard(
                image_url=jogo.get("capa_url", ""),
                title_top=jogo.get("nome", ""),
                title_bottom="",
                download_url=f"{API_BASE}/jogos/{jogo['id']}/download?user_id={uid}",
                genres=jogo.get("genero", []),
                user_info=self.user_info,
                descricao=jogo.get("descricao", "")
            )

            self.cards.append(card)
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

        for card in self.cards:
            title = card.game_title.lower()
            genre_match = True
            if active_genres:
                # compara interseção de gêneros do card com selecionados
                genre_match = any(g in card.genres for g in active_genres)
            card.setVisible(search_text in title and genre_match)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont(FONT_PATH)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
