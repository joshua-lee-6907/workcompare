"""
批量计算模块 — 对各分段数据进行滑动窗口统计计算
Calculation Module: sliding-window Q1d / A8 metric computation
Ported from calweb.py
"""

import os
import sqlite3
import numpy as np
import pandas as pd

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QFileDialog, QMessageBox, QGroupBox, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from .styles import COLORS


# ─── Core Logic (identical to calweb.py) ──────────────────────────────────────

def calculate_Q1d_A82(dvh1, time1, dp1):
    window_size = len(dvh1)
    BeforeSize = len(time1)

    if len(time1) < 2:
        return [0, window_size, np.nan, np.nan, np.nan]

    P = np.polyfit(time1, dvh1, 1)
    Q1d = P[0]
    b_array = P[1]

    disti = np.abs((Q1d * time1 - dvh1 + b_array) / np.sqrt(Q1d**2 + 1))
    tempavg = np.sum(disti) / (window_size + 1)
    Wi = np.abs(disti - tempavg)
    temperr = np.sqrt(np.sum((disti - tempavg)**2 / window_size))
    idx_outliers = np.where(Wi > 5 * temperr)[0]

    time1_clean = np.delete(time1, idx_outliers)
    dvh1_clean = np.delete(dvh1, idx_outliers)
    dp1_clean = np.delete(dp1, idx_outliers)
    AfterSize = len(time1_clean)
    num_removed = BeforeSize - AfterSize

    if len(time1_clean) >= 2:
        P = np.polyfit(time1_clean, dvh1_clean, 1)
        Q1d = P[0]
        b_array = P[1]
    else:
        Q1d = np.nan
        b_array = np.nan

    N = len(dvh1_clean)
    A0 = np.sum(time1_clean)
    A1 = np.sum(dvh1_clean)
    A2 = np.dot(time1_clean, dvh1_clean)
    A3 = np.dot(time1_clean, time1_clean)
    A4 = np.dot(dvh1_clean, dvh1_clean)

    if N >= 3 and (N * A3 - A0**2) != 0 and (A3 - (A0**2) / N) != 0:
        A5 = (A1 * A3 - A0 * A2) / (N * A3 - A0**2)
        A7 = (A2 - A1 * A0 / N) / (A3 - A0**2 / N)
        A6 = np.sqrt((A4 - A5 * A1 - A7 * A2) / (N - 2))
    else:
        A6 = np.nan

    if num_removed == 0:
        timen = time1_clean[-1] if len(time1_clean) > 0 else 0
        t0 = time1_clean[0] if len(time1_clean) > 0 else 0
        Iins = 0.5
        denom = (timen - t0) ** 2
        A8 = np.sqrt((Iins / 100) ** 2 + 36 * A6 / denom) if denom != 0 else np.nan
    else:
        timen = (window_size - num_removed) / 2
        t0 = 0
        Iins = 0.5
        denom = (timen - t0) ** 2
        A8 = np.sqrt((Iins / 100) ** 2 + 36 * A6 / denom) if denom != 0 else np.nan

    dp_mean = np.mean(dp1_clean) if len(dp1_clean) > 0 else np.nan
    return [0, window_size, Q1d, A8, dp_mean]


def calculate_table(db_path: str, table_name: str):
    conn = sqlite3.connect(db_path)
    total_df = pd.read_sql_query(f"SELECT COUNT(*) AS total FROM {table_name}", conn)
    total_rows = int(total_df['total'].iloc[0]) if not total_df.empty else 0
    if total_rows == 0:
        conn.close()
        return []

    columns = pd.read_sql_query(f"PRAGMA table_info({table_name})", conn)
    conn.close()

    dvh_col = next((c for c in columns['name'] if 'DVH' in c), None)
    time_col = next((c for c in columns['name'] if 'time' in c), None)
    dp_col = next((c for c in columns['name'] if 'DP' in c), None)
    if not (dvh_col and time_col and dp_col):
        return []

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        f"SELECT {dvh_col}, {time_col}, {dp_col} FROM {table_name} "
        f"WHERE rowid BETWEEN 1 AND {total_rows}",
        conn
    )
    conn.close()

    W0 = 48
    results = []
    for window_size in range(13, W0 + 1):
        for start in range(len(df) - window_size + 1):
            dvh = df[dvh_col].iloc[start:start + window_size].to_numpy()
            tim = df[time_col].iloc[start:start + window_size].to_numpy()
            dp = df[dp_col].iloc[start:start + window_size].to_numpy()
            r = calculate_Q1d_A82(dvh, tim, dp)
            results.append((start, start + window_size - 1, r[2], r[3], r[4]))
    return results


def save_results_to_db(results, table_name: str, out_dir: str = '.'):
    db_filename = os.path.join(out_dir, f"{table_name}.db")
    conn = sqlite3.connect(db_filename)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS results (
            start_index INTEGER,
            end_index   INTEGER,
            Q1d         REAL,
            A8          REAL,
            dp_mean     REAL
        )
    """)
    c.executemany(
        "INSERT INTO results (start_index, end_index, Q1d, A8, dp_mean) VALUES (?,?,?,?,?)",
        results
    )
    conn.commit()
    conn.close()
    return db_filename


# ─── Background Thread ────────────────────────────────────────────────────────

class CalThread(QThread):
    progress_signal = pyqtSignal(int, str)   # (percent, msg)
    table_done_signal = pyqtSignal(str, str, int)  # (table_name, db_file, row_count)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, db_path: str, out_dir: str):
        super().__init__()
        self.db_path = db_path
        self.out_dir = out_dir

    def run(self):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall() if r[0].startswith("Segment_")]
            conn.close()

            if not tables:
                self.finished_signal.emit(False, "未找到 Segment_ 开头的表")
                return

            total = len(tables)
            for idx, tname in enumerate(tables):
                self.progress_signal.emit(
                    int(idx / total * 100),
                    f"正在计算 {tname} ({idx+1}/{total}) …"
                )
                results = calculate_table(self.db_path, tname)
                out_file = save_results_to_db(results, tname, self.out_dir)
                self.table_done_signal.emit(tname, out_file, len(results))

            self.progress_signal.emit(100, "全部计算完成")
            self.finished_signal.emit(True, f"已处理 {total} 个分段表")
        except Exception as e:
            self.finished_signal.emit(False, str(e))


# ─── Widget ───────────────────────────────────────────────────────────────────

class CalWidget(QWidget):
    """批量计算面板"""

    status_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._results_log = []
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # 标题
        title = QLabel("批量计算 — Q1d / A8 滑动窗口计算")
        title.setObjectName("lbl_title")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        sub = QLabel("对各分段表执行窗口大小 13~48 的滑动回归计算，结果保存为独立 .db 文件")
        sub.setObjectName("lbl_subtitle")
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(_hline())

        # 数据库选择
        db_group = QGroupBox("数据库配置")
        db_layout = QVBoxLayout(db_group)

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("源数据库 (含 Segment_ 表):"))
        self.src_edit = QLineEdit("30.db")
        src_btn = QPushButton("浏览")
        src_btn.setFixedWidth(80)
        src_btn.clicked.connect(self._choose_src)
        src_row.addWidget(self.src_edit)
        src_row.addWidget(src_btn)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("结果输出目录:"))
        self.out_edit = QLineEdit(".")
        out_btn = QPushButton("选择")
        out_btn.setFixedWidth(80)
        out_btn.clicked.connect(self._choose_out)
        out_row.addWidget(self.out_edit)
        out_row.addWidget(out_btn)

        db_layout.addLayout(src_row)
        db_layout.addLayout(out_row)
        root.addWidget(db_group)

        # 进度
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(26)
        self.status_lbl = QLabel("就绪")
        self.status_lbl.setObjectName("lbl_subtitle")
        root.addWidget(self.progress)
        root.addWidget(self.status_lbl)

        # 结果日志表
        log_group = QGroupBox("计算结果日志")
        log_layout = QVBoxLayout(log_group)
        self.log_table = QTableWidget(0, 3)
        self.log_table.setHorizontalHeaderLabels(["分段表", "输出文件", "行数"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setFixedHeight(200)
        log_layout.addWidget(self.log_table)
        root.addWidget(log_group)

        # 操作按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.run_btn = QPushButton("🚀  开始批量计算")
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

    def _choose_src(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "选择源数据库", "", "SQLite 数据库 (*.db);;所有文件 (*)"
        )
        if p:
            self.src_edit.setText(p)

    def _choose_out(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", ".")
        if d:
            self.out_edit.setText(d)

    def _reset(self):
        self.src_edit.setText("30.db")
        self.out_edit.setText(".")
        self.progress.setValue(0)
        self.status_lbl.setText("就绪")
        self.log_table.setRowCount(0)
        self._results_log.clear()

    def _run(self):
        src = self.src_edit.text().strip()
        out_dir = self.out_edit.text().strip() or '.'
        if not os.path.exists(src):
            QMessageBox.critical(self, "错误", f"源数据库不存在:\n{src}")
            return
        if not os.path.isdir(out_dir):
            QMessageBox.critical(self, "错误", f"输出目录不存在:\n{out_dir}")
            return

        self.run_btn.setEnabled(False)
        self.log_table.setRowCount(0)
        self._results_log.clear()
        self.progress.setValue(0)
        self.status_lbl.setText("处理中 …")

        self._thread = CalThread(src, out_dir)
        self._thread.progress_signal.connect(self._on_progress)
        self._thread.table_done_signal.connect(self._on_table_done)
        self._thread.finished_signal.connect(self._on_finished)
        self._thread.start()

    def _on_progress(self, pct, msg):
        self.progress.setValue(pct)
        self.status_lbl.setText(msg)
        self.status_changed.emit(msg)

    def _on_table_done(self, table_name, db_file, row_count):
        row = self.log_table.rowCount()
        self.log_table.insertRow(row)
        self.log_table.setItem(row, 0, QTableWidgetItem(table_name))
        self.log_table.setItem(row, 1, QTableWidgetItem(db_file))
        self.log_table.setItem(row, 2, QTableWidgetItem(str(row_count)))
        self.log_table.scrollToBottom()

    def _on_finished(self, ok, msg):
        self.run_btn.setEnabled(True)
        if ok:
            self.progress.setValue(100)
            self.status_lbl.setText("计算完成")
            self.status_changed.emit("批量计算完成")
            QMessageBox.information(self, "完成", msg)
        else:
            self.status_lbl.setText("失败")
            self.status_changed.emit("批量计算失败")
            QMessageBox.critical(self, "计算失败", msg)


def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f
