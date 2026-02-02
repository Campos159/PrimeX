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

from login import LoginWindow


# ================================
# Janela de registro
# ================================
class RegisterWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PrimeX - Registro")
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
        # LOGO (ESPAÇO MAIOR)
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
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo.setFixedHeight(220)
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

        self.nome_input = criar_input("NOME")
        self.email_input = criar_input("EMAIL")
        self.senha_input = criar_input("SENHA", True)
        self.confirmar_senha_input = criar_input("CONFIRMAR SENHA", True)

        layout.addWidget(self.nome_input)
        layout.addWidget(self.email_input)
        layout.addWidget(self.senha_input)
        layout.addWidget(self.confirmar_senha_input)

        # ================================
        # Botões (CENTRALIZADOS)
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

        register_btn = criar_botao("REGISTRAR")
        register_btn.clicked.connect(self.register_usuario)

        back_btn = criar_botao("VOLTAR")
        back_btn.clicked.connect(self.voltar_login)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #836FFF;
                border: 2px solid #836FFF;
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: #836FFF;
                color: #0d0b1f;
            }
        """)

        layout.addWidget(register_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(card)

    # ================================
    # Registrar usuário
    # ================================
    def register_usuario(self):
        nome = self.nome_input.text().strip()
        email = self.email_input.text().strip()
        senha = self.senha_input.text()
        confirmar = self.confirmar_senha_input.text()

        if not nome or not email or not senha or not confirmar:
            QMessageBox.warning(self, "Erro", "Preencha todos os campos!")
            return

        if senha != confirmar:
            QMessageBox.warning(self, "Erro", "As senhas não coincidem!")
            return

        # (Opcional, mas MUITO recomendado) evita o erro do bcrypt no backend:
        if len(senha.encode("utf-8")) > 72:
            QMessageBox.warning(
                self,
                "Erro",
                "Senha muito longa.\n"
                "O limite é 72 bytes (bcrypt).\n"
                "Evite emojis e muitos acentos e reduza o tamanho."
            )
            return

        try:
            r = requests.post(
                f"{API_BASE}/register",
                json={"nome": nome, "email": email, "password": senha},
                timeout=10
            )

            data = {}
            try:
                data = r.json()
            except Exception:
                pass

            if r.status_code in (200, 201):
                QMessageBox.information(self, "Sucesso", "Conta criada com sucesso!")
                self.voltar_login()
                return

            # Trata 422 do Pydantic bonitinho
            if r.status_code == 422:
                detail = data.get("detail")
                if isinstance(detail, list) and detail:
                    # tenta pegar a primeira mensagem
                    msg = detail[0].get("msg", "Dados inválidos.")
                else:
                    msg = "Dados inválidos."
                QMessageBox.warning(self, "Erro", msg)
                return

            # Outros erros
            detail = data.get("detail", "Erro ao registrar")
            QMessageBox.warning(self, "Erro", str(detail))

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha na conexão:\n{e}")

    # ================================
    # Voltar login
    # ================================
    def voltar_login(self):
        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RegisterWindow()
    window.show()
    sys.exit(app.exec())
