from PyQt5.QtWidgets import QWidget, QGridLayout, QFrame, QVBoxLayout, QLabel


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        g = QGridLayout(self)
        metrics = [('今日任务', '24'), ('成功率', '98.5%'), ('平均耗时', '1.4s'), ('异常数', '1')]
        for i, (k, v) in enumerate(metrics):
            card = QFrame(self)
            card.setStyleSheet('background:#fff;border:1px solid #e2e8f0;border-radius:8px;')
            l = QVBoxLayout(card)
            l.addWidget(QLabel(k))
            lbl = QLabel(v)
            lbl.setStyleSheet('font-size:28px;color:#1e3a8a;font-weight:700;')
            l.addWidget(lbl)
            g.addWidget(card, i//2, i%2)
