import os
import sys
import json
import requests

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QGridLayout, QSizePolicy, QScrollArea
)
from PyQt6.QtGui import QPainter, QPainterPath, QFontDatabase, QPixmap, QIcon
from PyQt6.QtCore import Qt, QSize, QTimer

from navbar import NavBar
from profile import ProfilePage
from filter_bar import FilterBar
from utils import resource_path
from api_config import API_BASE


BASE_DIR = os.getcwd()
FONT_PATH = os.path.join(BASE_DIR, "assets", "fonts", "VT323-Regular.ttf")

base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
GAMES_DIR = os.path.join(base_dir, "PrimeX", "games")


class FavoritesPage(QWidget):
    def __init__(self, usuario_info=None):
        super().__init__()
        self._navigating = False
        self.user_info = usuario_info or {
            "id": "",
            "nome": "Usuário",
            "is_admin": False,
            "token": "",
        }

        self.setWindowTitle("PrimeX • Favoritos")
        self.setMinimumSize(720, 480)
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

        self._build_header()
        self._build_navbar()
        self._build_filter_bar()
        self._build_grid()

        self.cards = []

        self.setLayout(self.main_layout)
        self.showMaximized()

        QTimer.singleShot(200, self.load_favorite_games)

    def _build_header(self):
        header = QHBoxLayout()
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

    def _build_navbar(self):
        nav_callbacks = {
            "EXPLORAR": self.open_explore,
            "FAVORITOS": self.reload_page,
            "INSTALADOS": self.open_instalados,
            "DOWNLOADS": self.open_downloads,
        }

        self.nav_bar = NavBar(parent=self, callbacks=nav_callbacks)
        self.main_layout.addWidget(self.nav_bar)

    def _build_filter_bar(self):
        self.filter_bar = FilterBar(on_filter_change=self.apply_filters)
        self.filter_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.main_layout.addWidget(self.filter_bar)

    def _build_grid(self):
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

    def _safe_open_window(self, create_window_func, error_title="Erro"):
        if self._navigating:
            return

        self._navigating = True

        try:
            if hasattr(self, "nav_bar"):
                self.nav_bar.setEnabled(False)

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
            QMessageBox.warning(self, error_title, str(e))

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

    def open_instalados(self):
        def create():
            from installed import InstaladosPage
            return InstaladosPage(usuario_info=self.user_info)

        self._safe_open_window(create, "Não foi possível abrir Instalados")

    def reload_page(self):
        if self._navigating:
            return

        self.load_favorite_games()

    def _clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def _show_empty_message(self, text):
        self._clear_grid()

        empty = QLabel(text)
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet("""
            QLabel {
                color: #b9a9ff;
                font-size: 26px;
                padding: 40px;
                background-color: #120f2a;
                border: 2px solid #2a245f;
                border-radius: 18px;
            }
        """)

        self.grid_layout.addWidget(empty, 0, 0, 1, 5)

    def _add_placeholders(self, total_visible):
        total_slots = max(5, total_visible)

        for idx in range(total_visible, total_slots):
            row = idx // 5
            col = idx % 5

            placeholder = QLabel()
            placeholder.setFixedSize(260, 485)
            placeholder.setStyleSheet("background-color: transparent; border: none;")

            self.grid_layout.addWidget(
                placeholder,
                row,
                col,
                alignment=Qt.AlignmentFlag.AlignTop
            )

    def load_favorite_games(self):
        self._clear_grid()
        self.cards.clear()

        uid = self.user_info.get("id")

        if not uid:
            self._show_empty_message("Não foi possível identificar o usuário.")
            return

        try:
            fav_response = requests.get(
                f"{API_BASE}/favorites/{uid}",
                timeout=15
            )

            if fav_response.status_code != 200:
                print("[PrimeX] Erro ao buscar favoritos:", fav_response.status_code, fav_response.text)
                self._show_empty_message("Não foi possível carregar seus favoritos.")
                return

            favorite_ids = set(
                int(x) for x in fav_response.json().get("favorites", [])
            )

            if not favorite_ids:
                self._show_empty_message("Você ainda não adicionou nenhum jogo aos favoritos.")
                return

            jogos_response = requests.get(
                f"{API_BASE}/admin/listar_jogos",
                timeout=15
            )

            if jogos_response.status_code != 200:
                print("[PrimeX] Erro ao buscar jogos:", jogos_response.status_code, jogos_response.text)
                self._show_empty_message("Não foi possível carregar a lista de jogos.")
                return

            jogos = jogos_response.json().get("jogos", [])

            favoritos = [
                jogo for jogo in jogos
                if int(jogo.get("id") or 0) in favorite_ids
            ]

            if not favoritos:
                self._show_empty_message("Nenhum dos seus favoritos foi encontrado no catálogo.")
                return

            for jogo in favoritos:
                from explore_page import GameCard
                card = GameCard(
                    image_url=jogo.get("capa_url", ""),
                    title_top=jogo.get("nome", ""),
                    title_bottom="",
                    download_url=(jogo.get("dropbox_token", "") or "").strip(),
                    genres=jogo.get("genero", []),
                    user_info=self.user_info,
                    descricao=jogo.get("descricao", ""),
                    requisitos={
                        "min": {
                            "os": jogo.get("min_os", ""),
                            "cpu": jogo.get("min_cpu", ""),
                            "ram": jogo.get("min_ram_gb"),
                            "gpu": jogo.get("min_gpu", ""),
                            "dx": jogo.get("min_directx", ""),
                            "storage": jogo.get("min_storage_gb"),
                            "notes": jogo.get("min_notes", ""),
                        },
                        "rec": {
                            "os": jogo.get("rec_os", ""),
                            "cpu": jogo.get("rec_cpu", ""),
                            "ram": jogo.get("rec_ram_gb"),
                            "gpu": jogo.get("rec_gpu", ""),
                            "dx": jogo.get("rec_directx", ""),
                            "storage": jogo.get("rec_storage_gb"),
                            "notes": jogo.get("rec_notes", ""),
                        }
                    },
                    exe_principal=jogo.get("exe_principal", ""),
                    game_id=jogo.get("id"),
                    is_favorite=True
                )

                self.cards.append(card)

            self.apply_filters()

        except Exception as e:
            print(f"[PrimeX] Erro ao carregar favoritos: {e}")
            self._show_empty_message("Erro ao carregar seus favoritos.")

    def apply_filters(self, search_text=None, active_genres=None):
        if search_text is None or active_genres is None:
            search_text, active_genres = self.filter_bar.get_filters()

        search_text = (search_text or "").lower().strip()
        active_genres = active_genres or []

        filtered_cards = []

        for card in self.cards:
            title = card.game_title.lower()

            genre_match = True
            if active_genres:
                genre_match = any(g in card.genres for g in active_genres)

            text_match = search_text in title

            if text_match and genre_match:
                filtered_cards.append(card)

        self._clear_grid()

        if not filtered_cards:
            self._show_empty_message("Nenhum favorito encontrado com esse filtro.")
            return

        for idx, card in enumerate(filtered_cards):
            row = idx // 5
            col = idx % 5

            self.grid_layout.addWidget(
                card,
                row,
                col,
                alignment=Qt.AlignmentFlag.AlignTop
            )

        self._add_placeholders(len(filtered_cards))

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
            size,
            size,
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


def main():
    os.makedirs(GAMES_DIR, exist_ok=True)

    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont(FONT_PATH)

    window = FavoritesPage()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()