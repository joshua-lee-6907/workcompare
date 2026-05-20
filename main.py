#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import platform
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QMessageBox,
    QAbstractItemView, QSplitter, QFileDialog, QGroupBox, QSpinBox, QMainWindow,
    QSizePolicy
)

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.figure import Figure
import matplotlib.font_manager as fm
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

try:
    from qfluentwidgets import (
        FluentWindow, FluentIcon, setTheme, Theme, ScrollArea, PushButton, PrimaryPushButton,
        ComboBox, LineEdit, CheckBox, BodyLabel, TitleLabel, StrongBodyLabel, SimpleCardWidget,
    )
except Exception:
    from qfluentwidgets import (
        MSFluentWindow as FluentWindow, FluentIcon, setTheme, Theme, ScrollArea, PushButton, PrimaryPushButton,
        ComboBox, LineEdit, CheckBox, BodyLabel, TitleLabel, StrongBodyLabel, SimpleCardWidget,
    )


def set_chinese_font():
    candidates = {
        "Windows": [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc"],
        "Darwin": ["/System/Library/Fonts/PingFang.ttc"],
    }.get(platform.system(), ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"])

    chosen = "SimHei"
    for fp in candidates:
        if os.path.exists(fp):
            try:
                fm.fontManager.addfont(fp)
                chosen = fm.FontProperties(fname=fp).get_name()
                break
            except Exception:
                pass

    rcParams["font.family"] = "sans-serif"
    rcParams["font.sans-serif"] = ["SimHei", chosen, "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False


set_chinese_font()
plt.style.use("default")
plt.rcParams.update({"figure.dpi": 120, "axes.grid": True, "grid.alpha": 0.28, "grid.linestyle": "--"})
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")


class DataProcessor:
    def __init__(self):
        self.variables = {}
        self.length = 0

    def get_sheet_names(self, file_path):
        return pd.ExcelFile(file_path).sheet_names

    def load_from_excel(self, file_path, sheet_name):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            self.variables = {}
            for col in df.columns:
                ser = pd.to_numeric(df[col], errors="coerce")
                self.variables[str(col)] = ser.to_numpy() if ser.notna().any() else df[col].astype(str).tolist()
            self.length = int(df.shape[0])
            return True, ""
        except Exception as e:
            return False, str(e)

    def names(self):
        return list(self.variables.keys())

    def data(self, key):
        return self.variables.get(key, [])


class PlotCanvas(FigureCanvas):
    def __init__(self):
        self.figure = Figure(facecolor="white", dpi=110)
        super().__init__(self.figure)

    def draw_plot(self, x_data, y_data_dict, x_label, y_label, title, start_idx, end_idx, mode, show_grid):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#f8fafc")
        x = np.asarray(x_data)[start_idx:end_idx + 1]
        palette = ["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#d62728", "#17becf"]

        for i, (name, arr) in enumerate(y_data_dict.items()):
            y = np.asarray(arr)[start_idx:end_idx + 1]
            c = palette[i % len(palette)]
            if mode in ("line", "line_scatter", "area"):
                ax.plot(x, y, color=c, linewidth=2.2, label=name)
            if mode in ("scatter", "line_scatter"):
                ax.scatter(x, y, s=34, color=c, edgecolor="white", linewidth=0.8)
            if mode == "area":
                ax.fill_between(x, y, alpha=0.2, color=c)

        ax.set_title(title, fontsize=14, fontweight="bold", color="#0f172a")
        ax.set_xlabel(x_label, fontsize=11, color="#1e293b")
        ax.set_ylabel(y_label, fontsize=11, color="#1e293b")
        if show_grid:
            ax.grid(True)
        ax.legend(loc="upper left", frameon=True)
        self.figure.tight_layout()
        self.draw()

    def draw_pie(self, y_data_dict, title):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        totals = []
        labels = []
        for k, v in y_data_dict.items():
            vals = np.asarray(v, dtype=float)
            vals = vals[np.isfinite(vals)]
            if vals.size:
                labels.append(k)
                totals.append(float(np.nanmean(vals)))
        if not totals:
            return
        colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#d62728", "#17becf"]
        ax.pie(totals, labels=labels, autopct="%1.1f%%", startangle=120, colors=colors[:len(totals)], wedgeprops={"linewidth":1, "edgecolor":"white"})
        ax.set_title(title, fontsize=14, fontweight="bold", color="#0f172a")
        self.figure.tight_layout()
        self.draw()


class PlotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图表展示区")
        self.setWindowIcon(QIcon())
        self.resize(1320, 780)
        self.canvas = PlotCanvas()
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(NavigationToolbar(self.canvas, self))
        layout.addWidget(self.canvas)
        self.setCentralWidget(central)


class ExcelVisualizerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dp = DataProcessor()
        self.plot_window = PlotWindow()
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav = QWidget(self)
        nav.setStyleSheet("background:#0b2a4a;")
        navl = QHBoxLayout(nav)
        navl.setContentsMargins(20, 12, 20, 12)
        navl.addWidget(TitleLabel("Data Analysis Management System", self))
        self.clock = StrongBodyLabel("", self)
        navl.addStretch(1)
        navl.addWidget(self.clock)
        root.addWidget(nav)

        body = QSplitter(Qt.Horizontal, self)
        body.setChildrenCollapsible(False)
        body.setHandleWidth(8)

        ctrl = self._control_panel()
        right = QWidget(self)
        rv = QVBoxLayout(right)
        tip = BodyLabel("图表展示区已独立为可拖动/可调整大小窗口。点击“打开图表窗口”查看。", self)
        rv.addWidget(tip)
        rv.addStretch(1)

        body.addWidget(ctrl)
        body.addWidget(right)
        body.setSizes([460, 900])
        root.addWidget(body, 1)

        self.setStyleSheet("""
        QWidget{background:#f3f4f6;color:#111827;font-size:13px;}
        QGroupBox{background:white;border:1px solid #d1d5db;border-radius:10px;margin-top:10px;padding:10px;}
        QGroupBox::title{left:10px;padding:0 6px;color:#1f2937;font-weight:600;}
        """)

    def _control_panel(self):
        sa = ScrollArea(self)
        sa.setWidgetResizable(True)
        panel = QWidget()
        sa.setWidget(panel)
        l = QVBoxLayout(panel)

        self.file_edit = LineEdit(); self.file_edit.setReadOnly(True); self.file_edit.setPlaceholderText("未选择Excel文件")
        self.sheet_combo = ComboBox()
        b_file = PrimaryPushButton("选择Excel"); b_file.clicked.connect(self.choose_file)
        b_load = PushButton("读取Sheet"); b_load.clicked.connect(self.load_sheet)

        box = QGroupBox("数据源")
        bl = QVBoxLayout(box)
        r1 = QHBoxLayout(); r1.addWidget(b_file); r1.addWidget(self.file_edit, 1)
        r2 = QHBoxLayout(); r2.addWidget(self.sheet_combo, 1); r2.addWidget(b_load)
        bl.addLayout(r1); bl.addLayout(r2)
        l.addWidget(box)

        self.title_edit = LineEdit(); self.title_edit.setText("企业数据分析看板")
        self.xname = LineEdit(); self.xname.setText("X轴")
        self.yname = LineEdit(); self.yname.setText("Y轴")
        self.mode_combo = ComboBox(); self.mode_combo.addItems(["散点图", "折线图", "折线+散点图", "面积图", "饼图"])
        self.start = QSpinBox(); self.end = QSpinBox()
        self.x_combo = ComboBox(); self.y_list = QListWidget(); self.y_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.grid = CheckBox("显示网格"); self.grid.setChecked(True)

        for t, w in [("图表标题", self.title_edit), ("X轴名称", self.xname), ("Y轴名称", self.yname), ("图表类型", self.mode_combo), ("X变量", self.x_combo), ("Y变量(多选)", self.y_list), ("起始索引", self.start), ("结束索引", self.end), ("图表网格", self.grid)]:
            g = QGroupBox(t); gl = QVBoxLayout(g); gl.addWidget(w); l.addWidget(g)

        b_plot = PrimaryPushButton("生成图表"); b_plot.clicked.connect(self.plot)
        b_show = PushButton("打开图表窗口"); b_show.clicked.connect(self.plot_window.show)
        b_save = PushButton("保存图片"); b_save.clicked.connect(self.save_fig)
        for b in (b_plot, b_show, b_save):
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            l.addWidget(b)

        l.addStretch(1)
        return sa

    def _tick(self):
        self.clock.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择Excel", "", "Excel (*.xlsx *.xls)")
        if not path:
            return
        self.file_edit.setText(path)
        try:
            self.sheet_combo.clear()
            self.sheet_combo.addItems(self.dp.get_sheet_names(path))
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def load_sheet(self):
        p = self.file_edit.text().strip(); s = self.sheet_combo.currentText().strip()
        if not p or not s:
            QMessageBox.warning(self, "提示", "请先选择文件与Sheet")
            return
        ok, err = self.dp.load_from_excel(p, s)
        if not ok:
            QMessageBox.critical(self, "错误", err)
            return
        names = self.dp.names()
        n = max(0, self.dp.length - 1)
        self.start.setMaximum(n); self.end.setMaximum(n); self.end.setValue(n)
        self.x_combo.clear(); self.x_combo.addItems(names)
        self.y_list.clear(); self.y_list.addItems(names)

    def plot(self):
        xvar = self.x_combo.currentText().strip()
        ys = self.y_list.selectedItems()
        if not xvar or not ys:
            QMessageBox.warning(self, "提示", "请选择X和至少一个Y")
            return
        x = np.asarray(self.dp.data(xvar))
        yd = {i.text(): np.asarray(self.dp.data(i.text())) for i in ys}
        s, e = self.start.value(), self.end.value()
        e = min(e, min([len(x)-1] + [len(v)-1 for v in yd.values()]))
        mode = {"散点图":"scatter", "折线图":"line", "折线+散点图":"line_scatter", "面积图":"area", "饼图":"pie"}[self.mode_combo.currentText()]
        if mode == "pie":
            self.plot_window.canvas.draw_pie(yd, self.title_edit.text().strip() or "饼图分析")
        else:
            self.plot_window.canvas.draw_plot(x, yd, self.xname.text().strip() or xvar, self.yname.text().strip() or "Y", self.title_edit.text().strip() or "数据分析", s, e, mode, self.grid.isChecked())
        self.plot_window.show()

    def save_fig(self):
        if not self.plot_window.canvas.figure.axes:
            QMessageBox.warning(self, "提示", "请先生成图表")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存", "chart.png", "PNG (*.png);;TIFF (*.tiff);;SVG (*.svg);;PDF (*.pdf)")
        if not path:
            return
        ext = os.path.splitext(path)[1].lower() or ".png"
        if ext == "": path += ".png"
        fmt = {".png":"png", ".tiff":"tiff", ".tif":"tiff", ".svg":"svg", ".pdf":"pdf"}.get(ext, "png")
        self.plot_window.canvas.figure.savefig(path, dpi=300, format=fmt, bbox_inches="tight")


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        page = ExcelVisualizerPage(self)
        page.setObjectName("enterpriseAnalysisPage")
        self.addSubInterface(page, FluentIcon.LIBRARY, "企业数据分析")
        self.setWindowTitle("企业数据分析管理系统")
        self.resize(1680, 960)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("企业数据分析管理系统")
    app.setFont(QFont("Microsoft YaHei", 10))
    setTheme(Theme.LIGHT)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
