from __future__ import annotations

import os
import platform
import re
import warnings

import numpy as np
import pandas as pd

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QListWidget,
        QMessageBox, QAbstractItemView, QButtonGroup, QRadioButton, QFileDialog,
        QGroupBox
    )
except Exception:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QListWidget,
        QMessageBox, QAbstractItemView, QButtonGroup, QRadioButton, QFileDialog,
        QGroupBox
    )

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib.font_manager as fm
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

try:
    from qfluentwidgets import (
        ScrollArea, PushButton, PrimaryPushButton, ComboBox, LineEdit,
        CheckBox, BodyLabel, TitleLabel, SimpleCardWidget,
    )
except Exception:
    # fallback aliases when qfluentwidgets unavailable
    from PyQt5.QtWidgets import QScrollArea as ScrollArea, QPushButton as PushButton, QPushButton as PrimaryPushButton, QComboBox as ComboBox, QLineEdit as LineEdit, QCheckBox as CheckBox, QLabel as BodyLabel, QLabel as TitleLabel, QWidget as SimpleCardWidget


plt.style.use("default")
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")


def set_chinese_font() -> str:
    candidates = []
    if platform.system() == "Windows":
        candidates = [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc"]
    elif platform.system() == "Darwin":
        candidates = ["/System/Library/Fonts/PingFang.ttc"]
    else:
        candidates = ["/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"]

    chosen = "SimHei"
    for fp in candidates:
        if os.path.exists(fp):
            try:
                fm.fontManager.addfont(fp)
                chosen = fm.FontProperties(fname=fp).get_name()
                break
            except Exception:
                pass

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["SimHei", chosen, "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return chosen


set_chinese_font()


def axis_group_key(var_name: str):
    m = re.match(r"^([A-Za-z\u4e00-\u9fff]+)", var_name or "")
    return m.group(1) if m else var_name


class DataProcessor:
    def __init__(self):
        self.variables = {}
        self.length = 0

    def get_sheet_names(self, file_path):
        return pd.ExcelFile(file_path).sheet_names

    def load_from_excel(self, file_path, sheet_name):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            if df.shape[1] == 0:
                return False, "工作表中没有列"
            self.variables = {}
            for col in df.columns:
                ser = df[col]
                ser_num = pd.to_numeric(ser, errors="coerce")
                self.variables[str(col)] = ser_num.to_numpy() if ser_num.notna().any() else ser.astype(str).tolist()
            self.length = int(df.shape[0])
            return True, ""
        except Exception as e:
            return False, str(e)


class PlotCanvas(FigureCanvas):
    def __init__(self, parent_window=None):
        self.figure = Figure(facecolor="white", dpi=110)
        super().__init__(self.figure)
        self.parent_window = parent_window
        self.axes_list = []
        self._legend_map = {}
        self._axis_outward = {}
        self.mpl_connect("pick_event", self._on_pick)

    def _on_pick(self, event):
        if event.artist in self._legend_map:
            orig = self._legend_map[event.artist]
            orig.set_visible(not orig.get_visible())
            self.draw_idle()

    def draw_plot(self, x_data, y_data_dict, x_label, title_text, y_axis_name, start_idx, end_idx, show_grid=True, plot_mode="scatter"):
        self.figure.clear()
        self._legend_map.clear()
        self.axes_list = []
        self._axis_outward = {}

        x_slice = np.asarray(x_data)[start_idx:end_idx + 1]
        ax_main = self.figure.add_subplot(111)
        self.axes_list.append(ax_main)

        groups = {}
        for n in y_data_dict:
            groups.setdefault(axis_group_key(n), []).append(n)

        handles, labels = [], []
        colors = ["#2563EB", "#F59E0B", "#10B981", "#7C3AED", "#DC2626"]

        for gi, (gk, vars_) in enumerate(groups.items()):
            ax = ax_main if gi == 0 else ax_main.twinx()
            if gi > 0:
                self._axis_outward[gi] = 70 * (gi - 1)
                ax.spines["right"].set_position(("outward", self._axis_outward[gi]))
                self.axes_list.append(ax)
            for vi, var in enumerate(vars_):
                y_slice = np.asarray(y_data_dict[var])[start_idx:end_idx + 1]
                color = colors[(gi * 2 + vi) % len(colors)]
                line_obj = None
                scatter_obj = None
                if plot_mode in ("line", "line_scatter"):
                    line_obj, = ax.plot(x_slice, y_slice, color=color, linewidth=1.8, label=var)
                if plot_mode in ("scatter", "line_scatter"):
                    scatter_obj = ax.scatter(x_slice, y_slice, s=30, color=color, edgecolor="white", linewidth=0.6, label=var)
                obj = scatter_obj if scatter_obj is not None else line_obj
                handles.append(obj); labels.append(var)
            ax.set_ylabel(y_axis_name if gi == 0 else f"{y_axis_name}-{gk}")

        ax_main.set_xlabel(x_label)
        ax_main.set_title(title_text)
        if show_grid:
            ax_main.grid(True, linestyle="--", alpha=0.35)
        lg = ax_main.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1), frameon=True)
        for h, orig in zip(getattr(lg, "legendHandles", []), handles):
            h.set_picker(True)
            self._legend_map[h] = orig

        self.figure.tight_layout(rect=[0, 0, 0.85, 1])
        self.draw()


class DataChartPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        card = SimpleCardWidget(self)
        cl = QVBoxLayout(card)
        cl.addWidget(TitleLabel("数据图表页", self))
        self.plot_canvas = PlotCanvas()
        self.toolbar = NavigationToolbar(self.plot_canvas, self)
        cl.addWidget(self.toolbar)
        cl.addWidget(self.plot_canvas, 1)
        l.addWidget(card)


class ExcelVisualizerPage(QWidget):
    def __init__(self, chart_page, parent=None):
        super().__init__(parent)
        self.chart_page = chart_page
        self.data_processor = DataProcessor()
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        scroll = ScrollArea(self)
        if hasattr(scroll, "setWidgetResizable"):
            scroll.setWidgetResizable(True)
        panel = QWidget()
        if hasattr(scroll, "setWidget"):
            scroll.setWidget(panel)
        root = QHBoxLayout(panel)
        left, right = QVBoxLayout(), QVBoxLayout()

        self.file_label = LineEdit(); self.file_label.setReadOnly(True)
        btn_file = PrimaryPushButton("选择 Excel 文件", self); btn_file.clicked.connect(self.choose_excel_file)
        self.sheet_combo = ComboBox(self)
        btn_load = PushButton("读取 Sheet", self); btn_load.clicked.connect(self.load_selected_sheet)
        self.title_edit = LineEdit(self); self.title_edit.setText("科学数据可视化")
        self.xname_edit = LineEdit(self); self.xname_edit.setText("X 轴")
        self.yname_edit = LineEdit(self); self.yname_edit.setText("Y 轴")
        self.mode_combo = ComboBox(self); self.mode_combo.addItems(["散点图", "折线图", "折线+散点图"])
        self.start_spin, self.end_spin = QSpinBox(self), QSpinBox(self)
        self.x_combo = ComboBox(self)
        self.y_list = QListWidget(self); self.y_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.grid_cb = CheckBox("显示网格", self); self.grid_cb.setChecked(True)

        def pack(container, title, items):
            box = QGroupBox(title)
            bl = QVBoxLayout(box)
            for it in items:
                bl.addLayout(it) if isinstance(it, (QHBoxLayout, QVBoxLayout)) else bl.addWidget(it)
            container.addWidget(box)

        r1 = QHBoxLayout(); r1.addWidget(btn_file); r1.addWidget(self.file_label)
        r2 = QHBoxLayout(); r2.addWidget(QLabel("Sheet:")); r2.addWidget(self.sheet_combo); r2.addWidget(btn_load)
        pack(left, "数据源", [r1, r2])
        pack(left, "标题与坐标轴", [self.title_edit, self.xname_edit, self.yname_edit])
        pack(left, "图型", [self.mode_combo])
        pack(left, "数据索引", [self.start_spin, self.end_spin])
        pack(right, "变量选择", [self.x_combo, self.y_list])
        pack(right, "网格", [self.grid_cb])

        row = QHBoxLayout()
        plot_btn = PrimaryPushButton("生成图表", self); plot_btn.clicked.connect(self.plot_data)
        save_btn = PushButton("保存无损图片", self); save_btn.clicked.connect(self.save_figure_lossless)
        row.addWidget(plot_btn); row.addWidget(save_btn)
        right.addLayout(row); right.addStretch(1)

        root.addLayout(left, 1); root.addLayout(right, 1)
        main.addWidget(scroll)

    def choose_excel_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Excel 文件", "", "Excel 文件 (*.xlsx *.xls)")
        if path:
            self.file_label.setText(path)
            self.sheet_combo.clear(); self.sheet_combo.addItems(self.data_processor.get_sheet_names(path))

    def load_selected_sheet(self):
        ok, err = self.data_processor.load_from_excel(self.file_label.text().strip(), self.sheet_combo.currentText().strip())
        if not ok:
            QMessageBox.critical(self, "错误", f"读取失败: {err}"); return
        names = list(self.data_processor.variables.keys())
        length = self.data_processor.length
        self.start_spin.setMaximum(max(0, length - 1)); self.end_spin.setMaximum(max(0, length - 1)); self.end_spin.setValue(max(0, length - 1))
        self.x_combo.clear(); self.x_combo.addItems(names)
        self.y_list.clear(); self.y_list.addItems(names)

    def plot_data(self):
        s, e = self.start_spin.value(), self.end_spin.value()
        if s > e:
            QMessageBox.warning(self, "错误", "起始索引不能大于结束索引"); return
        xvar = self.x_combo.currentText().strip(); yitems = self.y_list.selectedItems()
        if not xvar or not yitems:
            QMessageBox.warning(self, "错误", "请先选择 X 与至少一个 Y"); return
        xdata = np.asarray(self.data_processor.variables.get(xvar, []))
        ydict = {it.text(): np.asarray(self.data_processor.variables.get(it.text(), [])) for it in yitems}
        mode_map = {"散点图": "scatter", "折线图": "line", "折线+散点图": "line_scatter"}
        self.chart_page.plot_canvas.draw_plot(xdata, ydict, self.xname_edit.text() or xvar, self.title_edit.text() or "科学数据可视化", self.yname_edit.text() or "Y", s, e, self.grid_cb.isChecked(), mode_map.get(self.mode_combo.currentText(), "scatter"))

    def save_figure_lossless(self):
        if not self.chart_page.plot_canvas.figure.axes:
            QMessageBox.warning(self, "提示", "请先生成图表"); return
        path, _ = QFileDialog.getSaveFileName(self, "保存无损图片", "plot.png", "PNG (*.png);;TIFF (*.tiff);;SVG (*.svg);;PDF (*.pdf)")
        if path:
            self.chart_page.plot_canvas.figure.savefig(path, dpi=300, bbox_inches="tight", facecolor="white", edgecolor="white")
