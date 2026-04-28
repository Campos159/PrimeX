import sys
import os
import httpx
from datetime import datetime, timezone
from install_config import get_install_root, save_install_root
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QFileDialog, QSizePolicy, QLineEdit, QMessageBox, QDialog, QGridLayout
)
from PyQt6.QtGui import QPixmap, QCursor, QFontDatabase, QFont, QIcon
from PyQt6.QtCore import Qt, QSize

from api_config import API_BASE
from session import load_session, save_session
from utils import resource_path
from navbar import NavBar
from PyQt6.QtWidgets import QFrame
from PyQt6.QtCore import QByteArray
from PyQt6.QtGui import QPainter, QPainterPath

FONT_PATH = resource_path(os.path.join("fonts", "VT323-Regular.ttf"))


class ProfilePage(QWidget):
    def __init__(self, user_info=None):
        super().__init__()

        self._navigating = False

        # =========================
        # 1) USER INFO + PERSISTÊNCIA (CORRETO)
        # =========================
        self.user_info = dict(user_info or {})

        sess = load_session()
        if isinstance(sess, dict):
            # sessão por cima para persistir entre telas
            self.user_info.update(sess)

        # chaves mínimas
        self.user_info.setdefault("id", "")
        self.user_info.setdefault("nome", "Usuário")
        self.user_info.setdefault("token", "")
        self.user_info.setdefault("plan", "Nenhum")
        self.user_info.setdefault("plan_active", False)
        self.user_info.setdefault("expires_at", None)
        self.user_info.setdefault("avatar_url", "")

        # =========================
        # 2) TEMA
        # =========================
        self.setWindowTitle("Perfil - PrimeX")
        self.setStyleSheet("""
            QWidget {
                background-color: #0d0b1f;
                color: #b9a9ff;
                font-family: 'VT323';
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 10, 20, 20)
        main_layout.setSpacing(15)

        # =========================
        # HEADER
        # =========================
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
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
        header.addWidget(self.user_btn, alignment=Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(header)

        # =========================
        # NAVBAR
        # =========================
        nav_callbacks = {
            "EXPLORAR": self.open_explore_page,
            "INSTALADOS": self.open_instalados,
            "DOWNLOADS": self.open_downloads
        }
        self.nav_bar = NavBar(parent=self, callbacks=nav_callbacks)
        main_layout.addWidget(self.nav_bar)

        # =========================
        # CARD DO PERFIL
        # =========================
        profile_card = QFrame()
        profile_card.setStyleSheet("""
            QFrame {
                background-color: #120f2a;
                border: 2px solid #2a245f;
                border-radius: 22px;
            }
        """)
        profile_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        card_layout = QVBoxLayout(profile_card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(18)

        title = QLabel("Meu Perfil")
        title.setStyleSheet("font-size: 28px; color: white; font-weight: bold;")
        card_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)

        profile_layout = QHBoxLayout()
        profile_layout.setSpacing(26)
        profile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Avatar
        self.profile_pic = QLabel()
        self.profile_pic.setFixedSize(150, 150)
        self.profile_pic.setStyleSheet("""
            QLabel {
                border-radius: 75px;
                background-color: #1b1640;
                border: 3px solid #836FFF;
            }
        """)
        self.profile_pic.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.profile_pic.mousePressEvent = lambda e: self.open_avatar_picker()
        self._apply_avatar(self.user_info.get("avatar_url", ""))

        # info
        profile_info_layout = QVBoxLayout()
        profile_info_layout.setSpacing(10)

        self.name_label = QLabel(self.user_info.get("nome", "Usuário"))
        self.name_label.setStyleSheet("font-size: 26px; font-weight: bold; color: white;")

        self.plan_label = QLabel("Plano Ativo: —")
        self.plan_label.setStyleSheet("font-size: 18px; color: #ff5555;")

        self.time_left_label = QLabel("Tempo restante: —")
        self.time_left_label.setStyleSheet("font-size: 18px; color: #e0d9ff;")

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Digite seu token aqui")
        self.token_input.setFixedHeight(38)
        self.token_input.setFixedWidth(280)
        self.token_input.setText(self.user_info.get("token", ""))
        self.token_input.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border-radius: 8px;
                border: 1px solid #007eff;
                background-color: #0d0b1f;
                color: white;
                font-size: 14px;
            }
        """)

        self.token_btn = QPushButton("Ativar Token")
        self.token_btn.setFixedHeight(38)
        self.token_btn.setFixedWidth(280)
        self.token_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.token_btn.setStyleSheet("""
            QPushButton {
                background-color: #007eff;
                color: white;
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #005bb5;
            }
        """)
        self.token_btn.clicked.connect(self.activate_token)

        self.install_path_label = QLabel(f"Pasta de instalação:\n{get_install_root()}")
        self.install_path_label.setStyleSheet("font-size: 15px; color: #e0d9ff;")

        self.install_path_btn = QPushButton("Escolher local de instalação")
        self.install_path_btn.setFixedHeight(38)
        self.install_path_btn.setFixedWidth(280)
        self.install_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_path_btn.setStyleSheet("""
            QPushButton {
                background-color: #836FFF;
                color: white;
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #6f55ff;
            }
        """)
        self.install_path_btn.clicked.connect(self.choose_install_path)

        self.avatar_btn = QPushButton("Alterar avatar")
        self.avatar_btn.setFixedHeight(38)
        self.avatar_btn.setFixedWidth(280)
        self.avatar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.avatar_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a245f;
                color: #e0d9ff;
                border: 1px solid #836FFF;
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #836FFF;
                color: #0d0b1f;
            }
        """)
        self.avatar_btn.clicked.connect(self.open_avatar_picker)

        self.logout_btn = QPushButton("Sair da conta")
        self.logout_btn.setFixedHeight(38)
        self.logout_btn.setFixedWidth(280)
        self.logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 85, 85, 0.12);
                color: #ffb3b3;
                border: 1px solid #ff5555;
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ff5555;
                color: #0d0b1f;
            }
        """)
        self.logout_btn.clicked.connect(self.logout_user)

        profile_info_layout.addWidget(self.name_label)
        profile_info_layout.addWidget(self.plan_label)
        profile_info_layout.addWidget(self.time_left_label)
        profile_info_layout.addWidget(self.token_input)
        profile_info_layout.addWidget(self.token_btn)
        profile_info_layout.addWidget(self.install_path_label)
        profile_info_layout.addWidget(self.install_path_btn)
        profile_info_layout.addWidget(self.avatar_btn)
        profile_info_layout.addWidget(self.logout_btn)

        profile_layout.addWidget(self.profile_pic)
        profile_layout.addLayout(profile_info_layout)

        card_layout.addLayout(profile_layout)

        main_layout.addWidget(profile_card, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addStretch()

        self.setLayout(main_layout)
        self.setMinimumSize(720, 480)
        self.showMaximized()

        # =========================
        # 3) APLICA UI DO PLANO (LENDO SESSÃO)
        # =========================
        self._apply_plan_ui()



    # =========================
    # UI helpers
    # =========================
    def _apply_plan_ui(self):
        plano = self.user_info.get("plan", "Nenhum")
        ativo = bool(self.user_info.get("plan_active"))

        self.plan_label.setText(f"Plano Ativo: {plano}")
        if ativo:
            self.plan_label.setStyleSheet("font-size: 18px; color: #00ff88;")
        else:
            self.plan_label.setStyleSheet("font-size: 16px; color: #ff5555;")

        expires_at = self.user_info.get("expires_at")

        if ativo:
            if expires_at:
                try:
                    exp_str = str(expires_at).replace("Z", "+00:00")
                    exp = datetime.fromisoformat(exp_str)
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    delta = exp - now
                    if delta.total_seconds() <= 0:
                        self.time_left_label.setText("Tempo restante: Expirado")
                        self.user_info["plan_active"] = False
                        self._persist_session()
                        self.plan_label.setStyleSheet("font-size: 16px; color: #ff5555;")
                    else:
                        dias = delta.days
                        horas = (delta.seconds // 3600)
                        minutos = (delta.seconds % 3600) // 60
                        self.time_left_label.setText(f"Tempo restante: {dias}d {horas}h {minutos}m")
                except Exception:
                    self.time_left_label.setText("Tempo restante: —")
            else:
                self.time_left_label.setText("Tempo restante: Permanente ✅")
        else:
            self.time_left_label.setText("Tempo restante: —")

        # garante que o campo token mostre o token salvo
        self.token_input.setText(self.user_info.get("token", ""))

    def _persist_session(self):
        save_session({
            "id": self.user_info.get("id"),
            "nome": self.user_info.get("nome"),
            "token": self.user_info.get("token"),
            "plan": self.user_info.get("plan"),
            "plan_active": self.user_info.get("plan_active"),
            "expires_at": self.user_info.get("expires_at"),
            "avatar_url": self.user_info.get("avatar_url"),
        })

    def _get_avatar_options(self):
        try:
            response = httpx.get(f"{API_BASE}/avatars/disponiveis", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("avatars", [])
        except Exception:
            pass

        return []

    def _pixmap_from_source(self, source: str, size: int = 130):
        pixmap = QPixmap()

        if not source:
            return pixmap

        if source.startswith("http://") or source.startswith("https://"):
            try:
                r = httpx.get(source, timeout=10)
                if r.status_code == 200:
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

    def _apply_avatar(self, source: str):
        size = 150
        inner_margin = 5
        x_offset = 0  # negativo = puxa para a esquerda
        y_offset = 0

        pix = self._pixmap_from_source(source, size)

        if pix.isNull():
            default_avatar = resource_path("assets/profile_default.png")
            pix = self._pixmap_from_source(default_avatar, size)

        if pix.isNull():
            return

        # recorte central quadrado
        w = pix.width()
        h = pix.height()
        side = min(w, h)

        x = (w - side) // 2
        y = (h - side) // 2

        cropped = pix.copy(x, y, side, side)

        cropped = cropped.scaled(
            size, size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        path = QPainterPath()
        path.addEllipse(
            inner_margin,
            inner_margin,
            size - (inner_margin * 2),
            size - (inner_margin * 2)
        )
        painter.setClipPath(path)

        draw_size = size - (inner_margin * 2)

        painter.drawPixmap(
            inner_margin + x_offset,
            inner_margin + y_offset,
            draw_size,
            draw_size,
            cropped
        )

        painter.end()

        self.profile_pic.setPixmap(rounded)
        self.profile_pic.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _save_avatar(self, source: str):
        self.user_info["avatar_url"] = source
        self._persist_session()
        self._apply_avatar(source)

    def open_downloads(self):
        if self._navigating:
            return

        self._navigating = True

        try:
            from downloads import DownloadsPage
            self.downloads_window = DownloadsPage(usuario_info=self.user_info)
            self.downloads_window.show()

            self.hide()
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(300, self.close)

        except Exception as e:
            self._navigating = False
            QMessageBox.warning(self, "Erro", f"Não foi possível abrir Downloads:\n{e}")

    # =========================
    # Avatares
    # =========================
    def open_avatar_picker(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Escolher Avatar")
        dialog.setFixedSize(520, 420)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #120f2a;
                color: #b9a9ff;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Escolha um avatar")
        title.setStyleSheet("font-size: 24px; color: #e0d9ff; font-weight: bold;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)

        subtitle = QLabel("Selecione um ícone para o seu perfil")
        subtitle.setStyleSheet("font-size: 16px; color: #b9a9ff;")
        layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignHCenter)

        grid = QGridLayout()
        grid.setSpacing(14)

        avatars = self._get_avatar_options()

        if not avatars:
            empty_label = QLabel("Nenhum avatar disponível no momento.")
            empty_label.setStyleSheet("font-size: 16px; color: #e0d9ff;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty_label)

        row = col = 0
        for avatar in avatars:
            name = avatar.get("nome", "")
            source = avatar.get("image_url", "")

            btn = QPushButton()
            btn.setFixedSize(110, 110)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(name)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0d0b1f;
                    border: 2px solid #2a245f;
                    border-radius: 16px;
                }
                QPushButton:hover {
                    border: 2px solid #836FFF;
                    background-color: #1b1640;
                }
            """)

            pix = self._pixmap_from_source(source, 96)
            if not pix.isNull():
                btn.setIcon(QIcon(pix))
                btn.setIconSize(QSize(96, 96))

            btn.clicked.connect(lambda _, s=source: self._select_avatar_and_close(s, dialog))
            grid.addWidget(btn, row, col)

            col += 1
            if col == 3:
                col = 0
                row += 1

        layout.addLayout(grid)

        custom_btn = QPushButton("Escolher imagem do computador")
        custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        custom_btn.setStyleSheet("""
            QPushButton {
                background-color: #007eff;
                color: white;
                font-size: 16px;
                padding: 10px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #005bb5;
            }
        """)
        custom_btn.clicked.connect(lambda: self.change_profile_picture(dialog))
        layout.addWidget(custom_btn)

        dialog.exec()

    def _select_avatar_and_close(self, source, dialog=None):
        self._save_avatar(source)
        if dialog:
            dialog.accept()

    def change_profile_picture(self, dialog=None):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar foto de perfil",
            "",
            "Imagens (*.png *.jpg *.jpeg)"
        )
        if file_name:
            self._save_avatar(file_name)
            if dialog:
                dialog.accept()

    def choose_install_path(self):
        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Escolher local de instalação",
            os.path.dirname(get_install_root())
        )

        if not selected_folder:
            return

        final_path = os.path.join(selected_folder, "PrimeX", "games")
        os.makedirs(final_path, exist_ok=True)

        try:
            os.system(f'attrib +h "{final_path}"')
        except Exception:
            pass

        save_install_root(final_path)
        self.install_path_label.setText(f"Pasta de instalação:\n{final_path}")

        QMessageBox.information(
            self,
            "Local de instalação definido",
            f"Os próximos jogos serão instalados em:\n{final_path}"
        )

    # =========================
    # Token
    # =========================

    def logout_user(self):
        confirm = QMessageBox.question(
            self,
            "Sair da conta",
            "Deseja realmente sair da sua conta?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        save_session({})

        try:
            from login import LoginWindow
            self.login_window = LoginWindow()
            self.login_window.show()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Aviso",
                f"Sessão apagada com sucesso, mas não consegui abrir a tela de login.\n\nErro: {e}"
            )

        self.close()


    def activate_token(self):
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Erro", "Por favor, digite um token válido.")
            return

        user_id = self.user_info.get("id")
        if not user_id:
            QMessageBox.warning(self, "Erro", "Sessão inválida. Faça login novamente.")
            return

        try:
            payload = {"token": token, "user_id": user_id}
            response = httpx.post(f"{API_BASE}/token/ativar", json=payload, timeout=10)

            if response.status_code == 200:
                data = response.json()

                plano = data.get("plano", "Desconhecido")
                expires_at = data.get("expires_at")  # pode ser None (permanente)

                # atualiza estado
                self.user_info["token"] = token
                self.user_info["plan"] = plano
                self.user_info["plan_active"] = True
                self.user_info["expires_at"] = expires_at

                # persiste
                self._persist_session()

                # aplica UI (verde + tempo)
                self._apply_plan_ui()

                QMessageBox.information(self, "Sucesso", f"Token ativado! Plano: {plano}")
                return

            # erro do backend
            try:
                detail = response.json().get("detail", "Token inválido ou expirado.")
            except Exception:
                detail = "Token inválido ou expirado."
            QMessageBox.warning(self, "Erro", detail)

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha na conexão com servidor: {e}")

    # =========================
    # Navbar callbacks
    # =========================
    def open_explore_page(self):
        if self._navigating:
            return

        self._navigating = True

        try:
            from explore_page import MainWindow
            self.explore_window = MainWindow(usuario_info=self.user_info)
            self.explore_window.show()

            self.hide()
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(300, self.close)

        except Exception as e:
            self._navigating = False
            QMessageBox.warning(self, "Erro", f"Não foi possível abrir Explorar:\n{e}")

    def open_instalados(self):
        if self._navigating:
            return

        self._navigating = True

        try:
            from installed import InstaladosPage
            self.installed_window = InstaladosPage(usuario_info=self.user_info)
            self.installed_window.show()

            self.hide()
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(300, self.close)

        except Exception as e:
            self._navigating = False
            QMessageBox.warning(self, "Erro", f"Não foi possível abrir Instalados:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont(FONT_PATH)
    window = ProfilePage()
    window.show()
    sys.exit(app.exec())
