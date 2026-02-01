import sys
import httpx
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QSpacerItem, QSizePolicy, QFrame, QProgressBar, QFileDialog, QGridLayout, QLineEdit, QMessageBox
)
from PyQt6.QtGui import QPixmap, QCursor
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QCursor, QFontDatabase, QFont
from PyQt6.QtGui import QPixmap, QCursor
import os
from PyQt6.QtWidgets import QDialog, QGridLayout
from datetime import datetime, timezone
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize

from navbar import NavBar

FONT_PATH = os.path.join(os.getcwd(), "assets", "fonts", "VT323-Regular.ttf")

class ProfilePage(QWidget):
    def __init__(self, user_info=None):
        super().__init__()
        self.setWindowTitle("Perfil - PrimeX")
        # =========================
        # TEMA + FONTE (VT323)
        # =========================
        self.setStyleSheet("""
            QWidget {
                background-color: #0d0b1f;
                color: #b9a9ff;
                font-family: 'VT323';
            }
        """)

        # RECEBE INFORMAÇÕES DO USUÁRIO
        self.user_info = user_info or {"nome": "Usuário", "token": "", "plan": "Nenhum"}

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 10, 20, 20)
        main_layout.setSpacing(15)

        # ---------- HEADER ----------
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addStretch()

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

        header.addWidget(user_btn, alignment=Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(header)

        # ---------- NAVBAR ----------
        nav_callbacks = {
            "EXPLORAR": self.open_explore_page,
            "INSTALADOS": self.open_instalados
        }
        self.nav_bar = NavBar(parent=self, callbacks=nav_callbacks)
        main_layout.addWidget(self.nav_bar)

        # ---------- FOTO + NOME + PLANO ----------
        profile_layout = QHBoxLayout()
        profile_layout.setSpacing(20)
        profile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.profile_pic = QLabel()
        self.profile_pic.setFixedSize(130, 130)
        self.profile_pic.setStyleSheet("border-radius: 65px; background-color: #444;")
        self.profile_pic.setPixmap(QPixmap("assets/profile_default.png").scaled(
            130, 130, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.profile_pic.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.profile_pic.mousePressEvent = lambda e: self.open_avatar_picker()

        profile_info_layout = QVBoxLayout()
        profile_info_layout.setSpacing(8)

        self.name_label = QLabel(self.user_info.get("nome", "Usuário"))
        self.name_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        self.plan_label = QLabel(f"Plano Ativo: {self.user_info.get('plan', 'Nenhum')}")
        self.plan_label.setStyleSheet("font-size: 16px; color: #ff5555;")

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Digite seu token aqui")
        self.token_input.setFixedHeight(30)
        self.token_input.setFixedWidth(180)
        self.token_input.setText(self.user_info.get("token", ""))
        self.token_input.setStyleSheet("""
            QLineEdit {
                padding: 2px 6px;
                border-radius: 4px;
                border: 1px solid #007eff;
                background-color: #1e1e1e;
                color: white;
                font-size: 11px;
            }
        """)

        self.token_btn = QPushButton("Ativar Token")
        self.time_left_label = QLabel("Tempo restante: —")
        self.time_left_label.setStyleSheet("font-size: 18px; color: #e0d9ff;")
        profile_info_layout.addWidget(self.name_label)
        profile_info_layout.addWidget(self.plan_label)
        profile_info_layout.addWidget(self.token_input)
        profile_info_layout.addWidget(self.token_btn)
        profile_info_layout.addWidget(self.time_left_label)
        profile_info_layout.addWidget(self.time_left_label)
        self.token_btn.setFixedHeight(30)
        self.token_btn.setFixedWidth(180)
        self.token_btn.setStyleSheet("""
            QPushButton {
                background-color: #007eff;
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #005bb5;
            }
        """)
        self.token_btn.clicked.connect(self.activate_token)

        profile_info_layout.addWidget(self.name_label)
        profile_info_layout.addWidget(self.plan_label)
        profile_info_layout.addWidget(self.token_input)
        profile_info_layout.addWidget(self.token_btn)

        profile_layout.addWidget(self.profile_pic)
        profile_layout.addLayout(profile_info_layout)
        main_layout.addLayout(profile_layout)

        main_layout.addStretch()

        self.setLayout(main_layout)
        self.setMinimumSize(720, 480)
        self.showMaximized()


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

        # ✅ ÍCONES PRONTOS (você vai colocar esses arquivos em assets/avatars/)
        avatars = [
            ("Masculino 1", "assets/avatars/male_1.png"),
            ("Masculino 2", "assets/avatars/male_2.png"),
            ("Feminino 1", "assets/avatars/female_1.png"),
            ("Feminino 2", "assets/avatars/female_2.png"),
            ("Neutro 1", "assets/avatars/neutral_1.png"),
            ("Neutro 2", "assets/avatars/neutral_2.png"),
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
                pix2 = pix.scaled(
                    96, 96,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
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
        custom_btn.clicked.connect(lambda: self.change_profile_picture(None))
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

    def change_profile_picture(self, event):
        file_name, _ = QFileDialog.getOpenFileName(self, "Selecionar foto de perfil", "", "Imagens (*.png *.jpg *.jpeg)")
        if file_name:
            pixmap = QPixmap(file_name).scaled(130, 130, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.profile_pic.setPixmap(pixmap)

    def activate_token(self):
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Erro", "Por favor, digite um token válido.")
            return

        try:
            payload = {
                "token": token,
                "user_id": self.user_info.get("id", 1)
            }

            response = httpx.post("http://127.0.0.1:8000/token/ativar", json=payload, timeout=10)

            if response.status_code == 200:
                data = response.json()
                plano = data.get("plano", "Desconhecido")

                self.plan_label.setText(f"Plano Ativo: {plano}")
                self.plan_label.setStyleSheet("font-size: 18px; color: #00ff88;")

                expires_at = data.get("expires_at")  # pode vir None no permanente
                if expires_at:
                    # pode vir como string ISO
                    exp = datetime.fromisoformat(str(expires_at)).replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    delta = exp - now

                    if delta.total_seconds() <= 0:
                        self.time_left_label.setText("Tempo restante: Expirado")
                    else:
                        dias = delta.days
                        horas = (delta.seconds // 3600)
                        minutos = (delta.seconds % 3600) // 60
                        self.time_left_label.setText(f"Tempo restante: {dias}d {horas}h {minutos}m")
                else:
                    self.time_left_label.setText("Tempo restante: Permanente ✅")

                QMessageBox.information(self, "Sucesso", f"Token ativado! Plano: {plano}")

            else:
                # mostra msg do backend se tiver
                try:
                    detail = response.json().get("detail", "Token inválido ou expirado.")
                except:
                    detail = "Token inválido ou expirado."

                QMessageBox.warning(self, "Erro", detail)

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha na conexão com servidor: {e}")

    # ---------- CALLBACKS NAVBAR ----------
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
