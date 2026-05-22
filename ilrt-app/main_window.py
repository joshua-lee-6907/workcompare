from __future__ import annotations

try:
    from PySide6.QtWidgets import QMainWindow, QTabWidget
except Exception:
    from PyQt5.QtWidgets import QMainWindow, QTabWidget

from views.page_calculator import PageCalculator
from setting_interface import SettingInterface


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ILRT Industrial Shell")
        self.resize(1200, 800)

        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        # Equivalent to addSubInterface in fluent shells.
        self.addSubInterface(PageCalculator(self), "计算页")
        self.addSubInterface(SettingInterface(self), "设置")

    def addSubInterface(self, widget, title: str):
        self.tabs.addTab(widget, title)
