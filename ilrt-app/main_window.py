from __future__ import annotations

try:
    from PySide6.QtWidgets import QMainWindow, QTabWidget
except Exception:
    from PyQt5.QtWidgets import QMainWindow, QTabWidget

from views.page_calculator import DataChartPage, ExcelVisualizerPage
from setting_interface import SettingInterface


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Excel 数据可视化 - ILRT Shell")
        self.resize(1400, 900)

        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        self.chart_page = DataChartPage(self)
        self.function_page = ExcelVisualizerPage(self.chart_page, self)

        self.addSubInterface(self.chart_page, "数据图表")
        self.addSubInterface(self.function_page, "功能页")
        self.addSubInterface(SettingInterface(self), "设置")

    def addSubInterface(self, widget, title: str):
        self.tabs.addTab(widget, title)
