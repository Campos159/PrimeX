import os
import sys
import json
from PyQt6.QtGui import QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QGridLayout, QSizePolicy
)
import requests
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, QSize, QTimer
from navbar import NavBar
from profile import ProfilePage
from filter_bar import FilterBar
from utils import resource_path

# IMPORTA O GameCard da explore_page (assim o botão "JOGAR" usa a mesma lógica)
from explore_page import GameCard



# =========================
# PATHS (MESMO PADRÃO DO explore_page.py)
# =========================
BASE_DIR = os.getcwd()
FONT_PATH = os.path.join(BASE_DIR, "assets", "fonts", "VT323-Regular.ttf")

base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
GAMES_DIR = os.path.join(base_dir, "PrimeX", "games")
JSON_INSTALLED = os.path.join(GAMES_DIR, "instalados.json")


# =========================
# INSTALADOS PAGE
# =========================
class InstaladosPage(QWidget):
    def __init__(self, usuario_info=None):
        super().__init__()
        self._navigating = False

        self.user_info = usuario_info or {
            "id": "usuario123",
            "nome": "Usuário",
            "is_admin": False,
            "token": "",
            # opcional: se você usa plano_status pra download, pode manter
            # "plano_status": "ATIVO"
        }

        self.setWindowTitle("PrimeX • Instalados")
        self.setStyleSheet("""
            QWidget {
                background-color: #0d0b1f;
                color: #b9a9ff;
                font-family: 'VT323';
            }
        """)

        self.main_layout = QVBoxLayout(self)
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

        # =========================
        # NAVBAR
        # =========================
        nav_callbacks = {
            "EXPLORAR": self.open_explore,
            "INSTALADOS": self.reload_page,
            "DOWNLOADS": self.open_downloads,
            "FAVORITOS": self.open_favoritos
        }
        self.nav_bar = NavBar(parent=self, callbacks=nav_callbacks)
        self.main_layout.addWidget(self.nav_bar)

        # =========================
        # FILTER BAR
        # =========================
        self.filter_bar = FilterBar(on_filter_change=self.apply_filters)
        self.filter_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.main_layout.addWidget(self.filter_bar)

        # =========================
        # GRID
        # =========================
        # ===== SCROLL + GRID =====
        from PyQt6.QtWidgets import QScrollArea

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
            QScrollBar::handle:vertical:hover {
                background: #9a7dff;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background: transparent;")

        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setHorizontalSpacing(20)
        self.grid_layout.setVerticalSpacing(50)
        self.grid_layout.setContentsMargins(0, 5, 0, 25)

        self.scroll_area.setWidget(self.grid_widget)
        self.main_layout.addWidget(self.scroll_area)

        self.cards = []

        self.setLayout(self.main_layout)
        self.setMinimumSize(720, 480)
        self.showMaximized()

        self.load_installed_games()
        self.apply_filters()

    # =========================
    # NAV ACTIONS
    # =========================

    def _safe_open_window(self, create_window_func, error_title="Erro"):
        if getattr(self, "_navigating", False):
            return

        self._navigating = True

        try:
            if hasattr(self, "nav_bar"):
                self.nav_bar.setEnabled(False)

            # desativa todos os botões da tela imediatamente
            for btn in self.findChildren(QPushButton):
                btn.setEnabled(False)

            new_window = create_window_func()
            self._next_window = new_window

            self.hide()
            new_window.show()

            QTimer.singleShot(100, self.close)

        except Exception as e:
            self._navigating = False

            if hasattr(self, "nav_bar"):
                self.nav_bar.setEnabled(True)

            for btn in self.findChildren(QPushButton):
                btn.setEnabled(True)

            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, error_title, f"{e}")

    def open_downloads(self):
        def create():
            from downloads import DownloadsPage
            return DownloadsPage(usuario_info=self.user_info)

        self._safe_open_window(create, "Não foi possível abrir Downloads")

    def open_profile(self):
        def create():
            return ProfilePage(user_info=self.user_info)

        self._safe_open_window(create, "Não foi possível abrir Perfil")

    def open_explore(self):
        def create():
            from explore_page import MainWindow
            return MainWindow(usuario_info=self.user_info)

        self._safe_open_window(create, "Não foi possível abrir Explorar")

    def open_favoritos(self):
        def create():
            from favorites import FavoritesPage
            return FavoritesPage(usuario_info=self.user_info)

        self._safe_open_window(create, "Não foi possível abrir Favoritos")

    def reload_page(self):
        if self._navigating:
            return

        self.load_installed_games()
        self.apply_filters()

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

    # =========================
    # LOAD INSTALLED GAMES
    # =========================
    def load_installed_games(self):
        # limpa grid
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                self.grid_layout.removeWidget(widget)
                widget.setParent(None)

        self.cards.clear()

        if not os.path.exists(JSON_INSTALLED):
            return

        # instalados.json é dict:
        # { "Nome do Jogo": {install_dir, exe, exe_enc, capa_url, genero} }
        try:
            with open(JSON_INSTALLED, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}

        # monta lista apenas dos válidos (pasta existe)
        valid_items = []
        for game_title, info in data.items():
            info = info or {}
            install_dir = (info.get("install_dir") or "").strip()
            if install_dir and os.path.isdir(install_dir):
                valid_items.append((game_title, info))

        # cria cards só para válidos
        for idx, (game_title, info) in enumerate(valid_items):
            capa_url = (info.get("capa_url") or "").strip()
            genero = info.get("genero") or []

            card = GameCard(
                image_url=capa_url,
                title_top=game_title,
                title_bottom="",
                download_url="",  # não usado em instalados
                genres=genero,
                user_info=self.user_info
            )

            # força estado JOGAR (usa a lógica do GameCard, inclusive exe protegido)
            card.set_playable()

            self.cards.append(card)

            row = idx // 5
            col = idx % 5
            self.grid_layout.addWidget(card, row, col, alignment=Qt.AlignmentFlag.AlignTop)

        # placeholders pra manter layout (opcional)
        total_slots = max(5, len(valid_items))
        for idx in range(len(valid_items), total_slots):
            row = idx // 5
            col = idx % 5
            placeholder = QLabel()
            placeholder.setFixedSize(280, 390)
            placeholder.setStyleSheet("background-color: transparent; border: none;")
            self.grid_layout.addWidget(placeholder, row, col)

    # =========================
    # FILTERS
    # =========================
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


def main():
    os.makedirs(GAMES_DIR, exist_ok=True)
    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont(FONT_PATH)
    window = InstaladosPage()
    sys.exit(app.exec())