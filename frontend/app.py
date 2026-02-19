# app.py
import sys
import os

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase, QIcon, QFont

from utils import resource_path
from homepage import HomePage
from login import LoginWindow

FONT_PATH = resource_path(os.path.join("fonts", "VT323-Regular.ttf"))


def main():
    app = QApplication(sys.argv)

    # Ícone do app
    app.setWindowIcon(QIcon(resource_path(os.path.join("logos", "primex_ico.ico"))))

    # Fonte VT323 (vem junto no build)
    font_id = QFontDatabase.addApplicationFont(FONT_PATH)
    if font_id != -1:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0]))

    def create_login_window():
        return LoginWindow()

    splash = HomePage(next_window_factory=create_login_window, delay_ms=1800)
    splash.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
