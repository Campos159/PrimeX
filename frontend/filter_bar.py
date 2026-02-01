from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton, QMenu
)
from PyQt6.QtCore import Qt, QTimer
from functools import partial


class FilterBar(QWidget):
    def __init__(self, on_filter_change=None, parent=None):
        super().__init__(parent)

        self.on_filter_change = on_filter_change
        self.active_genres = set()
        self.tag_buttons = {}  # cache dos botões (UX + performance)

        # ===== LAYOUT PRINCIPAL =====
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # ============================
        # LINHA DE BUSCA
        # ============================
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar jogo...")
        self.search_input.setFixedHeight(36)
        self.search_input.setStyleSheet("""
        QLineEdit {
            background-color: #120f2a;
            border: 2px solid #2a245f;
            border-radius: 18px;
            padding: 0 14px;
            color: #e0d9ff;
            font-size: 16px;
        }
        QLineEdit:focus {
            border-color: #836FFF;
            background-color: #18134a;
        }
        QLineEdit::placeholder {
            color: #6f66b3;
        }
        """)
        self.search_input.textChanged.connect(self._emit_filter_change)

        search_layout.addWidget(self.search_input)

        # ===== BOTÃO GÊNEROS =====
        self.genre_btn = QPushButton("🎮 Gêneros")
        self.genre_btn.setFixedHeight(36)
        self.genre_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.genre_btn.setStyleSheet("""
        QPushButton {
            background-color: #120f2a;
            border: 2px solid #2a245f;
            border-radius: 18px;
            color: #b9a9ff;
            font-size: 15px;
            padding: 0 16px;
        }
        QPushButton:hover {
            border-color: #836FFF;
            background-color: #18134a;
            color: #e0d9ff;
        }
        """)

        self.genre_menu = QMenu(self)
        self.genres = ["Ação", "Aventura", "RPG", "Esporte", "Simulação"]
        for g in self.genres:
            self.genre_menu.addAction(g, partial(self.toggle_genre, g))

        self.genre_btn.setMenu(self.genre_menu)
        search_layout.addWidget(self.genre_btn)

        main_layout.addLayout(search_layout)

        # ============================
        # ÁREA DAS TAGS (FIXA)
        # ============================
        self.tags_container = QWidget()
        self.tags_container.setFixedHeight(34)

        self.genre_tags_layout = QHBoxLayout(self.tags_container)
        self.genre_tags_layout.setContentsMargins(0, 0, 0, 0)
        self.genre_tags_layout.setSpacing(6)
        self.genre_tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        main_layout.addWidget(self.tags_container)

    # ============================
    # LÓGICA DE FILTRO
    # ============================
    def toggle_genre(self, genre):
        QTimer.singleShot(0, lambda g=genre: self._toggle_genre_safe(g))

    def _toggle_genre_safe(self, genre):
        if genre in self.active_genres:
            self.active_genres.remove(genre)
            self.tag_buttons[genre].setVisible(False)
        else:
            self.active_genres.add(genre)
            self._show_tag(genre)

        self._emit_filter_change()

    # ============================
    # TAGS (UX OTIMIZADO)
    # ============================
    def _show_tag(self, genre):
        if genre not in self.tag_buttons:
            btn = QPushButton(f"{genre} ✕")
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
            QPushButton {
                background-color: #836FFF;
                color: #0d0b1f;
                border-radius: 12px;
                padding: 0 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9a7dff;
            }
            """)
            btn.clicked.connect(partial(self.toggle_genre, genre))
            self.genre_tags_layout.addWidget(btn)
            self.tag_buttons[genre] = btn

        self.tag_buttons[genre].setVisible(True)

    # ============================
    def _emit_filter_change(self):
        if self.on_filter_change:
            self.on_filter_change(
                self.search_input.text().lower(),
                self.active_genres
            )

    def get_filters(self):
        return self.search_input.text().lower(), self.active_genres
