import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication

# 关键修复：避免入口文件 app.py 与 app/ 包同名导致导入冲突
# 运行 `python app.py` 时，Python 会先把当前文件当作模块 app，
# 导致 `from app.core...` 误解析到本文件而不是 app/ 目录。
# 这里直接把 app/ 目录加入 sys.path，然后按子模块导入。
BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.config_manager import load_config, save_config
from ui.splash import SplashScreen
from ui.login import LoginDialog
from ui.main_window import MainWindow


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
