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
from PyQt6.QtCore import Qt
import secrets
import string
from functools import partial
from PyQt6.QtGui import QFontDatabase, QFont

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

    def create_add_game_page(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)

        title = QLabel("Adicionar Novo Jogo")
        title.setStyleSheet("""
            font-size: 22px;
            font-weight: bold;
            color: #836FFF;
        """)
        layout.addWidget(title)

        # Campos do formulário
        from PyQt6.QtWidgets import QLineEdit, QTextEdit

        self.game_name = QLineEdit()
        self.game_name.setPlaceholderText("Nome do jogo")
        self.game_name.setStyleSheet("padding: 5px; border: 2px solid #007eff; border-radius: 5px; color: white;")
        layout.addWidget(self.game_name)

        self.game_desc = QTextEdit()
        self.game_desc.setPlaceholderText("Descrição do jogo")
        self.game_desc.setStyleSheet("padding: 5px; border: 2px solid #007eff; border-radius: 5px; color: white;")
        layout.addWidget(self.game_desc)

        self.game_dropbox = QLineEdit()
        self.game_dropbox.setPlaceholderText("Token ou Link do Dropbox")
        self.game_dropbox.setStyleSheet("padding: 5px; border: 2px solid #007eff; border-radius: 5px; color: white;")
        layout.addWidget(self.game_dropbox)

        self.game_cover = QLineEdit()
        self.game_cover.setPlaceholderText("URL da capa (opcional)")
        self.game_cover.setStyleSheet("padding: 5px; border: 2px solid #007eff; border-radius: 5px; color: white;")
        layout.addWidget(self.game_cover)

        # Botão para salvar
        save_btn = QPushButton("Salvar Jogo")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #007eff;
                color: white;
                font-size: 14px;
                padding: 8px 12px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #005bb5;
            }
        """)
        save_btn.clicked.connect(self.save_game)
        layout.addWidget(save_btn)

        layout.addStretch()
        return frame

    def save_game(self):
        data = {
            "nome": (self.game_name.text() or "").strip(),
            "descricao": (self.game_desc.toPlainText() or "").strip(),
            "dropbox_token": (self.game_dropbox.text() or "").strip(),
            "capa_url": (self.game_cover.text() or "").strip()
        }

        if not data["nome"]:
            QMessageBox.warning(self, "Erro", "Preencha o nome do jogo.")
            return

        if not data["dropbox_token"]:
            QMessageBox.warning(self, "Erro", "Informe o Token/Link do Dropbox.")
            return

        try:
            response = request_api(self, "POST", "/admin/adicionar_jogo", json_body=data, timeout=20)

            # Debug SEMPRE quando der ruim (e opcionalmente quando ok)
            if response.status_code != 200:
                payload = safe_json(response) or {}
                detail = payload.get("detail") or payload.get("message") or ""
                debug_http_dialog(self, "Erro 500/4xx - adicionar_jogo", response, extra=f"DETAIL: {detail}")
                QMessageBox.warning(self, "Erro",
                                    f"Não foi possível salvar o jogo ({response.status_code}).\n\n{detail or response.text[:1200]}")
                return

            QMessageBox.information(self, "Sucesso", "Jogo adicionado com sucesso!")
            self.game_name.clear()
            self.game_desc.clear()
            self.game_dropbox.clear()
            self.game_cover.clear()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao conectar ao servidor:\n{e}")

    def create_manage_games_page(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)

        title = QLabel("Gerenciar Jogos")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(title)

        self.games_list = QVBoxLayout()  # usamos QVBoxLayout para ter botões junto
        layout.addLayout(self.games_list)

        refresh_btn = QPushButton("Atualizar Lista")
        refresh_btn.setStyleSheet("background-color: #007eff; color: white; font-size: 18px;")
        refresh_btn.clicked.connect(self.load_games)
        layout.addWidget(refresh_btn)

        layout.addStretch()
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
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(10, 6, 10, 6)

                label = QLabel(f"[{jogo.get('id')}] {jogo.get('nome')} - {jogo.get('descricao')}")
                label.setStyleSheet("color: white; font-size: 14px;")
                row_layout.addWidget(label)

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
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Jogo")
        dialog.setStyleSheet("background-color: #1e1e1e; color: white;")

        layout = QVBoxLayout(dialog)

        nome_input = QLineEdit(jogo["nome"])
        nome_input.setPlaceholderText("Nome do jogo")
        layout.addWidget(nome_input)

        desc_input = QTextEdit(jogo["descricao"])
        desc_input.setPlaceholderText("Descrição do jogo")
        layout.addWidget(desc_input)

        token_input = QLineEdit(jogo["dropbox_token"])
        token_input.setPlaceholderText("Token do Dropbox")
        layout.addWidget(token_input)

        capa_input = QLineEdit(jogo["capa_url"])
        capa_input.setPlaceholderText("URL da capa")
        layout.addWidget(capa_input)

        save_btn = QPushButton("Salvar Alterações")
        save_btn.setStyleSheet("background-color: #007eff; color: white; font-size: 14px;")
        layout.addWidget(save_btn)

        def salvar():
            try:
                response = request_api(
                    self, "PUT", f"/admin/editar_jogo/{jogo['id']}",
                    json_body={
                        "nome": (nome_input.text() or "").strip(),
                        "descricao": (desc_input.toPlainText() or "").strip(),
                        "dropbox_token": (token_input.text() or "").strip(),
                        "capa_url": (capa_input.text() or "").strip()
                    },
                    timeout=20
                )
                if response.status_code != 200:
                    debug_http_dialog(self, "Erro - editar_jogo", response)
                if response.status_code == 200:
                    QMessageBox.information(self, "Sucesso", "Jogo atualizado com sucesso")
                    dialog.accept()
                    self.load_games()
                else:
                    QMessageBox.warning(self, "Erro", f"Falha ao editar jogo ({response.status_code})")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao salvar: {e}")

        save_btn.clicked.connect(salvar)
        dialog.exec()

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
