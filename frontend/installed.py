import os
import sys
import json

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFontDatabase

from navbar import NavBar
from profile import ProfilePage
from filter_bar import FilterBar
from explore_page import GameCard


# =========================
# PATHS
# =========================
BASE_DIR = os.getcwd()
GAMES_DIR = os.path.join(BASE_DIR, "games")
JSON_INSTALLED = os.path.join(GAMES_DIR, "instalados.json")

FONT_PATH = os.path.join(BASE_DIR, "assets", "fonts", "VT323-Regular.ttf")


# =========================
# INSTALADOS PAGE
# =========================
class InstaladosPage(QWidget):
    def __init__(self, usuario_info=None):
        super().__init__()

        self.user_info = usuario_info or {
            "id": "usuario123",
            "nome": "Usuário",
            "is_admin": False,
            "token": ""
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
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addStretch()

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

        header_layout.addWidget(user_btn)
        self.main_layout.addLayout(header_layout)

        # =========================
        # NAVBAR
        # =========================
        nav_callbacks = {
            "EXPLORAR": self.open_explore,
            "INSTALADOS": self.reload_page
        }
        self.nav_bar = NavBar(parent=self, callbacks=nav_callbacks)
        self.main_layout.addWidget(self.nav_bar)

        # =========================
        # FILTER BAR (REUTILIZADO)
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
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(20)
        self.grid_layout.setContentsMargins(0, 5, 0, 0)

        self.main_layout.addWidget(self.grid_widget)

        self.cards = []

        self.setLayout(self.main_layout)
        self.setMinimumSize(720, 480)
        self.showMaximized()

        self.load_installed_games()
        self.apply_filters()

    # =========================
    # NAV ACTIONS
    # =========================
    def open_profile(self):
        self.profile_window = ProfilePage(user_info=self.user_info)
        self.profile_window.show()
        self.close()

    def open_explore(self):
        from explore_page import MainWindow
        self.explore_window = MainWindow(usuario_info=self.user_info)
        self.explore_window.show()
        self.close()

    def reload_page(self):
        self.new_window = InstaladosPage(usuario_info=self.user_info)
        self.new_window.show()
        self.close()

    # =========================
    # LOAD INSTALLED GAMES
    # =========================
    def load_installed_games(self):
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                self.grid_layout.removeWidget(widget)
                widget.setParent(None)

        self.cards.clear()

        if not os.path.exists(JSON_INSTALLED):
            return

        try:
            with open(JSON_INSTALLED, "r", encoding="utf-8") as f:
                jogos = json.load(f)
            if not isinstance(jogos, list):
                jogos = []
        except Exception:
            jogos = []

        for idx, jogo in enumerate(jogos):
            card = GameCard(
                image_url=jogo.get("capa_url", ""),
                title_top=jogo.get("nome", ""),
                title_bottom="",
                download_url="",  # não usado em instalados
                genres=jogo.get("genero", [])
            )

            # força estado "JOGAR"
            card.set_playable()

            self.cards.append(card)

            row = idx // 5
            col = idx % 5
            self.grid_layout.addWidget(
                card, row, col, alignment=Qt.AlignmentFlag.AlignTop
            )

    # =========================
    # FILTERS
    # =========================
    def apply_filters(self, search_text=None, active_genres=None):
        if search_text is None or active_genres is None:
            search_text, active_genres = self.filter_bar.get_filters()

        for card in self.cards:
            title = card.game_title.lower()
            genre_match = True

            if active_genres:
                genre_match = any(g in card.genres for g in active_genres)

            card.setVisible(search_text in title and genre_match)


# =========================
# MAIN
# =========================
def main():
    os.makedirs(GAMES_DIR, exist_ok=True)
    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont(FONT_PATH)
    window = InstaladosPage()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
