#!/usr/bin/env python3
"""
hebing.py — 数据处理与分析集成平台
主程序入口：登录 → 侧边栏导航 → 各功能模块
"""

import sys
import os
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QStackedWidget, QFrame,
    QMessageBox, QDialog, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSizePolicy, QScrollArea,
    QFileDialog, QSplitter, QAction, QMenu, QMenuBar, QStatusBar,
    QComboBox, QCheckBox, QSpinBox, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPainter, QColor, QLinearGradient

from modules.styles import MAIN_STYLESHEET, LOGIN_STYLESHEET, COLORS
from modules.auth import UserDatabase
from modules.read_module import ReadWidget
from modules.pre_module import PreWidget
from modules.cal_module import CalWidget
from modules.data_module import DataWidget
from modules.q1d_module import Q1DWidget
from modules.q60_module import Q60Widget


APP_NAME = "数据处理与分析集成平台"
APP_VERSION = "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# 登录窗口
# ═══════════════════════════════════════════════════════════════════════════════

class LoginWindow(QWidget):
    login_success = pyqtSignal(dict)  # user_info

    def __init__(self, user_db: UserDatabase):
        super().__init__()
        self.user_db = user_db
        self.setWindowTitle(f"{APP_NAME} — 登录")
        self.setFixedSize(420, 520)
        self.setStyleSheet(LOGIN_STYLESHEET)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 40, 50, 40)
        layout.setSpacing(16)

        # 标题区
        layout.addSpacing(10)
        icon_lbl = QLabel("⬡")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 48px; color: #00a8ff;")
        layout.addWidget(icon_lbl)

        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #00d4ff;")
        layout.addWidget(title)

        ver = QLabel(f"v{APP_VERSION}")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("font-size: 11px; color: #4a6a8a;")
        layout.addWidget(ver)
        layout.addSpacing(24)

        # 用户名
        u_lbl = QLabel("用户名")
        u_lbl.setStyleSheet("color: #7a9ab8; font-size: 12px;")
        layout.addWidget(u_lbl)
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("请输入用户名")
        self.user_input.setText("admin")
        layout.addWidget(self.user_input)

        # 密码
        p_lbl = QLabel("密码")
        p_lbl.setStyleSheet("color: #7a9ab8; font-size: 12px;")
        layout.addWidget(p_lbl)
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("请输入密码")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setText("admin123")
        layout.addWidget(self.pass_input)
        layout.addSpacing(8)

        # 登录按钮
        self.login_btn = QPushButton("登  录")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self._do_login)
        layout.addWidget(self.login_btn)

        # 注册按钮
        self.reg_btn = QPushButton("注册新账户")
        self.reg_btn.setObjectName("btn_register")
        self.reg_btn.setCursor(Qt.PointingHandCursor)
        self.reg_btn.clicked.connect(self._show_register)
        layout.addWidget(self.reg_btn)

        layout.addStretch()

        # 底部信息
        foot = QLabel("默认管理员: admin / admin123")
        foot.setAlignment(Qt.AlignCenter)
        foot.setStyleSheet("color: #2a4a6a; font-size: 10px;")
        layout.addWidget(foot)

        # 回车登录
        self.pass_input.returnPressed.connect(self._do_login)
        self.user_input.returnPressed.connect(lambda: self.pass_input.setFocus())

    def _do_login(self):
        u = self.user_input.text().strip()
        p = self.pass_input.text()
        if not u or not p:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return
        ok, info = self.user_db.verify_user(u, p)
        if ok:
            self.login_success.emit(info)
        else:
            err = info.get('error', '用户名或密码错误') if info else '用户名或密码错误'
            QMessageBox.critical(self, "登录失败", err)

    def _show_register(self):
        dlg = RegisterDialog(self.user_db, self)
        dlg.exec_()


# ═══════════════════════════════════════════════════════════════════════════════
# 注册对话框
# ═══════════════════════════════════════════════════════════════════════════════

class RegisterDialog(QDialog):
    def __init__(self, user_db, parent=None):
        super().__init__(parent)
        self.user_db = user_db
        self.setWindowTitle("注册新账户")
        self.setFixedSize(360, 300)
        self.setStyleSheet(MAIN_STYLESHEET)
        self._build()

    def _build(self):
        layout = QFormLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        self.u_edit = QLineEdit()
        self.u_edit.setPlaceholderText("至少 3 个字符，字母/数字/下划线")
        layout.addRow("用户名:", self.u_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("可选，显示用名称")
        layout.addRow("显示名:", self.name_edit)

        self.p_edit = QLineEdit()
        self.p_edit.setEchoMode(QLineEdit.Password)
        self.p_edit.setPlaceholderText("至少 6 个字符")
        layout.addRow("密码:", self.p_edit)

        self.p2_edit = QLineEdit()
        self.p2_edit.setEchoMode(QLineEdit.Password)
        self.p2_edit.setPlaceholderText("再次输入密码")
        layout.addRow("确认密码:", self.p2_edit)

        btn = QPushButton("注册")
        btn.setObjectName("btn_primary")
        btn.clicked.connect(self._do_reg)
        layout.addRow("", btn)

    def _do_reg(self):
        u = self.u_edit.text().strip()
        n = self.name_edit.text().strip()
        p1 = self.p_edit.text()
        p2 = self.p2_edit.text()
        if p1 != p2:
            QMessageBox.warning(self, "提示", "两次密码不一致")
            return
        ok, msg = self.user_db.create_user(u, p1, 'user', n)
        if ok:
            QMessageBox.information(self, "成功", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "注册失败", msg)


# ═══════════════════════════════════════════════════════════════════════════════
# 修改密码对话框
# ═══════════════════════════════════════════════════════════════════════════════

class ChangePasswordDialog(QDialog):
    def __init__(self, user_db, username, parent=None):
        super().__init__(parent)
        self.user_db = user_db
        self.username = username
        self.setWindowTitle("修改密码")
        self.setFixedSize(360, 260)
        self.setStyleSheet(MAIN_STYLESHEET)
        layout = QFormLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        self.old_edit = QLineEdit()
        self.old_edit.setEchoMode(QLineEdit.Password)
        layout.addRow("原密码:", self.old_edit)

        self.new_edit = QLineEdit()
        self.new_edit.setEchoMode(QLineEdit.Password)
        layout.addRow("新密码:", self.new_edit)

        self.new2_edit = QLineEdit()
        self.new2_edit.setEchoMode(QLineEdit.Password)
        layout.addRow("确认新密码:", self.new2_edit)

        btn = QPushButton("修改")
        btn.setObjectName("btn_primary")
        btn.clicked.connect(self._do_change)
        layout.addRow("", btn)

    def _do_change(self):
        if self.new_edit.text() != self.new2_edit.text():
            QMessageBox.warning(self, "提示", "两次密码不一致")
            return
        ok, msg = self.user_db.change_password(
            self.username, self.old_edit.text(), self.new_edit.text()
        )
        if ok:
            QMessageBox.information(self, "成功", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "失败", msg)


# ═══════════════════════════════════════════════════════════════════════════════
# 用户管理面板（管理员可见）
# ═══════════════════════════════════════════════════════════════════════════════

class UserManagementWidget(QWidget):
    def __init__(self, user_db: UserDatabase, parent=None):
        super().__init__(parent)
        self.user_db = user_db
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("用户管理")
        title.setObjectName("lbl_title")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        sub = QLabel("查看、添加、禁用或删除系统用户")
        sub.setObjectName("lbl_subtitle")
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(_hline())

        # 用户表
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["用户名", "角色", "显示名", "创建时间", "最近登录", "状态"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, stretch=1)

        # 操作按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        refresh_btn = QPushButton("刷新列表")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(refresh_btn)

        add_btn = QPushButton("添加用户")
        add_btn.setObjectName("btn_success")
        add_btn.clicked.connect(self._add_user)
        btn_row.addWidget(add_btn)

        toggle_btn = QPushButton("启用/禁用")
        toggle_btn.clicked.connect(self._toggle)
        btn_row.addWidget(toggle_btn)

        reset_btn = QPushButton("重置密码")
        reset_btn.clicked.connect(self._reset_pwd)
        btn_row.addWidget(reset_btn)

        del_btn = QPushButton("删除用户")
        del_btn.setObjectName("btn_danger")
        del_btn.clicked.connect(self._delete)
        btn_row.addWidget(del_btn)

        btn_row.addStretch()
        root.addLayout(btn_row)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self):
        users = self.user_db.list_users()
        self.table.setRowCount(0)
        for u in users:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(u['username']))
            self.table.setItem(r, 1, QTableWidgetItem(u['role']))
            self.table.setItem(r, 2, QTableWidgetItem(u.get('display_name', '')))
            self.table.setItem(r, 3, QTableWidgetItem(u.get('created_at', '') or ''))
            self.table.setItem(r, 4, QTableWidgetItem(u.get('last_login', '') or ''))
            status = "启用" if u.get('is_active') else "禁用"
            item = QTableWidgetItem(status)
            item.setForeground(
                QColor(COLORS['accent_green'] if u.get('is_active') else COLORS['accent_red'])
            )
            self.table.setItem(r, 5, item)

    def _selected_username(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "提示", "请先选择一个用户")
            return None
        return self.table.item(rows[0].row(), 0).text()

    def _add_user(self):
        dlg = RegisterDialog(self.user_db, self)
        if dlg.exec_() == QDialog.Accepted:
            self.refresh()

    def _toggle(self):
        u = self._selected_username()
        if not u:
            return
        # Check current status
        users = self.user_db.list_users()
        current = next((x for x in users if x['username'] == u), None)
        if not current:
            return
        new_active = not current.get('is_active', True)
        ok, msg = self.user_db.set_user_active(u, new_active)
        QMessageBox.information(self, "结果", msg)
        self.refresh()

    def _reset_pwd(self):
        u = self._selected_username()
        if not u:
            return
        ok, msg = self.user_db.admin_reset_password(u, "123456")
        if ok:
            QMessageBox.information(self, "成功", f"{msg}\n新密码: 123456")
        else:
            QMessageBox.critical(self, "失败", msg)

    def _delete(self):
        u = self._selected_username()
        if not u:
            return
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除用户 '{u}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = self.user_db.delete_user(u)
            QMessageBox.information(self, "结果", msg)
            self.refresh()


# ═══════════════════════════════════════════════════════════════════════════════
# 操作日志面板
# ═══════════════════════════════════════════════════════════════════════════════

class ActivityLogWidget(QWidget):
    def __init__(self, user_db: UserDatabase, parent=None):
        super().__init__(parent)
        self.user_db = user_db
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("操作日志")
        title.setObjectName("lbl_title")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        sub = QLabel("系统操作记录，含登录、用户管理等事件")
        sub.setObjectName("lbl_subtitle")
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(_hline())

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["时间", "用户", "操作", "详情"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        root.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh)
        export_btn = QPushButton("导出日志")
        export_btn.setObjectName("btn_success")
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self):
        logs = self.user_db.get_activity_log(500)
        self.table.setRowCount(0)
        for log in logs:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(log.get('timestamp', '')))
            self.table.setItem(r, 1, QTableWidgetItem(log.get('username', '')))
            self.table.setItem(r, 2, QTableWidgetItem(log.get('action', '')))
            self.table.setItem(r, 3, QTableWidgetItem(log.get('detail', '')))

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "activity_log.csv",
            "CSV 文件 (*.csv);;所有文件 (*)"
        )
        if not path:
            return
        try:
            logs = self.user_db.get_activity_log(10000)
            with open(path, 'w', encoding='utf-8-sig') as f:
                f.write("时间,用户,操作,详情\n")
                for log in logs:
                    vals = [log.get('timestamp', ''), log.get('username', ''),
                            log.get('action', ''), log.get('detail', '')]
                    line = ','.join(f'"{v}"' for v in vals)
                    f.write(line + '\n')
            QMessageBox.information(self, "成功", f"日志已导出至:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 关于对话框
# ═══════════════════════════════════════════════════════════════════════════════

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self.setFixedSize(380, 280)
        self.setStyleSheet(MAIN_STYLESHEET)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignCenter)

        icon = QLabel("⬡")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 40px; color: #00a8ff;")
        layout.addWidget(icon)

        t = QLabel(APP_NAME)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-size: 16px; font-weight: bold; color: #00d4ff;")
        layout.addWidget(t)

        v = QLabel(f"版本 {APP_VERSION}")
        v.setAlignment(Qt.AlignCenter)
        v.setStyleSheet("color: #7a9ab8;")
        layout.addWidget(v)

        desc = QLabel(
            "集成 Excel 数据读取、异常检测与分段、\n"
            "Q1d/A8 统计计算、Q1D 滑动窗口分析、\n"
            "Q60 线性回归等完整数据处理流程。\n\n"
            "深蓝科技风 GUI · PyQt5"
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #7a9ab8; font-size: 12px;")
        layout.addWidget(desc)

        btn = QPushButton("确定")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignCenter)


# ═══════════════════════════════════════════════════════════════════════════════
# 侧边栏按钮
# ═══════════════════════════════════════════════════════════════════════════════

class SidebarButton(QPushButton):
    def __init__(self, text, icon_char="", parent=None):
        display = f" {icon_char}  {text}" if icon_char else f"  {text}"
        super().__init__(display, parent)
        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #7a9ab8;
                border: none;
                border-left: 3px solid transparent;
                text-align: left;
                padding-left: 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0a1830;
                color: #b0d0f0;
            }
            QPushButton:checked {
                background-color: #0a1e48;
                color: #00d4ff;
                border-left: 3px solid #00a8ff;
            }
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# 主窗口
# ═══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self, user_db: UserDatabase, user_info: dict):
        super().__init__()
        self.user_db = user_db
        self.user_info = user_info
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1100, 720)
        self.resize(1280, 820)
        self.setStyleSheet(MAIN_STYLESHEET)

        self._build_menubar()
        self._build_central()
        self._build_statusbar()

        # 记录登录日志
        self.user_db.log_action(user_info['username'], 'open_app', '')

    # ── Menu Bar ──────────────────────────────────────────────────────────────

    def _build_menubar(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("文件(&F)")
        file_menu.addAction("关于(&A)", lambda: AboutDialog(self).exec_())
        file_menu.addSeparator()
        file_menu.addAction("退出(&Q)", self.close)

        user_menu = mb.addMenu("账户(&U)")
        user_menu.addAction("修改密码", self._change_pwd)
        user_menu.addAction("注销并重新登录", self._logout)

    # ── Central Widget ────────────────────────────────────────────────────────

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # ── 侧边栏 ──
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(f"background-color: {COLORS['sidebar_bg']};")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        # 侧边栏顶部标题
        header = QLabel(f"  ⬡  {APP_NAME[:6]}")
        header.setFixedHeight(52)
        header.setStyleSheet(
            f"background-color: {COLORS['header_bg']}; "
            f"color: #00d4ff; font-size: 15px; font-weight: bold; "
            f"padding-left: 8px; border-bottom: 1px solid #1a2d5a;"
        )
        sb_layout.addWidget(header)

        # 用户信息
        display_name = self.user_info.get('display_name', self.user_info['username'])
        role_label = "管理员" if self.user_info.get('role') == 'admin' else "用户"
        user_lbl = QLabel(f"  {display_name} ({role_label})")
        user_lbl.setFixedHeight(36)
        user_lbl.setStyleSheet(
            "color: #4a8ab0; font-size: 11px; padding-left: 18px; "
            "border-bottom: 1px solid #0a1830;"
        )
        sb_layout.addWidget(user_lbl)

        # 导航按钮定义: (名称, 图标字符, Widget类或类名)
        self.nav_items = [
            ("数据读取",   "◈", ReadWidget),
            ("数据预处理", "◇", PreWidget),
            ("批量计算",   "◆", CalWidget),
            ("数据管理",   "◫", DataWidget),
            ("Q1D 分析",   "△", Q1DWidget),
            ("Q60 回归",   "▽", Q60Widget),
        ]
        if self.user_info.get('role') == 'admin':
            self.nav_items.append(("用户管理", "☷", "UserMgmt"))
        self.nav_items.append(("操作日志", "☰", "ActivityLog"))

        self.nav_buttons = []
        self.stack = QStackedWidget()

        sep_lbl = QLabel("  功能模块")
        sep_lbl.setFixedHeight(32)
        sep_lbl.setStyleSheet(
            "color: #2a4a6a; font-size: 10px; padding-left: 18px; "
            "padding-top: 8px; font-weight: bold;"
        )
        sb_layout.addWidget(sep_lbl)

        for idx, (name, icon, widget_cls) in enumerate(self.nav_items):
            btn = SidebarButton(name, icon)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

            # 创建对应的页面 widget
            if widget_cls == "UserMgmt":
                w = UserManagementWidget(self.user_db)
            elif widget_cls == "ActivityLog":
                w = ActivityLogWidget(self.user_db)
            else:
                w = widget_cls()
                # 连接 status_changed 信号
                if hasattr(w, 'status_changed'):
                    w.status_changed.connect(self._on_module_status)

            # 包装到滚动区域
            scroll = QScrollArea()
            scroll.setWidget(w)
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border: none; }")
            self.stack.addWidget(scroll)

        sb_layout.addStretch()

        # 侧边栏底部注销按钮
        logout_btn = QPushButton("  ⏻  注销")
        logout_btn.setFixedHeight(40)
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #5a3a3a;
                border: none; border-top: 1px solid #1a1020;
                text-align: left; padding-left: 18px;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1a0a10; color: #ff6080; }
        """)
        logout_btn.clicked.connect(self._logout)
        sb_layout.addWidget(logout_btn)

        h_layout.addWidget(sidebar)
        h_layout.addWidget(self.stack, stretch=1)

        # 默认选中第一页
        self._switch_page(0)

    # ── Status Bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        sb = self.statusBar()
        self.status_msg = QLabel("就绪")
        sb.addWidget(self.status_msg, stretch=1)
        self.time_label = QLabel()
        sb.addPermanentWidget(self.time_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_time)
        self._timer.start(1000)
        self._update_time()

    def _update_time(self):
        self.time_label.setText(datetime.now().strftime("  %Y-%m-%d %H:%M:%S  "))

    # ── Navigation ────────────────────────────────────────────────────────────

    def _switch_page(self, index):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)
        name = self.nav_items[index][0]
        self.status_msg.setText(f"当前模块: {name}")

    def _on_module_status(self, msg):
        self.status_msg.setText(msg)

    # ── Account Actions ───────────────────────────────────────────────────────

    def _change_pwd(self):
        dlg = ChangePasswordDialog(self.user_db, self.user_info['username'], self)
        dlg.exec_()

    def _logout(self):
        reply = QMessageBox.question(
            self, "确认注销", "确定要注销当前用户并返回登录界面吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.user_db.log_action(self.user_info['username'], 'logout', '')
            self.close()
            # 重新显示登录窗口
            start_app(self.user_db)


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════

def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


# ═══════════════════════════════════════════════════════════════════════════════
# 应用启动
# ═══════════════════════════════════════════════════════════════════════════════

_main_window = None  # 保持引用防止 GC


def start_app(user_db: UserDatabase = None):
    """显示登录窗口，登录成功后打开主窗口。"""
    global _main_window

    if user_db is None:
        user_db = UserDatabase()

    login_win = LoginWindow(user_db)

    def on_login(user_info):
        global _main_window
        login_win.close()
        _main_window = MainWindow(user_db, user_info)
        _main_window.show()

    login_win.login_success.connect(on_login)
    login_win.show()


def main():
    # 确保工作目录为脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei", 10))

    user_db = UserDatabase()
    start_app(user_db)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
