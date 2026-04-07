"""
数据读取模块 — Excel 批量转 SQLite 数据库
Read Module: batch convert .xls files to SQLite
Ported from readweb.py
"""

import os
import sqlite3
import xlrd
from datetime import date, timedelta

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDateEdit, QProgressBar, QFileDialog, QMessageBox,
    QGroupBox, QSizePolicy, QFrame
)
from PyQt5.QtCore import QDate, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from .styles import COLORS


# ─── Core Logic ───────────────────────────────────────────────────────────────

def read_excel_file(excel_file: str, time_offset: float):
    """Read DVH (col O) and DP (col C) from an .xls file."""
    try:
        workbook = xlrd.open_workbook(excel_file)
    except Exception as e:
        raise Exception(f"无法打开文件 {excel_file}: {e}")

    sheet = workbook.sheet_by_index(0)
    data = []
    num_data_rows = sheet.nrows - 4
    for i in range(4, sheet.nrows):
        try:
            dp_value = float(sheet.cell(i, 2).value)   # C列
            dvh_value = float(sheet.cell(i, 14).value)  # O列
        except (ValueError, TypeError):
            continue
        local_index = i - 4
        time_val = time_offset + 0.5 * (local_index + 1)
        data.append((time_val, dvh_value, dp_value))
    new_offset = time_offset + 0.5 * num_data_rows
    return data, new_offset


def generate_file_names(start_date: date, end_date: date, dir_path: str):
    delta = timedelta(days=1)
    current = start_date
    file_names = []
    while current <= end_date:
        fname = (f"半小时计算数据报表2023年"
                 f"{current.month}月{current.day}日.xls")
        file_names.append(os.path.join(dir_path, fname))
        current += delta
    return file_names


def save_to_sqlite(db_file: str, data: list):
    if os.path.exists(db_file):
        os.remove(db_file)
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS data (
            time REAL,
            DVH  REAL,
            DP   REAL
        )
    """)
    c.executemany("INSERT INTO data (time, DVH, DP) VALUES (?, ?, ?)", data)
    conn.commit()
    conn.close()


# ─── Background Thread ────────────────────────────────────────────────────────

class ReadThread(QThread):
    progress_signal = pyqtSignal(int, str)      # (percent_done, msg)
    finished_signal = pyqtSignal(bool, str, int)  # (ok, msg, row_count)

    def __init__(self, files, db_file):
        super().__init__()
        self.files = files
        self.db_file = db_file

    def run(self):
        all_data = []
        time_offset = 0.0
        total = len(self.files)
        for idx, f in enumerate(self.files):
            try:
                file_data, time_offset = read_excel_file(f, time_offset)
                all_data.extend(file_data)
            except Exception as e:
                pass  # skip missing/corrupt files silently
            pct = int((idx + 1) / total * 95)
            self.progress_signal.emit(pct, f"正在读取 {idx+1}/{total}: {os.path.basename(f)}")

        if not all_data:
            self.finished_signal.emit(False, "未读取到有效数据，请检查文件路径和格式。", 0)
            return
        try:
            save_to_sqlite(self.db_file, all_data)
            self.progress_signal.emit(100, "数据写入数据库完成")
            self.finished_signal.emit(True, "", len(all_data))
        except Exception as e:
            self.finished_signal.emit(False, f"写入数据库失败: {e}", 0)


# ─── Widget ───────────────────────────────────────────────────────────────────

class ReadWidget(QWidget):
    """Excel → SQLite 读取面板"""

    status_changed = pyqtSignal(str)  # 供主窗口状态栏使用

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── 标题 ──
        title = QLabel("数据读取 — Excel 批量转 SQLite")
        title.setObjectName("lbl_title")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        sub = QLabel("将半小时计算数据报表(.xls)批量导入到 SQLite 数据库文件")
        sub.setObjectName("lbl_subtitle")
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(_hline())

        # ── 日期范围 ──
        date_group = QGroupBox("日期范围")
        date_layout = QHBoxLayout(date_group)
        date_layout.setSpacing(20)

        self.start_date = QDateEdit()
        self.start_date.setDate(QDate(2023, 4, 1))
        self.start_date.setDisplayFormat('yyyy-MM-dd')
        self.start_date.setCalendarPopup(True)

        self.end_date = QDateEdit()
        self.end_date.setDate(QDate(2023, 10, 30))
        self.end_date.setDisplayFormat('yyyy-MM-dd')
        self.end_date.setCalendarPopup(True)

        date_layout.addWidget(QLabel("开始日期:"))
        date_layout.addWidget(self.start_date)
        date_layout.addSpacing(20)
        date_layout.addWidget(QLabel("结束日期:"))
        date_layout.addWidget(self.end_date)
        date_layout.addStretch()
        root.addWidget(date_group)

        # ── 文件夹选择 ──
        dir_group = QGroupBox("Excel 文件夹")
        dir_layout = QHBoxLayout(dir_group)
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("点击右侧按钮选择包含 .xls 文件的文件夹 …")
        dir_btn = QPushButton("浏览")
        dir_btn.setFixedWidth(80)
        dir_btn.clicked.connect(self._choose_dir)
        dir_layout.addWidget(self.dir_edit)
        dir_layout.addWidget(dir_btn)
        root.addWidget(dir_group)

        # ── 输出数据库 ──
        db_group = QGroupBox("输出数据库文件")
        db_layout = QHBoxLayout(db_group)
        self.db_edit = QLineEdit("d1.db")
        self.db_edit.setPlaceholderText("输出 SQLite 文件路径，如 d1.db")
        db_btn = QPushButton("另存为")
        db_btn.setFixedWidth(80)
        db_btn.clicked.connect(self._choose_db)
        db_layout.addWidget(self.db_edit)
        db_layout.addWidget(db_btn)
        root.addWidget(db_group)

        # ── 进度 ──
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setFixedHeight(26)
        self.status_lbl = QLabel("就绪")
        self.status_lbl.setObjectName("lbl_subtitle")
        root.addWidget(self.progress)
        root.addWidget(self.status_lbl)

        # ── 操作按钮 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.run_btn = QPushButton("🚀  开始处理")
        self.run_btn.setObjectName("btn_primary")
        self.run_btn.clicked.connect(self._run)
        self.run_btn.setCursor(Qt.PointingHandCursor)

        self.reset_btn = QPushButton("↺  复位")
        self.reset_btn.setObjectName("btn_reset")
        self.reset_btn.setFixedWidth(100)
        self.reset_btn.clicked.connect(self._reset)
        self.reset_btn.setCursor(Qt.PointingHandCursor)

        btn_row.addStretch()
        btn_row.addWidget(self.reset_btn)
        btn_row.addWidget(self.run_btn)
        root.addLayout(btn_row)
        root.addStretch()

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择 Excel 文件夹", "")
        if d:
            self.dir_edit.setText(d)

    def _choose_db(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存数据库为", "d1.db",
            "SQLite 数据库 (*.db);;所有文件 (*)"
        )
        if path:
            self.db_edit.setText(path)

    def _reset(self):
        self.start_date.setDate(QDate(2023, 4, 1))
        self.end_date.setDate(QDate(2023, 10, 30))
        self.dir_edit.clear()
        self.db_edit.setText("d1.db")
        self.progress.setValue(0)
        self.status_lbl.setText("就绪")

    def _run(self):
        dir_path = self.dir_edit.text().strip()
        db_file = self.db_edit.text().strip()

        if not dir_path or not os.path.isdir(dir_path):
            QMessageBox.critical(self, "错误", "请选择有效的 Excel 文件夹！")
            return
        if not db_file:
            QMessageBox.critical(self, "错误", "请指定输出数据库文件名！")
            return

        sd = self.start_date.date()
        ed = self.end_date.date()
        if ed < sd:
            QMessageBox.critical(self, "错误", "结束日期不能早于开始日期！")
            return

        start = date(sd.year(), sd.month(), sd.day())
        end = date(ed.year(), ed.month(), ed.day())
        files = generate_file_names(start, end, dir_path)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.run_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)

        self._thread = ReadThread(files, db_file)
        self._thread.progress_signal.connect(self._on_progress)
        self._thread.finished_signal.connect(self._on_finished)
        self._thread.start()

    def _on_progress(self, pct, msg):
        self.progress.setValue(pct)
        self.status_lbl.setText(msg)
        self.status_changed.emit(msg)

    def _on_finished(self, ok, msg, row_count):
        self.run_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        if ok:
            self.progress.setValue(100)
            info = (f"数据已成功写入: {self.db_edit.text()}\n"
                    f"共导入 {row_count:,} 行数据。")
            self.status_lbl.setText(f"完成 — 共 {row_count:,} 行")
            self.status_changed.emit("读取完成")
            QMessageBox.information(self, "完成", info)
        else:
            self.status_lbl.setText("失败")
            self.status_changed.emit("读取失败")
            QMessageBox.critical(self, "处理失败", msg)


# ── helpers ───────────────────────────────────────────────────────────────────

def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f
