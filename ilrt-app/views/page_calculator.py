from __future__ import annotations

import numpy as np

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
        QPushButton, QTextEdit
    )
except Exception:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
        QPushButton, QTextEdit
    )

import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.decimal_engine import DecimalEngine
from config.app_config import AppConfig


class PageCalculator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self.engine = DecimalEngine(self.config.decimal_precision)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        self.left = QLineEdit("1.234567890123456789")
        self.op = QComboBox(); self.op.addItems(["+", "-", "*", "/"])
        self.right = QLineEdit("9.876543210987654321")
        btn = QPushButton("计算并绘图")
        btn.clicked.connect(self.compute)

        row.addWidget(QLabel("A")); row.addWidget(self.left)
        row.addWidget(self.op)
        row.addWidget(QLabel("B")); row.addWidget(self.right)
        row.addWidget(btn)

        self.out = QTextEdit(); self.out.setReadOnly(True)
        self.figure = Figure(figsize=(6, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)

        layout.addLayout(row)
        layout.addWidget(self.out)
        layout.addWidget(self.canvas)

    def compute(self):
        self.engine.set_precision(self.config.decimal_precision)
        res = self.engine.evaluate(self.left.text(), self.op.currentText(), self.right.text())
        self.out.setPlainText(f"precision={self.engine.precision}\n{res.expression} = {res.value}")

        x = np.linspace(0, 4 * np.pi, 200)
        y = np.sin(x)
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(x, y, linewidth=2)
        ax.set_title("Matplotlib Canvas (Shell Integration)")
        ax.grid(True, alpha=0.3)
        self.canvas.draw_idle()
