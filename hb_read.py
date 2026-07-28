"""hb_read.py – Tab 1: Excel batch import to SQLite."""

import os
import xlrd
import sqlite3
from datetime import date, timedelta

from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QDateEdit, QMessageBox, QProgressBar, QGroupBox
)
from PyQt5.QtCore import QDate, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont


# ─── Core logic ──────────────────────────────────────────────────────────────

def read_excel_file(excel_file, time_offset):
    try:
        workbook = xlrd.open_workbook(excel_file)
    except Exception as e:
        raise Exception(f"无法打开文件 {excel_file}: {e}")
    sheet = workbook.sheet_by_index(0)
    data = []
    num_data_rows = sheet.nrows - 4
    for i in range(4, sheet.nrows):
        dp_cell  = sheet.cell(i, 2)
        dvh_cell = sheet.cell(i, 14)
        try:
            dp_value  = float(dp_cell.value)
            dvh_value = float(dvh_cell.value)
        except (ValueError, TypeError):
            continue
        local_index = i - 4
        time_val = time_offset + 0.5 * (local_index + 1)
        data.append((time_val, dvh_value, dp_value))
    new_offset = time_offset + 0.5 * num_data_rows
    return data, new_offset


def generate_file_names(start_date, end_date, dir_path):
    delta = timedelta(days=1)
    current = start_date
    file_names = []
    while current <= end_date:
        file_name = f"半小时计算数据报表2023年{current.month}月{current.day}日.xls"
        file_names.append(os.path.join(dir_path, file_name))
        current += delta
    return file_names


def save_to_sqlite(db_file, data):
    if os.path.exists(db_file):
        os.remove(db_file)
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data (
            time REAL, DVH REAL, DP REAL
        )
    """)
    cursor.executemany("INSERT INTO data (time, DVH, DP) VALUES (?, ?, ?)", data)
    conn.commit()
    conn.close()


# ─── Background worker ────────────────────────────────────────────────────────

class ReadWorker(QThread):
    progress    = pyqtSignal(int)
    finished    = pyqtSignal(int)   # total rows
    error       = pyqtSignal(str)

    def __init__(self, files, db_file):
        super().__init__()
        self.files   = files
        self.db_file = db_file

    def run(self):
        all_data = []
        offset   = 0.0
        total    = len(self.files)
        for i, f in enumerate(self.files):
            try:
                file_data, offset = read_excel_file(f, offset)
                all_data.extend(file_data)
            except Exception as e:
                print(f"[WARN] {e}")
            self.progress.emit(i + 1)
        if not all_data:
            self.error.emit("没有读取到任何有效数据，请检查文件夹和日期范围。")
            return
        try:
            save_to_sqlite(self.db_file, all_data)
            self.finished.emit(len(all_data))
        except Exception as e:
            self.error.emit(f"保存数据库时出错：{e}")


# ─── Tab widget ───────────────────────────────────────────────────────────────

class ReadTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 16, 20, 16)

        # ── Title ──
        title = QLabel("📂  Excel 批量读取 → SQLite 数据库")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        # ── Date range ──
        grp_date = QGroupBox("日期范围")
        gl = QHBoxLayout(grp_date)
        gl.setSpacing(16)

        gl.addWidget(QLabel("开始日期:"))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate(2023, 4, 1))
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setCalendarPopup(True)
        gl.addWidget(self.start_date)

        gl.addSpacing(20)
        gl.addWidget(QLabel("结束日期:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate(2023, 10, 30))
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setCalendarPopup(True)
        gl.addWidget(self.end_date)
        gl.addStretch()
        root.addWidget(grp_date)

        # ── Source folder ──
        grp_src = QGroupBox("Excel 源文件夹")
        sl = QHBoxLayout(grp_src)
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("选择包含所有 Excel 文件的文件夹…")
        btn_dir = QPushButton("浏览")
        btn_dir.setObjectName("secondary")
        btn_dir.setFixedWidth(80)
        btn_dir.clicked.connect(self._choose_dir)
        sl.addWidget(self.dir_edit)
        sl.addWidget(btn_dir)
        root.addWidget(grp_src)

        # ── Target DB ──
        grp_db = QGroupBox("保存到 SQLite 数据库")
        dl = QHBoxLayout(grp_db)
        self.db_edit = QLineEdit("d1.db")
        self.db_edit.setPlaceholderText("如 d1.db")
        btn_db = QPushButton("另存为…")
        btn_db.setObjectName("secondary")
        btn_db.setFixedWidth(90)
        btn_db.clicked.connect(self._choose_db)
        dl.addWidget(self.db_edit)
        dl.addWidget(btn_db)
        root.addWidget(grp_db)

        # ── Progress ──
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setAlignment(Qt.AlignCenter)
        root.addWidget(self.progress)

        # ── Status label ──
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("status")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_status)

        # ── Buttons row ──
        btn_row = QHBoxLayout()
        self.btn_run = QPushButton("🚀  开始处理")
        self.btn_run.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.btn_run.clicked.connect(self._run)

        btn_reset = QPushButton("↺  复位")
        btn_reset.setObjectName("reset")
        btn_reset.clicked.connect(self._reset)

        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(btn_reset)
        root.addLayout(btn_row)
        root.addStretch()

    # ── Slots ──────────────────────────────────────────────────────────────

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择 Excel 文件夹", "")
        if d:
            self.dir_edit.setText(d)

    def _choose_db(self):
        p, _ = QFileDialog.getSaveFileName(self, "保存数据库", "d1.db",
                                           "SQLite DB (*.db);;所有文件 (*)")
        if p:
            self.db_edit.setText(p)

    def _reset(self):
        self.start_date.setDate(QDate(2023, 4, 1))
        self.end_date.setDate(QDate(2023, 10, 30))
        self.dir_edit.clear()
        self.db_edit.setText("d1.db")
        self.progress.setValue(0)
        self.lbl_status.setText("已复位")

    def _run(self):
        dir_path = self.dir_edit.text().strip()
        db_file  = self.db_edit.text().strip()
        if not dir_path or not os.path.isdir(dir_path):
            QMessageBox.critical(self, "错误", "请选择有效的 Excel 文件夹！")
            return
        if not db_file:
            QMessageBox.critical(self, "错误", "请输入数据库文件名！")
            return
        s = self.start_date.date()
        e = self.end_date.date()
        if e < s:
            QMessageBox.critical(self, "错误", "结束日期不能早于开始日期！")
            return

        start = date(s.year(), s.month(), s.day())
        end   = date(e.year(), e.month(), e.day())
        files = generate_file_names(start, end, dir_path)

        self.progress.setMaximum(len(files))
        self.progress.setValue(0)
        self.lbl_status.setText(f"正在处理 0 / {len(files)} 个文件…")
        self.btn_run.setEnabled(False)

        self._worker = ReadWorker(files, db_file)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, n):
        self.progress.setValue(n)
        total = self.progress.maximum()
        self.lbl_status.setText(f"正在处理 {n} / {total} 个文件…")

    def _on_finished(self, rows):
        self.btn_run.setEnabled(True)
        self.lbl_status.setText(f"✅ 完成！共写入 {rows} 行数据。")
        QMessageBox.information(self, "完成",
            f"所有数据已保存到 {self.db_edit.text()}\n共 {rows} 行。")

    def _on_error(self, msg):
        self.btn_run.setEnabled(True)
        self.lbl_status.setText("❌ 出错")
        QMessageBox.critical(self, "错误", msg)
