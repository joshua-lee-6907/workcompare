#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Excel 数据交互式可视化（JSON 驱动）"""

import json
import os
import platform
import re
import sys
import warnings

import matplotlib
matplotlib.use("QtAgg", force=True)
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
from matplotlib import rcParams
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox,
                               QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow,
                               QMessageBox, QPushButton, QRadioButton, QScrollArea, QSpinBox, QSplitter, QVBoxLayout,
                               QWidget)

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
except Exception:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

plt.style.use("default")
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")


def set_chinese_font():
    candidates = []
    if platform.system() == "Windows":
        candidates = [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc"]
    elif platform.system() == "Darwin":
        candidates = ["/System/Library/Fonts/PingFang.ttc"]
    else:
        candidates = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"]
    chosen_name = "SimHei"
    for fp in candidates:
        if os.path.exists(fp):
            try:
                fm.fontManager.addfont(fp)
                chosen_name = fm.FontProperties(fname=fp).get_name()
                break
            except Exception:
                pass
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["SimHei", chosen_name, "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


set_chinese_font()
rcParams["font.family"] = "sans-serif"


class DataProcessor:
    def __init__(self):
        self.file_path = None
        self.variables = {}
        self.length = 0

    def get_sheet_names(self, file_path):
        return pd.ExcelFile(file_path).sheet_names

    def load_from_excel(self, file_path, sheet_name):
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        self.variables = {}
        for col in df.columns:
            ser = df[col]
            ser_num = pd.to_numeric(ser, errors="coerce")
            self.variables[str(col)] = ser_num.to_numpy() if ser_num.notna().any() else ser.astype(str).tolist()
        self.file_path = file_path
        self.length = int(df.shape[0])

    def get_variable_names(self):
        return list(self.variables.keys())

    def get_variable_data(self, variable_name):
        return self.variables.get(variable_name, [])


def axis_group_key(var_name: str):
    m = re.match(r"^([A-Za-z\u4e00-\u9fff]+)", var_name or "")
    return m.group(1) if m else var_name


class PlotCanvas(FigureCanvas):
    def __init__(self, parent_window=None):
        self.figure = Figure(facecolor="#fafbfc", dpi=110)
        super().__init__(self.figure)
        self.parent_window = parent_window
        self.axes_list = []

    def draw_plot(self, x_data, y_data_dict, x_label, title_text, y_axis_name, start_idx, end_idx, show_grid=True, plot_mode="scatter"):
        self.figure.clear()
        self.axes_list = []
        x_slice = np.asarray(x_data)[start_idx:end_idx + 1]
        ax_main = self.figure.add_subplot(111)
        self.axes_list.append(ax_main)
        colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]
        groups = {}
        for name in y_data_dict:
            groups.setdefault(axis_group_key(name), []).append(name)
        handles, labels = [], []
        for gi, (group_key, var_names) in enumerate(groups.items()):
            ax = ax_main if gi == 0 else ax_main.twinx()
            if gi > 0:
                ax.spines["right"].set_position(("outward", 70 * (gi - 1)))
                self.axes_list.append(ax)
            for vi, var in enumerate(var_names):
                y_slice = np.asarray(y_data_dict[var])[start_idx:end_idx + 1]
                color = colors[(gi + vi) % len(colors)]
                line = None
                if plot_mode in ("line", "line_scatter"):
                    line, = ax.plot(x_slice, y_slice, color=color, linewidth=2.0, label=var)
                if plot_mode in ("scatter", "line_scatter"):
                    sc = ax.scatter(x_slice, y_slice, s=40, facecolor=color, edgecolor="white", linewidth=0.8, alpha=0.9, label=var)
                    handles.append(sc)
                else:
                    handles.append(line)
                labels.append(var)
            ax.set_ylabel(y_axis_name if gi == 0 else f"{y_axis_name}-{group_key}")
        ax_main.set_xlabel(x_label)
        ax_main.set_title(title_text)
        if show_grid:
            ax_main.grid(True, linestyle="--", linewidth=0.7, alpha=0.35)
        ax_main.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1), frameon=True, fontsize=9)
        self.figure.tight_layout(rect=[0, 0, 0.85, 1])
        self.draw()


class MainWindow(QMainWindow):
    def __init__(self, config=None):
        super().__init__()
        self.data_processor = DataProcessor()
        self.config = config or {}
        self.setup_style()
        self.init_ui()
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(2000)
        self.apply_config()

    def update_status(self):
        self.statusBar().showMessage(f"变量: {len(self.data_processor.get_variable_names())}")

    def setup_style(self):
        self.setStyleSheet("QMainWindow{background:#f8fafc;font-family:'Microsoft YaHei';}")

    def init_ui(self):
        self.setWindowTitle("Excel 数据交互式可视化")
        self.setGeometry(50, 50, 1650, 1000)
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QHBoxLayout(central); splitter = QSplitter(Qt.Horizontal); main_layout.addWidget(splitter)
        splitter.addWidget(self.create_control_panel()); splitter.addWidget(self.create_plot_widget()); splitter.setSizes([450, 1200])

    def create_plot_widget(self):
        w = QWidget(); l = QVBoxLayout(w); self.plot_canvas = PlotCanvas(parent_window=self); self.toolbar = NavigationToolbar(self.plot_canvas, self)
        l.addWidget(self.toolbar); l.addWidget(self.plot_canvas); return w

    def create_control_panel(self):
        panel = QWidget(); scroll = QScrollArea(); scroll.setWidget(panel); scroll.setWidgetResizable(True); layout = QVBoxLayout(panel)
        self.file_label = QLabel("未选择文件"); self.sheet_combo = QComboBox(); self.x_combo = QComboBox(); self.y_list = QListWidget(); self.y_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.title_edit = QLineEdit("科学数据可视化"); self.xname_edit = QLineEdit("X 轴"); self.yname_edit = QLineEdit("Y 轴")
        self.mode_combo = QComboBox(); self.mode_combo.addItems(["散点图", "折线图", "折线+散点图"])
        self.start_spin = QSpinBox(); self.end_spin = QSpinBox(); self.grid_cb = QCheckBox("显示网格"); self.grid_cb.setChecked(True)
        for w in [QLabel("文件"), self.file_label, QLabel("Sheet"), self.sheet_combo, QLabel("标题"), self.title_edit, QLabel("X"), self.xname_edit,
                  QLabel("Y"), self.yname_edit, self.mode_combo, self.start_spin, self.end_spin, self.x_combo, self.y_list, self.grid_cb]:
            layout.addWidget(w)
        btn_load = QPushButton("读取 Sheet"); btn_load.clicked.connect(self.load_selected_sheet)
        btn_plot = QPushButton("生成图表"); btn_plot.clicked.connect(self.plot_data)
        layout.addWidget(btn_load); layout.addWidget(btn_plot); layout.addStretch(); return scroll

    def apply_config(self):
        file_path = self.config.get("file_path", "")
        sheet_name = self.config.get("sheet_name", "")
        if file_path:
            self.file_label.setText(file_path)
            try:
                sheets = self.data_processor.get_sheet_names(file_path)
                self.sheet_combo.clear(); self.sheet_combo.addItems(sheets)
                if sheet_name and sheet_name in sheets:
                    self.sheet_combo.setCurrentText(sheet_name)
                if self.config.get("auto_load", True):
                    self.load_selected_sheet()
            except Exception as e:
                QMessageBox.warning(self, "配置错误", str(e))
        if self.config.get("title"):
            self.title_edit.setText(str(self.config.get("title")))
        if self.config.get("x_label"):
            self.xname_edit.setText(str(self.config.get("x_label")))
        if self.config.get("y_label"):
            self.yname_edit.setText(str(self.config.get("y_label")))
        if self.config.get("show_grid") is not None:
            self.grid_cb.setChecked(bool(self.config.get("show_grid")))
        mode_map = {"scatter": "散点图", "line": "折线图", "line_scatter": "折线+散点图"}
        if self.config.get("plot_mode") in mode_map:
            self.mode_combo.setCurrentText(mode_map[self.config.get("plot_mode")])

    def load_selected_sheet(self):
        file_path = self.file_label.text().strip(); sheet = self.sheet_combo.currentText().strip()
        if not file_path or not sheet:
            return
        self.data_processor.load_from_excel(file_path, sheet)
        names = self.data_processor.get_variable_names(); length = max(0, len(self.data_processor.get_variable_data(names[0])) - 1) if names else 0
        self.start_spin.setMaximum(length); self.end_spin.setMaximum(length); self.end_spin.setValue(length)
        if isinstance(self.config.get("start_idx"), int):
            self.start_spin.setValue(max(0, min(length, self.config.get("start_idx"))))
        if isinstance(self.config.get("end_idx"), int):
            self.end_spin.setValue(max(0, min(length, self.config.get("end_idx"))))
        self.x_combo.clear(); self.x_combo.addItems(names); self.y_list.clear(); self.y_list.addItems(names)
        if self.config.get("x_var") in names:
            self.x_combo.setCurrentText(self.config["x_var"])
        for i in range(self.y_list.count()):
            it = self.y_list.item(i)
            if it.text() in self.config.get("y_vars", []):
                it.setSelected(True)

    def plot_data(self):
        yitems = self.y_list.selectedItems(); xvar = self.x_combo.currentText().strip()
        if not xvar or not yitems:
            return
        xdata = np.asarray(self.data_processor.get_variable_data(xvar)); ydict = {it.text(): np.asarray(self.data_processor.get_variable_data(it.text())) for it in yitems}
        mode_map = {"散点图": "scatter", "折线图": "line", "折线+散点图": "line_scatter"}
        self.plot_canvas.draw_plot(xdata, ydict, self.xname_edit.text().strip() or xvar, self.title_edit.text().strip() or "科学数据可视化",
                                 self.yname_edit.text().strip() or "Y", self.start_spin.value(), self.end_spin.value(), self.grid_cb.isChecked(),
                                 mode_map.get(self.mode_combo.currentText(), "scatter"))


def load_config(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    config = load_config(sys.argv[1]) if len(sys.argv) > 1 else {}
    app = QApplication(sys.argv); app.setStyle("Fusion"); app.setApplicationName("Excel 数据可视化"); app.setFont(QFont("SimHei", 10))
    wnd = MainWindow(config=config); wnd.show(); sys.exit(app.exec())


if __name__ == "__main__":
    main()
