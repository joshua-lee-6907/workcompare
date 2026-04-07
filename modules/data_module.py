"""
数据管理模块 — 选择并复制分段结果数据库为 2.db
Data Management Module: copy a selected .db file to 2.db for downstream analysis
Ported from dataweb.py (tkinter → PyQt5)
"""

import os
import shutil

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QGroupBox, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from .styles import COLORS


class DataWidget(QWidget):
    """数据管理面板 — 将指定的 .db 文件复制为 2.db"""

    status_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── 标题 ──
        title = QLabel("数据管理 — 选择分析数据源")
        title.setObjectName("lbl_title")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        sub = QLabel("将某个分段计算结果(.db)复制为 2.db，供 Q1D / Q60 分析模块使用")
        sub.setObjectName("lbl_subtitle")
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(_hline())

        # ── 说明 ──
        info = QLabel(
            "流程说明：批量计算完成后，会生成多个 Segment_X.db 文件。\n"
            "在此处选择其中一个，复制为 2.db，即可在下游分析中使用。"
        )
        info.setObjectName("lbl_info")
        info.setWordWrap(True)
        root.addWidget(info)

        # ── 源文件选择 ──
        src_group = QGroupBox("源文件")
        src_layout = QHBoxLayout(src_group)
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("选择要复制的 .db 文件 …")
        src_btn = QPushButton("浏览")
        src_btn.setFixedWidth(80)
        src_btn.clicked.connect(self._choose_src)
        src_layout.addWidget(self.src_edit)
        src_layout.addWidget(src_btn)
        root.addWidget(src_group)

        # ── 目标文件 ──
        dst_group = QGroupBox("目标文件")
        dst_layout = QHBoxLayout(dst_group)
        self.dst_edit = QLineEdit("2.db")
        self.dst_edit.setPlaceholderText("目标文件名，默认 2.db")
        dst_btn = QPushButton("另存为")
        dst_btn.setFixedWidth(80)
        dst_btn.clicked.connect(self._choose_dst)
        dst_layout.addWidget(self.dst_edit)
        dst_layout.addWidget(dst_btn)
        root.addWidget(dst_group)

        # ── 文件信息 ──
        info_group = QGroupBox("文件信息")
        info_layout = QVBoxLayout(info_group)
        self.info_table = QTableWidget(2, 2)
        self.info_table.setHorizontalHeaderLabels(["属性", "值"])
        self.info_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.info_table.setFixedHeight(90)
        self.info_table.setItem(0, 0, QTableWidgetItem("源文件大小"))
        self.info_table.setItem(0, 1, QTableWidgetItem("—"))
        self.info_table.setItem(1, 0, QTableWidgetItem("目标路径"))
        self.info_table.setItem(1, 1, QTableWidgetItem("—"))
        info_layout.addWidget(self.info_table)
        root.addWidget(info_group)

        # ── 状态 ──
        self.status_lbl = QLabel("就绪")
        self.status_lbl.setObjectName("lbl_subtitle")
        root.addWidget(self.status_lbl)

        # ── 按钮 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.copy_btn = QPushButton("📋  复制并重命名")
        self.copy_btn.setObjectName("btn_primary")
        self.copy_btn.clicked.connect(self._do_copy)
        self.copy_btn.setCursor(Qt.PointingHandCursor)

        self.reset_btn = QPushButton("↺  复位")
        self.reset_btn.setObjectName("btn_reset")
        self.reset_btn.setFixedWidth(100)
        self.reset_btn.clicked.connect(self._reset)
        self.reset_btn.setCursor(Qt.PointingHandCursor)

        btn_row.addStretch()
        btn_row.addWidget(self.reset_btn)
        btn_row.addWidget(self.copy_btn)
        root.addLayout(btn_row)
        root.addStretch()

        # connect src change to info update
        self.src_edit.textChanged.connect(self._update_info)
        self.dst_edit.textChanged.connect(self._update_info)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _choose_src(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "选择源 .db 文件", "", "SQLite 数据库 (*.db);;所有文件 (*)"
        )
        if p:
            self.src_edit.setText(p)
            # Auto-set destination in same directory
            dst = os.path.join(os.path.dirname(p), "2.db")
            self.dst_edit.setText(dst)

    def _choose_dst(self):
        p, _ = QFileDialog.getSaveFileName(
            self, "保存目标文件", "2.db",
            "SQLite 数据库 (*.db);;所有文件 (*)"
        )
        if p:
            self.dst_edit.setText(p)

    def _update_info(self):
        src = self.src_edit.text().strip()
        dst = self.dst_edit.text().strip()
        if src and os.path.isfile(src):
            size_kb = os.path.getsize(src) / 1024
            self.info_table.setItem(0, 1, QTableWidgetItem(f"{size_kb:.1f} KB"))
        else:
            self.info_table.setItem(0, 1, QTableWidgetItem("—"))
        self.info_table.setItem(1, 1, QTableWidgetItem(dst or "—"))

    def _reset(self):
        self.src_edit.clear()
        self.dst_edit.setText("2.db")
        self.status_lbl.setText("就绪")
        self.info_table.setItem(0, 1, QTableWidgetItem("—"))
        self.info_table.setItem(1, 1, QTableWidgetItem("—"))

    def _do_copy(self):
        src = self.src_edit.text().strip()
        dst = self.dst_edit.text().strip()

        if not src or not os.path.isfile(src):
            QMessageBox.critical(self, "错误", "请选择一个有效的源 .db 文件！")
            return
        if not dst:
            QMessageBox.critical(self, "错误", "请指定目标文件名！")
            return

        try:
            if os.path.exists(dst):
                reply = QMessageBox.question(
                    self, "确认覆盖",
                    f"目标文件已存在:\n{dst}\n是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
                os.remove(dst)
            shutil.copy2(src, dst)
            size_kb = os.path.getsize(dst) / 1024
            self.status_lbl.setText(f"✔ 已复制到 {dst} ({size_kb:.1f} KB)")
            self.status_changed.emit("数据文件复制完成")
            self._update_info()
            QMessageBox.information(
                self, "成功",
                f"文件已复制:\n{src}\n→ {dst}\n大小: {size_kb:.1f} KB"
            )
        except Exception as e:
            self.status_lbl.setText("复制失败")
            self.status_changed.emit("数据文件复制失败")
            QMessageBox.critical(self, "复制失败", str(e))


def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f
