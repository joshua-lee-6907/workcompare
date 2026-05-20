#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Excel 数据交互式可视化（支持 xls/xlsx）
- 读取 xls/xlsx 文件（第一行为变量名，每列一个变量）
- 用户选择文件与 sheet
- 中文字体与科学风格
- 可选图型：折线图 / 散点图 / 折线+散点图
- 可修改图名、X轴名、Y轴名
- 图片可保存为无损格式（PNG/TIFF/SVG/PDF）

保留核心功能：多Y变量、按变量名前缀自动分组多坐标轴、图例点选显隐、轴范围/轴偏移可调。
"""

import os
import re
import sys
import platform
import warnings

import numpy as np
import pandas as pd

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QListWidget, QMessageBox, QAbstractItemView, QSplitter,
    QCheckBox, QRadioButton, QButtonGroup, QDoubleSpinBox, QFileDialog,
    QGroupBox
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
        FluentWindow,
        FluentIcon,
        setTheme,
        Theme,
        ScrollArea,
        PushButton,
        PrimaryPushButton,
        ComboBox,
        LineEdit,
        CheckBox,
        BodyLabel,
        TitleLabel,
        SimpleCardWidget,
    )
except Exception:
    from qfluentwidgets import (
        MSFluentWindow as FluentWindow,
        FluentIcon,
        setTheme,
        Theme,
        ScrollArea,
        PushButton,
        PrimaryPushButton,
        ComboBox,
        LineEdit,
        CheckBox,
        BodyLabel,
        TitleLabel,
        SimpleCardWidget,
    )


plt.style.use("default")


def set_chinese_font():
    candidates = []
    if platform.system() == "Windows":
        candidates = [
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\msyhbd.ttc",
            r"C:\Windows\Fonts\simsun.ttc",
        ]
    elif platform.system() == "Darwin":
        candidates = [
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/arphic/ukai.ttc",
        ]

    chosen_name = "SimHei"
    try:
        fm.fontManager = fm._load_fontmanager(try_read_cache=False)
    except Exception:
        try:
            fm.fontManager = fm.FontManager()
        except Exception:
            pass

    for fp in candidates:
        if os.path.exists(fp):
            try:
                fm.fontManager.addfont(fp)
                chosen_name = fm.FontProperties(fname=fp).get_name()
                break
            except Exception:
                continue

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["SimHei", chosen_name, "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return chosen_name


PREFERRED_APP_FONT = set_chinese_font()
rcParams["font.family"] = "sans-serif"
rcParams["font.sans-serif"] = ["SimHei", PREFERRED_APP_FONT, "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False
plt.rcParams.update({"axes.grid": True, "grid.linestyle": "--", "grid.alpha": 0.35, "axes.spines.top": False, "figure.dpi": 120})
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")


def axis_group_key(var_name: str):
    if not isinstance(var_name, str) or var_name == "":
        return var_name
    m = re.match(r"^([A-Za-z\u4e00-\u9fff]+)", var_name)
    return m.group(1) if m else var_name


class DataProcessor:
    def __init__(self):
        self.file_path = None
        self.sheet_name = None
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
            self.file_path = file_path
            self.sheet_name = sheet_name
            self.length = int(df.shape[0])
            return True, ""
        except Exception as e:
            return False, str(e)

    def get_variable_names(self):
        return list(self.variables.keys())

    def get_variable_data(self, variable_name):
        return self.variables.get(variable_name, [])

    def get_data_length(self):
        return self.length


class PlotCanvas(FigureCanvas):
    def __init__(self, parent_window=None):
        self.figure = Figure(facecolor="white", dpi=110)
        super().__init__(self.figure)
        self.parent_window = parent_window
        self._plot_storage = {}
        self._legend_map = {}
        self.axes_list = []
        self._axis_outward = {}
        self.mpl_connect("pick_event", self._on_pick)

    def _on_pick(self, event):
        artist = event.artist
        if artist in self._legend_map:
            orig = self._legend_map[artist]
            orig.set_visible(not orig.get_visible())
            self.draw_idle()

    def _update_axis_positions(self):
        for i, ax in enumerate(self.axes_list[1:], start=1):
            ax.spines["right"].set_position(("outward", self._axis_outward.get(i, 0)))

    def _apply_axis_ranges(self, axis_ranges):
        if not axis_ranges:
            return
        if "x" in axis_ranges and self.axes_list:
            xr = axis_ranges["x"]
            if not xr.get("auto", True):
                xmin, xmax = float(xr["min"]), float(xr["max"])
                if xmin < xmax:
                    self.axes_list[0].set_xlim(xmin, xmax)
        for idx in range(len(self.axes_list)):
            if idx in axis_ranges:
                yr = axis_ranges[idx]
                if not yr.get("auto", True):
                    ymin, ymax = float(yr["min"]), float(yr["max"])
                    if ymin < ymax:
                        self.axes_list[idx].set_ylim(ymin, ymax)

    def draw_plot(self, x_data, y_data_dict, x_label, title_text, y_axis_name,
                  start_idx, end_idx, show_grid=True, plot_mode="scatter", axis_ranges=None):
        self.figure.clear()
        self._plot_storage.clear()
        self._legend_map.clear()
        self._axis_outward.clear()
        self.axes_list = []

        x_slice = np.asarray(x_data)[start_idx:end_idx + 1]
        ax_main = self.figure.add_subplot(111)
        self.axes_list.append(ax_main)
        colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b"]

        groups = {}
        for name in y_data_dict:
            groups.setdefault(axis_group_key(name), []).append(name)

        handles, labels, axis_group_keys = [], [], []
        for gi, (group_key, var_names) in enumerate(groups.items()):
            axis_group_keys.append(group_key)
            ax = ax_main if gi == 0 else ax_main.twinx()
            if gi > 0:
                self._axis_outward[gi] = 70 * (gi - 1)
                ax.spines["right"].set_position(("outward", self._axis_outward[gi]))
                self.axes_list.append(ax)

            for vi, var in enumerate(var_names):
                y_slice = np.asarray(y_data_dict[var])[start_idx:end_idx + 1]
                color = colors[(gi * 2 + vi) % len(colors)]
                line_obj = None
                scatter_obj = None
                if plot_mode in ("line", "line_scatter"):
                    line_obj, = ax.plot(x_slice, y_slice, color=color, linewidth=2.0, alpha=0.9, label=var)
                if plot_mode in ("scatter", "line_scatter"):
                    scatter_obj = ax.scatter(x_slice, y_slice, s=46, facecolor=color, edgecolor="white", linewidth=0.8, alpha=0.9, label=var)
                obj = scatter_obj if scatter_obj is not None else line_obj
                self._plot_storage[var] = (x_slice, y_slice, ax, obj)
                handles.append(obj)
                labels.append(var)

            custom_axis_label = self.parent_window.get_axis_custom_label(gi) if self.parent_window else None
            axis_label_text = custom_axis_label or (y_axis_name if gi == 0 else f"{y_axis_name}-{group_key}")
            ax.set_ylabel(axis_label_text, fontsize=12, fontweight="bold")

        ax_main.set_xlabel(x_label, fontsize=12, fontweight="bold")
        ax_main.set_title(title_text, fontsize=14, fontweight="bold", pad=10)
        if show_grid:
            ax_main.grid(True, linestyle="--", linewidth=0.7, alpha=0.35)

        legend = ax_main.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1), frameon=True, fontsize=9)
        legend.set_draggable(True)
        legend_handles = getattr(legend, "legendHandles", None) or getattr(legend, "legend_handles", [])
        for lh, lab in zip(legend_handles, labels):
            lh.set_picker(True)
            self._legend_map[lh] = self._plot_storage[lab][3]

        if self.parent_window:
            self.parent_window.update_axis_offset_controls(self._axis_outward, axis_group_keys)
            self.parent_window.populate_axis_selector(axis_group_keys)

        self._update_axis_positions()
        self._apply_axis_ranges(axis_ranges or {})
        self.figure.tight_layout(rect=[0, 0, 0.85, 1])
        self.draw()


class ExcelVisualizerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("enterpriseAnalysisPage")
        self.data_processor = DataProcessor()
        self.range_widgets = {}
        self.axis_name_edits = {}
        self._build_ui()
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(2000)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        main_layout.addWidget(splitter)
        self.control_panel = self.create_control_panel()
        splitter.addWidget(self.control_panel)
        self.plot_panel = self.create_plot_widget()
        splitter.addWidget(self.plot_panel)
        splitter.setSizes([480, 1170])
        self.status_label = BodyLabel("就绪", self)
        main_layout.addWidget(self.status_label)

    def update_status(self):
        self.status_label.setText(f"变量: {len(self.data_processor.get_variable_names())} | 行数: {self.data_processor.get_data_length()}")

    def create_plot_widget(self):
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        self.plot_canvas = PlotCanvas(parent_window=self)
        self.toolbar = NavigationToolbar(self.plot_canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.plot_canvas)
        return widget

    def create_control_panel(self):
        scroll = ScrollArea(self)
        scroll.setWidgetResizable(True)
        panel = QWidget(); scroll.setWidget(panel)
        layout = QVBoxLayout(panel)

        self.file_label = LineEdit(); self.file_label.setReadOnly(True); self.file_label.setPlaceholderText("未选择文件")
        btn_file = PrimaryPushButton("选择 Excel 文件", self); btn_file.clicked.connect(self.choose_excel_file)
        self.sheet_combo = ComboBox(self)
        btn_load = PushButton("读取 Sheet", self); btn_load.clicked.connect(self.load_selected_sheet)

        self.title_edit = LineEdit(self); self.title_edit.setText("科学数据可视化")
        self.xname_edit = LineEdit(self); self.xname_edit.setText("X 轴")
        self.yname_edit = LineEdit(self); self.yname_edit.setText("Y 轴")
        self.mode_combo = ComboBox(self); self.mode_combo.addItems(["散点图", "折线图", "折线+散点图"])
        self.start_spin = QSpinBox(self); self.end_spin = QSpinBox(self)
        self.x_combo = ComboBox(self)
        self.y_list = QListWidget(self); self.y_list.setSelectionMode(QAbstractItemView.MultiSelection); self.y_list.setMinimumHeight(180)
        self.grid_cb = CheckBox("显示网格", self); self.grid_cb.setChecked(True)

        self.axis_button_group = QButtonGroup(self)
        self.axis_radio_buttons = []
        self.axis_radio_layout = QVBoxLayout()
        self.offsets_layout = QVBoxLayout()
        self.ranges_layout = QVBoxLayout()
        self.axis_name_layout = QVBoxLayout()

        def pack(title, items):
            box = QGroupBox(title); bl = QVBoxLayout(box)
            for it in items:
                if isinstance(it, QHBoxLayout) or isinstance(it, QVBoxLayout): bl.addLayout(it)
                else: bl.addWidget(it)
            layout.addWidget(box)

        r1 = QHBoxLayout(); r1.addWidget(btn_file); r1.addWidget(self.file_label, 1)
        r2 = QHBoxLayout(); r2.addWidget(QLabel("Sheet:")); r2.addWidget(self.sheet_combo, 1); r2.addWidget(btn_load)
        pack("数据源", [r1, r2])
        pack("标题与坐标轴", [self.title_edit, self.xname_edit, self.yname_edit])
        pack("图型", [self.mode_combo])
        pack("数据索引", [self.start_spin, self.end_spin])
        pack("变量选择", [self.x_combo, self.y_list])
        pack("网格", [self.grid_cb])
        pack("活动轴", [self.axis_radio_layout])
        pack("轴偏移", [self.offsets_layout])
        pack("轴范围", [self.ranges_layout])
        pack("Y轴重命名", [self.axis_name_layout])

        btn_plot = PrimaryPushButton("生成图表", self); btn_plot.clicked.connect(self.plot_data)
        btn_save = PushButton("保存无损图片", self); btn_save.clicked.connect(self.save_figure_lossless)
        layout.addWidget(btn_plot); layout.addWidget(btn_save); layout.addStretch(1)
        return scroll

    def choose_excel_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Excel 文件", "", "Excel 文件 (*.xlsx *.xls)")
        if not path:
            return
        self.file_label.setText(path)
        try:
            self.sheet_combo.clear(); self.sheet_combo.addItems(self.data_processor.get_sheet_names(path))
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def load_selected_sheet(self):
        file_path = self.file_label.text().strip()
        sheet = self.sheet_combo.currentText().strip()
        if not file_path or file_path == "未选择文件" or not sheet:
            QMessageBox.warning(self, "提示", "请先选择 Excel 文件和 Sheet")
            return
        ok, err = self.data_processor.load_from_excel(file_path, sheet)
        if not ok:
            QMessageBox.critical(self, "错误", f"读取失败: {err}")
            return
        names = self.data_processor.get_variable_names()
        length = self.data_processor.get_data_length()
        self.start_spin.setMaximum(max(0, length - 1)); self.start_spin.setValue(0)
        self.end_spin.setMaximum(max(0, length - 1)); self.end_spin.setValue(max(0, length - 1))
        self.x_combo.clear(); self.x_combo.addItems(names)
        self.y_list.clear(); self.y_list.addItems(names)

    def populate_axis_selector(self, axis_group_keys):
        for b in self.axis_radio_buttons:
            self.axis_button_group.removeButton(b); b.setParent(None)
        self.axis_radio_buttons.clear()
        for idx, name in enumerate(axis_group_keys):
            rb = QRadioButton(f"轴{idx}-{name}"); rb.setChecked(idx == 0)
            self.axis_button_group.addButton(rb, idx)
            self.axis_radio_layout.addWidget(rb)
            self.axis_radio_buttons.append(rb)

    def update_axis_offset_controls(self, offsets_dict, axis_group_keys):
        while self.offsets_layout.count():
            item = self.offsets_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for idx in range(1, len(axis_group_keys)):
            row = QWidget(); hl = QHBoxLayout(row); hl.setContentsMargins(0, 0, 0, 0)
            hl.addWidget(BodyLabel(f"轴{idx}({axis_group_keys[idx]})", self))
            sp = QSpinBox(self); sp.setRange(0, 2000); sp.setValue(offsets_dict.get(idx, 70 * (idx - 1)))
            sp.valueChanged.connect(lambda v, i=idx: self._set_axis_offset(i, v)); hl.addWidget(sp)
            self.offsets_layout.addWidget(row)
        self._build_axis_name_controls(axis_group_keys)

    def _build_axis_name_controls(self, axis_group_keys):
        while self.axis_name_layout.count():
            item = self.axis_name_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        old_values = {k: v.text().strip() for k, v in self.axis_name_edits.items()}
        self.axis_name_edits.clear()
        for idx, name in enumerate(axis_group_keys):
            row = QWidget(); hl = QHBoxLayout(row); hl.setContentsMargins(0, 0, 0, 0)
            hl.addWidget(BodyLabel(f"轴{idx}:", self))
            edit = LineEdit(self)
            edit.setPlaceholderText(f"默认: {self.yname_edit.text().strip() or 'Y'}{'-' + name if idx > 0 else ''}")
            if idx in old_values: edit.setText(old_values[idx])
            hl.addWidget(edit)
            self.axis_name_layout.addWidget(row)
            self.axis_name_edits[idx] = edit

    def get_axis_custom_label(self, axis_index):
        edit = self.axis_name_edits.get(axis_index)
        if not edit:
            return None
        txt = edit.text().strip()
        return txt if txt else None

    def _set_axis_offset(self, idx, val):
        self.plot_canvas._axis_outward[idx] = int(val)
        self.plot_canvas._update_axis_positions()
        self.plot_canvas.draw_idle()

    def _gather_axis_ranges_from_ui(self):
        return {}

    def plot_data(self):
        s, e = self.start_spin.value(), self.end_spin.value()
        if s > e:
            QMessageBox.warning(self, "错误", "起始索引不能大于结束索引")
            return
        xvar = self.x_combo.currentText().strip(); yitems = self.y_list.selectedItems()
        if not xvar or not yitems:
            QMessageBox.warning(self, "错误", "请先选择 X 与至少一个 Y")
            return
        xdata = np.asarray(self.data_processor.get_variable_data(xvar))
        ydict = {it.text(): np.asarray(self.data_processor.get_variable_data(it.text())) for it in yitems}
        max_idx = min([len(xdata) - 1] + [len(v) - 1 for v in ydict.values()])
        if e > max_idx:
            e = max_idx
            self.end_spin.setValue(e)
        mode_map = {"散点图": "scatter", "折线图": "line", "折线+散点图": "line_scatter"}
        self.plot_canvas.draw_plot(xdata, ydict, self.xname_edit.text().strip() or xvar,
                                   self.title_edit.text().strip() or "科学数据可视化",
                                   self.yname_edit.text().strip() or "Y", s, e,
                                   show_grid=self.grid_cb.isChecked(),
                                   plot_mode=mode_map.get(self.mode_combo.currentText(), "scatter"),
                                   axis_ranges=self._gather_axis_ranges_from_ui())

    def save_figure_lossless(self):
        if not self.plot_canvas.figure.axes:
            QMessageBox.warning(self, "提示", "请先生成图表")
            return
        path, selected_filter = QFileDialog.getSaveFileName(self, "保存无损图片", "plot.png",
                                                            "PNG 无损位图 (*.png);;TIFF 无损位图 (*.tiff);;SVG 矢量图 (*.svg);;PDF 矢量图 (*.pdf)")
        if not path:
            return
        if not os.path.splitext(path)[1]:
            if "TIFF" in selected_filter: path += ".tiff"
            elif "SVG" in selected_filter: path += ".svg"
            elif "PDF" in selected_filter: path += ".pdf"
            else: path += ".png"
        ext = os.path.splitext(path)[1].lower()
        fmt = {".png": "png", ".tif": "tiff", ".tiff": "tiff", ".svg": "svg", ".pdf": "pdf"}.get(ext)
        if fmt is None:
            QMessageBox.warning(self, "提示", "请保存为 PNG / TIFF / SVG / PDF")
            return
        self.plot_canvas.figure.savefig(path, dpi=300, format=fmt, bbox_inches="tight", pad_inches=0.05, facecolor="white", edgecolor="white")
        self.status_label.setText(f"已保存: {path}")


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.page = ExcelVisualizerPage(self)
        self.addSubInterface(self.page, FluentIcon.LIBRARY, "Excel 可视化")
        self.setWindowTitle("Excel 数据可视化")
        self.setWindowIcon(QIcon())
        self.resize(1650, 1000)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Excel 数据可视化")
    app.setFont(QFont("Microsoft YaHei", 10))
    setTheme(Theme.LIGHT)
    wnd = MainWindow()
    wnd.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
