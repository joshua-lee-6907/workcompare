"""hb_q1d.py – Tab 5: Q1D statistics computation (converted from Flask)."""

import os
import json
import sqlite3
import numpy as np

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QProgressBar, QGroupBox, QSplitter,
    QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from hb_common import MPL_STYLE, BG_DARK, ACCENT, DANGER, SUCCESS, WARNING, BG_MID


# ─── Core logic ──────────────────────────────────────────────────────────────

def get_max_end_index(db_path):
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.execute("SELECT MAX(end_index) FROM results")
    val = cur.fetchone()[0]
    conn.close()
    return val or 0


def fetch_window_data(db_path, lower, upper):
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.execute(
        "SELECT start_index, end_index, Q1d, dp_mean, A8 FROM results "
        "WHERE start_index >= ? AND end_index <= ?", (lower, upper))
    rows = cur.fetchall()
    conn.close()
    return rows


def calculate_statistics(rows):
    if not rows:
        return {}
    q1d   = np.array([r[2] for r in rows])
    dpm   = np.array([r[3] for r in rows])
    a8    = np.array([r[4] for r in rows])
    return {
        "Q1d":     {"max": np.max(q1d), "min": np.min(q1d),
                    "mean": np.mean(q1d), "std": np.std(q1d)},
        "dp_mean": {"max": np.max(dpm), "min": np.min(dpm),
                    "mean": np.mean(dpm), "std": np.std(dpm)},
        "A8":      {"max": np.max(a8),  "min": np.min(a8),
                    "mean": np.mean(a8), "std": np.std(a8)},
    }


# ─── Worker thread ────────────────────────────────────────────────────────────

class Q1DWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, src_db, out_db):
        super().__init__()
        self.src_db = src_db
        self.out_db = out_db

    def run(self):
        try:
            max_end = get_max_end_index(self.src_db)
        except Exception as e:
            self.error.emit(f"读取源数据库出错：{e}")
            return

        # recreate computed_results table
        conn = sqlite3.connect(self.out_db)
        cur  = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS computed_results")
        cur.execute("""CREATE TABLE computed_results
            (step INTEGER, avg_q1d REAL, avg_dp_mean REAL, avg_a8 REAL,
             min_a8_row TEXT)""")
        conn.commit()

        total = max_end - 47
        if total <= 0:
            self.error.emit("数据量不足，无法计算（需要 end_index > 47）。")
            conn.close()
            return

        for idx, step in enumerate(range(1, total)):
            rows  = fetch_window_data(self.src_db, step, step + 47)
            stats = calculate_statistics(rows)
            if stats and rows:
                min_row = min(rows, key=lambda r: r[4])
                min_json = json.dumps({
                    "start_index": min_row[0], "end_index": min_row[1],
                    "Q1d": min_row[2], "dp_mean": min_row[3], "A8": min_row[4]
                })
                cur.execute(
                    "INSERT INTO computed_results VALUES (?,?,?,?,?)",
                    (step, stats["Q1d"]["mean"],
                     stats["dp_mean"]["mean"], stats["A8"]["mean"], min_json))
            if idx % 50 == 0:
                conn.commit()
                pct = int((idx + 1) / total * 100)
                self.progress.emit(pct, f"步骤 {idx+1}/{total}")

        conn.commit()
        conn.close()
        self.finished.emit()


# ─── Multi-chart widget ───────────────────────────────────────────────────────

class Q1DChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        self.fig = Figure(figsize=(10, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet("background: #101d42;")
        vl.addWidget(self.toolbar)
        vl.addWidget(self.canvas)

    def plot(self, steps, avg_q1d, avg_dpm, avg_a8):
        matplotlib.rcParams.update(MPL_STYLE)
        self.fig.clear()
        colors = [ACCENT, "#fffb00", "#ff9000"]
        titles = ["平均 Q1d", "平均 dp_mean", "平均 A8"]
        series = [avg_q1d, avg_dpm, avg_a8]
        axes   = self.fig.subplots(1, 3)
        for ax, col, ttl, data in zip(axes, colors, titles, series):
            ax.set_facecolor("#0d1836")
            for lw, a in [(10, 0.05), (6, 0.10), (3, 0.18)]:
                ax.plot(steps, data, color=col, lw=lw, alpha=a)
            ax.plot(steps, data, color=col, lw=2, alpha=0.92)
            ax.set_title(ttl, color=ACCENT)
            ax.set_xlabel("Step", color="#e9f1fb", fontsize=10)
            ax.tick_params(colors="#70c6ff")
        self.canvas.draw()


# ─── Tab widget ───────────────────────────────────────────────────────────────

class Q1DTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._computed_db = "5.db"
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(20, 16, 20, 16)

        title = QLabel("📈  Q1D 统计分析")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        splitter = QSplitter(Qt.Vertical)

        # ── Control panel ──
        ctrl = QWidget()
        cl = QVBoxLayout(ctrl)
        cl.setSpacing(8)
        cl.setContentsMargins(0, 0, 0, 0)

        # DB paths row
        db_row = QHBoxLayout()
        grp_src = QGroupBox("源数据库 (2.db)")
        sl = QHBoxLayout(grp_src)
        self.src_edit = QLineEdit("2.db")
        btn_src = QPushButton("浏览")
        btn_src.setObjectName("secondary")
        btn_src.setFixedWidth(60)
        btn_src.clicked.connect(self._choose_src)
        sl.addWidget(self.src_edit)
        sl.addWidget(btn_src)
        db_row.addWidget(grp_src)

        grp_out = QGroupBox("输出数据库 (5.db)")
        ol = QHBoxLayout(grp_out)
        self.out_edit = QLineEdit("5.db")
        btn_out = QPushButton("另存")
        btn_out.setObjectName("secondary")
        btn_out.setFixedWidth(60)
        btn_out.clicked.connect(self._choose_out)
        ol.addWidget(self.out_edit)
        ol.addWidget(btn_out)
        db_row.addWidget(grp_out)
        cl.addLayout(db_row)

        # Progress
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setAlignment(Qt.AlignCenter)
        cl.addWidget(self.progress)

        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("status")
        cl.addWidget(self.lbl_status)

        # Step range query
        grp_q = QGroupBox("查询步骤范围")
        ql = QHBoxLayout(grp_q)
        ql.addWidget(QLabel("起步:"))
        self.spin_start = QSpinBox()
        self.spin_start.setRange(1, 999999)
        self.spin_start.setValue(1)
        ql.addWidget(self.spin_start)
        ql.addWidget(QLabel("终步:"))
        self.spin_end = QSpinBox()
        self.spin_end.setRange(1, 999999)
        self.spin_end.setValue(100)
        ql.addWidget(self.spin_end)
        btn_query = QPushButton("📊  查询并绘图")
        btn_query.clicked.connect(self._query_plot)
        ql.addWidget(btn_query)
        cl.addWidget(grp_q)

        # Button row
        btn_row = QHBoxLayout()
        self.btn_run = QPushButton("🚀  开始计算 (后台)")
        self.btn_run.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.btn_run.clicked.connect(self._run)

        btn_reset = QPushButton("↺  复位")
        btn_reset.setObjectName("reset")
        btn_reset.clicked.connect(self._reset)

        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(btn_reset)
        cl.addLayout(btn_row)

        splitter.addWidget(ctrl)

        # ── Charts + table ──
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)

        inner_tab = QTabWidget()
        inner_tab.setStyleSheet(f"QTabBar::tab {{ padding: 6px 14px; font-size: 12px; }}")

        # chart tab
        self.chart = Q1DChart()
        inner_tab.addTab(self.chart, "趋势图")

        # min A8 table tab
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(
            ["step", "start_index", "end_index", "Q1d", "dp_mean", "A8"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        inner_tab.addTab(self.tbl, "最小 A8 明细")

        bl.addWidget(inner_tab)
        splitter.addWidget(bottom)
        splitter.setSizes([260, 360])
        root.addWidget(splitter)

    # ── Slots ──────────────────────────────────────────────────────────────

    def _choose_src(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择源数据库", "",
                                           "SQLite DB (*.db);;所有文件 (*)")
        if p:
            self.src_edit.setText(p)

    def _choose_out(self):
        p, _ = QFileDialog.getSaveFileName(self, "输出数据库", "5.db",
                                           "SQLite DB (*.db);;所有文件 (*)")
        if p:
            self.out_edit.setText(p)

    def _reset(self):
        self.src_edit.setText("2.db")
        self.out_edit.setText("5.db")
        self.progress.setValue(0)
        self.lbl_status.setText("已复位")
        self.chart.fig.clear()
        self.chart.canvas.draw()
        self.tbl.setRowCount(0)

    def _run(self):
        src = self.src_edit.text().strip()
        out = self.out_edit.text().strip()
        if not os.path.exists(src):
            QMessageBox.critical(self, "错误", "源数据库文件不存在！")
            return
        self.btn_run.setEnabled(False)
        self.progress.setValue(0)
        self.lbl_status.setText("正在计算 …")
        self._computed_db = out
        self._worker = Q1DWorker(src, out)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, pct, msg):
        self.progress.setValue(pct)
        self.lbl_status.setText(f"计算中 … {msg}")

    def _on_finished(self):
        self.btn_run.setEnabled(True)
        self.progress.setValue(100)
        self.lbl_status.setText("✅ 计算完成！可在下方设置步骤范围并绘图。")
        QMessageBox.information(self, "完成",
            f"Q1D 统计计算完成，结果已写入 {self._computed_db}")

    def _on_error(self, msg):
        self.btn_run.setEnabled(True)
        self.lbl_status.setText("❌ 出错")
        QMessageBox.critical(self, "错误", msg)

    def _query_plot(self):
        db = self._computed_db if self._computed_db else self.out_edit.text().strip()
        if not os.path.exists(db):
            QMessageBox.critical(self, "错误",
                f"计算结果数据库 {db} 不存在，请先运行计算。")
            return
        s = self.spin_start.value()
        e = self.spin_end.value()
        if e <= s:
            QMessageBox.warning(self, "参数错误", "终步须大于起步。")
            return
        try:
            conn = sqlite3.connect(db)
            cur  = conn.cursor()
            cur.execute(
                "SELECT step, avg_q1d, avg_dp_mean, avg_a8, min_a8_row "
                "FROM computed_results WHERE step BETWEEN ? AND ? ORDER BY step",
                (s, e))
            rows = cur.fetchall()
            conn.close()
        except Exception as ex:
            QMessageBox.critical(self, "错误", f"查询出错：{ex}")
            return

        if not rows:
            QMessageBox.information(self, "无数据", "该步骤范围内没有数据。")
            return

        steps   = [r[0] for r in rows]
        avg_q1d = [r[1] for r in rows]
        avg_dpm = [r[2] for r in rows]
        avg_a8  = [r[3] for r in rows]
        self.chart.plot(steps, avg_q1d, avg_dpm, avg_a8)

        # populate min A8 table
        self.tbl.setRowCount(0)
        for r in rows:
            try:
                min_row = json.loads(r[4])
            except Exception:
                continue
            row_data = [
                r[0],
                min_row.get("start_index", ""),
                min_row.get("end_index", ""),
                min_row.get("Q1d", ""),
                min_row.get("dp_mean", ""),
                min_row.get("A8", ""),
            ]
            ri = self.tbl.rowCount()
            self.tbl.insertRow(ri)
            for ci, val in enumerate(row_data):
                txt  = f"{val:.6g}" if isinstance(val, float) else str(val)
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignCenter)
                self.tbl.setItem(ri, ci, item)
