# homepage.py
import os
import sys
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer
from utils import resource_path



def resource_path(relative_path: str) -> str:
    """
    Funciona em DEV e também no PyInstaller (onefile/onedir).
    """
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class HomePage(QWidget):
    def __init__(self, *, next_window_factory, delay_ms: int = 1800):
        """
        next_window_factory: função/callback que cria a próxima janela (LoginWindow).
        delay_ms: tempo do splash antes de ir pro login.
        """
        super().__init__()
        self.next_window_factory = next_window_factory
        self.delay_ms = delay_ms
        self.next_window = None

        self.setWindowTitle("PrimeX")
        self.setStyleSheet("""
            QWidget {
                background-color: #0d0b1f;
                color: #b9a9ff;
            }
        """)

        # Layout central
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)

        # Logo
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_path = resource_path(os.path.join("logos", "primex_logo.png"))
        pix = QPixmap(logo_path)
        if os.path.exists(logo_path):
            pm = QPixmap(logo_path)
            # deixa grande e bonito
            pm = pm.scaled(420, 420, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.logo.setPixmap(pm)

        layout.addWidget(self.logo)


        # Abre login depois do delay
        QTimer.singleShot(self.delay_ms, self.go_next)

        self.showMaximized()

    def go_next(self):
        self.next_window = self.next_window_factory()
        self.next_window.show()
        self.close()
