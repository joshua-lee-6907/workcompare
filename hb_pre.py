"""hb_pre.py – Tab 2: Data segmentation & anomaly detection."""

import os
import sqlite3

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QGroupBox, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from hb_common import MPL_STYLE, BG_DARK, ACCENT, DANGER, SUCCESS, WARNING


# ─── Core logic ──────────────────────────────────────────────────────────────

def fetch_data_from_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT time, DVH, DP FROM data ORDER BY time")
        rows = cursor.fetchall()
        return [(float(t), float(d), float(p)) for t, d, p in rows]
    finally:
        conn.close()


def flag_outliers(data, window_size=12, threshold=15):
    flags = [False] * len(data)
    for start in range(len(data) - window_size + 1):
        window = data[start:start + window_size]
        dps = [p[2] for p in window]
        if max(dps) - min(dps) > threshold:
            for i in range(start, start + window_size):
                flags[i] = True
    return flags


def segment_non_outlier_data(data, flags):
    segments, cur = [], []
    for i, point in enumerate(data):
        if not flags[i]:
            cur.append(point)
        else:
            if cur:
                segments.append(cur)
                cur = []
    if cur:
        segments.append(cur)
    return segments


def save_segments_to_db(segments, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for idx, seg in enumerate(segments, start=1):
        tname = f"Segment_{idx}"
        cursor.execute(f"DROP TABLE IF EXISTS {tname}")
        cursor.execute(f"""CREATE TABLE {tname}
            (id INTEGER PRIMARY KEY AUTOINCREMENT, time REAL, DVH REAL, DP REAL)""")
        cursor.executemany(
            f"INSERT INTO {tname} (time, DVH, DP) VALUES (?, ?, ?)", seg)
    conn.commit()
    conn.close()


# ─── Background worker ────────────────────────────────────────────────────────

class PreWorker(QThread):
    result  = pyqtSignal(object, object, object)   # data, flags, segments
    error   = pyqtSignal(str)

    def __init__(self, src_db, tgt_db):
        super().__init__()
        self.src_db = src_db
        self.tgt_db = tgt_db

    def run(self):
        try:
            data = fetch_data_from_db(self.src_db)
        except Exception as e:
            self.error.emit(f"读取源数据库出错：{e}")
            return
        if not data:
            self.error.emit("源数据库中没有数据。")
            return
        flags    = flag_outliers(data)
        segments = segment_non_outlier_data(data, flags)
        try:
            save_segments_to_db(segments, self.tgt_db)
        except Exception as e:
            self.error.emit(f"保存分段数据库出错：{e}")
            return
        self.result.emit(data, flags, segments)


# ─── Embedded chart ───────────────────────────────────────────────────────────

class PreChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)

        self.fig = Figure(figsize=(9, 4), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet(f"background: #101d42;")

        vl.addWidget(self.toolbar)
        vl.addWidget(self.canvas)

    def plot(self, data, flags, segments):
        matplotlib.rcParams.update(MPL_STYLE)
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor("#0d1836")

        times_all = [p[0] for p in data]
        dps_all   = [p[2] for p in data]

        seg_colors = ["#00ffe0","#fffb00","#ff00f7","#ff9000","#3800ff","#00ff57","#ff0057"]
        # all data (glow)
        for lw, a in [(10,0.06),(7,0.11),(4,0.18)]:
            ax.plot(times_all, dps_all, color=ACCENT, lw=lw, alpha=a)
        ax.plot(times_all, dps_all, color=ACCENT, lw=2.2, alpha=0.9, label="全部数据")

        # outliers
        out_t = [data[i][0] for i, f in enumerate(flags) if f]
        out_dp = [data[i][2] for i, f in enumerate(flags) if f]
        if out_t:
            ax.scatter(out_t, out_dp, color=DANGER, s=38, zorder=5,
                       edgecolors="white", linewidths=0.8, label="异常点")

        # segments
        for k, seg in enumerate(segments):
            c = seg_colors[k % len(seg_colors)]
            st = [p[0] for p in seg]
            sd = [p[2] for p in seg]
            ax.plot(st, sd, color=c, lw=2.2, alpha=0.88,
                    label=f"分段 {k+1}" if k < 5 else None)

        ax.set_title("DP 随时间变化 · 分段与异常检测", color=ACCENT, fontsize=13)
        ax.set_xlabel("时间", color="#e9f1fb")
        ax.set_ylabel("DP (压差)", color="#e9f1fb")
        ax.legend(fontsize=10, loc="upper right")
        self.canvas.draw()


# ─── Tab widget ───────────────────────────────────────────────────────────────

class PreTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker   = None
        self._last_data = self._last_flags = self._last_segs = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(20, 16, 20, 16)

        title = QLabel("🔬  数据分段与异常检测")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        splitter = QSplitter(Qt.Vertical)

        # ── Control panel ──
        ctrl = QWidget()
        cl = QVBoxLayout(ctrl)
        cl.setSpacing(10)
        cl.setContentsMargins(0, 0, 0, 0)

        grp_src = QGroupBox("源数据库 (d1.db)")
        sl = QHBoxLayout(grp_src)
        self.src_edit = QLineEdit("d1.db")
        btn_src = QPushButton("浏览")
        btn_src.setObjectName("secondary")
        btn_src.setFixedWidth(70)
        btn_src.clicked.connect(self._choose_src)
        sl.addWidget(self.src_edit)
        sl.addWidget(btn_src)
        cl.addWidget(grp_src)

        grp_tgt = QGroupBox("保存分段数据库 (30.db)")
        tl = QHBoxLayout(grp_tgt)
        self.tgt_edit = QLineEdit("30.db")
        btn_tgt = QPushButton("另存为…")
        btn_tgt.setObjectName("secondary")
        btn_tgt.setFixedWidth(90)
        btn_tgt.clicked.connect(self._choose_tgt)
        tl.addWidget(self.tgt_edit)
        tl.addWidget(btn_tgt)
        cl.addWidget(grp_tgt)

        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("status")
        cl.addWidget(self.lbl_status)

        btn_row = QHBoxLayout()
        self.btn_run = QPushButton("🚀  执行分段并保存")
        self.btn_run.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.btn_run.clicked.connect(self._run)

        self.btn_plot = QPushButton("📊  显示图表")
        self.btn_plot.setObjectName("secondary")
        self.btn_plot.clicked.connect(self._show_plot)
        self.btn_plot.setEnabled(False)

        btn_reset = QPushButton("↺  复位")
        btn_reset.setObjectName("reset")
        btn_reset.clicked.connect(self._reset)

        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_plot)
        btn_row.addWidget(btn_reset)
        cl.addLayout(btn_row)
        splitter.addWidget(ctrl)

        # ── Chart area ──
        self.chart = PreChart()
        splitter.addWidget(self.chart)
        splitter.setSizes([220, 380])

        root.addWidget(splitter)

    # ── Slots ──────────────────────────────────────────────────────────────

    def _choose_src(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择源数据库", "",
                                           "SQLite DB (*.db);;所有文件 (*)")
        if p:
            self.src_edit.setText(p)

    def _choose_tgt(self):
        p, _ = QFileDialog.getSaveFileName(self, "保存分段数据库", "30.db",
                                           "SQLite DB (*.db);;所有文件 (*)")
        if p:
            self.tgt_edit.setText(p)

    def _reset(self):
        self.src_edit.setText("d1.db")
        self.tgt_edit.setText("30.db")
        self.lbl_status.setText("已复位")
        self.btn_plot.setEnabled(False)
        self._last_data = self._last_flags = self._last_segs = None
        self.chart.fig.clear()
        self.chart.canvas.draw()

    def _run(self):
        src = self.src_edit.text().strip()
        tgt = self.tgt_edit.text().strip()
        if not os.path.exists(src):
            QMessageBox.critical(self, "错误", "源数据库文件不存在！")
            return
        if not tgt:
            QMessageBox.critical(self, "错误", "请输入保存数据库文件名！")
            return
        self.btn_run.setEnabled(False)
        self.lbl_status.setText("正在处理…")
        self._worker = PreWorker(src, tgt)
        self._worker.result.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, data, flags, segments):
        self.btn_run.setEnabled(True)
        self._last_data  = data
        self._last_flags = flags
        self._last_segs  = segments
        n_out = sum(flags)
        self.lbl_status.setText(
            f"✅ 完成！共 {len(segments)} 段，异常点 {n_out} 个。")
        self.btn_plot.setEnabled(True)
        self.chart.plot(data, flags, segments)
        QMessageBox.information(self, "完成",
            f"分段结果已保存到 {self.tgt_edit.text()}\n共 {len(segments)} 段。")

    def _on_error(self, msg):
        self.btn_run.setEnabled(True)
        self.lbl_status.setText("❌ 出错")
        QMessageBox.critical(self, "错误", msg)

    def _show_plot(self):
        if self._last_data:
            self.chart.plot(self._last_data, self._last_flags, self._last_segs)
        else:
            QMessageBox.information(self, "提示", "请先执行分段操作。")
