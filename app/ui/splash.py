from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QSplashScreen, QLabel
from PyQt5.QtGui import QPixmap


class SplashScreen(QSplashScreen):
    def __init__(self):
        pix = QPixmap(620, 320)
        pix.fill(Qt.white)
        super().__init__(pix)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setStyleSheet('background:#f8fafc;color:#1e3a8a;font-size:28px;font-weight:700;')
        self.label = QLabel('数据可视化系统 启动中...', self)
        self.label.setGeometry(60, 130, 500, 50)

    def show_for(self, ms=1500):
        self.show()
        QTimer.singleShot(ms, self.close)
