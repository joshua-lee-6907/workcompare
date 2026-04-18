"""
Q60 回归分析模块 — 300点滑动窗口线性回归（本地 GUI 版）
Q60 Regression Module: 300-point sliding window with subset filtering and regression
Ported from q60web.py (Flask → PyQt5 native GUI)
"""

import os
import math
import sqlite3

import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QFileDialog, QMessageBox, QGroupBox, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox, QTabWidget, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from .styles import COLORS, ChartDialog, style_axes


# ─── Configuration ────────────────────────────────────────────────────────────

CONFIG = {
    "num_subsets":              20,
    "num_exclude":              12,
    "min_points_for_regression": 5,
}
WINDOW_SIZE = 300
SLIDE       = 30


# ─── Core Logic (identical to q60web.py DataProcessor) ───────────────────────

def _get_max_end_index(source_db: str) -> int:
    conn = sqlite3.connect(source_db)
    c = conn.cursor()
    c.execute("SELECT MAX(end_index) FROM results")
    val = c.fetchone()[0]
    conn.close()
    return val or 0


def _fetch_data(source_db: str, lower: int, upper: int):
    conn = sqlite3.connect(source_db)
    c = conn.cursor()
    c.execute(
        "SELECT start_index, end_index, Q1d, dp_mean, A8 FROM results "
        "WHERE start_index >= ? AND end_index <= ?",
        (lower, upper)
    )
    rows = c.fetchall()
    conn.close()
    return rows


def _partition_list(data, num_parts):
    n = len(data)
    if n == 0:
        return [[] for _ in range(num_parts)]
    base, rem = divmod(n, num_parts)
    sizes = [base + (1 if i < rem else 0) for i in range(num_parts)]
    subsets, idx = [], 0
    for s in sizes:
        subsets.append(data[idx:idx + s])
        idx += s
    return subsets


def _linear_regression_std(candidate):
    x = np.array([r[3] for r in candidate])
    y = np.array([r[2] for r in candidate])
    slope, intercept = np.polyfit(x, y, 1)
    return float(np.std(y - (slope * x + intercept)))


def process_windows(source_db: str, inter_db: str,
                    progress_callback=None) -> str:
    """Create sliding window tables in inter_db. Returns error or ''."""
    max_end = _get_max_end_index(source_db)
    if not max_end:
        return "无法获取 end_index，请检查 2.db。"

    if os.path.exists(inter_db):
        os.remove(inter_db)

    conn = sqlite3.connect(inter_db)
    cur = conn.cursor()

    total_windows = math.ceil((max_end - WINDOW_SIZE + 1) / SLIDE) + 1
    processed, window_count = set(), 0
    current_lower = 1

    while True:
        if current_lower + WINDOW_SIZE - 1 > max_end:
            current_lower = max_end - WINDOW_SIZE + 1
            current_upper = max_end
            key = (current_lower, current_upper)
            if key in processed:
                break
        else:
            current_upper = current_lower + WINDOW_SIZE - 1
            key = (current_lower, current_upper)

        data = _fetch_data(source_db, current_lower, current_upper)
        tname = f"window_{current_lower}_{current_upper}"
        cur.execute(f"DROP TABLE IF EXISTS {tname}")
        cur.execute(f"""
            CREATE TABLE {tname} (
                start_index INTEGER, end_index INTEGER,
                Q1d REAL, dp_mean REAL, A8 REAL
            )
        """)
        cur.executemany(
            f"INSERT INTO {tname} (start_index,end_index,Q1d,dp_mean,A8) VALUES(?,?,?,?,?)",
            data
        )
        conn.commit()
        processed.add(key)
        window_count += 1

        if progress_callback:
            pct = int(window_count / max(total_windows, 1) * 50)
            progress_callback(pct, f"处理滑动窗口 {window_count}/{total_windows}")

        if current_upper == max_end:
            break
        nxt = current_lower + SLIDE
        if nxt + WINDOW_SIZE - 1 > max_end:
            current_lower = max_end - WINDOW_SIZE + 1
        else:
            current_lower = nxt

    conn.close()
    return ''


def process_final_results(inter_db: str, final_db: str,
                           progress_callback=None) -> str:
    """Filter and regress each window table. Returns error or ''."""
    if not os.path.exists(inter_db):
        return f"中间数据库不存在: {inter_db}"

    conn_i = sqlite3.connect(inter_db)
    tables = [r[0] for r in conn_i.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'window_%'"
    ).fetchall()]
    conn_i.close()

    if os.path.exists(final_db):
        os.remove(final_db)

    conn_f = sqlite3.connect(final_db)
    conn_f.execute("""
        CREATE TABLE total_summary (
            table_identifier TEXT, slope REAL, slope_times_60 REAL,
            intercept REAL, residual_std REAL
        )
    """)
    conn_f.commit()

    total = len(tables)
    for idx, wtable in enumerate(tables):
        conn_i = sqlite3.connect(inter_db)
        rows = conn_i.execute(
            f"SELECT start_index,end_index,Q1d,dp_mean,A8 FROM {wtable}"
        ).fetchall()
        conn_i.close()

        if not rows:
            continue

        sorted_rows = sorted(rows, key=lambda r: r[3])
        subsets = _partition_list(sorted_rows, CONFIG["num_subsets"])

        subset_stats = [(i, s, np.std([r[2] for r in s]) if s else float('inf'))
                        for i, s in enumerate(subsets)]
        nonempty = [x for x in subset_stats if x[1]]
        if len(nonempty) > CONFIG["num_exclude"]:
            selected = sorted(nonempty, key=lambda x: x[2])[:len(nonempty) - CONFIG["num_exclude"]]
        else:
            selected = []

        final_points = []
        for _, sub, _ in selected:
            if len(sub) >= CONFIG["min_points_for_regression"]:
                best_std, best_cand = float('inf'), None
                for i in range(len(sub) - CONFIG["min_points_for_regression"] + 1):
                    cand = sub[i:i + CONFIG["min_points_for_regression"]]
                    s = _linear_regression_std(cand)
                    if s < best_std:
                        best_std, best_cand = s, cand
                if best_cand:
                    med = CONFIG["min_points_for_regression"] // 2
                    fp = best_cand[med]
                    final_points.append((fp[0], fp[1], fp[2], fp[3], fp[4], best_std))
            elif sub:
                med = len(sub) // 2
                fp = sub[med]
                final_points.append((fp[0], fp[1], fp[2], fp[3], fp[4], None))

        ftable = "final_" + wtable
        conn_f.execute(f"DROP TABLE IF EXISTS {ftable}")
        conn_f.execute(f"""
            CREATE TABLE {ftable} (
                start_index INTEGER, end_index INTEGER,
                Q1d REAL, dp_mean REAL, A8 REAL, residual_std REAL
            )
        """)
        for pt in final_points:
            conn_f.execute(
                f"INSERT INTO {ftable} VALUES(?,?,?,?,?,?)", pt
            )
        conn_f.commit()

        if len(final_points) >= 2:
            dpm = np.array([p[3] for p in final_points])
            q1d = np.array([p[2] for p in final_points])
            slope, intercept = np.polyfit(dpm, q1d, 1)
            res_std = float(np.std(q1d - (slope * dpm + intercept)))
            slope_60 = float(slope * 60)
        else:
            slope = intercept = res_std = slope_60 = None

        conn_f.execute(
            "INSERT INTO total_summary VALUES(?,?,?,?,?)",
            (wtable, slope, slope_60, intercept, res_std)
        )
        conn_f.commit()

        if progress_callback:
            pct = 50 + int((idx + 1) / max(total, 1) * 48)
            progress_callback(pct, f"回归处理窗口 {idx+1}/{total}")

    conn_f.close()
    if progress_callback:
        progress_callback(100, "处理完成")
    return ''


# ─── Background Thread ────────────────────────────────────────────────────────

class Q60ProcessThread(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, source_db, inter_db, final_db):
        super().__init__()
        self.source_db = source_db
        self.inter_db  = inter_db
        self.final_db  = final_db

    def run(self):
        err = process_windows(
            self.source_db, self.inter_db,
            progress_callback=lambda p, m: self.progress_signal.emit(p, m)
        )
        if err:
            self.finished_signal.emit(False, err)
            return
        err = process_final_results(
            self.inter_db, self.final_db,
            progress_callback=lambda p, m: self.progress_signal.emit(p, m)
        )
        if err:
            self.finished_signal.emit(False, err)
        else:
            self.finished_signal.emit(True, "")


# ─── Data Query Helpers ───────────────────────────────────────────────────────

def list_window_tables(inter_db: str):
    if not os.path.exists(inter_db):
        return []
    conn = sqlite3.connect(inter_db)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'window_%'"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_raw_data(inter_db: str, window_table: str):
    conn = sqlite3.connect(inter_db)
    rows = conn.execute(
        f"SELECT start_index,end_index,Q1d,dp_mean,A8 FROM {window_table}"
    ).fetchall()
    conn.close()
    return rows


def get_final_points(final_db: str, window_table: str):
    ftable = "final_" + window_table
    conn = sqlite3.connect(final_db)
    rows = conn.execute(
        f"SELECT start_index,end_index,Q1d,dp_mean,A8,residual_std FROM {ftable}"
    ).fetchall()
    conn.close()
    return rows


def get_summary(final_db: str, window_table: str):
    conn = sqlite3.connect(final_db)
    row = conn.execute(
        "SELECT slope,slope_times_60,intercept,residual_std "
        "FROM total_summary WHERE table_identifier=?",
        (window_table,)
    ).fetchone()
    conn.close()
    return row  # (slope, slope_times_60, intercept, residual_std)


# ─── Chart Helper ─────────────────────────────────────────────────────────────

def _plot_regression(fig, raw_rows, final_pts, summary):
    fig.clear()
    ax = fig.add_subplot(111)
    style_axes(ax)

    if raw_rows:
        raw_dp  = [r[3] for r in raw_rows]
        raw_q1d = [r[2] for r in raw_rows]
        ax.scatter(raw_dp, raw_q1d, color=COLORS['text_secondary'],
                   alpha=0.35, s=18, label="窗口原始数据", zorder=2)

    if final_pts:
        fp_dp  = [r[3] for r in final_pts]
        fp_q1d = [r[2] for r in final_pts]
        ax.scatter(fp_dp, fp_q1d, color=COLORS['accent_cyan'],
                   alpha=0.95, s=55, zorder=4, label=f"精选点 ({len(final_pts)})",
                   edgecolors='#ffffff', linewidths=0.6)

    if summary and summary[0] is not None:
        slope, slope60, intercept, res_std = summary
        all_dp = ([r[3] for r in raw_rows] if raw_rows else []) + \
                 ([r[3] for r in final_pts] if final_pts else [])
        if all_dp:
            x_min, x_max = min(all_dp), max(all_dp)
            xs = np.linspace(x_min, x_max, 200)
            ys = slope * xs + intercept
            ax.plot(xs, ys, '-', color=COLORS['accent_red'],
                    linewidth=2.2, alpha=0.9, zorder=3,
                    label=f"回归线 slope={slope:.4g}  ×60={slope60:.4g}")
            ax.annotate(
                f"slope×60 = {slope60:.6g}\nintercept = {intercept:.6g}\n"
                f"residual_std = {res_std:.6g}",
                xy=(0.02, 0.98), xycoords='axes fraction',
                va='top', ha='left', fontsize=10,
                color=COLORS['text_primary'],
                bbox=dict(boxstyle='round,pad=0.4', fc='#0c1530', ec='#1a2d5a')
            )

    ax.set_title("Q1d vs dp_mean 线性回归", fontsize=13,
                 color=COLORS['accent_cyan'], pad=12)
    ax.set_xlabel("dp_mean", fontsize=11)
    ax.set_ylabel("Q1d", fontsize=11)
    ax.legend(fontsize=9, facecolor='#0c1530',
              edgecolor='#1a2d5a', labelcolor='#d8eeff')
    fig.tight_layout()


# ─── Widget ───────────────────────────────────────────────────────────────────

class Q60Widget(QWidget):
    """Q60 回归分析面板"""

    status_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # 标题
        title = QLabel("Q60 回归分析 — 300点滑动窗口线性回归")
        title.setObjectName("lbl_title")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        sub = QLabel("300点窗口 × 30步长滑动，子集筛选后进行 Q1d = slope × dp_mean + intercept 回归")
        sub.setObjectName("lbl_subtitle")
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(_hline())

        # 数据库配置
        db_group = QGroupBox("数据库配置")
        db_layout = QVBoxLayout(db_group)

        for label_text, attr, default, btn_text, btn_slot in [
            ("源数据库 (2.db):", "src_edit", "2.db", "浏览", self._choose_src),
            ("中间数据库 (20.db):", "inter_edit", "20.db", "另存为", self._choose_inter),
            ("最终数据库 (21.db):", "final_edit", "21.db", "另存为", self._choose_final),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            edit = QLineEdit(default)
            setattr(self, attr, edit)
            btn = QPushButton(btn_text)
            btn.setFixedWidth(80)
            btn.clicked.connect(btn_slot)
            row.addWidget(edit)
            row.addWidget(btn)
            db_layout.addLayout(row)

        root.addWidget(db_group)

        # 进度
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFixedHeight(26)
        self.status_lbl = QLabel("就绪")
        self.status_lbl.setObjectName("lbl_subtitle")
        root.addWidget(self.progress)
        root.addWidget(self.status_lbl)

        # 分析区
        analysis_group = QGroupBox("窗口分析与回归可视化")
        al = QVBoxLayout(analysis_group)

        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("选择窗口:"))
        self.window_combo = QComboBox()
        self.window_combo.setMinimumWidth(220)
        self.load_windows_btn = QPushButton("加载窗口列表")
        self.load_windows_btn.setFixedWidth(130)
        self.load_windows_btn.clicked.connect(self._load_windows)
        self.load_windows_btn.setEnabled(False)
        sel_row.addWidget(self.window_combo)
        sel_row.addWidget(self.load_windows_btn)
        sel_row.addStretch()
        al.addLayout(sel_row)

        # 摘要表
        self.summary_table = _make_table(
            ["窗口", "slope", "slope×60", "intercept", "residual_std"]
        )
        self.summary_table.setFixedHeight(120)
        al.addWidget(self.summary_table)

        # 图表按钮
        chart_row = QHBoxLayout()
        self.reg_btn = QPushButton("📈  查看回归图")
        self.reg_btn.clicked.connect(self._show_regression)
        self.reg_btn.setEnabled(False)
        self.all_summary_btn = QPushButton("📊  全窗口回归汇总图")
        self.all_summary_btn.clicked.connect(self._show_all_summary)
        self.all_summary_btn.setEnabled(False)
        chart_row.addStretch()
        chart_row.addWidget(self.reg_btn)
        chart_row.addWidget(self.all_summary_btn)
        al.addLayout(chart_row)

        root.addWidget(analysis_group)

        # 操作按钮
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

    def _choose_src(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择源数据库", "",
                                           "SQLite 数据库 (*.db);;所有文件 (*)")
        if p:
            self.src_edit.setText(p)

    def _choose_inter(self):
        p, _ = QFileDialog.getSaveFileName(self, "保存中间数据库", "20.db",
                                           "SQLite 数据库 (*.db);;所有文件 (*)")
        if p:
            self.inter_edit.setText(p)

    def _choose_final(self):
        p, _ = QFileDialog.getSaveFileName(self, "保存最终数据库", "21.db",
                                           "SQLite 数据库 (*.db);;所有文件 (*)")
        if p:
            self.final_edit.setText(p)

    def _reset(self):
        self.src_edit.setText("2.db")
        self.inter_edit.setText("20.db")
        self.final_edit.setText("21.db")
        self.progress.setValue(0)
        self.status_lbl.setText("就绪")
        self.window_combo.clear()
        self.summary_table.setRowCount(0)
        self.load_windows_btn.setEnabled(False)
        self.reg_btn.setEnabled(False)
        self.all_summary_btn.setEnabled(False)

    def _run(self):
        src   = self.src_edit.text().strip()
        inter = self.inter_edit.text().strip()
        final = self.final_edit.text().strip()
        if not os.path.exists(src):
            QMessageBox.critical(self, "错误", f"源数据库不存在:\n{src}")
            return
        self.run_btn.setEnabled(False)
        self.load_windows_btn.setEnabled(False)
        self.progress.setValue(0)
        self.status_lbl.setText("处理中 …")

        self._thread = Q60ProcessThread(src, inter, final)
        self._thread.progress_signal.connect(self._on_progress)
        self._thread.finished_signal.connect(self._on_finished)
        self._thread.start()

    def _on_progress(self, pct, msg):
        self.progress.setValue(pct)
        self.status_lbl.setText(msg)
        self.status_changed.emit(msg)

    def _on_finished(self, ok, msg):
        self.run_btn.setEnabled(True)
        if ok:
            self.progress.setValue(100)
            self.load_windows_btn.setEnabled(True)
            self.status_lbl.setText("处理完成")
            self.status_changed.emit("Q60 处理完成")
            self._load_windows()
            QMessageBox.information(self, "完成", "Q60 回归分析处理完成！")
        else:
            self.status_lbl.setText("失败")
            self.status_changed.emit("Q60 处理失败")
            QMessageBox.critical(self, "失败", msg)

    def _load_windows(self):
        inter = self.inter_edit.text().strip()
        tables = list_window_tables(inter)
        self.window_combo.clear()
        if tables:
            self.window_combo.addItems(tables)
            self.reg_btn.setEnabled(True)
            self.all_summary_btn.setEnabled(True)
            self._populate_summary(tables)
        else:
            QMessageBox.warning(self, "提示", f"未找到窗口表，请先运行处理。\n{inter}")

    def _populate_summary(self, tables):
        final = self.final_edit.text().strip()
        self.summary_table.setRowCount(0)
        if not os.path.exists(final):
            return
        for wt in tables:
            s = get_summary(final, wt)
            ri = self.summary_table.rowCount()
            self.summary_table.insertRow(ri)
            vals = [wt] + (list(s) if s else [None]*4)
            for ci, v in enumerate(vals):
                item = QTableWidgetItem(_fmt(v))
                item.setTextAlignment(Qt.AlignCenter)
                self.summary_table.setItem(ri, ci, item)

    def _show_regression(self):
        wtable = self.window_combo.currentText()
        if not wtable:
            return
        inter = self.inter_edit.text().strip()
        final = self.final_edit.text().strip()
        raw   = get_raw_data(inter, wtable)
        fps   = get_final_points(final, wtable) if os.path.exists(final) else []
        summ  = get_summary(final, wtable) if os.path.exists(final) else None

        dlg = ChartDialog(self, title=f"回归图 — {wtable}")
        _plot_regression(dlg.get_figure(), raw, fps, summ)
        dlg.refresh()
        dlg.exec_()

    def _show_all_summary(self):
        final = self.final_edit.text().strip()
        if not os.path.exists(final):
            QMessageBox.warning(self, "提示", "最终数据库不存在")
            return
        conn = sqlite3.connect(final)
        rows = conn.execute(
            "SELECT table_identifier, slope_times_60, residual_std FROM total_summary "
            "WHERE slope_times_60 IS NOT NULL ORDER BY table_identifier"
        ).fetchall()
        conn.close()
        if not rows:
            QMessageBox.information(self, "提示", "暂无汇总数据")
            return

        dlg = ChartDialog(self, title="全窗口 slope×60 汇总图", figsize=(12, 6))
        fig = dlg.get_figure()
        fig.clear()
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)
        style_axes(ax1)
        style_axes(ax2)

        labels = [r[0].replace("window_", "w") for r in rows]
        s60    = [r[1] for r in rows]
        res    = [r[2] for r in rows]
        xs     = range(len(rows))

        ax1.bar(xs, s60, color=COLORS['accent_cyan'], alpha=0.8, width=0.7)
        ax1.set_xticks(list(xs)[::max(1, len(xs)//10)])
        ax1.set_xticklabels(labels[::max(1, len(xs)//10)], rotation=45, ha='right', fontsize=8)
        ax1.set_title("slope×60 各窗口", fontsize=12, color=COLORS['accent_cyan'])
        ax1.set_ylabel("slope×60", fontsize=10)

        ax2.bar(xs, res, color=COLORS['accent_red'], alpha=0.8, width=0.7)
        ax2.set_xticks(list(xs)[::max(1, len(xs)//10)])
        ax2.set_xticklabels(labels[::max(1, len(xs)//10)], rotation=45, ha='right', fontsize=8)
        ax2.set_title("残差标准差各窗口", fontsize=12, color=COLORS['accent_red'])
        ax2.set_ylabel("residual_std", fontsize=10)

        fig.tight_layout()
        dlg.refresh()
        dlg.exec_()


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    return t


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v) if v is not None else "—"


def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f
