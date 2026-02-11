import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QGridLayout, QSizePolicy, QSpacerItem, QLineEdit, QMenu, QMessageBox
)
from PyQt6.QtGui import QPixmap, QImage, QIcon, QPainter, QColor
from PyQt6.QtCore import Qt, QSize
from profile import ProfilePage
from admin import AdminPage
from navbar import NavBar
from downloader import baixar_jogo, decrypt_file_to
from filter_bar import FilterBar
from PyQt6.QtGui import QFontDatabase
from api_config import API_BASE
import hashlib
import requests



FONT_PATH = os.path.join(os.getcwd(), "assets", "fonts", "VT323-Regular.ttf")


# Pastas/arquivos
base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
GAMES_DIR = os.path.join(base_dir, "PrimeX", "games")
JSON_INSTALLED = os.path.join(GAMES_DIR, "instalados.json")


def load_installed():
    if not os.path.exists(JSON_INSTALLED):
        return {}
    try:
        with open(JSON_INSTALLED, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

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
    """
    Regra local (client-side). O backend ainda deve validar (regra real).
    Aqui é só pra bloquear o botão.
    """
    plano = (user_info or {}).get("plano_status") or (user_info or {}).get("status") or ""
    plano = str(plano).upper().strip()

    # Ajuste os nomes conforme seu backend:
    # ATIVO / PERMANENTE / VENCIDO / SEM PLANO etc
    return plano in ("ATIVO", "PERMANENTE")





# =========================
# GAME CARD
# =========================
class GameCard(QWidget):
    def __init__(self, image_url, title_top, title_bottom, download_url, genres=None, user_info=None):

        super().__init__()

        self.user_info = user_info or {}
        self.download_url = download_url
        self.game_title = f"{title_top} {title_bottom}".strip()
        self.image_url = image_url
        self.genres = genres or []


        self.setFixedSize(260, 380)

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
        self.image_label.setFixedSize(260, 220)  # ✅ agora tá no lugar certo
        self.image_label.setFixedHeight(220)
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
        title = QLabel(self.game_title.upper())
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
        color: #e0d9ff;
        font-size: 22px;
        letter-spacing: 2px;
        padding: 12px;
        background-color: rgba(0,0,0,0.3);
        """)

        root.addWidget(title)

        # ===== BUTTONS =====
        btns = QVBoxLayout()
        btns.setContentsMargins(12, 0, 12, 12)
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

        btns.addWidget(self.btn_install)
        btns.addWidget(self.btn_req)

        root.addLayout(btns)

        if self.is_installed():
            self.set_playable()

    # =========================
    # MÉTODOS AUXILIARES
    # =========================
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_cover_pixmap()

    def install_game(self):
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

        # salva no instalados.json
        data = load_installed()
        data[self.game_title] = {
            "install_dir": install_dir,
            "exe": exe_rel,  # caminho relativo do exe original (que foi removido)
            "exe_enc": exe_enc,  # caminho do arquivo criptografado
            "capa_url": self.image_url or "",
            "genero": self.genres or []
        }
        save_installed(data)

        self.set_playable()
        QMessageBox.information(self, "Sucesso", f"{self.game_title} instalado com sucesso!")

    def play_game(self):
        data = load_installed()
        info = data.get(self.game_title) or {}

        install_dir = info.get("install_dir", "")
        if not install_dir or not os.path.isdir(install_dir):
            QMessageBox.warning(self, "Erro", "Jogo não encontrado. Reinstale.")
            self.btn_install.setText("INSTALAR")
            return

        exe_rel = (info.get("exe") or "").strip()
        exe_enc = (info.get("exe_enc") or "").strip()

        # 1) se ainda existir exe (caso antigo), tenta abrir direto
        if exe_rel:
            exe_path = os.path.join(install_dir, exe_rel)
            if os.path.exists(exe_path):
                os.startfile(exe_path)
                return

        # 2) se exe foi protegido: descriptografa para temp e executa
        if exe_enc and os.path.exists(exe_enc):
            run_dir = os.path.join(os.getenv("LOCALAPPDATA") or os.path.expanduser("~"), "PrimeX", "run_cache",
                                   self.game_title)
            os.makedirs(run_dir, exist_ok=True)

            # nome do exe temp
            temp_exe = os.path.join(run_dir, os.path.basename(exe_rel) if exe_rel else f"{self.game_title}.exe")

            try:
                decrypt_file_to(exe_enc, temp_exe)
                os.startfile(temp_exe)
                return
            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Não foi possível iniciar o jogo:\n{e}")
                return

        # 3) fallback: tenta detectar exe normal (casos antigos)
        exe_rel = find_best_exe(install_dir)
        if exe_rel:
            exe_path = os.path.join(install_dir, exe_rel)
            if os.path.exists(exe_path):
                # salva pra não precisar detectar toda hora
                info["exe"] = exe_rel
                data[self.game_title] = info
                save_installed(data)

                os.startfile(exe_path)
                return

        QMessageBox.information(self, "Atenção",
                                "Não consegui localizar o executável automaticamente. Abrindo a pasta.")
        os.startfile(install_dir)

    def show_requirements(self):
        QMessageBox.information(
            self,
            "Requisitos",
            "Requisitos do jogo ainda não definidos."
        )



    def is_installed(self):
        data = load_installed()
        info = data.get(self.game_title)
        if not info:
            return False

        install_dir = info.get("install_dir", "")
        return bool(install_dir) and os.path.isdir(install_dir)

    def set_playable(self):
        self.btn_install.setText("JOGAR")
        self.btn_install.setStyleSheet("""
        QPushButton {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #4cc3ff,
                stop:1 #00ffaa
            );
            color: #0d0b1f;
            font-size: 18px;
            border-radius: 10px;
            padding: 10px;
        }
        """)

        try:
            self.btn_install.clicked.disconnect()
        except Exception:
            pass
        self.btn_install.clicked.connect(self.play_game)


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
        self.user_info = usuario_info or {"id": "usuario123", "nome": "Usuário", "is_admin": False, "token": ""}

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
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(20)
        self.grid_layout.setContentsMargins(0, 5, 0, 0)
        self.grid_widget.setLayout(self.grid_layout)
        self.main_layout.addWidget(self.grid_widget)

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
        import requests
        try:
            response = requests.get(f"{API_BASE}/admin/listar_jogos")
            jogos_data = response.json().get("jogos", [])
        except:
            jogos_data = []

        for i in reversed(range(self.grid_layout.count())):
            widget_to_remove = self.grid_layout.itemAt(i).widget()
            if widget_to_remove:
                self.grid_layout.removeWidget(widget_to_remove)
                widget_to_remove.setParent(None)

        self.cards.clear()

        for idx, jogo in enumerate(jogos_data):
            card = GameCard(
                image_url=jogo.get("capa_url", ""),
                title_top=jogo.get("nome", ""),
                title_bottom="",
                download_url=f"{API_BASE}/jogos/{jogo['id']}/download?user_id={self.user_info['id']}",
                genres=jogo.get("genero", []),
                user_info=self.user_info
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
            placeholder.setFixedSize(280, 390)
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
