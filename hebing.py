#!/usr/bin/env python3
"""
hebing.py – 主程序入口
深蓝科技风 · 工业数据分析一体化平台

架构:
  hebing.py      本文件，登录对话框 + 主窗口 + 菜单/状态栏
  hb_common.py   公共样式、颜色、用户管理工具
  hb_read.py     Tab1 Excel批量读取
  hb_pre.py      Tab2 数据分段与异常检测
  hb_cal.py      Tab3 分段表批量计算
  hb_data.py     Tab4 数据管理（复制Segment→2.db）
  hb_q1d.py      Tab5 Q1D统计分析
  hb_q60.py      Tab6 Q60滑动窗口回归
"""

import sys
import os
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDialog, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFormLayout, QMessageBox, QStatusBar, QMenuBar, QMenu,
    QAction, QGroupBox, QCheckBox, QSizePolicy, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QLinearGradient, QColor, QPen

from hb_common import (
    MAIN_STYLESHEET, BG_DARK, BG_MID, ACCENT, TEXT_MAIN, TEXT_DIM,
    BORDER, HIGHLIGHT, DANGER, BG_WIDGET,
    verify_login, register_user, change_password, get_user_role, load_users, save_users
)
from hb_read  import ReadTab
from hb_pre   import PreTab
from hb_cal   import CalTab
from hb_data  import DataTab
from hb_q1d   import Q1DTab
from hb_q60   import Q60Tab


# ─── Login Dialog ─────────────────────────────────────────────────────────────

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录 — 工业数据分析平台")
        self.setFixedSize(420, 520)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self._username = ""
        self._build_ui()
        self._drag_pos = None

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header banner ──
        header = QFrame()
        header.setFixedHeight(120)
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #0c1228, stop:0.6 #142468, stop:1 #0059c1);
            border-bottom: 2px solid {BORDER};
        """)
        hl = QVBoxLayout(header)
        hl.setAlignment(Qt.AlignCenter)
        logo_lbl = QLabel("⚙  工业数据分析平台")
        logo_lbl.setFont(QFont("Segoe UI", 18, QFont.Bold))
        logo_lbl.setStyleSheet(f"color: {ACCENT}; background: transparent;")
        logo_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl = QLabel("Industrial Data Analysis Platform v2.0")
        sub_lbl.setFont(QFont("Segoe UI", 10))
        sub_lbl.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        sub_lbl.setAlignment(Qt.AlignCenter)
        hl.addWidget(logo_lbl)
        hl.addWidget(sub_lbl)
        root.addWidget(header)

        # ── Form area ──
        form_wrap = QWidget()
        form_wrap.setStyleSheet(f"background: {BG_MID};")
        fl = QVBoxLayout(form_wrap)
        fl.setContentsMargins(40, 32, 40, 32)
        fl.setSpacing(18)

        lbl_title = QLabel("用户登录")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        lbl_title.setStyleSheet(f"color: {ACCENT};")
        fl.addWidget(lbl_title)

        # username
        fl.addWidget(self._field_label("用户名"))
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("请输入用户名 (默认: admin)")
        self.user_edit.setText("admin")
        fl.addWidget(self.user_edit)

        # password
        fl.addWidget(self._field_label("密码"))
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setPlaceholderText("请输入密码 (默认: admin123)")
        self.pass_edit.returnPressed.connect(self._login)
        fl.addWidget(self.pass_edit)

        self.remember_cb = QCheckBox("记住用户名")
        self.remember_cb.setStyleSheet(f"color: {TEXT_DIM}; font-size: 13px;")
        fl.addWidget(self.remember_cb)

        self.lbl_err = QLabel("")
        self.lbl_err.setStyleSheet(f"color: {DANGER}; font-size: 13px;")
        fl.addWidget(self.lbl_err)

        btn_login = QPushButton("登  录")
        btn_login.setFont(QFont("Segoe UI", 14, QFont.Bold))
        btn_login.setMinimumHeight(42)
        btn_login.clicked.connect(self._login)
        fl.addWidget(btn_login)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        fl.addWidget(sep)

        btn_register = QPushButton("注册新账号")
        btn_register.setObjectName("secondary")
        btn_register.clicked.connect(self._open_register)
        fl.addWidget(btn_register)

        # close button
        btn_close = QPushButton("✕  退出")
        btn_close.setObjectName("danger")
        btn_close.clicked.connect(self.reject)
        fl.addWidget(btn_close)

        root.addWidget(form_wrap)

        # ── Footer ──
        footer = QLabel("© 2025  工业数据分析平台  |  深蓝科技风")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px; "
            f"background: {BG_DARK}; padding: 8px;")
        root.addWidget(footer)

    def _field_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {ACCENT}; font-size: 13px; font-weight: bold;")
        return lbl

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)

    def _login(self):
        user = self.user_edit.text().strip()
        pwd  = self.pass_edit.text()
        if not user or not pwd:
            self.lbl_err.setText("用户名和密码不能为空")
            return
        if verify_login(user, pwd):
            self._username = user
            self.accept()
        else:
            self.lbl_err.setText("用户名或密码错误，请重试")
            self.pass_edit.clear()

    def _open_register(self):
        dlg = RegisterDialog(self)
        dlg.exec_()

    def get_username(self):
        return self._username


# ─── Register Dialog ──────────────────────────────────────────────────────────

class RegisterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("注册新账号")
        self.setFixedSize(380, 320)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        title = QLabel("注册新账号")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {ACCENT};")
        root.addWidget(title)

        root.addWidget(self._lbl("用户名"))
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("新用户名")
        root.addWidget(self.user_edit)

        root.addWidget(self._lbl("密码"))
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        root.addWidget(self.pass_edit)

        root.addWidget(self._lbl("确认密码"))
        self.pass2_edit = QLineEdit()
        self.pass2_edit.setEchoMode(QLineEdit.Password)
        root.addWidget(self.pass2_edit)

        self.lbl_err = QLabel("")
        self.lbl_err.setStyleSheet(f"color: {DANGER}; font-size: 12px;")
        root.addWidget(self.lbl_err)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("注 册")
        btn_ok.clicked.connect(self._register)
        btn_cancel = QPushButton("取 消")
        btn_cancel.setObjectName("secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        root.addLayout(btn_row)

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"color: {ACCENT}; font-size: 13px; font-weight: bold;")
        return l

    def _register(self):
        user = self.user_edit.text().strip()
        pwd  = self.pass_edit.text()
        pwd2 = self.pass2_edit.text()
        if not user or not pwd:
            self.lbl_err.setText("请填写完整信息")
            return
        if pwd != pwd2:
            self.lbl_err.setText("两次密码不一致")
            return
        if len(pwd) < 6:
            self.lbl_err.setText("密码至少 6 位")
            return
        if register_user(user, pwd):
            QMessageBox.information(self, "成功", f"账号 [{user}] 注册成功！")
            self.accept()
        else:
            self.lbl_err.setText("该用户名已存在")


# ─── Change Password Dialog ───────────────────────────────────────────────────

class ChangePasswordDialog(QDialog):
    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.username = username
        self.setWindowTitle("修改密码")
        self.setFixedSize(360, 280)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        title = QLabel(f"修改密码 — {self.username}")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet(f"color: {ACCENT};")
        root.addWidget(title)

        for attr, lbl_text, ph in [
            ("old_edit",  "当前密码", ""),
            ("new_edit",  "新密码",   "至少 6 位"),
            ("new2_edit", "确认新密码", ""),
        ]:
            l = QLabel(lbl_text)
            l.setStyleSheet(f"color: {ACCENT}; font-size: 13px; font-weight: bold;")
            root.addWidget(l)
            e = QLineEdit()
            e.setEchoMode(QLineEdit.Password)
            if ph:
                e.setPlaceholderText(ph)
            setattr(self, attr, e)
            root.addWidget(e)

        self.lbl_err = QLabel("")
        self.lbl_err.setStyleSheet(f"color: {DANGER}; font-size: 12px;")
        root.addWidget(self.lbl_err)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("确 认")
        btn_ok.clicked.connect(self._change)
        btn_cancel = QPushButton("取 消")
        btn_cancel.setObjectName("secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        root.addLayout(btn_row)

    def _change(self):
        old  = self.old_edit.text()
        new  = self.new_edit.text()
        new2 = self.new2_edit.text()
        if new != new2:
            self.lbl_err.setText("两次新密码不一致")
            return
        if len(new) < 6:
            self.lbl_err.setText("新密码至少 6 位")
            return
        if change_password(self.username, old, new):
            QMessageBox.information(self, "成功", "密码已成功修改！")
            self.accept()
        else:
            self.lbl_err.setText("当前密码错误")


# ─── User Management Dialog (admin only) ──────────────────────────────────────

class UserMgrDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("用户管理")
        self.setFixedSize(500, 400)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel("用户管理 (管理员)")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {ACCENT};")
        root.addWidget(title)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["用户名", "角色"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_del = QPushButton("删除选中用户")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self._delete_user)
        btn_close = QPushButton("关 闭")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_del)
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

    def _refresh(self):
        from PyQt5.QtWidgets import QTableWidgetItem
        users = load_users()
        self.table.setRowCount(0)
        for uname, info in users.items():
            ri = self.table.rowCount()
            self.table.insertRow(ri)
            self.table.setItem(ri, 0, QTableWidgetItem(uname))
            self.table.setItem(ri, 1, QTableWidgetItem(info.get("role", "user")))

    def _delete_user(self):
        row = self.table.currentRow()
        if row < 0:
            return
        uname = self.table.item(row, 0).text()
        if uname == "admin":
            QMessageBox.warning(self, "警告", "不能删除 admin 账号！")
            return
        reply = QMessageBox.question(self, "确认", f"确认删除用户 [{uname}]？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            users = load_users()
            users.pop(uname, None)
            save_users(users)
            self._refresh()


# ─── About Dialog ─────────────────────────────────────────────────────────────

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self.setFixedSize(400, 300)
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(10)

        lines = [
            ("⚙  工业数据分析平台", 16, True, ACCENT),
            ("版本: v2.0  (2025)", 12, False, TEXT_MAIN),
            ("", 10, False, TEXT_DIM),
            ("功能模块:", 12, True, ACCENT),
            ("  Tab 1  Excel 批量读取 → SQLite", 12, False, TEXT_MAIN),
            ("  Tab 2  数据分段与异常检测", 12, False, TEXT_MAIN),
            ("  Tab 3  分段表批量计算 (Q1d/A8)", 12, False, TEXT_MAIN),
            ("  Tab 4  数据管理 (复制 Segment→2.db)", 12, False, TEXT_MAIN),
            ("  Tab 5  Q1D 统计分析", 12, False, TEXT_MAIN),
            ("  Tab 6  Q60 滑动窗口回归", 12, False, TEXT_MAIN),
        ]
        for text, size, bold, color in lines:
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", size, QFont.Bold if bold else QFont.Normal))
            lbl.setStyleSheet(f"color: {color}; background: transparent;")
            root.addWidget(lbl)
        root.addStretch()
        btn = QPushButton("关 闭")
        btn.clicked.connect(self.accept)
        root.addWidget(btn)


# ─── Main Window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.role     = get_user_role(username)
        self.setWindowTitle(f"工业数据分析平台  |  {username}")
        self.resize(1180, 820)
        self.setMinimumSize(900, 640)
        self._build_menubar()
        self._build_central()
        self._build_statusbar()

    # ── Menu bar ───────────────────────────────────────────────────────────

    def _build_menubar(self):
        mb = self.menuBar()

        # File
        m_file = mb.addMenu("文件(&F)")
        act_exit = QAction("退出(&Q)", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

        # Account
        m_acct = mb.addMenu("账户(&A)")
        act_chpwd = QAction("修改密码…", self)
        act_chpwd.triggered.connect(self._change_pwd)
        m_acct.addAction(act_chpwd)
        if self.role == "admin":
            act_usrmgr = QAction("用户管理…", self)
            act_usrmgr.triggered.connect(self._user_mgr)
            m_acct.addAction(act_usrmgr)
        act_logout = QAction("注销登录", self)
        act_logout.triggered.connect(self._logout)
        m_acct.addAction(act_logout)

        # Help
        m_help = mb.addMenu("帮助(&H)")
        act_about = QAction("关于…", self)
        act_about.triggered.connect(lambda: AboutDialog(self).exec_())
        m_help.addAction(act_about)
        act_wf = QAction("工作流程说明…", self)
        act_wf.triggered.connect(self._show_workflow)
        m_help.addAction(act_wf)

    # ── Central widget ─────────────────────────────────────────────────────

    def _build_central(self):
        # Header strip
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #0c1228, stop:0.5 #101d42, stop:1 #0c1228);
            border-bottom: 1.5px solid {BORDER};
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)

        title_lbl = QLabel("⚙  工业数据分析平台")
        title_lbl.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {ACCENT}; background: transparent;")
        hl.addWidget(title_lbl)
        hl.addStretch()

        self.clock_lbl = QLabel("")
        self.clock_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px; background: transparent;")
        hl.addWidget(self.clock_lbl)

        user_lbl = QLabel(f"  👤 {self.username}  [{self.role}]  ")
        user_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 13px; "
            f"background: {BG_WIDGET}; border-radius: 6px; padding: 4px 10px;")
        hl.addWidget(user_lbl)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(ReadTab(),  "📂  数据读取")
        self.tabs.addTab(PreTab(),   "🔬  数据预处理")
        self.tabs.addTab(CalTab(),   "⚙️  批量计算")
        self.tabs.addTab(DataTab(),  "💾  数据管理")
        self.tabs.addTab(Q1DTab(),   "📈  Q1D 统计")
        self.tabs.addTab(Q60Tab(),   "📉  Q60 计算")

        container = QWidget()
        vl = QVBoxLayout(container)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        vl.addWidget(header)
        vl.addWidget(self.tabs)
        self.setCentralWidget(container)

        # Clock timer
        timer = QTimer(self)
        timer.timeout.connect(self._update_clock)
        timer.start(1000)
        self._update_clock()

    # ── Status bar ─────────────────────────────────────────────────────────

    def _build_statusbar(self):
        sb = QStatusBar(self)
        sb.setStyleSheet(
            f"background: {BG_MID}; color: {TEXT_DIM}; "
            f"border-top: 1px solid {BORDER}; font-size: 12px;")
        self.setStatusBar(sb)
        self.status_lbl = QLabel(
            f"就绪  |  当前用户: {self.username}  |  工作流程: Excel→d1.db→30.db→Segment_N.db→2.db→Q1D/Q60")
        sb.addWidget(self.status_lbl)

    # ── Slots ──────────────────────────────────────────────────────────────

    def _update_clock(self):
        now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        self.clock_lbl.setText(now)

    def _change_pwd(self):
        ChangePasswordDialog(self.username, self).exec_()

    def _user_mgr(self):
        UserMgrDialog(self).exec_()

    def _logout(self):
        reply = QMessageBox.question(self, "注销", "确定注销当前账号并返回登录界面？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.close()
            _restart_login()

    def _show_workflow(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("工作流程说明")
        msg.setText(
            "<b>推荐操作顺序:</b><br><br>"
            "1. <b>数据读取</b> — 批量读取 Excel 文件，生成 <code>d1.db</code><br>"
            "2. <b>数据预处理</b> — 对 d1.db 进行分段与异常检测，生成 <code>30.db</code><br>"
            "3. <b>批量计算</b> — 对 30.db 中各 Segment 表计算 Q1d/A8，"
            "生成 <code>Segment_N.db</code><br>"
            "4. <b>数据管理</b> — 选择某个 Segment_N.db，复制为 <code>2.db</code><br>"
            "5. <b>Q1D 统计</b> — 对 2.db 进行滑动统计，生成 <code>5.db</code><br>"
            "6. <b>Q60 计算</b> — 对 2.db 进行滑动窗口回归，生成 <code>20.db / 21.db</code>"
        )
        msg.setTextFormat(Qt.RichText)
        msg.exec_()


# ─── Restart helper ───────────────────────────────────────────────────────────

def _restart_login():
    dlg = LoginDialog()
    if dlg.exec_() == QDialog.Accepted:
        w = MainWindow(dlg.get_username())
        w.setStyleSheet(MAIN_STYLESHEET)
        w.show()
        # keep reference alive
        _MAIN_WINDOWS.append(w)


_MAIN_WINDOWS = []


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("工业数据分析平台")
    app.setOrganizationName("IndustrialTech")
    app.setStyleSheet(MAIN_STYLESHEET)

    dlg = LoginDialog()
    dlg.setStyleSheet(MAIN_STYLESHEET)
    if dlg.exec_() != QDialog.Accepted:
        sys.exit(0)

    username = dlg.get_username()
    window   = MainWindow(username)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
