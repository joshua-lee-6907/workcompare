import sys
from PyQt5.QtWidgets import QApplication
from app.core.config_manager import load_config, save_config
from app.ui.splash import SplashScreen
from app.ui.login import LoginDialog
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    cfg = load_config()

    splash = SplashScreen()
    splash.show_for(1200)
    app.processEvents()

    login = LoginDialog(cfg)
    if not cfg.get('auto_login', False):
        if login.exec_() != login.Accepted:
            return
        cfg.update(login.get_result())
        save_config(cfg)

    w = MainWindow(cfg, save_config)
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
