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
- 科技风 UI / 动效 / 可拖拽分栏 / 图表可独立浮窗
"""

import os
import re
import sys
import platform
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QIcon, QColor
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QMessageBox,
    QAbstractItemView, QSplitter, QCheckBox, QRadioButton, QButtonGroup,
    QDoubleSpinBox, QFileDialog, QGroupBox, QSpinBox, QDialog, QDialogButtonBox,
    QGraphicsDropShadowEffect
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
        StrongBodyLabel,
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
        StrongBodyLabel,
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
plt.rcParams.update({
    "axes.grid": True,
    "grid.linestyle": "--",
    "grid.alpha": 0.35,
    "axes.spines.top": False,
    "figure.dpi": 120,
})
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
        self.figure = Figure(facecolor="#0b1220", dpi=110)
        super().__init__(self.figure)
        self.parent_window = parent_window
        self._plot_storage = {}
        self._legend_map = {}
        self.axes_list = []
        self._axis_outward = {}

    def _update_axis_positions(self):
        for i, ax in enumerate(self.axes_list[1:], start=1):
            offset = self._axis_outward.get(i, 0)
            ax.spines["right"].set_position(("outward", offset))

    def draw_plot(self, x_data, y_data_dict, x_label, title_text, y_axis_name, start_idx, end_idx,
                  show_grid=True, plot_mode="scatter", axis_ranges=None):
        self.figure.clear()
        self._plot_storage.clear()
        self._legend_map.clear()
        self._axis_outward.clear()
        self.axes_list = []

        x_arr = np.asarray(x_data)
        x_slice = x_arr[start_idx:end_idx + 1]

        ax_main = self.figure.add_subplot(111)
        ax_main.set_facecolor("#111827")
        self.axes_list.append(ax_main)

        colors = ["#38bdf8", "#f472b6", "#34d399", "#a78bfa", "#f59e0b", "#22d3ee", "#fb7185"]
        groups = {}
        for name in y_data_dict:
            groups.setdefault(axis_group_key(name), []).append(name)

        handles, labels = [], []
        for gi, (group_key, var_names) in enumerate(groups.items()):
            ax = ax_main if gi == 0 else ax_main.twinx()
            if gi > 0:
                self._axis_outward[gi] = 65 * (gi - 1)
                ax.spines["right"].set_position(("outward", self._axis_outward[gi]))
                ax.set_facecolor("none")
                self.axes_list.append(ax)

            for vi, var in enumerate(var_names):
                y_slice = np.asarray(y_data_dict[var])[start_idx:end_idx + 1]
                color = colors[(gi * 2 + vi) % len(colors)]
                line_obj = None
                scatter_obj = None
                if plot_mode in ("line", "line_scatter"):
                    line_obj, = ax.plot(x_slice, y_slice, color=color, linewidth=2.2, alpha=0.95, label=var)
                if plot_mode in ("scatter", "line_scatter"):
                    scatter_obj = ax.scatter(x_slice, y_slice, s=40, facecolor=color, edgecolor="#e5e7eb", linewidth=0.8, alpha=0.95, label=var)
                handles.append(scatter_obj if scatter_obj is not None else line_obj)
                labels.append(var)

            ax.set_ylabel(y_axis_name if gi == 0 else f"{y_axis_name}-{group_key}", fontsize=11, fontweight="bold", color="#e5e7eb")
            ax.tick_params(colors="#cbd5e1")

        ax_main.set_xlabel(x_label, fontsize=11, fontweight="bold", color="#e5e7eb")
        ax_main.set_title(title_text, fontsize=14, fontweight="bold", color="#f8fafc")
        if show_grid:
            ax_main.grid(True, linestyle="--", linewidth=0.8, alpha=0.35, color="#334155")

        legend = ax_main.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=True, fontsize=9)
        legend.get_frame().set_facecolor("#0f172a")
        legend.get_frame().set_edgecolor("#334155")
        for txt in legend.get_texts():
            txt.set_color("#e2e8f0")

        self._update_axis_positions()
        self.figure.tight_layout(rect=[0, 0, 0.85, 1])
        self.draw()


class FloatingPlotWindow(QWidget):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图表浮窗")
        self.resize(980, 680)
        self.setWindowFlags(Qt.Window)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(NavigationToolbar(canvas, self))
        layout.addWidget(canvas)


class ExcelVisualizerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_processor = DataProcessor()
        self.plot_canvas = PlotCanvas(parent_window=self)
        self.floating_window = None
        self._build_ui()

    def _add_shadow(self, widget):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 7)
        shadow.setColor(QColor(56, 189, 248, 70))
        widget.setGraphicsEffect(shadow)

    def _build_ui(self):
        self.setObjectName("excelVisualizerPage")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        header = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(TitleLabel("⚡ Excel 数据交互式可视化", self))
        self.subtitle = BodyLabel("科技风控制台 | 多轴绘图 | 实时状态", self)
        left.addWidget(self.subtitle)
        header.addLayout(left, 1)

        self.clock_label = StrongBodyLabel(self)
        header.addWidget(self.clock_label, 0, Qt.AlignRight | Qt.AlignTop)
        main_layout.addLayout(header)

        split = QSplitter(Qt.Horizontal, self)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(10)

        control = self.create_control_panel()
        plot = self.create_plot_widget()
        split.addWidget(control)
        split.addWidget(plot)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([460, 1180])
        main_layout.addWidget(split, 1)

        self.status_label = BodyLabel("就绪", self)
        main_layout.addWidget(self.status_label)

        self._apply_style()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def _tick(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.clock_label.setText(f"🕒 {now}")
        self.status_label.setText(f"变量: {len(self.data_processor.get_variable_names())} | 行数: {self.data_processor.get_data_length()}")

    def _apply_style(self):
        self.setStyleSheet("""
        QWidget#excelVisualizerPage {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #020617, stop:1 #0f172a);} 
        QGroupBox {border:1px solid rgba(56,189,248,0.35); border-radius:12px; margin-top:12px; padding:10px; background:rgba(15,23,42,0.45);} 
        QGroupBox::title {color:#7dd3fc; font-weight:700; left:10px; padding:0 6px;} 
        """)

    def create_plot_widget(self):
        w = QWidget(self)
        l = QVBoxLayout(w)
        card = SimpleCardWidget(w)
        self._add_shadow(card)
        cl = QVBoxLayout(card)
        cl.addWidget(NavigationToolbar(self.plot_canvas, self))
        cl.addWidget(self.plot_canvas)
        l.addWidget(card)
        return w

    def create_control_panel(self):
        scroll = ScrollArea(self)
        scroll.setWidgetResizable(True)
        panel = QWidget()
        scroll.setWidget(panel)
        layout = QVBoxLayout(panel)

        file_box = QGroupBox("数据源")
        fl = QVBoxLayout(file_box)
        r1 = QHBoxLayout()
        self.file_label = LineEdit(self)
        self.file_label.setReadOnly(True)
        self.file_label.setPlaceholderText("未选择文件")
        btn_file = PrimaryPushButton("选择文件", self)
        btn_file.clicked.connect(self.choose_excel_file)
        r1.addWidget(btn_file)
        r1.addWidget(self.file_label, 1)
        fl.addLayout(r1)

        r2 = QHBoxLayout()
        self.sheet_combo = ComboBox(self)
        btn_load = PushButton("读取Sheet", self)
        btn_load.clicked.connect(self.load_selected_sheet)
        r2.addWidget(self.sheet_combo, 1)
        r2.addWidget(btn_load)
        fl.addLayout(r2)
        layout.addWidget(file_box)

        self.title_edit = LineEdit(self); self.title_edit.setText("科学数据可视化")
        self.xname_edit = LineEdit(self); self.xname_edit.setText("X 轴")
        self.yname_edit = LineEdit(self); self.yname_edit.setText("Y 轴")
        self.mode_combo = ComboBox(self); self.mode_combo.addItems(["散点图", "折线图", "折线+散点图"])
        self.start_spin = QSpinBox(self); self.end_spin = QSpinBox(self)
        self.x_combo = ComboBox(self)
        self.y_list = QListWidget(self); self.y_list.setSelectionMode(QAbstractItemView.MultiSelection); self.y_list.setMinimumHeight(140)
        self.grid_cb = CheckBox("显示网格", self); self.grid_cb.setChecked(True)

        for title, wdt in [("图名", self.title_edit), ("X轴名", self.xname_edit), ("Y轴名", self.yname_edit), ("图型", self.mode_combo), ("X轴变量", self.x_combo), ("Y轴变量(多选)", self.y_list), ("开始索引", self.start_spin), ("结束索引", self.end_spin), ("网格", self.grid_cb)]:
            box = QGroupBox(title)
            bl = QVBoxLayout(box)
            bl.addWidget(wdt)
            layout.addWidget(box)

        btn_plot = PrimaryPushButton("生成图表", self)
        btn_plot.clicked.connect(self.plot_data)
        btn_save = PushButton("保存无损图片", self)
        btn_save.clicked.connect(self.save_figure_lossless)
        btn_pop = PushButton("图表浮出窗口", self)
        btn_pop.clicked.connect(self.popout_plot)
        btn_reset = PushButton("重置参数", self)
        btn_reset.clicked.connect(self.reset_controls)

        for b in (btn_plot, btn_save, btn_pop, btn_reset):
            self._add_shadow(b)
            layout.addWidget(b)

        layout.addStretch(1)
        return scroll

    def choose_excel_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Excel 文件", "", "Excel 文件 (*.xlsx *.xls)")
        if not path:
            return
        self.file_label.setText(path)
        try:
            sheets = self.data_processor.get_sheet_names(path)
            self.sheet_combo.clear()
            self.sheet_combo.addItems(sheets)
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def load_selected_sheet(self):
        file_path = self.file_label.text().strip()
        sheet = self.sheet_combo.currentText().strip()
        if not file_path or file_path == "未选择文件" or not sheet:
            QMessageBox.warning(self, "提示", "请先选择文件与Sheet")
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

    def plot_data(self):
        s, e = self.start_spin.value(), self.end_spin.value()
        if s > e:
            QMessageBox.warning(self, "错误", "起始索引不能大于结束索引")
            return
        xvar = self.x_combo.currentText().strip()
        yitems = self.y_list.selectedItems()
        if not xvar or not yitems:
            QMessageBox.warning(self, "错误", "请先选择X与至少一个Y")
            return
        xdata = np.asarray(self.data_processor.get_variable_data(xvar))
        ydict = {it.text(): np.asarray(self.data_processor.get_variable_data(it.text())) for it in yitems}
        max_idx = min([len(xdata)-1] + [len(v)-1 for v in ydict.values()])
        if e > max_idx:
            e = max_idx
            self.end_spin.setValue(e)
        mode_map = {"散点图": "scatter", "折线图": "line", "折线+散点图": "line_scatter"}
        self.plot_canvas.draw_plot(
            x_data=xdata,
            y_data_dict=ydict,
            x_label=self.xname_edit.text().strip() or xvar,
            title_text=self.title_edit.text().strip() or "科学数据可视化",
            y_axis_name=self.yname_edit.text().strip() or "Y",
            start_idx=s,
            end_idx=e,
            show_grid=self.grid_cb.isChecked(),
            plot_mode=mode_map.get(self.mode_combo.currentText(), "scatter"),
            axis_ranges=None,
        )

    def popout_plot(self):
        if not self.plot_canvas.figure.axes:
            QMessageBox.warning(self, "提示", "请先生成图表")
            return
        self.floating_window = FloatingPlotWindow(self.plot_canvas, self)
        self.floating_window.show()

    def save_figure_lossless(self):
        if not self.plot_canvas.figure.axes:
            QMessageBox.warning(self, "提示", "请先生成图表")
            return
        path, selected_filter = QFileDialog.getSaveFileName(self, "保存无损图片", "plot.png",
            "PNG 无损位图 (*.png);;TIFF 无损位图 (*.tiff);;SVG 矢量图 (*.svg);;PDF 矢量图 (*.pdf)")
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".tiff" if "TIFF" in selected_filter else ".svg" if "SVG" in selected_filter else ".pdf" if "PDF" in selected_filter else ".png"
        ext = os.path.splitext(path)[1].lower()
        fmt = {".png":"png", ".tif":"tiff", ".tiff":"tiff", ".svg":"svg", ".pdf":"pdf"}.get(ext)
        if fmt is None:
            QMessageBox.warning(self, "提示", "请保存为 PNG/TIFF/SVG/PDF")
            return
        self.plot_canvas.figure.savefig(path, dpi=300, format=fmt, bbox_inches="tight", pad_inches=0.05, facecolor="#0b1220")
        QMessageBox.information(self, "完成", f"已保存: {path}")

    def reset_controls(self):
        self.title_edit.setText("科学数据可视化")
        self.xname_edit.setText("X 轴")
        self.yname_edit.setText("Y 轴")
        self.mode_combo.setCurrentIndex(0)
        self.grid_cb.setChecked(True)


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.page = ExcelVisualizerPage(self)
        self.addSubInterface(self.page, FluentIcon.LIBRARY, "Excel 可视化")
        self.setWindowTitle("Excel 数据可视化 | 科技风")
        self.setWindowIcon(QIcon())
        self.resize(1680, 1020)
        self._enter_anim = QPropertyAnimation(self, b"windowOpacity")
        self._enter_anim.setDuration(450)
        self._enter_anim.setStartValue(0.0)
        self._enter_anim.setEndValue(1.0)
        self._enter_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._enter_anim.start()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Excel 数据可视化")
    app.setFont(QFont("Microsoft YaHei", 10))
    setTheme(Theme.DARK)
    wnd = MainWindow()
    wnd.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
