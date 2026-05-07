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
"""

import sys
import re
import numpy as np
import pandas as pd

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QComboBox, QListWidget, QPushButton, QGroupBox,
    QMessageBox, QAbstractItemView, QSplitter, QScrollArea, QSlider,
    QCheckBox, QFrame, QRadioButton, QButtonGroup, QDoubleSpinBox,
    QFileDialog, QLineEdit
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.font_manager as fm


def set_chinese_font():
    preferred = [
        "Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans CJK SC",
        "WenQuanYi Zen Hei", "Heiti SC", "Arial Unicode MS"
    ]
    installed = {f.name for f in fm.fontManager.ttflist}
    usable = [name for name in preferred if name in installed]
    if usable:
        plt.rcParams['font.sans-serif'] = usable + ['DejaVu Sans']
        plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['axes.unicode_minus'] = False


set_chinese_font()
plt.style.use('seaborn-v0_8-whitegrid')


class DataProcessor:
    def __init__(self):
        self.file_path = None
        self.sheet_name = None
        self.variables = {}
        self.length = 0

    def get_sheet_names(self, file_path):
        try:
            return pd.ExcelFile(file_path).sheet_names
        except Exception as e:
            raise RuntimeError(f"读取工作表失败: {e}")

    def load_from_excel(self, file_path, sheet_name):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            if df.shape[1] == 0:
                return False, "工作表中没有列"

            self.variables = {}
            for col in df.columns:
                ser = df[col]
                ser_num = pd.to_numeric(ser, errors='coerce')
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


def axis_group_key(var_name: str):
    if not isinstance(var_name, str) or var_name == "":
        return var_name
    m = re.match(r'^([A-Za-z\u4e00-\u9fff]+)', var_name)
    return m.group(1) if m else var_name


class PlotCanvas(FigureCanvas):
    def __init__(self, parent_window=None, hover_threshold=0.02):
        self.figure = Figure(facecolor='#fafbfc', dpi=110)
        super().__init__(self.figure)
        self.parent_window = parent_window
        self.hover_threshold = hover_threshold
        self._plot_storage = {}
        self._legend_map = {}
        self.axes_list = []
        self._axis_outward = {}
        self._axis_group_keys = []
        self._active_axis_index = 0
        self.annotation = None
        self.mpl_connect('motion_notify_event', self._on_mouse_move)
        self.mpl_connect('button_press_event', self._on_axis_click)
        self.mpl_connect('pick_event', self._on_pick)

    def set_active_axis(self, axis_index):
        if 0 <= axis_index < len(self.axes_list):
            self._active_axis_index = axis_index
            self._highlight_active_axis()
            return True
        return False

    def _highlight_active_axis(self):
        for i, ax in enumerate(self.axes_list):
            if i == self._active_axis_index:
                ax.patch.set_facecolor('#fffbeb')
                ax.patch.set_alpha(0.55)
            else:
                ax.patch.set_facecolor('white')
                ax.patch.set_alpha(0.0)
        self.draw_idle()

    def _on_axis_click(self, event):
        if event.inaxes and event.inaxes in self.axes_list:
            idx = self.axes_list.index(event.inaxes)
            self.set_active_axis(idx)
            if self.parent_window:
                self.parent_window.update_active_axis_radio(idx)

    def _on_pick(self, event):
        artist = event.artist
        if artist in self._legend_map:
            orig = self._legend_map[artist]
            orig.set_visible(not orig.get_visible())
            self.draw_idle()
            return

    def _on_mouse_move(self, event):
        if event.inaxes is None or not self._plot_storage:
            if self.annotation:
                self.annotation.set_visible(False)
                self.draw_idle()
            return

    def _update_axis_positions(self):
        for i, ax in enumerate(self.axes_list[1:], start=1):
            offset = self._axis_outward.get(i, 0)
            ax.spines['right'].set_position(('outward', offset))

    def _apply_axis_ranges(self, axis_ranges):
        if not axis_ranges:
            return
        if 'x' in axis_ranges and self.axes_list:
            xr = axis_ranges['x']
            if not xr.get('auto', True):
                xmin, xmax = float(xr['min']), float(xr['max'])
                if xmin < xmax:
                    self.axes_list[0].set_xlim(xmin, xmax)
                    tick = float(xr.get('tick', 0) or 0)
                    if tick > 0:
                        self.axes_list[0].set_xticks(np.arange(xmin, xmax + 1e-9, tick))
        for idx in range(len(self.axes_list)):
            if idx in axis_ranges:
                yr = axis_ranges[idx]
                if not yr.get('auto', True):
                    ymin, ymax = float(yr['min']), float(yr['max'])
                    if ymin < ymax:
                        self.axes_list[idx].set_ylim(ymin, ymax)
                        tick = float(yr.get('tick', 0) or 0)
                        if tick > 0:
                            self.axes_list[idx].set_yticks(np.arange(ymin, ymax + 1e-9, tick))

    def draw_plot(self, x_data, y_data_dict, x_label, title_text, y_axis_name,
                  start_idx, end_idx, show_grid=True, plot_mode='scatter', axis_ranges=None):
        self.figure.clear()
        self._plot_storage.clear()
        self._legend_map.clear()
        self._axis_outward.clear()
        self.axes_list = []

        x_arr = np.asarray(x_data)
        x_slice = x_arr[start_idx:end_idx + 1]

        ax_main = self.figure.add_subplot(111)
        self.axes_list.append(ax_main)

        colors = ['#1f77b4', '#d62728', '#2ca02c', '#9467bd', '#ff7f0e', '#17becf', '#8c564b']
        groups = {}
        for name in y_data_dict:
            groups.setdefault(axis_group_key(name), []).append(name)

        handles, labels, axis_group_keys = [], [], []
        for gi, (group_key, var_names) in enumerate(groups.items()):
            axis_group_keys.append(group_key)
            ax = ax_main if gi == 0 else ax_main.twinx()
            if gi > 0:
                self._axis_outward[gi] = 70 * (gi - 1)
                ax.spines['right'].set_position(('outward', self._axis_outward[gi]))
                self.axes_list.append(ax)

            for vi, var in enumerate(var_names):
                y_slice = np.asarray(y_data_dict[var])[start_idx:end_idx + 1]
                color = colors[(gi * 2 + vi) % len(colors)]

                line_obj = None
                scatter_obj = None
                if plot_mode in ('line', 'line_scatter'):
                    line_obj, = ax.plot(x_slice, y_slice, color=color, linewidth=2.0, alpha=0.9, label=var)
                if plot_mode in ('scatter', 'line_scatter'):
                    scatter_obj = ax.scatter(x_slice, y_slice, s=46, facecolor=color, edgecolor='white', linewidth=0.8, alpha=0.9, label=var, picker=True)

                obj_for_legend = scatter_obj if scatter_obj is not None else line_obj
                self._plot_storage[var] = (x_slice, y_slice, ax, obj_for_legend)
                handles.append(obj_for_legend)
                labels.append(var)

            ax.set_ylabel(y_axis_name if gi == 0 else f"{y_axis_name}-{group_key}", fontsize=12, fontweight='bold')

        ax_main.set_xlabel(x_label, fontsize=12, fontweight='bold')
        ax_main.set_title(title_text, fontsize=14, fontweight='bold', pad=10)
        if show_grid:
            ax_main.grid(True, linestyle='--', linewidth=0.7, alpha=0.35)

        legend = ax_main.legend(handles, labels, loc='upper left', bbox_to_anchor=(1.02, 1), frameon=True, fontsize=9)
        legend.set_draggable(True)
        legend_handles = getattr(legend, "legendHandles", None)
        if legend_handles is None:
            legend_handles = getattr(legend, "legend_handles", [])
        for lh, lab in zip(legend_handles, labels):
            lh.set_picker(True)
            self._legend_map[lh] = self._plot_storage[lab][3]

        self._axis_group_keys = axis_group_keys
        self._active_axis_index = 0
        self._highlight_active_axis()

        if self.parent_window:
            self.parent_window.update_axis_offset_controls(self._axis_outward, axis_group_keys)
            self.parent_window.populate_axis_selector(axis_group_keys)

        self._update_axis_positions()
        self._apply_axis_ranges(axis_ranges or {})
        self.figure.tight_layout(rect=[0, 0, 0.85, 1])
        self.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data_processor = DataProcessor()
        self.range_widgets = {}
        self.setup_style()
        self.init_ui()

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(2000)

    def setup_style(self):
        self.setStyleSheet("QMainWindow{background:#f8fafc;font-family:'Microsoft YaHei';}")

    def init_ui(self):
        self.setWindowTitle("Excel 数据交互式可视化")
        self.setGeometry(50, 50, 1650, 1000)
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        splitter = QSplitter(Qt.Horizontal); main_layout.addWidget(splitter)
        splitter.addWidget(self.create_control_panel())
        splitter.addWidget(self.create_plot_widget())
        splitter.setSizes([450, 1200])
        self.statusBar().showMessage("就绪")

    def create_plot_widget(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.plot_canvas = PlotCanvas(parent_window=self, hover_threshold=0.02)
        self.toolbar = NavigationToolbar(self.plot_canvas, self)
        layout.addWidget(self.toolbar); layout.addWidget(self.plot_canvas)
        return widget

    def create_control_panel(self):
        panel = QWidget(); scroll = QScrollArea(); scroll.setWidget(panel); scroll.setWidgetResizable(True)
        layout = QVBoxLayout(panel)

        file_group = QGroupBox("📂 数据源")
        fl = QVBoxLayout(file_group)
        row = QHBoxLayout()
        self.file_label = QLabel("未选择文件")
        btn_file = QPushButton("选择 Excel 文件")
        btn_file.clicked.connect(self.choose_excel_file)
        row.addWidget(btn_file); row.addWidget(self.file_label)
        fl.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Sheet:"))
        self.sheet_combo = QComboBox()
        row2.addWidget(self.sheet_combo)
        btn_load = QPushButton("读取 Sheet")
        btn_load.clicked.connect(self.load_selected_sheet)
        row2.addWidget(btn_load)
        fl.addLayout(row2)
        layout.addWidget(file_group)

        self.title_edit = QLineEdit("科学数据可视化")
        self.xname_edit = QLineEdit("X 轴")
        self.yname_edit = QLineEdit("Y 轴")
        txt_group = QGroupBox("✏️ 标题与坐标轴名称")
        tl = QVBoxLayout(txt_group)
        for t, w in (("图名", self.title_edit), ("X轴名", self.xname_edit), ("Y轴名", self.yname_edit)):
            r = QHBoxLayout(); r.addWidget(QLabel(t)); r.addWidget(w); tl.addLayout(r)
        layout.addWidget(txt_group)

        mode_group = QGroupBox("📉 图型")
        ml = QHBoxLayout(mode_group)
        self.mode_combo = QComboBox(); self.mode_combo.addItems(["散点图", "折线图", "折线+散点图"])
        ml.addWidget(self.mode_combo); layout.addWidget(mode_group)

        self.start_spin = QSpinBox(); self.end_spin = QSpinBox()
        self.start_spin.setMinimum(0); self.end_spin.setMinimum(0)
        idx_group = QGroupBox("📏 数据索引范围")
        il = QVBoxLayout(idx_group)
        r1 = QHBoxLayout(); r1.addWidget(QLabel("开始")); r1.addWidget(self.start_spin)
        r2 = QHBoxLayout(); r2.addWidget(QLabel("结束")); r2.addWidget(self.end_spin)
        il.addLayout(r1); il.addLayout(r2); layout.addWidget(idx_group)

        self.x_combo = QComboBox(); self.y_list = QListWidget(); self.y_list.setSelectionMode(QAbstractItemView.MultiSelection)
        vg = QGroupBox("变量选择")
        vl = QVBoxLayout(vg); vl.addWidget(QLabel("X轴")); vl.addWidget(self.x_combo); vl.addWidget(QLabel("Y轴(多选)")); vl.addWidget(self.y_list)
        layout.addWidget(vg)

        self.grid_cb = QCheckBox("显示网格"); self.grid_cb.setChecked(True)
        layout.addWidget(self.grid_cb)

        self.axis_button_group = QButtonGroup(self)
        self.axis_radio_buttons = []
        self.axis_radio_layout = QVBoxLayout()
        ag = QGroupBox("活动轴")
        ag.setLayout(self.axis_radio_layout)
        layout.addWidget(ag)

        self.offsets_layout = QVBoxLayout(); og = QGroupBox("轴偏移")
        og.setLayout(self.offsets_layout); layout.addWidget(og)

        self.ranges_layout = QVBoxLayout(); rg = QGroupBox("轴范围")
        rg.setLayout(self.ranges_layout); layout.addWidget(rg)

        btn_plot = QPushButton("生成图表")
        btn_plot.clicked.connect(self.plot_data)
        btn_save = QPushButton("保存无损图片")
        btn_save.clicked.connect(self.save_figure_lossless)
        layout.addWidget(btn_plot); layout.addWidget(btn_save)
        layout.addStretch()
        return scroll

    def choose_excel_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Excel 文件", "", "Excel 文件 (*.xlsx *.xls)")
        if not path:
            return
        self.file_label.setText(path)
        try:
            sheets = self.data_processor.get_sheet_names(path)
            self.sheet_combo.clear(); self.sheet_combo.addItems(sheets)
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def load_selected_sheet(self):
        file_path = self.file_label.text().strip()
        sheet = self.sheet_combo.currentText().strip()
        if not file_path or file_path == "未选择文件":
            QMessageBox.warning(self, "提示", "请先选择 Excel 文件")
            return
        if not sheet:
            QMessageBox.warning(self, "提示", "请选择 Sheet")
            return

        ok, err = self.data_processor.load_from_excel(file_path, sheet)
        if not ok:
            QMessageBox.critical(self, "错误", f"读取失败: {err}")
            return
        self.update_ui()
        self.statusBar().showMessage(f"已加载: {sheet}", 3000)

    def update_ui(self):
        names = self.data_processor.get_variable_names(); length = self.data_processor.get_data_length()
        self.start_spin.setMaximum(max(0, length - 1)); self.end_spin.setMaximum(max(0, length - 1)); self.end_spin.setValue(max(0, length - 1))
        self.x_combo.clear(); self.x_combo.addItems(names)
        self.y_list.clear(); self.y_list.addItems(names)

    def populate_axis_selector(self, axis_group_keys):
        for b in self.axis_radio_buttons:
            self.axis_button_group.removeButton(b); b.setParent(None)
        self.axis_radio_buttons.clear()
        for idx, name in enumerate(axis_group_keys):
            rb = QRadioButton(f"轴{idx}-{name}"); rb.setChecked(idx == 0)
            rb.toggled.connect(lambda checked, i=idx: checked and self.plot_canvas.set_active_axis(i))
            self.axis_button_group.addButton(rb, idx); self.axis_radio_layout.addWidget(rb); self.axis_radio_buttons.append(rb)

    def update_active_axis_radio(self, axis_index):
        if 0 <= axis_index < len(self.axis_radio_buttons):
            self.axis_radio_buttons[axis_index].setChecked(True)

    def update_axis_offset_controls(self, offsets_dict, axis_group_keys):
        while self.offsets_layout.count():
            item = self.offsets_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for idx in range(1, len(axis_group_keys)):
            row = QWidget(); hl = QHBoxLayout(row)
            hl.addWidget(QLabel(f"轴{idx}({axis_group_keys[idx]})"))
            sp = QSpinBox(); sp.setRange(0, 2000); sp.setValue(offsets_dict.get(idx, 70 * (idx - 1)))
            sp.valueChanged.connect(lambda v, i=idx: self._set_axis_offset(i, v))
            hl.addWidget(sp); self.offsets_layout.addWidget(row)
        self._build_axis_range_controls(axis_group_keys)

    def _set_axis_offset(self, idx, val):
        self.plot_canvas._axis_outward[idx] = int(val)
        self.plot_canvas._update_axis_positions()
        self.plot_canvas.draw_idle()

    def _build_axis_range_controls(self, axis_group_keys):
        while self.ranges_layout.count():
            item = self.ranges_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.range_widgets.clear()

        def add_row(key, title):
            row = QWidget(); hl = QHBoxLayout(row)
            auto = QCheckBox("自动"); auto.setChecked(True)
            mn = QDoubleSpinBox(); mx = QDoubleSpinBox(); tk = QDoubleSpinBox()
            for w in (mn, mx): w.setRange(-1e12, 1e12); w.setDecimals(6)
            tk.setRange(1e-12, 1e12); tk.setDecimals(6); tk.setValue(1.0)
            auto.toggled.connect(lambda st, ws=(mn, mx, tk): [w.setEnabled(not st) for w in ws])
            hl.addWidget(QLabel(title)); hl.addWidget(auto); hl.addWidget(QLabel("最小")); hl.addWidget(mn); hl.addWidget(QLabel("最大")); hl.addWidget(mx); hl.addWidget(QLabel("刻度")); hl.addWidget(tk)
            self.ranges_layout.addWidget(row)
            self.range_widgets[key] = (auto, mn, mx, tk)

        add_row('x', 'X轴')
        for idx, name in enumerate(axis_group_keys):
            add_row(idx, f"Y轴{idx}({name})")

    def _gather_axis_ranges_from_ui(self):
        data = {}
        for key, (auto, mn, mx, tk) in self.range_widgets.items():
            payload = {'auto': auto.isChecked(), 'min': float(mn.value()), 'max': float(mx.value()), 'tick': float(tk.value())}
            data['x' if key == 'x' else int(key)] = payload
        return data

    def plot_data(self):
        s, e = self.start_spin.value(), self.end_spin.value()
        if s > e:
            QMessageBox.warning(self, "错误", "起始索引不能大于结束索引"); return
        xvar = self.x_combo.currentText().strip()
        yitems = self.y_list.selectedItems()
        if not xvar or not yitems:
            QMessageBox.warning(self, "错误", "请先选择 X 与至少一个 Y"); return

        xdata = np.asarray(self.data_processor.get_variable_data(xvar))
        ydict = {}
        for it in yitems:
            yname = it.text(); arr = np.asarray(self.data_processor.get_variable_data(yname))
            if len(arr) > 0: ydict[yname] = arr
        max_idx = min([len(xdata) - 1] + [len(v) - 1 for v in ydict.values()])
        if e > max_idx:
            e = max_idx; self.end_spin.setValue(e)

        mode_map = {"散点图": "scatter", "折线图": "line", "折线+散点图": "line_scatter"}
        mode = mode_map.get(self.mode_combo.currentText(), 'scatter')

        self.plot_canvas.draw_plot(
            x_data=xdata,
            y_data_dict=ydict,
            x_label=self.xname_edit.text().strip() or xvar,
            title_text=self.title_edit.text().strip() or "科学数据可视化",
            y_axis_name=self.yname_edit.text().strip() or "Y",
            start_idx=s,
            end_idx=e,
            show_grid=self.grid_cb.isChecked(),
            plot_mode=mode,
            axis_ranges=self._gather_axis_ranges_from_ui()
        )

    def save_figure_lossless(self):
        if not self.plot_canvas.figure.axes:
            QMessageBox.warning(self, "提示", "请先生成图表")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存无损图片", "plot.png", "PNG (*.png);;TIFF (*.tiff);;SVG (*.svg);;PDF (*.pdf)")
        if not path:
            return
        self.plot_canvas.figure.savefig(path, dpi=300, bbox_inches='tight')
        self.statusBar().showMessage(f"已保存: {path}", 5000)

    def update_status(self):
        nvars = len(self.data_processor.get_variable_names())
        npts = self.data_processor.get_data_length()
        self.statusBar().showMessage(f"变量: {nvars} | 行数: {npts}")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("Excel 数据可视化")
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    wnd = MainWindow(); wnd.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
