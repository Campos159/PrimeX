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

FONT_PATH = resource_path(os.path.join("fonts", "VT323-Regular.ttf"))


class ProfilePage(QWidget):
    def __init__(self, user_info=None):
        super().__init__()

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
        # FOTO + INFO
        # =========================
        profile_layout = QHBoxLayout()
        profile_layout.setSpacing(20)
        profile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.profile_pic = QLabel()
        self.profile_pic.setFixedSize(130, 130)
        self.profile_pic.setStyleSheet("border-radius: 65px; background-color: #444;")
        self.profile_pic.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.profile_pic.mousePressEvent = lambda e: self.open_avatar_picker()

        default_avatar = resource_path("assets/profile_default.png")
        pix = QPixmap(default_avatar)
        if not pix.isNull():
            self.profile_pic.setPixmap(
                pix.scaled(130, 130, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            )

        profile_info_layout = QVBoxLayout()
        profile_info_layout.setSpacing(8)

        self.name_label = QLabel(self.user_info.get("nome", "Usuário"))
        self.name_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")

        self.plan_label = QLabel("Plano Ativo: —")
        self.plan_label.setStyleSheet("font-size: 16px; color: #ff5555;")

        self.time_left_label = QLabel("Tempo restante: —")
        self.time_left_label.setStyleSheet("font-size: 18px; color: #e0d9ff;")

        # token input
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Digite seu token aqui")
        self.token_input.setFixedHeight(30)
        self.token_input.setFixedWidth(220)
        self.token_input.setText(self.user_info.get("token", ""))
        self.token_input.setStyleSheet("""
            QLineEdit {
                padding: 2px 6px;
                border-radius: 6px;
                border: 1px solid #007eff;
                background-color: #1e1e1e;
                color: white;
                font-size: 12px;
            }
        """)

        self.token_btn = QPushButton("Ativar Token")
        self.token_btn.setFixedHeight(32)
        self.token_btn.setFixedWidth(220)
        self.token_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.token_btn.setStyleSheet("""
            QPushButton {
                background-color: #007eff;
                color: white;
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #005bb5;
            }
        """)
        self.token_btn.clicked.connect(self.activate_token)

        # add widgets (UMA VEZ SÓ)
        profile_info_layout.addWidget(self.name_label)
        profile_info_layout.addWidget(self.plan_label)
        profile_info_layout.addWidget(self.time_left_label)
        profile_info_layout.addWidget(self.token_input)
        profile_info_layout.addWidget(self.token_btn)

        self.install_path_label = QLabel(f"Pasta de instalação:\n{get_install_root()}")
        self.install_path_label.setStyleSheet("font-size: 15px; color: #e0d9ff;")

        self.install_path_btn = QPushButton("Escolher local de instalação")
        self.install_path_btn.setFixedHeight(34)
        self.install_path_btn.setFixedWidth(220)
        self.install_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_path_btn.setStyleSheet("""
            QPushButton {
                background-color: #836FFF;
                color: white;
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #6f55ff;
            }
        """)
        self.install_path_btn.clicked.connect(self.choose_install_path)

        profile_info_layout.addWidget(self.install_path_label)
        profile_info_layout.addWidget(self.install_path_btn)

        profile_layout.addWidget(self.profile_pic)
        profile_layout.addLayout(profile_info_layout)

        main_layout.addLayout(profile_layout)
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
        # salva SOMENTE quando tiver algo para persistir (não no __init__)
        save_session({
            "id": self.user_info.get("id"),
            "nome": self.user_info.get("nome"),
            "token": self.user_info.get("token"),
            "plan": self.user_info.get("plan"),
            "plan_active": self.user_info.get("plan_active"),
            "expires_at": self.user_info.get("expires_at"),
        })

    def open_downloads(self):
        from downloads import DownloadsPage
        self.downloads_window = DownloadsPage(usuario_info=self.user_info)
        self.downloads_window.show()
        self.close()

    # =========================
    # Avatares
    # =========================
    def open_avatar_picker(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Escolher Avatar")
        dialog.setStyleSheet("background-color: #120f2a; color: #b9a9ff;")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        title = QLabel("Escolha um avatar")
        title.setStyleSheet("font-size: 22px; color: #e0d9ff;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(12)

        avatars = [
            ("Astro", resource_path("assets/avatars/robo.png")),
            ("Gamer", resource_path("assets/avatars/gamer.png")),
            ("Robot", resource_path("assets/avatars/robot.png")),
        ]

        row = col = 0
        for name, path in avatars:
            btn = QPushButton()
            btn.setFixedSize(110, 110)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0d0b1f;
                    border: 2px solid #2a245f;
                    border-radius: 16px;
                }
                QPushButton:hover {
                    border: 2px solid #836FFF;
                }
            """)

            pix = QPixmap(path)
            if not pix.isNull():
                pix2 = pix.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                btn.setIcon(QIcon(pix2))
                btn.setIconSize(QSize(96, 96))

            btn.clicked.connect(lambda _, p=path: self._set_avatar_from_path(p, dialog))

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
        custom_btn.clicked.connect(self.change_profile_picture)
        layout.addWidget(custom_btn)

        dialog.exec()

    def _set_avatar_from_path(self, path, dialog=None):
        pixmap = QPixmap(path).scaled(
            130, 130,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        self.profile_pic.setPixmap(pixmap)
        if dialog:
            dialog.accept()

    def change_profile_picture(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar foto de perfil",
            "",
            "Imagens (*.png *.jpg *.jpeg)"
        )
        if file_name:
            pixmap = QPixmap(file_name).scaled(
                130, 130,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.profile_pic.setPixmap(pixmap)

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
        from explore_page import MainWindow
        self.explore_window = MainWindow(usuario_info=self.user_info)
        self.explore_window.show()
        self.close()

    def open_instalados(self):
        from installed import InstaladosPage
        self.installed_window = InstaladosPage(usuario_info=self.user_info)
        self.installed_window.show()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont(FONT_PATH)
    window = ProfilePage()
    window.show()
    sys.exit(app.exec())
