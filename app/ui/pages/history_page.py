from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

class HistoryPage(QWidget):
    def __init__(self):
        super().__init__()
        l = QVBoxLayout(self)
        l.addWidget(QLabel('历史记录页面（可接数据库/日志）'))
