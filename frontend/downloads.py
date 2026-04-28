import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QFrame, QMessageBox
)
from PyQt6.QtGui import QFontDatabase

from navbar import NavBar
from profile import ProfilePage
from utils import resource_path
from download_manager import download_manager
import requests
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QPainter, QPainterPath
from PyQt6.QtGui import QPixmap, QIcon


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
        self.lbl_speed = QLabel("Velocidade: —")
        self.lbl_speed.setStyleSheet("""
            QLabel {
                color: #4cc3ff;
                font-size: 17px;
                background: transparent;
                border: none;
            }
        """)
        self.lbl_eta = QLabel("Tempo restante: —")
        self.lbl_eta.setStyleSheet("""
            QLabel {
                color: #b9a9ff;
                font-size: 17px;
                background: transparent;
                border: none;
            }
        """)
        self.btn_pause = QPushButton("PAUSAR")
        self.btn_cancel = QPushButton("CANCELAR")
        self.btn_retry = QPushButton("TENTAR NOVAMENTE")
        self.btn_remove = QPushButton("REMOVER")

        self.btn_retry.clicked.connect(self.retry_download)
        self.btn_remove.clicked.connect(self.remove_download)
        self.btn_pause.clicked.connect(self.pause_or_resume_download)
        self.btn_cancel.clicked.connect(self.cancel_download)

        bottom.addWidget(self.lbl_progress)
        bottom.addSpacing(18)
        bottom.addWidget(self.lbl_speed)
        bottom.addSpacing(18)
        bottom.addWidget(self.lbl_eta)
        bottom.addStretch()

        bottom.addWidget(self.btn_pause)
        bottom.addWidget(self.btn_cancel)
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
        speed = data.get("speed", "")
        eta = data.get("eta", "")

        status_text = {
            "na_fila": "Na fila",
            "baixando": "Baixando",
            "concluido": "Concluído",
            "erro": "Erro",
            "extraindo": "Extraindo",
            "instalando": "Instalando",
        }.get(status, status)

        if status == "baixando" and eta:
            self.lbl_eta.setText(f"Tempo restante: {eta}")
        elif status == "baixando":
            self.lbl_eta.setText("Tempo restante: calculando...")
        elif status == "pausado":
            self.lbl_eta.setText("Tempo restante: pausado")
        elif status == "concluido":
            self.lbl_eta.setText("Tempo restante: concluído")
        elif status == "cancelado":
            self.lbl_eta.setText("Tempo restante: cancelado")
        else:
            self.lbl_eta.setText("Tempo restante: —")

        self.lbl_status.setText(status_text)
        self.lbl_progress.setText(f"{progress}%")
        if status == "baixando" and speed:
            self.lbl_speed.setText(f"Velocidade: {speed}")
        elif status == "baixando":
            self.lbl_speed.setText("Velocidade: calculando...")
        elif status == "pausado":
            self.lbl_speed.setText("Pausado")
        elif status == "cancelado":
            self.lbl_speed.setText("Cancelado")
        elif status in ("extraindo", "instalando", "finalizando"):
            self.lbl_speed.setText("Velocidade: —")
        elif status == "concluido":
            self.lbl_speed.setText("Concluído")
        elif status == "erro":
            self.lbl_speed.setText("Interrompido")
        else:
            self.lbl_speed.setText("Velocidade: —")
        self._apply_progress(progress)

        self.btn_pause.setVisible(status in ("baixando", "pausado"))
        self.btn_cancel.setVisible(status in ("na_fila", "baixando", "pausado"))

        if status == "pausado":
            self.btn_pause.setText("RETOMAR")
        else:
            self.btn_pause.setText("PAUSAR")

        self.btn_retry.setVisible(status in ("erro", "cancelado"))
        self.btn_remove.setVisible(status in ("erro", "concluido", "na_fila", "cancelado"))

        if status == "erro" and error:
            self.lbl_status.setText(f"Erro: {error}")

    def pause_or_resume_download(self):
        data = download_manager.get_download(self.game_name) or {}
        status = data.get("status", "")

        if status == "pausado":
            download_manager.resume_download(self.game_name)
        else:
            download_manager.pause_download(self.game_name)

    def cancel_download(self):
        resp = QMessageBox.question(
            self,
            "Cancelar download",
            f"Deseja cancelar o download de '{self.game_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if resp != QMessageBox.StandardButton.Yes:
            return

        download_manager.cancel_download(self.game_name)

    def retry_download(self):
        download_manager.retry_download(self.game_name)

    def remove_download(self):
        download_manager.remove_download(self.game_name)
        self.setParent(None)
        self.deleteLater()


class DownloadsPage(QWidget):
    def __init__(self, usuario_info=None):
        super().__init__()

        self._navigating = False

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

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(8)

        self.rows = {}

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

    def _safe_open_window(self, create_window_func, error_title="Erro"):
        if getattr(self, "_navigating", False):
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

            QMessageBox.warning(self, error_title, f"{e}")

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
        if getattr(self, "_navigating", False):
            return

        self.reload_downloads()

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