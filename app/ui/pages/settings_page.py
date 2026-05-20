from PyQt5.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QLineEdit, QPushButton, QLabel, QFileDialog, QMessageBox

class SettingsPage(QWidget):
    def __init__(self, cfg: dict, on_save):
        super().__init__()
        self.cfg = cfg
        self.on_save = on_save
        l = QVBoxLayout(self)
        self.startup = QCheckBox('开机自启')
        self.startup.setChecked(cfg.get('start_with_windows', False))
        self.tray = QCheckBox('关闭时最小化到托盘')
        self.tray.setChecked(cfg.get('minimize_to_tray', True))
        self.theme = QLineEdit(cfg.get('theme', 'light'))
        self.path = QLineEdit(cfg.get('default_save_path', ''))
        self.api = QLineEdit(cfg.get('api_key', ''))
        btn_path = QPushButton('选择默认保存路径')
        btn_path.clicked.connect(self.pick_path)
        btn_save = QPushButton('保存设置')
        btn_save.clicked.connect(self.save)
        for w in [self.startup, self.tray, QLabel('外观主题(light/dark)'), self.theme, QLabel('默认保存路径'), self.path, btn_path, QLabel('API Key'), self.api, btn_save]:
            l.addWidget(w)

    def pick_path(self):
        d = QFileDialog.getExistingDirectory(self, '选择目录', self.path.text() or '.')
        if d:
            self.path.setText(d)

    def save(self):
        self.cfg.update({
            'start_with_windows': self.startup.isChecked(),
            'minimize_to_tray': self.tray.isChecked(),
            'theme': self.theme.text().strip() or 'light',
            'default_save_path': self.path.text().strip(),
            'api_key': self.api.text().strip(),
        })
        self.on_save(self.cfg)
        QMessageBox.information(self, '提示', '设置已保存')
