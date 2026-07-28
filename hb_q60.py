"""hb_q60.py – Tab 6: Q60 sliding-window computation (converted from Flask)."""

import os
import math
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
    QComboBox, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from hb_common import MPL_STYLE, BG_DARK, ACCENT, DANGER, SUCCESS, WARNING, BG_MID

CONFIG = {
    "num_subsets": 20,
    "num_exclude": 12,
    "min_points_for_regression": 5,
}


# ─── DataProcessor (ported from q60web.py) ───────────────────────────────────

class DataProcessor:
    def __init__(self, source_db, intermediate_db, final_db, progress_cb=None):
        self.source_db       = source_db
        self.intermediate_db = intermediate_db
        self.final_db        = final_db
        self.window_size     = 300
        self.slide           = 30
        self.progress_cb     = progress_cb
        self.max_end_index   = self._get_max_end_index()

    def _update(self, pct, msg=""):
        if self.progress_cb:
            self.progress_cb(pct, msg)

    def _get_max_end_index(self):
        conn = sqlite3.connect(self.source_db)
        cur  = conn.cursor()
        cur.execute("SELECT MAX(end_index) FROM results")
        val  = cur.fetchone()[0]
        conn.close()
        return val or 0

    def _fetch_data(self, lo, hi):
        conn = sqlite3.connect(self.source_db)
        cur  = conn.cursor()
        cur.execute(
            "SELECT start_index, end_index, Q1d, dp_mean, A8 FROM results "
            "WHERE start_index >= ? AND end_index <= ?", (lo, hi))
        rows = cur.fetchall()
        conn.close()
        return rows

    def process_windows(self):
        if os.path.exists(self.intermediate_db):
            os.remove(self.intermediate_db)
        conn = sqlite3.connect(self.intermediate_db)
        cur  = conn.cursor()

        cur_lower   = 1
        processed   = []
        total_wins  = math.ceil(
            (self.max_end_index - self.window_size + 1) / self.slide) + 1
        win_count   = 0

        while True:
            if cur_lower + self.window_size - 1 > self.max_end_index:
                cur_lower = self.max_end_index - self.window_size + 1
                cur_upper = self.max_end_index
                if (cur_lower, cur_upper) in processed:
                    break
            else:
                cur_upper = cur_lower + self.window_size - 1

            data  = self._fetch_data(cur_lower, cur_upper)
            tname = f"window_{cur_lower}_{cur_upper}"
            cur.execute(f"DROP TABLE IF EXISTS {tname}")
            cur.execute(f"""CREATE TABLE {tname}
                (start_index INTEGER, end_index INTEGER,
                 Q1d REAL, dp_mean REAL, A8 REAL)""")
            cur.executemany(
                f"INSERT INTO {tname} VALUES (?,?,?,?,?)", data)
            conn.commit()
            processed.append((cur_lower, cur_upper))
            win_count += 1
            self._update(int(win_count / max(total_wins, 1) * 50),
                         f"滑动窗口 {win_count}/{total_wins}")

            if cur_upper == self.max_end_index:
                break
            nxt = cur_lower + self.slide
            if nxt + self.window_size - 1 > self.max_end_index:
                cur_lower = self.max_end_index - self.window_size + 1
            else:
                cur_lower = nxt
        conn.close()

    def _partition(self, data, num_parts):
        n   = len(data)
        if n == 0:
            return [[] for _ in range(num_parts)]
        base, rem = divmod(n, num_parts)
        sizes = [base + (1 if i < rem else 0) for i in range(num_parts)]
        subs, idx = [], 0
        for sz in sizes:
            subs.append(data[idx:idx+sz])
            idx += sz
        return subs

    def _lin_reg_std(self, candidate):
        x = np.array([r[3] for r in candidate])
        y = np.array([r[2] for r in candidate])
        slope, intercept = np.polyfit(x, y, 1)
        return np.std(y - (slope * x + intercept))

    def process_final_results(self):
        if os.path.exists(self.final_db):
            os.remove(self.final_db)
        conn_inter = sqlite3.connect(self.intermediate_db)
        cur_inter  = conn_inter.cursor()
        cur_inter.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'window_%'")
        win_tables = [r[0] for r in cur_inter.fetchall()]
        conn_inter.close()

        conn_fin = sqlite3.connect(self.final_db)
        cur_fin  = conn_fin.cursor()
        cur_fin.execute("DROP TABLE IF EXISTS total_summary")
        cur_fin.execute("""CREATE TABLE total_summary
            (table_identifier TEXT, slope REAL, slope_times_60 REAL,
             intercept REAL, residual_std REAL)""")
        conn_fin.commit()

        total = len(win_tables)
        for idx, wtable in enumerate(win_tables):
            conn_inter = sqlite3.connect(self.intermediate_db)
            cur_inter  = conn_inter.cursor()
            cur_inter.execute(
                f"SELECT start_index, end_index, Q1d, dp_mean, A8 FROM {wtable}")
            rows = cur_inter.fetchall()
            conn_inter.close()

            if not rows:
                continue

            sorted_rows = sorted(rows, key=lambda r: r[3])
            subsets     = self._partition(sorted_rows, CONFIG["num_subsets"])
            subset_stats = [(i, sub, np.std([r[2] for r in sub]) if sub else float("inf"))
                            for i, sub in enumerate(subsets)]
            nonempty = [s for s in subset_stats if s[1]]
            if len(nonempty) > CONFIG["num_exclude"]:
                nonempty.sort(key=lambda x: x[2])
                selected = nonempty[:len(nonempty) - CONFIG["num_exclude"]]
            else:
                selected = []

            final_pts = []
            for _, sub, _ in selected:
                if len(sub) >= CONFIG["min_points_for_regression"]:
                    best_std, best_cand = float("inf"), None
                    for i in range(len(sub) - CONFIG["min_points_for_regression"] + 1):
                        cand = sub[i:i+CONFIG["min_points_for_regression"]]
                        std  = self._lin_reg_std(cand)
                        if std < best_std:
                            best_std, best_cand = std, cand
                    if best_cand:
                        mid = CONFIG["min_points_for_regression"] // 2
                        final_pts.append((*best_cand[mid], best_std))
                elif sub:
                    mid = len(sub) // 2
                    final_pts.append((*sub[mid], None))

            final_tname = "final_" + wtable
            cur_fin.execute(f"DROP TABLE IF EXISTS {final_tname}")
            cur_fin.execute(f"""CREATE TABLE {final_tname}
                (start_index INTEGER, end_index INTEGER, Q1d REAL,
                 dp_mean REAL, A8 REAL, residual_std REAL)""")
            for pt in final_pts:
                cur_fin.execute(f"INSERT INTO {final_tname} VALUES (?,?,?,?,?,?)", pt)
            conn_fin.commit()

            if len(final_pts) >= 2:
                dpm   = np.array([p[3] for p in final_pts])
                q1ds  = np.array([p[2] for p in final_pts])
                slope, intercept = np.polyfit(dpm, q1ds, 1)
                residual_std     = np.std(q1ds - (slope * dpm + intercept))
            else:
                slope = intercept = residual_std = None

            s60 = slope * 60 if slope is not None else None
            cur_fin.execute(
                "INSERT INTO total_summary VALUES (?,?,?,?,?)",
                (wtable, slope, s60, intercept, residual_std))
            conn_fin.commit()
            self._update(50 + int((idx+1) / max(total, 1) * 48),
                         f"窗口 {idx+1}/{total} 回归完成")

        conn_fin.close()
        self._update(100, "所有数据处理完成")


# ─── Worker thread ────────────────────────────────────────────────────────────

class Q60Worker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, src, inter, final):
        super().__init__()
        self.src   = src
        self.inter = inter
        self.final = final

    def run(self):
        try:
            dp = DataProcessor(self.src, self.inter, self.final,
                               progress_cb=lambda p, m: self.progress.emit(p, m))
            dp.process_windows()
            dp.process_final_results()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# ─── Chart widget ─────────────────────────────────────────────────────────────

class Q60Chart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        self.fig     = Figure(figsize=(10, 5), tight_layout=True)
        self.canvas  = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet("background: #101d42;")
        vl.addWidget(self.toolbar)
        vl.addWidget(self.canvas)

    def plot_window(self, raw_rows, final_pts, slope, intercept, slope60):
        matplotlib.rcParams.update(MPL_STYLE)
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor("#0d1836")

        if raw_rows:
            rx = [r[3] for r in raw_rows]
            ry = [r[2] for r in raw_rows]
            ax.scatter(rx, ry, color="#00d4ff", s=18, alpha=0.55,
                       label="原始数据点", zorder=2)

        if final_pts:
            fx = [p[3] for p in final_pts]
            fy = [p[2] for p in final_pts]
            ax.scatter(fx, fy, color="#ff9000", s=50, zorder=4,
                       edgecolors="white", linewidths=0.8, label="代表点")

        if slope is not None and len(final_pts) >= 2:
            x_range = np.linspace(min(p[3] for p in final_pts),
                                  max(p[3] for p in final_pts), 100)
            ax.plot(x_range, slope * x_range + intercept,
                    color="#00ffe0", lw=2, linestyle="--",
                    label=f"拟合 slope={slope:.4f} ×60={slope60:.4f}")

        ax.set_title("Q1d vs dp_mean 回归分析", color=ACCENT)
        ax.set_xlabel("dp_mean", color="#e9f1fb")
        ax.set_ylabel("Q1d",     color="#e9f1fb")
        ax.legend(fontsize=10)
        self.canvas.draw()


# ─── Tab widget ───────────────────────────────────────────────────────────────

class Q60Tab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker    = None
        self._inter_db  = "20.db"
        self._final_db  = "21.db"
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(20, 16, 20, 16)

        title = QLabel("📉  Q60 滑动窗口回归计算")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        splitter = QSplitter(Qt.Vertical)

        # ── Control ──
        ctrl = QWidget()
        cl = QVBoxLayout(ctrl)
        cl.setSpacing(8)
        cl.setContentsMargins(0, 0, 0, 0)

        db_row = QHBoxLayout()
        for label, attr, default in [
            ("源数据库 (2.db)",    "src_edit",   "2.db"),
            ("中间数据库 (20.db)", "inter_edit", "20.db"),
            ("结果数据库 (21.db)", "final_edit", "21.db"),
        ]:
            grp = QGroupBox(label)
            hl  = QHBoxLayout(grp)
            edit = QLineEdit(default)
            setattr(self, attr, edit)
            btn = QPushButton("…")
            btn.setObjectName("secondary")
            btn.setFixedWidth(36)
            btn.clicked.connect(lambda _, a=attr: self._browse_db(a))
            hl.addWidget(edit)
            hl.addWidget(btn)
            db_row.addWidget(grp)
        cl.addLayout(db_row)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setAlignment(Qt.AlignCenter)
        cl.addWidget(self.progress)

        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("status")
        cl.addWidget(self.lbl_status)

        # Window selector
        grp_w = QGroupBox("查看窗口结果")
        wl    = QHBoxLayout(grp_w)
        wl.addWidget(QLabel("选择窗口:"))
        self.combo_win = QComboBox()
        self.combo_win.setMinimumWidth(200)
        btn_load = QPushButton("加载窗口列表")
        btn_load.setObjectName("secondary")
        btn_load.clicked.connect(self._load_windows)
        btn_view = QPushButton("📊  查看图表")
        btn_view.clicked.connect(self._view_window)
        wl.addWidget(self.combo_win)
        wl.addWidget(btn_load)
        wl.addWidget(btn_view)
        cl.addWidget(grp_w)

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

        # ── Bottom: chart + summary ──
        bottom    = QWidget()
        bl        = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        inner_tab = QTabWidget()
        inner_tab.setStyleSheet("QTabBar::tab { padding: 6px 14px; font-size: 12px; }")

        self.chart = Q60Chart()
        inner_tab.addTab(self.chart, "回归图")

        self.summary_tbl = QTableWidget(0, 5)
        self.summary_tbl.setHorizontalHeaderLabels(
            ["窗口", "slope", "slope×60", "intercept", "residual_std"])
        self.summary_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.summary_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        inner_tab.addTab(self.summary_tbl, "汇总表 (total_summary)")

        bl.addWidget(inner_tab)
        splitter.addWidget(bottom)
        splitter.setSizes([300, 340])
        root.addWidget(splitter)

    # ── Slots ──────────────────────────────────────────────────────────────

    def _browse_db(self, attr):
        p, _ = QFileDialog.getSaveFileName(self, "选择/保存数据库", "",
                                           "SQLite DB (*.db);;所有文件 (*)")
        if p:
            getattr(self, attr).setText(p)

    def _reset(self):
        self.src_edit.setText("2.db")
        self.inter_edit.setText("20.db")
        self.final_edit.setText("21.db")
        self.progress.setValue(0)
        self.lbl_status.setText("已复位")
        self.combo_win.clear()
        self.chart.fig.clear()
        self.chart.canvas.draw()
        self.summary_tbl.setRowCount(0)

    def _run(self):
        src   = self.src_edit.text().strip()
        inter = self.inter_edit.text().strip()
        final = self.final_edit.text().strip()
        if not os.path.exists(src):
            QMessageBox.critical(self, "错误", "源数据库 (2.db) 不存在！")
            return
        self._inter_db = inter
        self._final_db = final
        self.btn_run.setEnabled(False)
        self.progress.setValue(0)
        self.lbl_status.setText("正在计算 …")
        self._worker = Q60Worker(src, inter, final)
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
        self.lbl_status.setText("✅ 计算完成！")
        QMessageBox.information(self, "完成",
            f"Q60 计算完成。\n中间库: {self._inter_db}\n结果库: {self._final_db}")
        self._load_windows()
        self._load_summary()

    def _on_error(self, msg):
        self.btn_run.setEnabled(True)
        self.lbl_status.setText("❌ 出错")
        QMessageBox.critical(self, "错误", msg)

    def _load_windows(self):
        inter = self.inter_edit.text().strip()
        if not os.path.exists(inter):
            QMessageBox.information(self, "提示",
                f"中间数据库 {inter} 不存在，请先运行计算。")
            return
        try:
            conn = sqlite3.connect(inter)
            cur  = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'window_%'")
            tables = sorted([r[0] for r in cur.fetchall()])
            conn.close()
            self.combo_win.clear()
            self.combo_win.addItems(tables)
            self.lbl_status.setText(f"已加载 {len(tables)} 个窗口")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def _load_summary(self):
        final = self.final_edit.text().strip()
        if not os.path.exists(final):
            return
        try:
            conn = sqlite3.connect(final)
            cur  = conn.cursor()
            cur.execute(
                "SELECT table_identifier, slope, slope_times_60, "
                "intercept, residual_std FROM total_summary ORDER BY table_identifier")
            rows = cur.fetchall()
            conn.close()
            self.summary_tbl.setRowCount(0)
            for row in rows:
                ri = self.summary_tbl.rowCount()
                self.summary_tbl.insertRow(ri)
                for ci, val in enumerate(row):
                    txt  = f"{val:.6g}" if isinstance(val, float) else str(val)
                    item = QTableWidgetItem(txt)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.summary_tbl.setItem(ri, ci, item)
        except Exception:
            pass

    def _view_window(self):
        wtable = self.combo_win.currentText()
        if not wtable:
            QMessageBox.information(self, "提示", "请先加载窗口列表并选择窗口。")
            return
        inter = self.inter_edit.text().strip()
        final = self.final_edit.text().strip()
        try:
            conn = sqlite3.connect(inter)
            cur  = conn.cursor()
            cur.execute(f"SELECT start_index, end_index, Q1d, dp_mean, A8 FROM {wtable}")
            raw_rows = cur.fetchall()
            conn.close()

            final_tname = "final_" + wtable
            conn = sqlite3.connect(final)
            cur  = conn.cursor()
            cur.execute(
                f"SELECT start_index, end_index, Q1d, dp_mean, A8, residual_std "
                f"FROM {final_tname}")
            final_pts = cur.fetchall()
            cur.execute(
                "SELECT slope, intercept, residual_std, slope_times_60 "
                "FROM total_summary WHERE table_identifier=?", (wtable,))
            summary = cur.fetchone()
            conn.close()

            slope    = summary[0] if summary else None
            intercept= summary[1] if summary else None
            slope60  = summary[3] if summary else None
            self.chart.plot_window(raw_rows, final_pts, slope, intercept, slope60)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载窗口数据出错：{e}")
