#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import numpy as np
import pandas as pd

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QListWidget, QListWidgetItem, QFileDialog,
    QLineEdit, QMessageBox, QAbstractItemView, QGroupBox, QFormLayout, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar


def set_chinese_font():
    font_path = os.path.join(os.path.dirname(__file__), "1.ttf")
    if os.path.exists(font_path):
        try:
            fm.fontManager.addfont(font_path)
            font_name = fm.FontProperties(fname=font_path).get_name()
            plt.rcParams["font.sans-serif"] = [font_name]
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["axes.unicode_minus"] = False
            return
        except Exception:
            pass
    preferred = [
        "Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans CJK SC",
        "WenQuanYi Zen Hei", "Heiti SC"
    ]
    for name in preferred:
        try:
            fp = fm.FontProperties(family=name)
            path = fm.findfont(fp, fallback_to_default=True)
            if path and "DejaVu" not in path:
                plt.rcParams["font.sans-serif"] = [name]
                plt.rcParams["font.family"] = "sans-serif"
                break
        except Exception:
            continue
    plt.rcParams["axes.unicode_minus"] = False


set_chinese_font()
plt.style.use("seaborn-v0_8-whitegrid")


class ExcelPlotter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_path = ""
        self.df = pd.DataFrame()
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("Excel 科学绘图工具（折线/散点/组合）")
        self.resize(1400, 900)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)

        left = QWidget()
        left.setMaximumWidth(460)
        left_layout = QVBoxLayout(left)

        file_group = QGroupBox("1) 文件与工作表")
        fg = QVBoxLayout(file_group)
        row = QHBoxLayout()
        self.file_label = QLabel("未选择文件")
        btn_file = QPushButton("选择 xls/xlsx")
        btn_file.clicked.connect(self.choose_file)
        row.addWidget(btn_file)
        row.addWidget(self.file_label)
        fg.addLayout(row)

        sheet_row = QHBoxLayout()
        self.sheet_combo = QComboBox()
        btn_sheet = QPushButton("读取 Sheet")
        btn_sheet.clicked.connect(self.load_sheet)
        sheet_row.addWidget(QLabel("Sheet:"))
        sheet_row.addWidget(self.sheet_combo)
        sheet_row.addWidget(btn_sheet)
        fg.addLayout(sheet_row)
        left_layout.addWidget(file_group)

        var_group = QGroupBox("2) 变量与图形类型")
        vg = QVBoxLayout(var_group)
        self.x_combo = QComboBox()
        self.y_list = QListWidget()
        self.y_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.plot_type = QComboBox()
        self.plot_type.addItems(["折线图", "散点图", "折线+散点图"])
        vg.addWidget(QLabel("X 轴变量"))
        vg.addWidget(self.x_combo)
        vg.addWidget(QLabel("Y 轴变量（多选）"))
        vg.addWidget(self.y_list)
        vg.addWidget(QLabel("图形类型"))
        vg.addWidget(self.plot_type)
        left_layout.addWidget(var_group)

        style_group = QGroupBox("3) 标题与轴名称")
        sg = QFormLayout(style_group)
        self.title_edit = QLineEdit("科学数据可视化")
        self.xlabel_edit = QLineEdit("X")
        self.ylabel_edit = QLineEdit("Y")
        self.legend_title_edit = QLineEdit("变量")
        self.tight_cb = QCheckBox("自动紧凑布局")
        self.tight_cb.setChecked(True)
        sg.addRow("图名", self.title_edit)
        sg.addRow("X 轴名", self.xlabel_edit)
        sg.addRow("Y 轴名", self.ylabel_edit)
        sg.addRow("图例标题", self.legend_title_edit)
        sg.addRow(self.tight_cb)
        left_layout.addWidget(style_group)

        btn_plot = QPushButton("绘图")
        btn_plot.clicked.connect(self.draw_plot)
        btn_save = QPushButton("保存无损图片")
        btn_save.clicked.connect(self.save_figure)
        left_layout.addWidget(btn_plot)
        left_layout.addWidget(btn_save)
        left_layout.addStretch()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.figure = Figure(figsize=(10, 7), dpi=120)
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)

        layout.addWidget(left)
        layout.addWidget(right)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Excel 文件",
            "",
            "Excel 文件 (*.xls *.xlsx)"
        )
        if not path:
            return
        self.file_path = path
        self.file_label.setText(os.path.basename(path))
        try:
            xls = pd.ExcelFile(path)
            self.sheet_combo.clear()
            self.sheet_combo.addItems(xls.sheet_names)
        except Exception as e:
            QMessageBox.critical(self, "读取失败", f"无法读取文件：\n{e}")

    def load_sheet(self):
        if not self.file_path:
            QMessageBox.warning(self, "提示", "请先选择 Excel 文件")
            return
        sheet = self.sheet_combo.currentText()
        if not sheet:
            QMessageBox.warning(self, "提示", "请选择 Sheet")
            return
        try:
            self.df = pd.read_excel(self.file_path, sheet_name=sheet)
            self.df = self.df.dropna(axis=1, how="all")
            if self.df.empty:
                QMessageBox.warning(self, "提示", "该 Sheet 无有效数据")
                return
            cols = [str(c) for c in self.df.columns]
            self.x_combo.clear()
            self.x_combo.addItems(cols)
            self.y_list.clear()
            for c in cols:
                self.y_list.addItem(QListWidgetItem(c))

            self.xlabel_edit.setText(self.x_combo.currentText() or "X")
            self.ylabel_edit.setText("Y")
            self.statusBar().showMessage(f"已读取: {sheet}，共 {len(self.df)} 行")
        except Exception as e:
            QMessageBox.critical(self, "读取失败", f"读取 Sheet 失败：\n{e}")

    def draw_plot(self):
        if self.df.empty:
            QMessageBox.warning(self, "提示", "请先读取数据")
            return

        x_col = self.x_combo.currentText()
        y_cols = [i.text() for i in self.y_list.selectedItems() if i.text() != x_col]
        if not x_col:
            QMessageBox.warning(self, "提示", "请选择 X 轴变量")
            return
        if not y_cols:
            QMessageBox.warning(self, "提示", "请至少选择一个 Y 轴变量（且不同于 X）")
            return

        x = pd.to_numeric(self.df[x_col], errors="coerce").to_numpy()
        valid_x = np.isfinite(x)

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        colors = plt.cm.tab10.colors

        ptype = self.plot_type.currentText()
        for idx, y_col in enumerate(y_cols):
            y = pd.to_numeric(self.df[y_col], errors="coerce").to_numpy()
            valid = valid_x & np.isfinite(y)
            if not np.any(valid):
                continue
            xv, yv = x[valid], y[valid]
            color = colors[idx % len(colors)]

            if ptype == "折线图":
                ax.plot(xv, yv, lw=2.0, color=color, label=y_col)
            elif ptype == "散点图":
                ax.scatter(xv, yv, s=28, alpha=0.9, color=color, label=y_col)
            else:
                ax.plot(xv, yv, lw=1.8, alpha=0.8, color=color)
                ax.scatter(xv, yv, s=26, alpha=0.95, color=color, label=y_col)

        ax.set_title(self.title_edit.text().strip() or "科学数据可视化", fontsize=15, weight="bold")
        ax.set_xlabel(self.xlabel_edit.text().strip() or x_col, fontsize=12)
        ax.set_ylabel(self.ylabel_edit.text().strip() or "Y", fontsize=12)
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.legend(title=self.legend_title_edit.text().strip() or "变量", frameon=True)

        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        ax.spines["left"].set_linewidth(1.2)
        ax.spines["bottom"].set_linewidth(1.2)

        if self.tight_cb.isChecked():
            self.figure.tight_layout()
        self.canvas.draw_idle()

    def save_figure(self):
        if not self.figure.axes:
            QMessageBox.warning(self, "提示", "请先绘图")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存无损图片",
            "plot.png",
            "PNG 无损 (*.png);;TIFF 无损 (*.tiff);;SVG 矢量 (*.svg);;PDF 矢量 (*.pdf)"
        )
        if not path:
            return
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in [".png", ".tiff"]:
                self.figure.savefig(path, dpi=300, bbox_inches="tight")
            else:
                self.figure.savefig(path, bbox_inches="tight")
            self.statusBar().showMessage(f"已保存: {path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei", 10))
    w = ExcelPlotter()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
