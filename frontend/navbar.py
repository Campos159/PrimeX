from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel
)
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap
from PyQt6.QtCore import Qt, QPropertyAnimation, QRect


# =========================
# BOTÃO DA NAVBAR
# =========================
class NavButton(QWidget):
    def __init__(self, text, icon="", badge_count=0, callback=None):
        super().__init__()

        self.button = QPushButton(f"{icon}  {text}")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #e0d9ff;
                font-size: 18px;
                font-weight: 600;
                padding: 6px 14px;
            }
            QPushButton:hover {
                color: #836FFF;
            }
        """)

        if callback:
            self.button.clicked.connect(callback)

        # Badge
        self.badge = QLabel(str(badge_count))
        self.badge.setVisible(badge_count > 0)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedSize(18, 18)
        self.badge.setStyleSheet("""
            QLabel {
                background-color: #ff3b3b;
                color: white;
                border-radius: 9px;
                font-size: 11px;
                font-weight: bold;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.button)
        layout.addWidget(self.badge)


# =========================
# NAVBAR
# =========================
class NavBar(QWidget):
    def __init__(self, parent=None, callbacks=None):
        super().__init__(parent)

        # Alturas
        self.expanded_height = 72
        self.compact_height = 56
        self.setFixedHeight(self.expanded_height)



        # Layout principal
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(28, 4, 28, 6)
        self.layout.setSpacing(36)
        # =========================
        # LOGO (lado esquerdo)
        # =========================
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        pix = QPixmap("assets/logos/primex_logo.png")
        self.logo.setPixmap(
            pix.scaledToHeight(
                180,  # <<< LOGO MAIOR
                Qt.TransformationMode.SmoothTransformation
            )
        )

        # Ajuste fino de posicionamento (sobe a logo)
        self.logo.setContentsMargins(0, -4, 0, 0)

        self.layout.addWidget(self.logo)
        self.layout.addSpacing(40)

        # =========================
        # BOTÕES (CENTRO)
        # =========================
        self.buttons_container = QHBoxLayout()
        self.buttons_container.setSpacing(34)

        self.buttons = {}

        if callbacks:
            for name, data in callbacks.items():

                # modo antigo
                if callable(data):
                    self.add_button(text=name, callback=data)

                # modo novo
                elif isinstance(data, dict):
                    self.add_button(
                        text=name,
                        callback=data.get("callback"),
                        icon=data.get("icon", ""),
                        badge=data.get("badge", 0)
                    )

        self.layout.addLayout(self.buttons_container)
        self.layout.addStretch()

        # =========================
        # ANIMAÇÃO DE ALTURA (SCROLL)
        # =========================
        self.height_anim = QPropertyAnimation(self, b"geometry")
        self.height_anim.setDuration(180)

    # =========================
    # BOTÕES
    # =========================
    def add_button(self, text, icon="", badge=0, callback=None):
        btn = NavButton(text, icon, badge, callback)
        self.buttons[text] = btn
        self.buttons_container.addWidget(btn)

    def set_badge(self, button_name, count):
        if button_name in self.buttons:
            badge = self.buttons[button_name].badge
            badge.setText(str(count))
            badge.setVisible(count > 0)

    # =========================
    # COMPACTAÇÃO NO SCROLL
    # =========================
    def on_scroll(self, scroll_value):
        target_height = self.compact_height if scroll_value > 10 else self.expanded_height

        if self.height() == target_height:
            return

        geo = self.geometry()
        new_geo = QRect(
            geo.x(),
            geo.y(),
            geo.width(),
            target_height
        )

        self.height_anim.stop()
        self.height_anim.setStartValue(geo)
        self.height_anim.setEndValue(new_geo)
        self.height_anim.start()

    # =========================
    # BORDA INFERIOR
    # =========================
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)

        pen = QPen(QColor("#2a245f"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(0, self.height() - 2, self.width(), self.height() - 2)

