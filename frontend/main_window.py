# main_window.py
from PyQt6.QtWidgets import QApplication, QMainWindow
from explore_page import MainWindow  # aqui é sua tela Explore
from profile import ProfilePage
from installed import InstaladosPage


class AppController(QMainWindow):
    def __init__(self, usuario_info=None):
        super().__init__()

        self.user_info = usuario_info

        # Abre a tela principal (explore_page.MainWindow)
        self.explore_window = MainWindow(usuario_info=self.user_info)
        self.setCentralWidget(self.explore_window)

        # Conecta botões
        self.explore_window.button_profile.clicked.connect(self.open_profile)

    def open_profile(self):
        self.profile_window = ProfilePage(usuario_info=self.user_info)
        self.setCentralWidget(self.profile_window)

        # 🔙 Botão de voltar do profile → explore
        self.profile_window.button_back.clicked.connect(self.open_explore)

    def open_explore(self):
        self.explore_window = MainWindow(usuario_info=self.user_info)
        self.setCentralWidget(self.explore_window)

        # Reativa o botão de perfil
        self.explore_window.button_profile.clicked.connect(self.open_profile)

    def open_instalados(self):
        self.installed_window = InstaladosPage(usuario_info=self.user_info)
        self.setCentralWidget(self.installed_window)

        # 🔙 Botão de voltar do instalados → explore
        self.installed_window.button_back.clicked.connect(self.open_explore)


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = AppController(usuario_info={"nome": "Pedro"})
    window.show()
    sys.exit(app.exec())
