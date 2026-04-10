import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase

from navbar import NavBar
from profile import ProfilePage
from utils import resource_path
from download_manager import download_manager


FONT_PATH = resource_path("fonts/VT323-Regular.ttf")


class DownloadRow(QFrame):
    def __init__(self, game_name: str, parent=None):
        super().__init__(parent)
        self.game_name = game_name

        self.setStyleSheet("""
            QFrame {
                background-color: #120f2a;
                border: 2px solid #2a245f;
                border-radius: 14px;
            }
            QLabel {
                color: #e0d9ff;
                font-size: 18px;
                background: transparent;
                border: none;
            }
            QPushButton {
                background-color: #836FFF;
                color: #0d0b1f;
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9a7dff;
            }
        """)

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(14, 14, 14, 14)
        self.root.setSpacing(10)

        top = QHBoxLayout()
        self.lbl_title = QLabel(game_name)
        self.lbl_status = QLabel("Na fila")
        top.addWidget(self.lbl_title)
        top.addStretch()
        top.addWidget(self.lbl_status)

        self.progress_bg = QFrame()
        self.progress_bg.setFixedHeight(18)
        self.progress_bg.setStyleSheet("""
            QFrame {
                background-color: #0d0b1f;
                border: 1px solid #2a245f;
                border-radius: 9px;
            }
        """)

        self.progress_fill = QFrame(self.progress_bg)
        self.progress_fill.setGeometry(0, 0, 0, 18)
        self.progress_fill.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #836FFF,
                    stop:1 #4cc3ff
                );
                border-radius: 9px;
            }
        """)

        bottom = QHBoxLayout()
        self.lbl_progress = QLabel("0%")
        self.btn_retry = QPushButton("TENTAR NOVAMENTE")
        self.btn_remove = QPushButton("REMOVER")

        self.btn_retry.clicked.connect(self.retry_download)
        self.btn_remove.clicked.connect(self.remove_download)

        bottom.addWidget(self.lbl_progress)
        bottom.addStretch()
        bottom.addWidget(self.btn_retry)
        bottom.addWidget(self.btn_remove)

        self.root.addLayout(top)
        self.root.addWidget(self.progress_bg)
        self.root.addLayout(bottom)

        self.update_data(download_manager.get_download(game_name))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        data = download_manager.get_download(self.game_name)
        self._apply_progress(data.get("progress", 0))

    def _apply_progress(self, pct: int):
        pct = max(0, min(100, int(pct)))
        w = self.progress_bg.width()
        fill_w = int(w * pct / 100)
        self.progress_fill.setGeometry(0, 0, fill_w, self.progress_bg.height())

    def update_data(self, data: dict):
        if not data:
            return

        status = data.get("status", "na_fila")
        progress = int(data.get("progress", 0))
        error = data.get("error", "")

        status_text = {
            "na_fila": "Na fila",
            "baixando": "Baixando",
            "concluido": "Concluído",
            "erro": "Erro",
            "extraindo": "Extraindo",
            "instalando": "Instalando",
        }.get(status, status)

        self.lbl_status.setText(status_text)
        self.lbl_progress.setText(f"{progress}%")
        self._apply_progress(progress)

        self.btn_retry.setVisible(status == "erro")
        self.btn_remove.setVisible(status in ("erro", "concluido", "na_fila"))

        if status == "erro" and error:
            self.lbl_status.setText(f"Erro: {error}")

    def retry_download(self):
        download_manager.retry_download(self.game_name)

    def remove_download(self):
        download_manager.remove_download(self.game_name)
        self.setParent(None)
        self.deleteLater()


class DownloadsPage(QWidget):
    def __init__(self, usuario_info=None):
        super().__init__()

        self.user_info = usuario_info or {
            "id": "",
            "nome": "Usuário",
            "is_admin": False,
            "token": ""
        }

        self.setWindowTitle("PrimeX • Downloads")
        self.setStyleSheet("""
            QWidget {
                background-color: #0d0b1f;
                color: #b9a9ff;
                font-family: 'VT323';
            }
        """)

        self.rows = {}

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(8)

        header = QHBoxLayout()
        header.addStretch()

        self.user_btn = QPushButton(f"👤 {self.user_info.get('nome', 'Usuário')}")
        self.user_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.user_btn.setStyleSheet("""
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
            }
        """)
        self.user_btn.clicked.connect(self.open_profile)
        header.addWidget(self.user_btn)
        self.main_layout.addLayout(header)

        nav_callbacks = {
            "EXPLORAR": self.open_explore,
            "INSTALADOS": self.open_instalados,
            "DOWNLOADS": self.reload_page
        }
        self.nav_bar = NavBar(parent=self, callbacks=nav_callbacks)
        self.main_layout.addWidget(self.nav_bar)

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

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 5, 0, 25)
        self.container_layout.setSpacing(14)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.container)
        self.main_layout.addWidget(self.scroll_area)

        self.empty_label = QLabel("Nenhum download no momento.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("font-size: 24px; color: #b9a9ff;")
        self.container_layout.addWidget(self.empty_label)

        download_manager.download_updated.connect(self.on_download_updated)
        download_manager.download_finished.connect(self.on_download_finished)
        download_manager.download_error.connect(self.on_download_error)
        download_manager.queue_updated.connect(self.reload_downloads)

        self.reload_downloads()
        self.showMaximized()

    def open_profile(self):
        self.profile_window = ProfilePage(user_info=self.user_info)
        self.profile_window.show()
        self.close()

    def open_explore(self):
        from explore_page import MainWindow
        self.explore_window = MainWindow(usuario_info=self.user_info)
        self.explore_window.show()
        self.close()

    def open_instalados(self):
        from installed import InstaladosPage
        self.installed_window = InstaladosPage(usuario_info=self.user_info)
        self.installed_window.show()
        self.close()

    def reload_page(self):
        self.new_window = DownloadsPage(usuario_info=self.user_info)
        self.new_window.show()
        self.close()

    def clear_rows(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def reload_downloads(self):
        self.clear_rows()
        self.rows.clear()

        items = download_manager.get_all_downloads()

        if not items:
            self.empty_label = QLabel("Nenhum download no momento.")
            self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.empty_label.setStyleSheet("font-size: 24px; color: #b9a9ff;")
            self.container_layout.addWidget(self.empty_label)
            return

        for item in items:
            row = DownloadRow(item["game_name"])
            self.rows[item["game_name"]] = row
            self.container_layout.addWidget(row)

            row.update_data(item)

        self.container_layout.addStretch()

    def on_download_updated(self, game_name: str, data: dict):
        if game_name not in self.rows:
            self.reload_downloads()
            return
        self.rows[game_name].update_data(data)

    def on_download_finished(self, game_name: str):
        if game_name in self.rows:
            self.rows[game_name].update_data(download_manager.get_download(game_name))

    def on_download_error(self, game_name: str, msg: str):
        if game_name in self.rows:
            self.rows[game_name].update_data(download_manager.get_download(game_name))


def main():
    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont(FONT_PATH)
    window = DownloadsPage()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()