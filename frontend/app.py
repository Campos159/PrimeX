# app.py
import sys
import os

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase, QIcon, QFont

from utils import resource_path
from homepage import HomePage
from session import load_session

FONT_PATH = resource_path(os.path.join("fonts", "VT323-Regular.ttf"))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PrimeX")
    app.setApplicationDisplayName("PrimeX")

    app.setWindowIcon(QIcon(resource_path(os.path.join("logos", "primex_ico.ico"))))

    font_id = QFontDatabase.addApplicationFont(FONT_PATH)
    if font_id != -1:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0]))

    def create_next_window():
        sess = load_session()

        if isinstance(sess, dict) and sess.get("id"):
            from explore_page import MainWindow
            return MainWindow(usuario_info=sess)

        from login import LoginWindow
        return LoginWindow()

    splash = HomePage(next_window_factory=create_next_window, delay_ms=1800)
    splash.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()