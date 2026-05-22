from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget, QTableWidgetItem, QFrame
from PyQt5.QtCore import Qt


class DropZone(QFrame):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.path = ''
        self.setStyleSheet('border:2px dashed #94a3b8;background:#fff;border-radius:8px;')
        self.label = QLabel('拖拽文件到这里，或点击“开始运行”使用已有路径', self)
        self.label.setAlignment(Qt.AlignCenter)
        l = QVBoxLayout(self)
        l.addWidget(self.label)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls()]
        if files:
            self.path = files[0]
            self.label.setText(f'已选择: {self.path}')


class BusinessPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        row = QHBoxLayout()
        self.btn_start = QPushButton('开始运行')
        self.btn_stop = QPushButton('停止')
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_stop)
        root.addLayout(row)

        self.drop_zone = DropZone()
        root.addWidget(self.drop_zone)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(['步骤', '状态', '说明'])
        root.addWidget(self.table)

    def fill_rows(self, rows):
        self.table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(str(item.get('步骤', ''))))
            self.table.setItem(r, 1, QTableWidgetItem(str(item.get('状态', ''))))
            self.table.setItem(r, 2, QTableWidgetItem(str(item.get('说明', ''))))
