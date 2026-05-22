from __future__ import annotations
import sys

try:
    from PySide6.QtWidgets import QApplication
except Exception:
    from PyQt5.QtWidgets import QApplication

from main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
