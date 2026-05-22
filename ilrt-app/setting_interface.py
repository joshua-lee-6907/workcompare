from __future__ import annotations

try:
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSpinBox
except Exception:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSpinBox

from config.app_config import AppConfig


class SettingInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = AppConfig()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Decimal Precision"))

        self.precision = QSpinBox(self)
        self.precision.setRange(10, 200)
        self.precision.setValue(self.cfg.decimal_precision)
        self.precision.valueChanged.connect(self._save_precision)
        layout.addWidget(self.precision)
        layout.addStretch(1)

    def _save_precision(self, value: int):
        self.cfg.decimal_precision = value
