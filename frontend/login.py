import sys
import os
import requests

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QMessageBox
)
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtCore import Qt
from api_config import API_BASE

from explore_page import MainWindow


# ================================
# Janela de Login
# ================================
class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PrimeX - Login")
        self.setStyleSheet("background-color: #0d0b1f;")
        self.showMaximized()  # JANELA CHEIA (não fullscreen)

        # Fonte VT323
        self.vt_font = QFont("VT323", 22)
        self.vt_font_small = QFont("VT323", 18)

        self.init_ui()

    # ================================
    # Layout da janela
    # ================================
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ================================
        # Card central
        # ================================
        card = QWidget()
        card.setFixedSize(540, 740)
        card.setStyleSheet("""
            QWidget {
                background-color: #120f2a;
                border: 2px solid #2a245f;
                border-radius: 24px;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(22)

        # ================================
        # LOGO
        # ================================
        logo_path = "assets/logos/primex_logo.png"
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(
                400, 250,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo = QLabel()
            logo.setPixmap(pix)
            logo.setFixedHeight(220)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo)

        # ================================
        # Inputs
        # ================================
        def criar_input(texto, senha=False):
            inp = QLineEdit()
            inp.setPlaceholderText(texto)
            inp.setFixedSize(400, 48)
            inp.setFont(self.vt_font_small)

            if senha:
                inp.setEchoMode(QLineEdit.EchoMode.Password)

            inp.setStyleSheet("""
                QLineEdit {
                    background-color: #14134a;
                    color: #e0d9ff;
                    border: 1px solid #2a245f;
                    border-radius: 12px;
                    padding-left: 14px;
                }
                QLineEdit:focus {
                    border: 2px solid #836FFF;
                }
            """)
            return inp

        self.email_input = criar_input("EMAIL")
        self.senha_input = criar_input("SENHA", True)

        layout.addWidget(self.email_input)
        layout.addWidget(self.senha_input)

        # ================================
        # Botões
        # ================================
        def criar_botao(texto):
            btn = QPushButton(texto)
            btn.setFont(self.vt_font)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(260, 54)
            btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #836FFF,
                        stop:1 #4cc3ff
                    );
                    color: #0d0b1f;
                    border-radius: 14px;
                }
                QPushButton:hover {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #9a7dff,
                        stop:1 #6fd4ff
                    );
                }
            """)
            return btn

        login_btn = criar_botao("ENTRAR")
        login_btn.clicked.connect(self.login_usuario)

        register_btn = QPushButton("CRIAR CONTA")
        register_btn.setFont(self.vt_font)
        register_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        register_btn.setFixedSize(260, 44)
        register_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #836FFF;
                border: none;
            }
            QPushButton:hover {
                text-decoration: underline;
            }
        """)
        register_btn.clicked.connect(self.open_register)

        layout.addWidget(login_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(register_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(card)

    # ================================
    # Login
    # ================================
    def login_usuario(self):
        email = self.email_input.text().strip()
        senha = self.senha_input.text().strip()

        if not email or not senha:
            QMessageBox.warning(self, "Erro", "Preencha todos os campos!")
            return

        try:
            r = requests.post(
                f"{API_BASE}/login",
                json={"email": email, "password": senha}
            )

            if r.status_code == 200:
                user_data = r.json()
                QMessageBox.information(
                    self,
                    "Sucesso",
                    f"Bem-vindo(a), {user_data.get('nome', 'Usuário')}!"
                )
                self.open_explore(user_data)
            else:
                QMessageBox.warning(
                    self,
                    "Erro",
                    r.json().get("detail", "Erro ao fazer login")
                )

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha na conexão:\n{e}")

    # ================================
    # Abrir Explore
    # ================================
    def open_explore(self, user_info):
        self.explore_window = MainWindow(usuario_info=user_info)
        self.explore_window.show()
        self.close()

    # ================================
    # Abrir Registro
    # ================================
    def open_register(self):
        from register import RegisterWindow
        self.register_window = RegisterWindow()
        self.register_window.show()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())
