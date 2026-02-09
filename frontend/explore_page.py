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
from downloader import baixar_jogo
from filter_bar import FilterBar
from PyQt6.QtGui import QFontDatabase
from api_config import API_BASE
import hashlib
import requests



FONT_PATH = os.path.join(os.getcwd(), "assets", "fonts", "VT323-Regular.ttf")


# Pastas/arquivos
GAMES_DIR = os.path.join(os.getcwd(), "games")
JSON_INSTALLED = os.path.join(GAMES_DIR, "instalados.json")


# =========================
# GAME CARD
# =========================
class GameCard(QWidget):
    def __init__(self, image_url, title_top, title_bottom, download_url, genres=None):
        super().__init__()

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
        QMessageBox.information(
            self,
            "Instalação",
            f"Iniciando download de {self.game_title}"
        )
        # aqui você já pode ligar com baixar_jogo depois

    def show_requirements(self):
        QMessageBox.information(
            self,
            "Requisitos",
            "Requisitos do jogo ainda não definidos."
        )

    def is_installed(self):
        if not os.path.exists(JSON_INSTALLED):
            return False

        try:
            with open(JSON_INSTALLED, "r", encoding="utf-8") as f:
                installed = json.load(f)
            return self.game_title in installed
        except:
            return False

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
                download_url=f"http://127.0.0.1:8000/jogos/{jogo['id']}/download",
                genres=jogo.get("genero", [])  # <<< NOVO: passa gêneros ao card
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
