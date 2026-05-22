from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QCheckBox, QPushButton, QLabel, QMessageBox


class LoginDialog(QDialog):
    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle('登录')
        self.resize(420, 300)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel('账号'))
        self.user = QLineEdit(self)
        self.user.setText(cfg.get('username', ''))
        lay.addWidget(self.user)
        lay.addWidget(QLabel('密码'))
        self.pwd = QLineEdit(self)
        self.pwd.setEchoMode(QLineEdit.Password)
        self.pwd.setText(cfg.get('password', ''))
        lay.addWidget(self.pwd)
        lay.addWidget(QLabel('验证码（占位）'))
        self.captcha = QLineEdit(self)
        self.captcha.setPlaceholderText('请输入验证码')
        lay.addWidget(self.captcha)
        self.remember = QCheckBox('记住密码', self)
        self.remember.setChecked(cfg.get('remember_password', False))
        self.auto = QCheckBox('自动登录', self)
        self.auto.setChecked(cfg.get('auto_login', False))
        lay.addWidget(self.remember)
        lay.addWidget(self.auto)
        btn = QPushButton('登录', self)
        btn.clicked.connect(self.do_login)
        lay.addWidget(btn)

    def do_login(self):
        if not self.user.text().strip() or not self.pwd.text().strip():
            QMessageBox.warning(self, '提示', '请输入账号和密码')
            return
        self.accept()

    def get_result(self):
        return {
            'username': self.user.text().strip(),
            'password': self.pwd.text().strip() if self.remember.isChecked() else '',
            'remember_password': self.remember.isChecked(),
            'auto_login': self.auto.isChecked(),
        }
