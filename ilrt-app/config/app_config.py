from __future__ import annotations

try:
    from PySide6.QtCore import QSettings
except Exception:
    from PyQt5.QtCore import QSettings


class AppConfig:
    ORG = "ILRT"
    APP = "ILRT-App"

    def __init__(self) -> None:
        self.settings = QSettings(self.ORG, self.APP)

    @property
    def decimal_precision(self) -> int:
        return int(self.settings.value("decimal_precision", 60))

    @decimal_precision.setter
    def decimal_precision(self, value: int) -> None:
        self.settings.setValue("decimal_precision", int(value))
