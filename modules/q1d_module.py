"""
Q1D 分析模块 — 48点滑动窗口统计分析（本地 GUI 版）
Q1D Analysis Module: 48-point sliding window statistics
Ported from q1dweb.py (Flask → PyQt5 native GUI)
"""

import os
import json
import sqlite3

import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QFileDialog, QMessageBox, QGroupBox, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSplitter, QSpinBox, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from .styles import COLORS, ChartDialog, style_axes


# ─── Core Logic (identical to q1dweb.py) ──────────────────────────────────────

def get_max_end_index(source_db: str) -> int:
    conn = sqlite3.connect(source_db)
    c = conn.cursor()
    c.execute("SELECT MAX(end_index) FROM results")
    val = c.fetchone()[0]
    conn.close()
    return val or 0


def fetch_data_range(source_db: str, lower: int, upper: int):
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


def calculate_statistics(data):
    if not data:
        return {}
    q1d = np.array([r[2] for r in data])
    dp = np.array([r[3] for r in data])
    a8 = np.array([r[4] for r in data])
    return {
        'Q1d':    {'max': float(np.max(q1d)),  'min': float(np.min(q1d)),
                   'mean': float(np.mean(q1d)), 'std': float(np.std(q1d))},
        'dp_mean':{'max': float(np.max(dp)),   'min': float(np.min(dp)),
                   'mean': float(np.mean(dp)),  'std': float(np.std(dp))},
        'A8':     {'max': float(np.max(a8)),   'min': float(np.min(a8)),
                   'mean': float(np.mean(a8)),  'std': float(np.std(a8))},
    }


def compute_statistics(source_db: str, computed_db: str,
                        progress_callback=None) -> str:
    """Run full 48-point window computation. Returns error string or ''."""
    max_end_index = get_max_end_index(source_db)
    if not max_end_index:
        return "无法获取 end_index，请检查 2.db 中是否有 results 表。"

    if os.path.exists(computed_db):
        conn = sqlite3.connect(computed_db)
        conn.execute("DROP TABLE IF EXISTS computed_results")
        conn.commit()
        conn.close()

    conn = sqlite3.connect(computed_db)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS computed_results (
            step        INTEGER,
            avg_q1d     REAL,
            avg_dp_mean REAL,
            avg_a8      REAL,
            min_a8_row  TEXT
        )
    """)
    conn.commit()

    total_steps = max_end_index - 47
    if total_steps <= 0:
        conn.close()
        return "数据不足，需要至少 48 个 end_index 范围。"

    for idx, step in enumerate(range(1, total_steps)):
        lower = step
        upper = step + 47
        data = fetch_data_range(source_db, lower, upper)
        stats = calculate_statistics(data)
        if stats:
            min_row = min(data, key=lambda x: x[4])
            min_row_str = json.dumps({
                "start_index": min_row[0], "end_index": min_row[1],
                "Q1d": min_row[2], "dp_mean": min_row[3], "A8": min_row[4]
            })
            conn.execute(
                "INSERT INTO computed_results (step,avg_q1d,avg_dp_mean,avg_a8,min_a8_row) "
                "VALUES (?,?,?,?,?)",
                (step, stats['Q1d']['mean'], stats['dp_mean']['mean'],
                 stats['A8']['mean'], min_row_str)
            )
        if progress_callback and idx % 100 == 0:
            pct = int(idx / total_steps * 100)
            progress_callback(pct, f"正在计算步骤 {idx+1}/{total_steps}")

    conn.commit()
    conn.close()
    return ''


def get_summary_data(computed_db: str, start_step: int, end_step: int):
    conn = sqlite3.connect(computed_db)
    c = conn.cursor()
    c.execute(
        "SELECT step, avg_q1d, avg_dp_mean, avg_a8 FROM computed_results "
        "WHERE step BETWEEN ? AND ? ORDER BY step",
        (start_step, end_step)
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_min_a8_rows(computed_db: str, start_step: int, end_step: int):
    conn = sqlite3.connect(computed_db)
    c = conn.cursor()
    c.execute(
        "SELECT step, min_a8_row FROM computed_results "
        "WHERE step BETWEEN ? AND ? ORDER BY step",
        (start_step, end_step)
    )
    rows = c.fetchall()
    conn.close()
    result = []
    for step, js in rows:
        d = json.loads(js)
        d['step'] = step
        result.append(d)
    return result


def get_step_range(computed_db: str):
    """Return (min_step, max_step) or (None, None) if db not ready."""
    if not os.path.exists(computed_db):
        return None, None
    try:
        conn = sqlite3.connect(computed_db)
        c = conn.cursor()
        c.execute("SELECT MIN(step), MAX(step) FROM computed_results")
        row = c.fetchone()
        conn.close()
        return row[0], row[1]
    except Exception:
        return None, None


# ─── Background Thread ────────────────────────────────────────────────────────

class Q1DComputeThread(QThread):
    progress_signal  = pyqtSignal(int, str)
    finished_signal  = pyqtSignal(bool, str)

    def __init__(self, source_db, computed_db):
        super().__init__()
        self.source_db   = source_db
        self.computed_db = computed_db

    def run(self):
        err = compute_statistics(
            self.source_db, self.computed_db,
            progress_callback=lambda p, m: self.progress_signal.emit(p, m)
        )
        self.progress_signal.emit(100, "完成")
        if err:
            self.finished_signal.emit(False, err)
        else:
            self.finished_signal.emit(True, "")


# ─── Chart Helpers ────────────────────────────────────────────────────────────

def _plot_statistics_chart(fig, rows, metric_idx, metric_name, color):
    """rows: (step, avg_q1d, avg_dp_mean, avg_a8)"""
    fig.clear()
    ax = fig.add_subplot(111)
    style_axes(ax)
    if not rows:
        ax.text(0.5, 0.5, "无数据", transform=ax.transAxes,
                color=COLORS['text_secondary'], ha='center', va='center')
        return

    steps = [r[0] for r in rows]
    vals  = [r[metric_idx] for r in rows]

    # glow
    for lw, alpha in zip([8, 5, 3], [0.06, 0.12, 0.20]):
        ax.plot(steps, vals, '-', color=color, linewidth=lw, alpha=alpha)
    ax.plot(steps, vals, '-', color=color, linewidth=1.8, alpha=0.92)

    ax.set_title(f"{metric_name} vs 步骤", fontsize=13,
                 color=COLORS['accent_cyan'], pad=12)
    ax.set_xlabel("步骤", fontsize=11)
    ax.set_ylabel(metric_name, fontsize=11)
    fig.tight_layout()


def _plot_multi_chart(fig, rows):
    """Plot avg_q1d, avg_dp_mean, avg_a8 on 3 subplots."""
    fig.clear()
    colors = [COLORS['accent_cyan'], COLORS['accent_green'], COLORS['accent_red']]
    labels = ['avg_Q1d', 'avg_dp_mean', 'avg_A8']
    indices = [1, 2, 3]

    if not rows:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "无数据", transform=ax.transAxes,
                color=COLORS['text_secondary'], ha='center', va='center')
        return

    steps = [r[0] for r in rows]
    for i, (col, label, idx) in enumerate(zip(colors, labels, indices)):
        ax = fig.add_subplot(3, 1, i + 1)
        style_axes(ax)
        vals = [r[idx] for r in rows]
        for lw, alpha in zip([7, 4], [0.07, 0.15]):
            ax.plot(steps, vals, '-', color=col, linewidth=lw, alpha=alpha)
        ax.plot(steps, vals, '-', color=col, linewidth=1.6, alpha=0.9)
        ax.set_ylabel(label, fontsize=10, color=col)
        if i == 2:
            ax.set_xlabel("步骤", fontsize=10)

    fig.suptitle("Q1D 滑动窗口统计总览", color=COLORS['accent_cyan'],
                 fontsize=13, y=1.01)
    fig.tight_layout()


# ─── Widget ───────────────────────────────────────────────────────────────────

class Q1DWidget(QWidget):
    """Q1D 分析面板"""

    status_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── 标题 ──
        title = QLabel("Q1D 分析 — 48点滑动窗口统计")
        title.setObjectName("lbl_title")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        sub = QLabel("对 2.db 中的 results 表执行 48 点滑动窗口分析，统计 Q1d / dp_mean / A8 趋势")
        sub.setObjectName("lbl_subtitle")
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(_hline())

        # ── 数据库配置 ──
        db_group = QGroupBox("数据库配置")
        db_layout = QVBoxLayout(db_group)

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("源数据库 (2.db):"))
        self.src_edit = QLineEdit("2.db")
        src_btn = QPushButton("浏览")
        src_btn.setFixedWidth(80)
        src_btn.clicked.connect(self._choose_src)
        src_row.addWidget(self.src_edit)
        src_row.addWidget(src_btn)

        cmp_row = QHBoxLayout()
        cmp_row.addWidget(QLabel("计算结果数据库:"))
        self.cmp_edit = QLineEdit("5.db")
        cmp_btn = QPushButton("另存为")
        cmp_btn.setFixedWidth(80)
        cmp_btn.clicked.connect(self._choose_cmp)
        cmp_row.addWidget(self.cmp_edit)
        cmp_row.addWidget(cmp_btn)

        db_layout.addLayout(src_row)
        db_layout.addLayout(cmp_row)
        root.addWidget(db_group)

        # ── 进度 ──
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFixedHeight(26)
        self.status_lbl = QLabel("就绪")
        self.status_lbl.setObjectName("lbl_subtitle")
        root.addWidget(self.progress)
        root.addWidget(self.status_lbl)

        # ── 分析区（步骤选择 + 表格 + 图表） ──
        analysis_group = QGroupBox("统计查询与可视化")
        analysis_layout = QVBoxLayout(analysis_group)

        range_row = QHBoxLayout()
        range_row.setSpacing(12)
        range_row.addWidget(QLabel("起始步骤:"))
        self.start_spin = QSpinBox()
        self.start_spin.setRange(1, 999999)
        self.start_spin.setValue(1)
        self.start_spin.setFixedWidth(90)
        range_row.addWidget(self.start_spin)
        range_row.addWidget(QLabel("结束步骤:"))
        self.end_spin = QSpinBox()
        self.end_spin.setRange(1, 999999)
        self.end_spin.setValue(100)
        self.end_spin.setFixedWidth(90)
        range_row.addWidget(self.end_spin)
        self.query_btn = QPushButton("🔍  查询")
        self.query_btn.setFixedWidth(90)
        self.query_btn.clicked.connect(self._query)
        self.query_btn.setEnabled(False)
        range_row.addWidget(self.query_btn)
        range_row.addStretch()
        analysis_layout.addLayout(range_row)

        # 标签页：统计表 / 最小A8表
        self.tab = QTabWidget()
        self.tab.setFixedHeight(200)

        self.stats_table = _make_table(
            ["步骤", "avg_Q1d", "avg_dp_mean", "avg_A8"]
        )
        self.mina8_table = _make_table(
            ["步骤", "start_idx", "end_idx", "Q1d", "dp_mean", "A8"]
        )
        self.tab.addTab(self.stats_table, "统计数据")
        self.tab.addTab(self.mina8_table, "最小 A8 行")
        analysis_layout.addWidget(self.tab)

        # 图表按钮
        chart_row = QHBoxLayout()
        self.chart_all_btn = QPushButton("📈  趋势总览图")
        self.chart_all_btn.clicked.connect(self._show_all_chart)
        self.chart_all_btn.setEnabled(False)
        self.chart_q1d_btn = QPushButton("📊  Q1d 图")
        self.chart_q1d_btn.clicked.connect(lambda: self._show_single_chart(1, 'avg_Q1d', COLORS['accent_cyan']))
        self.chart_q1d_btn.setEnabled(False)
        self.chart_a8_btn = QPushButton("📊  A8 图")
        self.chart_a8_btn.clicked.connect(lambda: self._show_single_chart(3, 'avg_A8', COLORS['accent_red']))
        self.chart_a8_btn.setEnabled(False)
        chart_row.addStretch()
        chart_row.addWidget(self.chart_all_btn)
        chart_row.addWidget(self.chart_q1d_btn)
        chart_row.addWidget(self.chart_a8_btn)
        analysis_layout.addLayout(chart_row)
        root.addWidget(analysis_group)

        # ── 操作按钮 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.run_btn = QPushButton("🚀  开始计算")
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

        self._current_rows = []

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _choose_src(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "选择源数据库", "", "SQLite 数据库 (*.db);;所有文件 (*)"
        )
        if p:
            self.src_edit.setText(p)

    def _choose_cmp(self):
        p, _ = QFileDialog.getSaveFileName(
            self, "保存计算数据库", "5.db",
            "SQLite 数据库 (*.db);;所有文件 (*)"
        )
        if p:
            self.cmp_edit.setText(p)

    def _reset(self):
        self.src_edit.setText("2.db")
        self.cmp_edit.setText("5.db")
        self.progress.setValue(0)
        self.status_lbl.setText("就绪")
        self.start_spin.setValue(1)
        self.end_spin.setValue(100)
        self.stats_table.setRowCount(0)
        self.mina8_table.setRowCount(0)
        self.query_btn.setEnabled(False)
        self.chart_all_btn.setEnabled(False)
        self.chart_q1d_btn.setEnabled(False)
        self.chart_a8_btn.setEnabled(False)
        self._current_rows = []

    def _run(self):
        src = self.src_edit.text().strip()
        cmp = self.cmp_edit.text().strip()
        if not os.path.exists(src):
            QMessageBox.critical(self, "错误", f"源数据库不存在:\n{src}")
            return
        self.run_btn.setEnabled(False)
        self.query_btn.setEnabled(False)
        self.progress.setValue(0)
        self.status_lbl.setText("计算中 …")

        self._thread = Q1DComputeThread(src, cmp)
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
            cmp = self.cmp_edit.text().strip()
            mn, mx = get_step_range(cmp)
            if mn is not None:
                self.start_spin.setValue(mn)
                self.end_spin.setValue(min(mn + 200, mx))
                self.start_spin.setRange(mn, mx)
                self.end_spin.setRange(mn, mx)
            self.query_btn.setEnabled(True)
            self.status_lbl.setText("计算完成，可开始查询")
            self.status_changed.emit("Q1D 计算完成")
            QMessageBox.information(self, "完成", "Q1D 统计计算完成！")
        else:
            self.status_lbl.setText("计算失败")
            self.status_changed.emit("Q1D 计算失败")
            QMessageBox.critical(self, "失败", msg)

    def _query(self):
        cmp = self.cmp_edit.text().strip()
        if not os.path.exists(cmp):
            QMessageBox.critical(self, "错误", f"计算数据库不存在:\n{cmp}")
            return
        s = self.start_spin.value()
        e = self.end_spin.value()
        if e < s:
            QMessageBox.warning(self, "警告", "结束步骤不能小于起始步骤")
            return

        rows = get_summary_data(cmp, s, e)
        self._current_rows = rows

        self.stats_table.setRowCount(0)
        for r in rows:
            ri = self.stats_table.rowCount()
            self.stats_table.insertRow(ri)
            for ci, val in enumerate(r):
                item = QTableWidgetItem(_fmt(val))
                item.setTextAlignment(Qt.AlignCenter)
                self.stats_table.setItem(ri, ci, item)

        mina8 = get_min_a8_rows(cmp, s, e)
        self.mina8_table.setRowCount(0)
        for d in mina8:
            ri = self.mina8_table.rowCount()
            self.mina8_table.insertRow(ri)
            for ci, key in enumerate(['step', 'start_index', 'end_index', 'Q1d', 'dp_mean', 'A8']):
                val = d.get(key, '')
                item = QTableWidgetItem(_fmt(val))
                item.setTextAlignment(Qt.AlignCenter)
                self.mina8_table.setItem(ri, ci, item)

        has = len(rows) > 0
        self.chart_all_btn.setEnabled(has)
        self.chart_q1d_btn.setEnabled(has)
        self.chart_a8_btn.setEnabled(has)
        self.status_lbl.setText(f"查询完成 — {len(rows)} 行")

    def _show_all_chart(self):
        if not self._current_rows:
            return
        dlg = ChartDialog(self, title="Q1D 统计趋势总览", figsize=(11, 9))
        _plot_multi_chart(dlg.get_figure(), self._current_rows)
        dlg.refresh()
        dlg.exec_()

    def _show_single_chart(self, idx, label, color):
        if not self._current_rows:
            return
        dlg = ChartDialog(self, title=f"{label} 趋势图")
        _plot_statistics_chart(dlg.get_figure(), self._current_rows, idx, label, color)
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
