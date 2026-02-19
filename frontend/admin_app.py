import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase

from admin import AdminPage

FONT_PATH = os.path.join(os.getcwd(), "assets", "fonts", "VT323-Regular.ttf")

def main():
    app = QApplication(sys.argv)

    try:
        QFontDatabase.addApplicationFont(FONT_PATH)
    except Exception:
        pass

    win = AdminPage()
    win.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
