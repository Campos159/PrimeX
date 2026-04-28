import sys
import requests
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QSpacerItem, QSizePolicy, QFrame, QComboBox, QMessageBox, QStackedLayout
)
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QHBoxLayout, QDialog, QLineEdit, QTextEdit
from PyQt6.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QComboBox, QMessageBox
)
from PyQt6.QtWidgets import QScrollArea
from PyQt6.QtCore import Qt
import secrets
import string
from functools import partial
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QSpacerItem, QSizePolicy, QFrame, QComboBox, QMessageBox, QStackedLayout,
    QScrollArea, QListWidget, QListWidgetItem, QDialog, QLineEdit, QTextEdit,
    QGridLayout, QSpinBox
)

from PyQt6.QtCore import QThread, pyqtSignal
from navbar import NavBar
from api_config import API_BASE
from urllib.parse import urljoin

def api_url(path: str) -> str:
    base = (API_BASE or "").rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))

def safe_json(response: requests.Response):
    try:
        return response.json()
    except Exception:
        return None

def debug_http_dialog(parent, title: str, response: requests.Response, extra: str = ""):
    # Alguns provedores colocam request-id em headers diferentes
    req_id = (
        response.headers.get("x-request-id")
        or response.headers.get("x-amzn-trace-id")
        or response.headers.get("cf-ray")
        or response.headers.get("x-vercel-id")
        or response.headers.get("x-render-request-id")
        or ""
    )

    body_preview = (response.text or "")[:3500]

    QMessageBox.information(
        parent,
        title,
        f"{extra}\n"
        f"URL: {response.url}\n"
        f"STATUS: {response.status_code}\n"
        f"REQUEST-ID: {req_id}\n"
        f"CONTENT-TYPE: {response.headers.get('content-type','')}\n\n"
        f"BODY (preview):\n{body_preview}"
    )

def request_api(parent, method: str, path: str, *, json_body=None, timeout=15):
    url = api_url(path)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    return requests.request(method, url, json=json_body, headers=headers, timeout=timeout)



class LoadTokensThread(QThread):
    success = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            url = api_url("/admin/listar_tokens")
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                self.error.emit(f"Erro {response.status_code}: {response.text}")
                return

            data = response.json()
            tokens = data.get("tokens", [])
            self.success.emit(tokens)

        except Exception as e:
            self.error.emit(str(e))


class LoadUsersThread(QThread):
    success = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            url = api_url("/admin/listar_usuarios")
            response = requests.get(url, timeout=15)

            if response.status_code != 200:
                self.error.emit(f"Erro {response.status_code}: {response.text}")
                return

            data = response.json()
            usuarios = data.get("usuarios", [])
            self.success.emit(usuarios)

        except Exception as e:
            self.error.emit(str(e))



class AdminPage(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Painel Administrativo - Gameprime")
        self.setStyleSheet("""
            background-color: #0d0b1f;
            color: #e0d9ff;
        """)
        self.threads = []

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 10, 20, 20)
        main_layout.setSpacing(15)

        # ---------- HEADER ----------
        header = QHBoxLayout()
        header.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        header.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        user_btn = QPushButton("👤")
        user_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        user_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid #007eff;
                border-radius: 15px;
                color: #007eff;
                font-size: 22px;
                width: 40px;
                height: 40px;
            }
            QPushButton:hover {
                background-color: #007eff;
                color: #282828;
            }
        """)
        header.addWidget(user_btn)
        main_layout.addLayout(header)

        # ---------- NAVBAR ----------
        callbacks = {
            "EXPLORAR": {"callback": self.open_explore_page, "icon": "🔎"},
            "INSTALADOS": {"callback": lambda: None, "icon": "💾"},
        }

        self.nav_bar = NavBar(callbacks=callbacks)
        main_layout.addWidget(self.nav_bar)


        # ---------- CONTEÚDO PRINCIPAL ----------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # MENU LATERAL
        side_menu = QFrame()
        side_menu.setFixedWidth(250)
        side_menu.setStyleSheet("""
            background-color: #120f2a;
            border: 2px solid #2a245f;
            border-radius: 18px;
        """)
        side_layout = QVBoxLayout(side_menu)
        side_layout.setContentsMargins(15, 15, 15, 15)
        side_layout.setSpacing(15)

        # botões do menu lateral
        self.menu_buttons = {
            "Adicionar Jogo": QPushButton("Adicionar Jogo"),
            "Gerenciar Jogos": QPushButton("Gerenciar Jogos"),
            "Gerenciar Avatares": QPushButton("Gerenciar Avatares"),
            "Gerenciar Usuários": QPushButton("Gerenciar Usuários"),
            "Gerenciar Tokens": QPushButton("Gerenciar Tokens"),
            "Estatísticas Gerais": QPushButton("Estatísticas Gerais"),
            "Gerar Tokens": QPushButton("Gerar Tokens")
        }

        for name, btn in self.menu_buttons.items():
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #836FFF,
                        stop:1 #4cc3ff
                    );
                    color: #0d0b1f;
                    border-radius: 12px;
                    padding: 10px;
                    font-size: 15px;
                }
                QPushButton:hover {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #9a7dff,
                        stop:1 #6fd4ff
                    );
                }
            """)

            btn.clicked.connect(lambda _, n=name: self.switch_page(n))
            side_layout.addWidget(btn)

        side_layout.addStretch()

        # ÁREA PRINCIPAL (QStackedLayout)
        self.main_area = QStackedLayout()

        # Criamos as páginas individuais
        self.pages = {
            "Adicionar Jogo": self.create_add_game_page(),
            "Gerenciar Jogos": self.create_manage_games_page(),
            "Gerenciar Avatares": self.create_manage_avatars_page(),
            "Gerenciar Usuários": self.create_manage_users_page(),
            "Gerenciar Tokens": self.create_manage_tokens_page(),
            "Estatísticas Gerais": self.create_placeholder_page("Tela com estatísticas do sistema"),
            "Gerar Tokens": self.create_token_page()
        }

        for page in self.pages.values():
            self.main_area.addWidget(page)

        # layout final
        content_layout.addWidget(side_menu)
        main_container = QFrame()
        main_container.setStyleSheet("""
            background-color: #120f2a;
            border: 2px solid #2a245f;
            border-radius: 18px;
        """)

        main_container_layout = QVBoxLayout(main_container)
        main_container_layout.setContentsMargins(20, 20, 20, 20)
        main_container_layout.addLayout(self.main_area)

        content_layout.addWidget(main_container, stretch=1)

        main_layout.addLayout(content_layout)

        self.setLayout(main_layout)
        self.setMinimumSize(720, 480)
        self.showMaximized()

    def create_manage_tokens_page(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)

        title = QLabel("Gerenciar Tokens")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #836FFF;")
        layout.addWidget(title)

        self.token_list = QListWidget()
        self.token_list.setStyleSheet("""
            QListWidget {
                background-color: #0d0b1f;
                border: 2px solid #2a245f;
                border-radius: 12px;
                color: white;
            }
        """)
        layout.addWidget(self.token_list)

        refresh_btn = QPushButton("Atualizar Tokens")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #007eff;
                color: white;
                font-size: 14px;
                padding: 8px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #005bb5;
            }
        """)
        refresh_btn.clicked.connect(self.load_tokens)
        layout.addWidget(refresh_btn)

        layout.addStretch()
        return frame






    def _make_copy_handler(self, tok: str):
        return lambda: self.copiar_token(tok)

    def load_tokens(self):
        self.token_list.clear()

        th = LoadTokensThread()
        th.success.connect(self.populate_tokens)
        th.error.connect(self.show_token_error)
        th.finished.connect(lambda: self.threads.remove(th) if th in self.threads else None)

        self.threads.append(th)
        th.start()

    def populate_tokens(self, tokens):
        from datetime import datetime

        self.token_list.clear()

        for t in tokens:

            # ---------- STATUS ----------
            if not t.get("active"):
                status_text = "DISPONÍVEL"
                status_color = "#4CAF50"  # verde

            else:
                expires_at = t.get("expires_at")

                # Token permanente (ativado mas sem expiração)
                if not expires_at:
                    status_text = "PERMANENTE"
                    status_color = "#2196F3"  # azul

                else:
                    expires = datetime.fromisoformat(expires_at)

                    if expires < datetime.utcnow():
                        status_text = "EXPIRADO"
                        status_color = "#FFC107"  # amarelo
                    else:
                        status_text = "ATIVO"
                        status_color = "#F44336"  # vermelho

            # ---------- UI ----------
            item = QListWidgetItem()
            widget = QWidget()
            row = QHBoxLayout(widget)
            row.setContentsMargins(10, 5, 10, 5)

            token_lbl = QLabel(t["token"])
            token_lbl.setStyleSheet("color: white; font-size: 13px;")

            plano_lbl = QLabel(t["type"])
            plano_lbl.setStyleSheet("color: #836FFF; font-weight: bold;")

            status_lbl = QLabel(status_text)
            status_lbl.setStyleSheet(f"color: {status_color}; font-weight: bold;")

            copiar_btn = QPushButton("Copiar")
            copiar_btn.clicked.connect(self._make_copy_handler(t["token"]))

            row.addWidget(token_lbl)
            row.addStretch()
            row.addWidget(plano_lbl)
            row.addWidget(status_lbl)
            row.addWidget(copiar_btn)

            item.setSizeHint(widget.sizeHint())
            self.token_list.addItem(item)
            self.token_list.setItemWidget(item, widget)

    def show_token_error(self, msg):
        QMessageBox.critical(self, "Erro", f"Falha ao carregar tokens:\n{msg}")

    def gerar_token_local(self, tamanho=16):
        alfabeto = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alfabeto) for _ in range(tamanho))

    def copiar_token(self, token):
        clipboard = QApplication.clipboard()
        clipboard.setText(token)

    def gerar_varios_tokens(self):
        print("CLIQUOU GERAR TOKENS ✅")
        self.lista_tokens.clear()

        token_type = self.token_type.currentText()

        try:
            response = requests.post(
                f"{API_BASE}/admin/criar_token",
                json={"type": token_type},  # backend criando 10 fixo
                timeout=10
            )

            QMessageBox.information(
                self,
                "Debug",
                f"Enviando type: {token_type}\nStatus: {response.status_code}\n\nResposta:\n{response.text[:800]}"
            )

            print("STATUS:", response.status_code)
            print("TEXTO:", response.text)

            if response.status_code != 200:
                QMessageBox.warning(
                    self, "Erro",
                    f"Falha ao gerar tokens ({response.status_code})\n\n{response.text}"
                )
                return

            data = response.json()
            tokens = data.get("tokens", [])

            # fallback se algum endpoint ainda retornar token único
            if not tokens and "token" in data:
                tokens = [{"token": data["token"]}]

            for t in tokens:
                token = t.get("token")
                if not token:
                    continue

                item = QListWidgetItem()
                widget = QWidget(self.lista_tokens)  # parent definido
                row = QHBoxLayout(widget)
                row.setContentsMargins(10, 5, 10, 5)

                label = QLabel(token)
                label.setStyleSheet("color: white; font-size: 14px;")

                copiar_btn = QPushButton("Copiar")
                copiar_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #836FFF;
                        color: #0d0b1f;
                        border-radius: 8px;
                        padding: 5px 10px;
                    }
                    QPushButton:hover {
                        background-color: #9a7dff;
                    }
                """)
                copiar_btn.clicked.connect(partial(self.copiar_token, token))

                row.addWidget(label)
                row.addStretch()
                row.addWidget(copiar_btn)

                item.setSizeHint(widget.sizeHint())
                self.lista_tokens.addItem(item)
                self.lista_tokens.setItemWidget(item, widget)

            QMessageBox.information(self, "Sucesso", f"{len(tokens)} tokens gerados!")
            return  # 🔒 garante que não continua

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao conectar ao servidor:\n{e}")
            return

    def create_manage_users_page(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)

        title = QLabel("Gerenciar Usuários")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #836FFF;")
        layout.addWidget(title)

        self.user_list = QListWidget()
        self.user_list.setStyleSheet("""
            QListWidget {
                background-color: #0d0b1f;
                border: 2px solid #2a245f;
                border-radius: 12px;
                color: white;
            }
        """)
        layout.addWidget(self.user_list)

        btns = QHBoxLayout()

        refresh_btn = QPushButton("Atualizar Usuários")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #007eff;
                color: white;
                font-size: 14px;
                padding: 8px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #005bb5; }
        """)
        refresh_btn.clicked.connect(self.load_users)
        btns.addWidget(refresh_btn)

        layout.addLayout(btns)
        layout.addStretch()
        return frame

    def load_users(self):
        self.user_list.clear()

        th = LoadUsersThread()
        th.success.connect(self.populate_users)
        th.error.connect(lambda msg: QMessageBox.critical(self, "Erro", f"Falha ao carregar usuários:\n{msg}"))
        th.finished.connect(lambda: self.threads.remove(th) if th in self.threads else None)

        self.threads.append(th)
        th.start()

    def populate_users(self, usuarios):
        from datetime import datetime

        self.user_list.clear()

        for u in usuarios:
            user_id = u.get("id")
            nome = u.get("nome", "")
            email = u.get("email", "")
            is_active = bool(u.get("is_active", True))

            plano_status = u.get("plano_status", "SEM PLANO")
            token_info = u.get("token_info") or {}
            token_usado = token_info.get("token", "")
            plano_tipo = token_info.get("type", "")

            # cores
            if not is_active:
                status_text = "BANIDO"
                status_color = "#F44336"  # vermelho
            else:
                if plano_status == "ATIVO":
                    status_text = "ATIVO"
                    status_color = "#4CAF50"  # verde
                elif plano_status == "VENCIDO":
                    status_text = "VENCIDO"
                    status_color = "#FFC107"  # amarelo
                elif plano_status == "PERMANENTE":
                    status_text = "PERMANENTE"
                    status_color = "#2196F3"  # azul
                else:
                    status_text = "SEM PLANO"
                    status_color = "#9E9E9E"  # cinza

            # linha visual
            item = QListWidgetItem()
            widget = QWidget()
            row = QHBoxLayout(widget)
            row.setContentsMargins(10, 6, 10, 6)

            left = QLabel(f"[{user_id}] {nome}  •  {email}")
            left.setStyleSheet("color: white; font-size: 13px;")
            row.addWidget(left)

            row.addStretch()

            plano_lbl = QLabel(plano_tipo or "-")
            plano_lbl.setStyleSheet("color: #836FFF; font-weight: bold;")
            row.addWidget(plano_lbl)

            token_lbl = QLabel((token_usado[:8] + "..." + token_usado[-6:]) if token_usado else "-")
            token_lbl.setStyleSheet("color: #BBBBBB; font-size: 12px;")
            row.addWidget(token_lbl)

            status_lbl = QLabel(status_text)
            status_lbl.setStyleSheet(f"color: {status_color}; font-weight: bold;")
            row.addWidget(status_lbl)

            action_btn = QPushButton("Desbanir" if not is_active else "Banir")
            action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a245f;
                    color: white;
                    padding: 6px 10px;
                    border-radius: 8px;
                }
                QPushButton:hover { background-color: #3b3390; }
            """)
            action_btn.clicked.connect(lambda _, uid=user_id, active=is_active: self.toggle_ban_user(uid, active))
            row.addWidget(action_btn)

            item.setSizeHint(widget.sizeHint())
            self.user_list.addItem(item)
            self.user_list.setItemWidget(item, widget)

    def toggle_ban_user(self, user_id: int, is_active: bool):
        try:
            if is_active:
                confirm = QMessageBox.question(
                    self, "Confirmar Ban",
                    f"Tem certeza que deseja BANIR o usuário ID {user_id}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return

                response = request_api(self, "PUT", f"/admin/banir_usuario/{user_id}", timeout=15)
            else:
                response = request_api(self, "PUT", f"/admin/desbanir_usuario/{user_id}", timeout=15)

            if response.status_code != 200:
                debug_http_dialog(self, "Erro - ban/desban", response)
                QMessageBox.warning(self, "Erro", f"Falha ({response.status_code}).")
                return

            self.load_users()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao conectar ao servidor:\n{e}")

    def create_placeholder_page(self, text):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        label = QLabel(text)
        label.setStyleSheet("font-size: 18px; color: white;")
        layout.addWidget(label)
        layout.addStretch()
        return frame

    def create_token_page(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)

        title_label = QLabel("Gerar Token de Ativação")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(title_label)

        self.token_type = QComboBox()

        self.token_type.addItems(["Teste Gratuito", "Mensal", "Trimestral", "Anual", "Permanente"])
        self.token_type.setStyleSheet("""
            QComboBox {
                background-color: #1e1e1e;
                color: white;
                padding: 5px;
                border: 2px solid #007eff;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.token_type)
        gerar_btn = QPushButton("Gerar Tokens")
        gerar_btn.setStyleSheet("""
            QPushButton {
                background-color: #007eff;
                color: white;
                font-size: 15px;
                padding: 10px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #005bb5;
            }
        """)
        gerar_btn.clicked.connect(self.gerar_varios_tokens)
        layout.addWidget(gerar_btn)

        self.lista_tokens = QListWidget()
        self.lista_tokens.setStyleSheet("""
            QListWidget {
                background-color: #0d0b1f;
                border: 2px solid #2a245f;
                border-radius: 12px;
                color: white;
            }
        """)
        layout.addWidget(self.lista_tokens)


        layout.addStretch()
        return frame

    def switch_page(self, page_name):
        index = list(self.pages.keys()).index(page_name)
        self.main_area.setCurrentIndex(index)

        if page_name == "Gerenciar Jogos":
            self.load_games()
        elif page_name == "Gerenciar Tokens":
            self.load_tokens()
        elif page_name == "Gerenciar Usuários":
            self.load_users()
        elif page_name == "Gerenciar Avatares":
            self.load_avatars()

    def generate_token(self):
        print("CHAMOU generate_token() ⚠️")
        token_type = self.token_type.currentText()

        try:
            response = requests.post(
                f"{API_BASE}/admin/criar_token",
                json={"type": token_type}
            )
            print("HEADER X-Gameprime-Endpoint:", response.headers.get("X-Gameprime-Endpoint"))
            print("JSON:", response.json())

            if response.status_code == 200:
                data = response.json()
                token = data.get("token") or (data.get("tokens", [{}])[0].get("token") if data.get("tokens") else None)
                self.token_label.setText(f"Token: {token}")
            else:
                QMessageBox.warning(
                    self, "Erro",
                    f"Não foi possível gerar o token ({response.status_code})"
                )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao conectar ao servidor: {e}")

    def _input_style(self):
        return """
            QLineEdit, QTextEdit, QSpinBox {
                background-color: #0d0b1f;
                color: white;
                border: 2px solid #2a245f;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
                border: 2px solid #007eff;
            }
        """

    def _section_title(self, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #836FFF;
            margin-top: 8px;
            margin-bottom: 6px;
        """)
        return lbl

    def _make_line_edit(self, placeholder="", value=""):
        w = QLineEdit()
        w.setPlaceholderText(placeholder)
        w.setText(value or "")
        w.setStyleSheet(self._input_style())
        return w

    def _make_text_edit(self, placeholder="", value=""):
        w = QTextEdit()
        w.setPlaceholderText(placeholder)
        w.setPlainText(value or "")
        w.setStyleSheet(self._input_style())
        w.setMinimumHeight(70)
        return w

    def _make_spinbox(self, value=None, minimum=0, maximum=9999, suffix=""):
        w = QSpinBox()
        w.setRange(minimum, maximum)
        w.setSuffix(suffix)
        w.setSpecialValueText("")
        w.setValue(value if isinstance(value, int) and value >= 0 else 0)
        w.setStyleSheet(self._input_style())
        return w

    def _create_requirements_section(self, prefix: str, initial: dict | None = None):
        initial = initial or {}

        box = QFrame()
        box.setStyleSheet("""
            QFrame {
                background-color: #151132;
                border: 1px solid #2a245f;
                border-radius: 12px;
            }
        """)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        fields = {}

        def add_row(row, label_text, widget):
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #e0d9ff; font-size: 13px; border: none;")
            grid.addWidget(lbl, row, 0)
            grid.addWidget(widget, row, 1)

        fields[f"{prefix}_os"] = self._make_line_edit("Ex: Windows 10 64-bit", initial.get(f"{prefix}_os", ""))
        add_row(0, "Sistema operacional", fields[f"{prefix}_os"])

        fields[f"{prefix}_cpu"] = self._make_line_edit("Ex: Intel i5-8400", initial.get(f"{prefix}_cpu", ""))
        add_row(1, "Processador", fields[f"{prefix}_cpu"])

        ram_value = initial.get(f"{prefix}_ram_gb")
        fields[f"{prefix}_ram_gb"] = self._make_spinbox(ram_value, suffix=" GB")
        add_row(2, "RAM", fields[f"{prefix}_ram_gb"])

        fields[f"{prefix}_gpu"] = self._make_line_edit("Ex: GTX 1060 / RX 580", initial.get(f"{prefix}_gpu", ""))
        add_row(3, "GPU", fields[f"{prefix}_gpu"])

        fields[f"{prefix}_directx"] = self._make_line_edit("Ex: DirectX 12", initial.get(f"{prefix}_directx", ""))
        add_row(4, "DirectX", fields[f"{prefix}_directx"])

        storage_value = initial.get(f"{prefix}_storage_gb")
        fields[f"{prefix}_storage_gb"] = self._make_spinbox(storage_value, suffix=" GB")
        add_row(5, "Armazenamento", fields[f"{prefix}_storage_gb"])

        fields[f"{prefix}_notes"] = self._make_text_edit(
            "Observações extras",
            initial.get(f"{prefix}_notes", "")
        )

        layout.addLayout(grid)

        notes_label = QLabel("Observações")
        notes_label.setStyleSheet("color: #e0d9ff; font-size: 13px; border: none;")
        layout.addWidget(notes_label)
        layout.addWidget(fields[f"{prefix}_notes"])

        return box, fields

    def _spin_value_or_none(self, spin: QSpinBox):
        return None if spin.value() <= 0 else spin.value()

    def _collect_game_payload(self):
        return {
            "nome": (self.game_name.text() or "").strip(),
            "descricao": (self.game_desc.toPlainText() or "").strip(),
            "dropbox_token": (self.game_dropbox.text() or "").strip(),
            "capa_url": (self.game_cover.text() or "").strip(),
            "banner_url": (self.game_banner.text() or "").strip(),
            "screenshot_1_url": (self.game_screenshot_1.text() or "").strip(),
            "screenshot_2_url": (self.game_screenshot_2.text() or "").strip(),

            "min_os": (self.req_fields["min_os"].text() or "").strip(),
            "min_cpu": (self.req_fields["min_cpu"].text() or "").strip(),
            "min_ram_gb": self._spin_value_or_none(self.req_fields["min_ram_gb"]),
            "min_gpu": (self.req_fields["min_gpu"].text() or "").strip(),
            "min_directx": (self.req_fields["min_directx"].text() or "").strip(),
            "min_storage_gb": self._spin_value_or_none(self.req_fields["min_storage_gb"]),
            "min_notes": (self.req_fields["min_notes"].toPlainText() or "").strip(),

            "rec_os": (self.req_fields["rec_os"].text() or "").strip(),
            "rec_cpu": (self.req_fields["rec_cpu"].text() or "").strip(),
            "rec_ram_gb": self._spin_value_or_none(self.req_fields["rec_ram_gb"]),
            "rec_gpu": (self.req_fields["rec_gpu"].text() or "").strip(),
            "rec_directx": (self.req_fields["rec_directx"].text() or "").strip(),
            "rec_storage_gb": self._spin_value_or_none(self.req_fields["rec_storage_gb"]),
            "rec_notes": (self.req_fields["rec_notes"].toPlainText() or "").strip(),
        }

    def _clear_game_form(self):
        self.game_name.clear()
        self.game_desc.clear()
        self.game_dropbox.clear()
        self.game_cover.clear()
        self.game_banner.clear()
        self.game_screenshot_1.clear()
        self.game_screenshot_2.clear()

        for key, widget in self.req_fields.items():
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QTextEdit):
                widget.clear()
            elif isinstance(widget, QSpinBox):
                widget.setValue(0)

    def create_add_game_page(self):
        frame = QFrame()
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #0d0b1f;
                width: 12px;
                margin: 6px 0 6px 0;
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
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title = QLabel("Adicionar Novo Jogo")
        title.setStyleSheet("""
            font-size: 22px;
            font-weight: bold;
            color: #836FFF;
        """)
        layout.addWidget(title)

        self.game_name = self._make_line_edit("Nome do jogo")
        layout.addWidget(self.game_name)

        self.game_desc = self._make_text_edit("Descrição do jogo")
        layout.addWidget(self.game_desc)

        self.game_dropbox = self._make_line_edit("Token, caminho ou link do arquivo")
        layout.addWidget(self.game_dropbox)

        self.game_cover = self._make_line_edit("URL da capa (opcional)")
        layout.addWidget(self.game_cover)

        self.game_banner = self._make_line_edit("URL da imagem grande do destaque / capa do carrossel")
        layout.addWidget(self.game_banner)

        self.game_screenshot_1 = self._make_line_edit("URL da imagem gameplay 1")
        layout.addWidget(self.game_screenshot_1)

        self.game_screenshot_2 = self._make_line_edit("URL da imagem gameplay 2")
        layout.addWidget(self.game_screenshot_2)

        layout.addWidget(self._section_title("Requisitos mínimos"))
        min_box, min_fields = self._create_requirements_section("min")
        layout.addWidget(min_box)

        layout.addWidget(self._section_title("Requisitos recomendados"))
        rec_box, rec_fields = self._create_requirements_section("rec")
        layout.addWidget(rec_box)

        self.req_fields = {}
        self.req_fields.update(min_fields)
        self.req_fields.update(rec_fields)

        save_btn = QPushButton("Salvar Jogo")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #007eff;
                color: white;
                font-size: 14px;
                padding: 10px 12px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #005bb5;
            }
        """)
        save_btn.clicked.connect(self.save_game)
        layout.addWidget(save_btn)

        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        return frame

    def save_game(self):
        data = self._collect_game_payload()

        if not data["nome"]:
            QMessageBox.warning(self, "Erro", "Preencha o nome do jogo.")
            return

        if not data["dropbox_token"]:
            QMessageBox.warning(self, "Erro", "Informe o Token/Link/Caminho do jogo.")
            return

        try:
            response = request_api(self, "POST", "/admin/adicionar_jogo", json_body=data, timeout=20)

            if response.status_code != 200:
                payload = safe_json(response) or {}
                detail = payload.get("detail") or payload.get("message") or ""
                debug_http_dialog(self, "Erro 500/4xx - adicionar_jogo", response, extra=f"DETAIL: {detail}")
                QMessageBox.warning(
                    self,
                    "Erro",
                    f"Não foi possível salvar o jogo ({response.status_code}).\n\n{detail or response.text[:1200]}"
                )
                return

            QMessageBox.information(self, "Sucesso", "Jogo adicionado com sucesso!")
            self._clear_game_form()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao conectar ao servidor:\n{e}")

    def create_manage_games_page(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Gerenciar Jogos")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(title)

        # ✅ Scroll
        self.games_scroll = QScrollArea()
        self.games_scroll.setWidgetResizable(True)
        self.games_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.games_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.games_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #0d0b1f;
                width: 12px;
                margin: 6px 0 6px 0;
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
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # ✅ Conteúdo do scroll (onde os rows vão ficar)
        self.games_scroll_content = QWidget()
        self.games_list = QVBoxLayout(self.games_scroll_content)
        self.games_list.setContentsMargins(10, 10, 10, 10)
        self.games_list.setSpacing(10)
        self.games_list.setAlignment(Qt.AlignmentFlag.AlignTop)  # ✅ não “puxa” pra baixo

        self.games_scroll.setWidget(self.games_scroll_content)
        layout.addWidget(self.games_scroll, stretch=1)

        refresh_btn = QPushButton("Atualizar Lista")
        refresh_btn.setStyleSheet(
            "background-color: #007eff; color: white; font-size: 18px; padding: 10px; border-radius: 8px;")
        refresh_btn.clicked.connect(self.load_games)
        layout.addWidget(refresh_btn)

        return frame

    def load_games(self):
        try:
            response = request_api(self, "GET", "/admin/listar_jogos", timeout=20)

            if response.status_code != 200:
                payload = safe_json(response) or {}
                detail = payload.get("detail") or payload.get("message") or ""
                debug_http_dialog(self, "Erro 500/4xx - listar_jogos", response, extra=f"DETAIL: {detail}")
                QMessageBox.warning(self, "Erro", f"Falha ao carregar jogos ({response.status_code}).\n\n{detail}")
                return

            data = safe_json(response) or {}
            jogos = data.get("jogos", [])

            # limpar lista
            while self.games_list.count():
                item = self.games_list.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

            for jogo in jogos:
                row_widget = QFrame()
                row_widget.setFixedHeight(56)
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(10, 6, 10, 6)

                nome = (jogo.get("nome") or "").strip()
                desc = (jogo.get("descricao") or "").strip()

                label = QLabel(f"[{jogo.get('id')}] {nome}")
                label.setStyleSheet("color: white; font-size: 14px;")
                label.setWordWrap(False)
                label.setMinimumWidth(0)
                label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                row_layout.addWidget(label, stretch=1)

                btn_details = QPushButton("Detalhes")
                btn_details.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(131,111,255,0.12);
                        border: 1px solid #836FFF;
                        color: #e0d9ff;
                        padding: 6px 10px;
                        border-radius: 8px;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #836FFF;
                        color: #0d0b1f;
                    }
                """)
                btn_details.clicked.connect(lambda _, n=nome, d=desc: QMessageBox.information(
                    self, f"Descrição - {n}", d if d else "Sem descrição."
                ))
                row_layout.addWidget(btn_details)

                btn_edit = QPushButton("Editar")
                btn_edit.setStyleSheet("background-color: orange; color: white; padding: 5px;")
                btn_edit.clicked.connect(lambda _, j=jogo: self.edit_game(j))
                row_layout.addWidget(btn_edit)

                btn_delete = QPushButton("Deletar")
                btn_delete.setStyleSheet("background-color: red; color: white; padding: 5px;")
                btn_delete.clicked.connect(lambda _, jid=jogo.get("id"): self.delete_game(jid))
                row_layout.addWidget(btn_delete)

                self.games_list.addWidget(row_widget)

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao conectar ao servidor:\n{e}")

    def delete_game(self, jogo_id):
        confirm = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Tem certeza que deseja deletar o jogo ID {jogo_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                response = request_api(self, "DELETE", f"/admin/deletar_jogo/{jogo_id}", timeout=20)
                if response.status_code != 200:
                    debug_http_dialog(self, "Erro - deletar_jogo", response)
                if response.status_code == 200:
                    QMessageBox.information(self, "Sucesso", "Jogo deletado com sucesso")
                    self.load_games()
                else:
                    QMessageBox.warning(self, "Erro", "Não foi possível deletar o jogo")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao conectar ao servidor: {e}")

    def edit_game(self, jogo):
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Editar Jogo")
            dialog.resize(760, 760)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #120f2a;
                    color: white;
                }
            """)

            outer = QVBoxLayout(dialog)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("""
                QScrollArea {
                    border: none;
                    background: transparent;
                }
            """)

            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(12)

            nome_input = self._make_line_edit("Nome do jogo", jogo.get("nome", ""))
            layout.addWidget(nome_input)

            desc_input = self._make_text_edit("Descrição do jogo", jogo.get("descricao", ""))
            layout.addWidget(desc_input)

            token_input = self._make_line_edit("Token/caminho/link do jogo", jogo.get("dropbox_token", ""))
            layout.addWidget(token_input)

            capa_input = self._make_line_edit("URL da capa", jogo.get("capa_url", ""))
            layout.addWidget(capa_input)

            banner_input = self._make_line_edit(
                "URL da imagem grande do destaque / capa do carrossel",
                jogo.get("banner_url", "")
            )
            layout.addWidget(banner_input)

            screenshot_1_input = self._make_line_edit(
                "URL da imagem gameplay 1",
                jogo.get("screenshot_1_url", "")
            )
            layout.addWidget(screenshot_1_input)

            screenshot_2_input = self._make_line_edit(
                "URL da imagem gameplay 2",
                jogo.get("screenshot_2_url", "")
            )
            layout.addWidget(screenshot_2_input)

            layout.addWidget(self._section_title("Requisitos mínimos"))
            min_box, min_fields = self._create_requirements_section("min", jogo)
            layout.addWidget(min_box)

            layout.addWidget(self._section_title("Requisitos recomendados"))
            rec_box, rec_fields = self._create_requirements_section("rec", jogo)
            layout.addWidget(rec_box)

            fields = {}
            fields.update(min_fields)
            fields.update(rec_fields)

            save_btn = QPushButton("Salvar Alterações")
            save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #007eff;
                    color: white;
                    font-size: 14px;
                    padding: 10px;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #005bb5;
                }
            """)
            layout.addWidget(save_btn)
            layout.addStretch()

            scroll.setWidget(content)
            outer.addWidget(scroll)

            def spin_value_or_none(spin):
                return None if spin.value() <= 0 else spin.value()

            def salvar():
                payload = {
                    "nome": (nome_input.text() or "").strip(),
                    "descricao": (desc_input.toPlainText() or "").strip(),
                    "dropbox_token": (token_input.text() or "").strip(),
                    "capa_url": (capa_input.text() or "").strip(),
                    "banner_url": (banner_input.text() or "").strip(),
                    "screenshot_1_url": (screenshot_1_input.text() or "").strip(),
                    "screenshot_2_url": (screenshot_2_input.text() or "").strip(),

                    "min_os": (fields["min_os"].text() or "").strip(),
                    "min_cpu": (fields["min_cpu"].text() or "").strip(),
                    "min_ram_gb": spin_value_or_none(fields["min_ram_gb"]),
                    "min_gpu": (fields["min_gpu"].text() or "").strip(),
                    "min_directx": (fields["min_directx"].text() or "").strip(),
                    "min_storage_gb": spin_value_or_none(fields["min_storage_gb"]),
                    "min_notes": (fields["min_notes"].toPlainText() or "").strip(),

                    "rec_os": (fields["rec_os"].text() or "").strip(),
                    "rec_cpu": (fields["rec_cpu"].text() or "").strip(),
                    "rec_ram_gb": spin_value_or_none(fields["rec_ram_gb"]),
                    "rec_gpu": (fields["rec_gpu"].text() or "").strip(),
                    "rec_directx": (fields["rec_directx"].text() or "").strip(),
                    "rec_storage_gb": spin_value_or_none(fields["rec_storage_gb"]),
                    "rec_notes": (fields["rec_notes"].toPlainText() or "").strip(),
                }

                if not payload["nome"]:
                    QMessageBox.warning(dialog, "Erro", "Preencha o nome do jogo.")
                    return

                if not payload["dropbox_token"]:
                    QMessageBox.warning(dialog, "Erro", "Informe o Token/Link/Caminho do jogo.")
                    return

                try:
                    response = request_api(
                        self,
                        "PUT",
                        f"/admin/editar_jogo/{jogo['id']}",
                        json_body=payload,
                        timeout=20
                    )

                    if response.status_code != 200:
                        debug_http_dialog(self, "Erro - editar_jogo", response)
                        QMessageBox.warning(dialog, "Erro", f"Falha ao editar jogo ({response.status_code})")
                        return

                    QMessageBox.information(self, "Sucesso", "Jogo atualizado com sucesso")
                    dialog.accept()
                    self.load_games()

                except Exception as e:
                    QMessageBox.critical(dialog, "Erro", f"Erro ao salvar: {e}")

            save_btn.clicked.connect(salvar)
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Erro ao abrir edição", str(e))

    def create_manage_avatars_page(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Gerenciar Avatares")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #836FFF;")
        layout.addWidget(title)

        self.avatar_name = self._make_line_edit("Nome do avatar")
        layout.addWidget(self.avatar_name)

        self.avatar_url = self._make_line_edit("URL da imagem do avatar")
        layout.addWidget(self.avatar_url)

        self.avatar_status = QComboBox()
        self.avatar_status.addItems(["Ativo", "Inativo"])
        self.avatar_status.setStyleSheet("""
            QComboBox {
                background-color: #0d0b1f;
                color: white;
                border: 2px solid #2a245f;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QComboBox:focus {
                border: 2px solid #007eff;
            }
        """)
        layout.addWidget(self.avatar_status)

        save_btn = QPushButton("Salvar Avatar")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #007eff;
                color: white;
                font-size: 14px;
                padding: 10px 12px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #005bb5;
            }
        """)
        save_btn.clicked.connect(self.save_avatar)
        layout.addWidget(save_btn)

        self.avatar_list = QVBoxLayout()
        self.avatar_list.setSpacing(10)
        layout.addLayout(self.avatar_list)

        refresh_btn = QPushButton("Atualizar Lista de Avatares")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #836FFF;
                color: white;
                font-size: 14px;
                padding: 10px 12px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #6f55ff;
            }
        """)
        refresh_btn.clicked.connect(self.load_avatars)
        layout.addWidget(refresh_btn)

        layout.addStretch()
        return frame

    def save_avatar(self):
        nome = (self.avatar_name.text() or "").strip()
        image_url = (self.avatar_url.text() or "").strip()
        is_active = self.avatar_status.currentText() == "Ativo"

        if not nome:
            QMessageBox.warning(self, "Erro", "Preencha o nome do avatar.")
            return

        if not image_url:
            QMessageBox.warning(self, "Erro", "Preencha a URL da imagem.")
            return

        payload = {
            "nome": nome,
            "image_url": image_url,
            "is_active": is_active
        }

        try:
            response = request_api(self, "POST", "/admin/adicionar_avatar", json_body=payload, timeout=20)

            if response.status_code != 200:
                debug_http_dialog(self, "Erro - adicionar_avatar", response)
                QMessageBox.warning(self, "Erro", f"Falha ao salvar avatar ({response.status_code})")
                return

            QMessageBox.information(self, "Sucesso", "Avatar adicionado com sucesso!")
            self.avatar_name.clear()
            self.avatar_url.clear()
            self.avatar_status.setCurrentIndex(0)
            self.load_avatars()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao conectar ao servidor:\n{e}")

    def load_avatars(self):
        try:
            response = request_api(self, "GET", "/admin/listar_avatars", timeout=20)

            if response.status_code != 200:
                debug_http_dialog(self, "Erro - listar_avatars", response)
                QMessageBox.warning(self, "Erro", f"Falha ao carregar avatares ({response.status_code})")
                return

            data = safe_json(response) or {}
            avatars = data.get("avatars", [])

            while self.avatar_list.count():
                item = self.avatar_list.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

            for avatar in avatars:
                row_widget = QFrame()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(10, 6, 10, 6)

                nome = avatar.get("nome", "")
                image_url = avatar.get("image_url", "")
                is_active = avatar.get("is_active", True)

                status_text = "Ativo" if is_active else "Inativo"
                status_color = "#4CAF50" if is_active else "#F44336"

                label = QLabel(f"[{avatar.get('id')}] {nome}")
                label.setStyleSheet("color: white; font-size: 14px;")
                row_layout.addWidget(label)

                row_layout.addStretch()

                status_lbl = QLabel(status_text)
                status_lbl.setStyleSheet(f"color: {status_color}; font-weight: bold;")
                row_layout.addWidget(status_lbl)

                btn_edit = QPushButton("Editar")
                btn_edit.setStyleSheet("background-color: orange; color: white; padding: 5px;")
                btn_edit.clicked.connect(lambda _, a=avatar: self.edit_avatar(a))
                row_layout.addWidget(btn_edit)

                btn_delete = QPushButton("Deletar")
                btn_delete.setStyleSheet("background-color: red; color: white; padding: 5px;")
                btn_delete.clicked.connect(lambda _, aid=avatar.get("id"): self.delete_avatar(aid))
                row_layout.addWidget(btn_delete)

                self.avatar_list.addWidget(row_widget)

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao conectar ao servidor:\n{e}")


    def edit_avatar(self, avatar):
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Avatar")
        dialog.resize(500, 260)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #120f2a;
                color: white;
            }
        """)

        layout = QVBoxLayout(dialog)

        nome_input = self._make_line_edit("Nome do avatar", avatar.get("nome", ""))
        layout.addWidget(nome_input)

        url_input = self._make_line_edit("URL da imagem", avatar.get("image_url", ""))
        layout.addWidget(url_input)

        status_combo = QComboBox()
        status_combo.addItems(["Ativo", "Inativo"])
        status_combo.setCurrentText("Ativo" if avatar.get("is_active", True) else "Inativo")
        status_combo.setStyleSheet("""
            QComboBox {
                background-color: #0d0b1f;
                color: white;
                border: 2px solid #2a245f;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
        """)
        layout.addWidget(status_combo)

        save_btn = QPushButton("Salvar Alterações")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #007eff;
                color: white;
                font-size: 14px;
                padding: 10px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #005bb5;
            }
        """)
        layout.addWidget(save_btn)

        def salvar():
            payload = {
                "nome": (nome_input.text() or "").strip(),
                "image_url": (url_input.text() or "").strip(),
                "is_active": status_combo.currentText() == "Ativo"
            }

            if not payload["nome"]:
                QMessageBox.warning(dialog, "Erro", "Preencha o nome do avatar.")
                return

            if not payload["image_url"]:
                QMessageBox.warning(dialog, "Erro", "Preencha a URL da imagem.")
                return

            try:
                response = request_api(
                    self,
                    "PUT",
                    f"/admin/editar_avatar/{avatar['id']}",
                    json_body=payload,
                    timeout=20
                )

                if response.status_code != 200:
                    debug_http_dialog(self, "Erro - editar_avatar", response)
                    QMessageBox.warning(dialog, "Erro", f"Falha ao editar avatar ({response.status_code})")
                    return

                QMessageBox.information(self, "Sucesso", "Avatar atualizado com sucesso")
                dialog.accept()
                self.load_avatars()

            except Exception as e:
                QMessageBox.critical(dialog, "Erro", f"Falha ao salvar avatar:\n{e}")

        save_btn.clicked.connect(salvar)
        dialog.exec()

    def delete_avatar(self, avatar_id):
        confirm = QMessageBox.question(
            self,
            "Confirmar Exclusão",
            f"Tem certeza que deseja deletar o avatar ID {avatar_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            response = request_api(self, "DELETE", f"/admin/deletar_avatar/{avatar_id}", timeout=20)

            if response.status_code != 200:
                debug_http_dialog(self, "Erro - deletar_avatar", response)
                QMessageBox.warning(self, "Erro", "Não foi possível deletar o avatar")
                return

            QMessageBox.information(self, "Sucesso", "Avatar deletado com sucesso")
            self.load_avatars()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao conectar ao servidor:\n{e}")

    def open_explore_page(self):
        try:
            # Import local para evitar circular imports
            from explore_page import MainWindow
            self.explore_window = MainWindow()
            self.explore_window.show()
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao abrir página de explorar: {e}")






if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AdminPage()
    sys.exit(app.exec())
