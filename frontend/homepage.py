# homepage.py
import os
import sys
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFrame, QProgressBar
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer
from utils import resource_path


class HomePage(QWidget):
    def __init__(self, *, next_window_factory, delay_ms: int = 1800):
        super().__init__()

        self.next_window_factory = next_window_factory
        self.delay_ms = delay_ms
        self.next_window = None
        self.progress_value = 0

        self.setWindowTitle("PrimeX")
        self.setStyleSheet("""
            QWidget {
                background-color: #0d0b1f;
                color: #b9a9ff;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setFixedSize(520, 520)
        card.setStyleSheet("""
            QFrame {
                background-color: #120f2a;
                border: 2px solid #2a245f;
                border-radius: 28px;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(18)
        card_layout.setContentsMargins(35, 35, 35, 35)

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setFixedSize(360, 260)
        self.logo.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
            }
        """)

        logo_path = resource_path(os.path.join("logos", "primex_logo.png"))

        if os.path.exists(logo_path):
            pm = QPixmap(logo_path)
            if not pm.isNull():
                pm = pm.scaled(
                    340,
                    240,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.logo.setPixmap(pm)
            else:
                self.logo.setText("PrimeX")
        else:
            self.logo.setText("PrimeX")

        self.logo.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                color: #836FFF;
                font-size: 54px;
                font-weight: bold;
            }
        """)

        card_layout.addWidget(self.logo)

        self.status = QLabel("Carregando sua biblioteca...")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                color: #e0d9ff;
                font-size: 28px;
            }
        """)
        card_layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setFixedSize(360, 16)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #0d0b1f;
                border: 1px solid #2a245f;
                border-radius: 8px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #836FFF,
                    stop:1 #4cc3ff
                );
                border-radius: 8px;
            }
        """)
        card_layout.addWidget(self.progress)

        self.tip = QLabel("Preparando a PrimeX para você...")
        self.tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tip.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                color: #8f82d8;
                font-size: 20px;
            }
        """)
        card_layout.addWidget(self.tip)

        main_layout.addWidget(card)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_progress)
        self.timer.start(25)

        QTimer.singleShot(self.delay_ms, self.go_next)

        self.showMaximized()

    def animate_progress(self):
        self.progress_value += 2
        if self.progress_value > 100:
            self.progress_value = 0

        self.progress.setValue(self.progress_value)

    def go_next(self):
        self.timer.stop()

        # NÃO esconder a splash antes.
        # Mantém a tela bonita aberta enquanto o Explore é criado.
        self.status.setText("Abrindo PrimeX...")
        self.tip.setText("Preparando sua biblioteca de jogos...")

        self.next_window = self.next_window_factory()
        self.next_window.setWindowTitle("PrimeX")
        self.next_window.showMaximized()

        # força o Qt a pintar a nova janela antes de fechar a splash
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        # fecha a splash só depois que o Explore já apareceu
        QTimer.singleShot(300, self.close)

    def close_extra_windows(self):
        from PyQt6.QtWidgets import QApplication

        for w in QApplication.topLevelWidgets():
            if w is self.next_window:
                continue

            title = (w.windowTitle() or "").strip().lower()

            if title in ("python", ""):
                try:
                    w.close()
                except Exception:
                    pass