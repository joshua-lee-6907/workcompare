from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QListWidget, QStackedWidget, QStatusBar, QLabel, QProgressBar, QAction, QMessageBox, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.business_page import BusinessPage
from app.ui.pages.history_page import HistoryPage
from app.ui.pages.settings_page import SettingsPage
from app.core.worker import CoreWorker


class MainWindow(QMainWindow):
    def __init__(self, cfg: dict, save_cfg):
        super().__init__()
        self.cfg = cfg
        self.save_cfg = save_cfg
        self.worker = None
        self.setWindowTitle('企业数据可视化平台')
        self.resize(1400, 900)
        self._build_menu()
        self._build_ui()
        self._build_status()
        self._build_tray()

    def _build_menu(self):
        m = self.menuBar()
        file_m = m.addMenu('文件')
        tool_m = m.addMenu('工具')
        help_m = m.addMenu('帮助')
        act_exit = QAction('退出', self); act_exit.triggered.connect(self.close)
        act_set = QAction('设置', self); act_set.triggered.connect(lambda: self.nav.setCurrentRow(3))
        act_about = QAction('关于', self); act_about.triggered.connect(lambda: QMessageBox.information(self, '关于', 'v1.0.0'))
        act_update = QAction('检查更新', self); act_update.triggered.connect(lambda: QMessageBox.information(self, '更新', '当前已是最新版本'))
        file_m.addAction(act_exit); tool_m.addAction(act_set); help_m.addAction(act_about); help_m.addAction(act_update)

    def _build_ui(self):
        c = QWidget(self)
        self.setCentralWidget(c)
        l = QHBoxLayout(c)
        self.nav = QListWidget(self)
        self.nav.addItems(['首页看板', '核心业务页', '历史记录', '系统设置'])
        self.stack = QStackedWidget(self)
        self.dashboard = DashboardPage()
        self.business = BusinessPage()
        self.history = HistoryPage()
        self.settings = SettingsPage(self.cfg, self.save_cfg)
        for p in [self.dashboard, self.business, self.history, self.settings]:
            self.stack.addWidget(p)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        l.addWidget(self.nav, 1)
        l.addWidget(self.stack, 6)

        self.business.btn_start.clicked.connect(self.start_task)
        self.business.btn_stop.clicked.connect(self.stop_task)

    def _build_status(self):
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self.lbl_status = QLabel('就绪')
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.lbl_ver = QLabel('v1.0.0')
        sb.addWidget(self.lbl_status, 2)
        sb.addWidget(self.progress, 3)
        sb.addPermanentWidget(self.lbl_ver, 1)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(QIcon(), self)
        menu = QMenu(self)
        act_show = menu.addAction('显示主界面')
        act_quit = menu.addAction('退出')
        act_show.triggered.connect(self.showNormal)
        act_quit.triggered.connect(self._quit_from_tray)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def start_task(self):
        if self.worker and self.worker.isRunning():
            return
        payload = {'file': self.business.drop_zone.path}
        self.worker = CoreWorker(payload)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.lbl_status.setText('正在处理...')
        self.progress.setValue(0)
        self.worker.start()

    def stop_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.lbl_status.setText('正在停止...')

    def on_progress(self, p, text):
        self.progress.setValue(p)
        self.lbl_status.setText(text)

    def on_finished(self, rows):
        self.lbl_status.setText('处理完成')
        self.business.fill_rows(rows)

    def on_failed(self, msg):
        self.lbl_status.setText('失败')
        QMessageBox.critical(self, '错误', msg)

    def closeEvent(self, event):
        if self.cfg.get('minimize_to_tray', True):
            self.hide()
            self.tray.showMessage('提示', '程序已最小化到托盘')
            event.ignore()
        else:
            event.accept()

    def _quit_from_tray(self):
        self.tray.hide()
        self.cfg['minimize_to_tray'] = False
        self.close()
