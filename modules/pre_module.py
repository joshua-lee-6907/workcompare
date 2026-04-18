"""
数据预处理模块 — 滑动窗口异常检测与数据分段
Pre-processing Module: outlier detection and segmentation
Ported from preweb.py
"""

import os
import sqlite3

import numpy as np
from matplotlib import font_manager

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QGroupBox, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from .styles import COLORS, ChartDialog, style_axes


# ─── Core Logic ───────────────────────────────────────────────────────────────

def fetch_data_from_db(db_path: str):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute("SELECT time, DVH, DP FROM data ORDER BY time")
        rows = c.fetchall()
        return [(float(t), float(d), float(p)) for t, d, p in rows]
    finally:
        conn.close()


def flag_outliers(data, window_size=12, threshold=15):
    flags = [False] * len(data)
    for start in range(len(data) - window_size + 1):
        window = data[start:start + window_size]
        _, _, dps = zip(*window)
        if max(dps) - min(dps) > threshold:
            for i in range(start, start + window_size):
                flags[i] = True
    return flags


def segment_non_outlier_data(data, flags):
    segments, current = [], []
    for i, point in enumerate(data):
        if not flags[i]:
            current.append(point)
        else:
            if current:
                segments.append(current)
                current = []
    if current:
        segments.append(current)
    return segments


def save_segments_to_db(segments, db_path: str):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for idx, seg in enumerate(segments, start=1):
        tname = f"Segment_{idx}"
        c.execute(f"DROP TABLE IF EXISTS {tname}")
        c.execute(f"""
            CREATE TABLE {tname} (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                time REAL,
                DVH  REAL,
                DP   REAL
            )
        """)
        for t, dvh, dp in seg:
            c.execute(f"INSERT INTO {tname} (time, DVH, DP) VALUES (?,?,?)", (t, dvh, dp))
    conn.commit()
    conn.close()


def _get_chinese_font():
    zh_fonts = [
        "Microsoft YaHei", "微软雅黑", "SimHei", "黑体",
        "PingFang SC", "Hiragino Sans GB", "WenQuanYi Micro Hei",
        "Arial Unicode MS"
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for fn in zh_fonts:
        if fn in available:
            return fn
    import matplotlib.pyplot as plt
    return plt.rcParams['font.sans-serif'][0]


def plot_data_to_figure(fig, data, flags, segments):
    """Render the segmentation chart onto an existing matplotlib Figure."""
    import matplotlib.pyplot as plt
    plt.rcParams['axes.unicode_minus'] = False

    bg_color = COLORS['chart_bg']
    all_line_color = COLORS['accent_cyan']
    outlier_color = COLORS['accent_red']
    segment_colors = ["#00ffe0", "#fffb00", "#ff00f7", "#ff9000",
                      "#3800ff", "#00ff57", "#ff0057"]

    font_name = _get_chinese_font()
    plt.rcParams['font.sans-serif'] = [font_name]

    fig.clear()
    ax = fig.add_subplot(111)
    ax.set_facecolor(bg_color)
    style_axes(ax)

    times_all, _, dps_all = zip(*data)

    # Glow: base data
    for lw, alpha in zip([13, 9, 6, 3], [0.05, 0.09, 0.14, 0.22]):
        ax.plot(times_all, dps_all, '-', color=all_line_color,
                linewidth=lw, alpha=alpha, zorder=1)
    ax.plot(times_all, dps_all, 'o-', color=all_line_color,
            markersize=3, linewidth=2.5, alpha=0.9, zorder=2)

    # Outliers
    outlier_pts = [data[i] for i, f in enumerate(flags) if f]
    if outlier_pts:
        ot, _, od = zip(*outlier_pts)
        for s in [30, 18, 10]:
            ax.scatter(ot, od, color=outlier_color, alpha=0.06, s=s, zorder=4)
        ax.scatter(ot, od, color=outlier_color, alpha=0.9, s=36,
                   edgecolors='#fff', linewidths=1.0, zorder=5,
                   label=f"异常点 ({len(outlier_pts)})")

    # Segments
    for i, seg in enumerate(segments):
        st, _, sd = zip(*seg)
        col = segment_colors[i % len(segment_colors)]
        for lw, alpha in zip([7, 5, 3], [0.08, 0.12, 0.18]):
            ax.plot(st, sd, '-', color=col, linewidth=lw, alpha=alpha, zorder=3)
        ax.plot(st, sd, '-', color=col, linewidth=2.0, alpha=0.88,
                zorder=4, label=f"片段 {i+1}")

    ax.axhline(y=0, color='#1e294f', linewidth=1.0, alpha=0.5,
               linestyle='--', zorder=0)
    ax.set_title("DP 随时间变化 · 分段与异常检测", fontsize=14,
                 color=COLORS['accent_cyan'], pad=16, fontweight="bold")
    ax.set_xlabel("时间 (h)", fontsize=12)
    ax.set_ylabel("DP (压差)", fontsize=12)

    if len(segments) + (1 if outlier_pts else 0) <= 12:
        ax.legend(fontsize=9, facecolor='#0c1530', edgecolor='#1a2d5a',
                  labelcolor='#d8eeff', loc='upper right')

    fig.tight_layout()


# ─── Background Thread ────────────────────────────────────────────────────────

class PreThread(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, object, object, object)

    def __init__(self, src_db, tgt_db, window_size=12, threshold=15):
        super().__init__()
        self.src_db = src_db
        self.tgt_db = tgt_db
        self.window_size = window_size
        self.threshold = threshold

    def run(self):
        try:
            self.progress_signal.emit("正在读取原始数据 …")
            data = fetch_data_from_db(self.src_db)
            if not data:
                self.finished_signal.emit(False, "未读取到数据", None, None, None)
                return
            self.progress_signal.emit(f"正在检测异常点 (共 {len(data)} 行) …")
            flags = flag_outliers(data, self.window_size, self.threshold)
            self.progress_signal.emit("正在分段 …")
            segments = segment_non_outlier_data(data, flags)
            self.progress_signal.emit("正在写入数据库 …")
            save_segments_to_db(segments, self.tgt_db)
            self.finished_signal.emit(True, "", data, flags, segments)
        except Exception as e:
            self.finished_signal.emit(False, str(e), None, None, None)


# ─── Widget ───────────────────────────────────────────────────────────────────

class PreWidget(QWidget):
    """数据预处理面板"""

    status_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_data = None
        self._last_flags = None
        self._last_segments = None
        self._thread = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── 标题 ──
        title = QLabel("数据预处理 — 异常检测与分段")
        title.setObjectName("lbl_title")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        sub = QLabel("使用滑动窗口算法检测 DP 异常，将正常数据分段保存到目标数据库")
        sub.setObjectName("lbl_subtitle")
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(_hline())

        # ── 数据库选择 ──
        db_group = QGroupBox("数据库配置")
        db_layout = QVBoxLayout(db_group)
        db_layout.setSpacing(10)

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("源数据库:"))
        self.src_edit = QLineEdit("d1.db")
        src_btn = QPushButton("浏览")
        src_btn.setFixedWidth(80)
        src_btn.clicked.connect(self._choose_src)
        src_row.addWidget(self.src_edit)
        src_row.addWidget(src_btn)

        tgt_row = QHBoxLayout()
        tgt_row.addWidget(QLabel("目标数据库:"))
        self.tgt_edit = QLineEdit("30.db")
        tgt_btn = QPushButton("另存为")
        tgt_btn.setFixedWidth(80)
        tgt_btn.clicked.connect(self._choose_tgt)
        tgt_row.addWidget(self.tgt_edit)
        tgt_row.addWidget(tgt_btn)

        db_layout.addLayout(src_row)
        db_layout.addLayout(tgt_row)
        root.addWidget(db_group)

        # ── 参数 ──
        param_group = QGroupBox("算法参数")
        param_layout = QHBoxLayout(param_group)
        param_layout.setSpacing(24)
        param_layout.addWidget(QLabel("滑动窗口大小:"))
        from PyQt5.QtWidgets import QSpinBox
        self.win_spin = QSpinBox()
        self.win_spin.setRange(4, 100)
        self.win_spin.setValue(12)
        self.win_spin.setFixedWidth(80)
        param_layout.addWidget(self.win_spin)
        param_layout.addSpacing(20)
        param_layout.addWidget(QLabel("异常阈值 (DP 范围):"))
        from PyQt5.QtWidgets import QDoubleSpinBox
        self.thr_spin = QDoubleSpinBox()
        self.thr_spin.setRange(0.1, 1000)
        self.thr_spin.setValue(15.0)
        self.thr_spin.setSingleStep(0.5)
        self.thr_spin.setFixedWidth(100)
        param_layout.addWidget(self.thr_spin)
        param_layout.addStretch()
        root.addWidget(param_group)

        # ── 状态 ──
        self.status_lbl = QLabel("就绪")
        self.status_lbl.setObjectName("lbl_subtitle")
        root.addWidget(self.status_lbl)

        # ── 结果摘要 ──
        self.result_lbl = QLabel("")
        self.result_lbl.setObjectName("lbl_info")
        root.addWidget(self.result_lbl)

        # ── 操作按钮 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.run_btn = QPushButton("🚀  执行分段与保存")
        self.run_btn.setObjectName("btn_primary")
        self.run_btn.clicked.connect(self._run)
        self.run_btn.setCursor(Qt.PointingHandCursor)

        self.plot_btn = QPushButton("📊  查看可视化")
        self.plot_btn.clicked.connect(self._show_chart)
        self.plot_btn.setCursor(Qt.PointingHandCursor)
        self.plot_btn.setEnabled(False)

        self.reset_btn = QPushButton("↺  复位")
        self.reset_btn.setObjectName("btn_reset")
        self.reset_btn.setFixedWidth(100)
        self.reset_btn.clicked.connect(self._reset)
        self.reset_btn.setCursor(Qt.PointingHandCursor)

        btn_row.addStretch()
        btn_row.addWidget(self.reset_btn)
        btn_row.addWidget(self.plot_btn)
        btn_row.addWidget(self.run_btn)
        root.addLayout(btn_row)
        root.addStretch()

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _choose_src(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择源数据库", "", "SQLite 数据库 (*.db);;所有文件 (*)")
        if p:
            self.src_edit.setText(p)

    def _choose_tgt(self):
        p, _ = QFileDialog.getSaveFileName(self, "保存目标数据库", "30.db",
                                           "SQLite 数据库 (*.db);;所有文件 (*)")
        if p:
            self.tgt_edit.setText(p)

    def _reset(self):
        self.src_edit.setText("d1.db")
        self.tgt_edit.setText("30.db")
        self.win_spin.setValue(12)
        self.thr_spin.setValue(15.0)
        self.status_lbl.setText("就绪")
        self.result_lbl.setText("")
        self.plot_btn.setEnabled(False)
        self._last_data = self._last_flags = self._last_segments = None

    def _run(self):
        src = self.src_edit.text().strip()
        tgt = self.tgt_edit.text().strip()
        if not os.path.exists(src):
            QMessageBox.critical(self, "错误", f"源数据库不存在:\n{src}")
            return
        if not tgt:
            QMessageBox.critical(self, "错误", "请指定目标数据库路径！")
            return

        self.run_btn.setEnabled(False)
        self.plot_btn.setEnabled(False)
        self.status_lbl.setText("处理中 …")

        self._thread = PreThread(src, tgt, self.win_spin.value(), self.thr_spin.value())
        self._thread.progress_signal.connect(self._on_progress)
        self._thread.finished_signal.connect(self._on_finished)
        self._thread.start()

    def _on_progress(self, msg):
        self.status_lbl.setText(msg)
        self.status_changed.emit(msg)

    def _on_finished(self, ok, msg, data, flags, segments):
        self.run_btn.setEnabled(True)
        if ok:
            self._last_data = data
            self._last_flags = flags
            self._last_segments = segments
            n_out = sum(flags)
            n_seg = len(segments)
            self.result_lbl.setText(
                f"✔ 完成 — 共 {len(data):,} 行数据，检出异常点 {n_out:,} 个，分为 {n_seg} 段"
            )
            self.status_lbl.setText("分段完成")
            self.plot_btn.setEnabled(True)
            self.status_changed.emit(f"预处理完成 — {n_seg} 段")
            QMessageBox.information(
                self, "完成",
                f"分段结果已保存至: {self.tgt_edit.text()}\n"
                f"共分为 {n_seg} 段，异常点 {n_out:,} 个。"
            )
        else:
            self.status_lbl.setText("失败")
            self.status_changed.emit("预处理失败")
            QMessageBox.critical(self, "处理失败", msg)

    def _show_chart(self):
        if not self._last_data:
            QMessageBox.information(self, "提示", "请先执行分段操作。")
            return
        dlg = ChartDialog(self, title="分段与异常检测可视化")
        fig = dlg.get_figure()
        plot_data_to_figure(fig, self._last_data, self._last_flags, self._last_segments)
        dlg.refresh()
        dlg.exec_()


def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f
