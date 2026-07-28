"""hb_cal.py – Tab 3: Batch calculation on Segment tables."""

import os
import sqlite3
import numpy as np
import pandas as pd

from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QProgressBar, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont


# ─── Core logic ──────────────────────────────────────────────────────────────

def calculate_Q1d_A82(dvh1, time1, dp1):
    window_size = len(dvh1)
    if len(time1) < 2:
        Q1d, b_array = np.nan, np.nan
    else:
        P = np.polyfit(time1, dvh1, 1)
        Q1d, b_array = P[0], P[1]

    disti = np.abs((Q1d * time1 - dvh1 + b_array) / np.sqrt(Q1d**2 + 1))
    tempavg = np.sum(disti) / (window_size + 1)
    Wi = np.abs(disti - tempavg)
    temperr = np.sqrt(np.sum((disti - tempavg)**2 / window_size))
    idx_out = np.where(Wi > 5 * temperr)[0]

    time1_c = np.delete(time1, idx_out)
    dvh1_c  = np.delete(dvh1, idx_out)
    dp1_c   = np.delete(dp1, idx_out)
    num_removed = len(time1) - len(time1_c)

    if len(time1_c) >= 2:
        P = np.polyfit(time1_c, dvh1_c, 1)
        Q1d, b_array = P[0], P[1]
    else:
        Q1d, b_array = np.nan, np.nan

    N  = len(dvh1_c)
    A0 = np.sum(time1_c)
    A1 = np.sum(dvh1_c)
    A2 = np.dot(time1_c, dvh1_c)
    A3 = np.dot(time1_c, time1_c)
    A4 = np.dot(dvh1_c, dvh1_c)

    if N >= 3 and (N * A3 - A0**2) != 0 and (A3 - A0**2 / N) != 0:
        A5 = (A1 * A3 - A0 * A2) / (N * A3 - A0**2)
        A7 = (A2 - A1 * A0 / N) / (A3 - A0**2 / N)
        A6 = np.sqrt((A4 - A5 * A1 - A7 * A2) / (N - 2))
    else:
        A6 = np.nan

    if num_removed == 0:
        timen = time1_c[-1] if len(time1_c) > 0 else 0
        t0    = time1_c[0]  if len(time1_c) > 0 else 0
        denom = (timen - t0) ** 2
        A8 = np.sqrt((0.5 / 100)**2 + 36 * A6 / denom) if denom != 0 else np.nan
    else:
        timen = (window_size - num_removed) / 2
        denom = timen**2
        A8 = np.sqrt((0.5 / 100)**2 + 36 * A6 / denom) if denom != 0 else np.nan

    dp_mean = np.mean(dp1_c) if len(dp1_c) > 0 else np.nan
    return [0, window_size, Q1d, A8, dp_mean]


def process_table(db_path, table_name):
    conn = sqlite3.connect(db_path)
    total_df = pd.read_sql_query(f"SELECT COUNT(*) as total FROM {table_name}", conn)
    if total_df.empty or total_df["total"].iloc[0] == 0:
        conn.close()
        return []
    cols = pd.read_sql_query(f"PRAGMA table_info({table_name})", conn)
    conn.close()

    dvh_col  = [c for c in cols["name"] if "DVH"  in c]
    time_col = [c for c in cols["name"] if "time" in c]
    dp_col   = [c for c in cols["name"] if "DP"   in c]
    if not dvh_col or not time_col or not dp_col:
        return []

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        f"SELECT {dvh_col[0]}, {time_col[0]}, {dp_col[0]} FROM {table_name}", conn)
    conn.close()

    w0, results = 48, []
    for ws in range(13, w0 + 1):
        for start in range(len(df) - ws + 1):
            dvh_w = df[dvh_col[0]].iloc[start:start+ws].to_numpy()
            t_w   = df[time_col[0]].iloc[start:start+ws].to_numpy()
            dp_w  = df[dp_col[0]].iloc[start:start+ws].to_numpy()
            r = calculate_Q1d_A82(dvh_w, t_w, dp_w)
            results.append((start, start + ws - 1, r[2], r[3], r[4]))
    return results


def save_results(results, table_name):
    fname = f"{table_name}.db"
    conn  = sqlite3.connect(fname)
    cur   = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS results
        (start_index INTEGER, end_index INTEGER,
         Q1d REAL, A8 REAL, dp_mean REAL)""")
    cur.executemany(
        "INSERT INTO results VALUES (?,?,?,?,?)", results)
    conn.commit()
    conn.close()


# ─── Background worker ────────────────────────────────────────────────────────

class CalWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, db_path, tables):
        super().__init__()
        self.db_path = db_path
        self.tables  = tables

    def run(self):
        for i, tname in enumerate(self.tables):
            self.progress.emit(i, f"正在计算 {tname} …")
            try:
                results = process_table(self.db_path, tname)
                save_results(results, tname)
            except Exception as e:
                self.error.emit(f"处理 {tname} 出错：{e}")
                return
        self.finished.emit()


# ─── Tab widget ───────────────────────────────────────────────────────────────

class CalTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 16, 20, 16)

        title = QLabel("⚙️  分段表批量计算")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        grp = QGroupBox("源数据库 (30.db)")
        gl = QHBoxLayout(grp)
        self.db_edit = QLineEdit("30.db")
        btn_db = QPushButton("浏览")
        btn_db.setObjectName("secondary")
        btn_db.setFixedWidth(70)
        btn_db.clicked.connect(self._choose_db)
        gl.addWidget(self.db_edit)
        gl.addWidget(btn_db)
        root.addWidget(grp)

        self.lbl_status = QLabel("就绪 — 每个 Segment 的计算结果将保存为独立 .db 文件")
        self.lbl_status.setObjectName("status")
        root.addWidget(self.lbl_status)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setAlignment(Qt.AlignCenter)
        root.addWidget(self.progress)

        btn_row = QHBoxLayout()
        self.btn_run = QPushButton("🚀  开始批量计算")
        self.btn_run.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.btn_run.clicked.connect(self._run)

        btn_reset = QPushButton("↺  复位")
        btn_reset.setObjectName("reset")
        btn_reset.clicked.connect(self._reset)

        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(btn_reset)
        root.addLayout(btn_row)
        root.addStretch()

    def _choose_db(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择数据库", "",
                                           "SQLite DB (*.db);;所有文件 (*)")
        if p:
            self.db_edit.setText(p)

    def _reset(self):
        self.db_edit.setText("30.db")
        self.progress.setValue(0)
        self.lbl_status.setText("已复位")

    def _run(self):
        db = self.db_edit.text().strip()
        if not db or not os.path.exists(db):
            QMessageBox.critical(self, "错误", "数据库文件不存在！")
            return
        conn = sqlite3.connect(db)
        cur  = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall() if r[0].startswith("Segment_")]
        conn.close()
        if not tables:
            QMessageBox.information(self, "信息", "未找到任何 Segment_ 表。")
            return

        self.progress.setMaximum(len(tables))
        self.progress.setValue(0)
        self.btn_run.setEnabled(False)

        self._worker = CalWorker(db, tables)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, n, msg):
        self.progress.setValue(n)
        self.lbl_status.setText(msg)

    def _on_finished(self):
        self.btn_run.setEnabled(True)
        total = self.progress.maximum()
        self.progress.setValue(total)
        self.lbl_status.setText(f"✅ 完成！共处理 {total} 个 Segment 表。")
        QMessageBox.information(self, "完成",
            f"批量计算完成，共处理 {total} 个分段表。\n"
            "每段结果已保存为 Segment_N.db 文件。")

    def _on_error(self, msg):
        self.btn_run.setEnabled(True)
        self.lbl_status.setText("❌ 出错")
        QMessageBox.critical(self, "错误", msg)
