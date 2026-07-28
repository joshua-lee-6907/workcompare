"""hb_data.py – Tab 4: Data management (copy & rename Segment DB to 2.db)."""

import os
import shutil
import sqlite3

from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class DataTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 16, 20, 16)

        title = QLabel("💾  数据管理 — 选择计算结果数据库")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        desc = QLabel(
            "选择某个 Segment_N.db 文件（由批量计算生成），复制并重命名为 2.db，"
            "供后续 Q1D 和 Q60 分析使用。"
        )
        desc.setObjectName("subtext")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # ── Source DB ──
        grp = QGroupBox("选择 Segment_N.db 文件")
        gl  = QHBoxLayout(grp)
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("如 Segment_1.db …")
        btn_src = QPushButton("浏览")
        btn_src.setObjectName("secondary")
        btn_src.setFixedWidth(70)
        btn_src.clicked.connect(self._choose_src)
        gl.addWidget(self.src_edit)
        gl.addWidget(btn_src)
        root.addWidget(grp)

        # ── Target path ──
        grp2 = QGroupBox("目标文件 (2.db)")
        gl2  = QHBoxLayout(grp2)
        self.tgt_edit = QLineEdit("2.db")
        self.tgt_edit.setPlaceholderText("目标路径…")
        btn_tgt = QPushButton("另存为…")
        btn_tgt.setObjectName("secondary")
        btn_tgt.setFixedWidth(90)
        btn_tgt.clicked.connect(self._choose_tgt)
        gl2.addWidget(self.tgt_edit)
        gl2.addWidget(btn_tgt)
        root.addWidget(grp2)

        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("status")
        root.addWidget(self.lbl_status)

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("📋  复制 → 2.db")
        btn_copy.setFont(QFont("Segoe UI", 13, QFont.Bold))
        btn_copy.clicked.connect(self._copy)

        btn_preview = QPushButton("🔍  预览数据库内容")
        btn_preview.setObjectName("secondary")
        btn_preview.clicked.connect(self._preview)

        btn_reset = QPushButton("↺  复位")
        btn_reset.setObjectName("reset")
        btn_reset.clicked.connect(self._reset)

        btn_row.addWidget(btn_copy)
        btn_row.addWidget(btn_preview)
        btn_row.addWidget(btn_reset)
        root.addLayout(btn_row)

        # ── Preview table ──
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["start_index", "end_index", "Q1d", "A8", "dp_mean"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table)

    def _choose_src(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择 Segment DB", "",
                                           "SQLite DB (*.db);;所有文件 (*)")
        if p:
            self.src_edit.setText(p)

    def _choose_tgt(self):
        p, _ = QFileDialog.getSaveFileName(self, "保存为", "2.db",
                                           "SQLite DB (*.db);;所有文件 (*)")
        if p:
            self.tgt_edit.setText(p)

    def _reset(self):
        self.src_edit.clear()
        self.tgt_edit.setText("2.db")
        self.lbl_status.setText("已复位")
        self.table.setRowCount(0)

    def _copy(self):
        src = self.src_edit.text().strip()
        tgt = self.tgt_edit.text().strip()
        if not os.path.isfile(src):
            QMessageBox.critical(self, "错误", "请选择一个有效的 .db 文件！")
            return
        if not tgt:
            QMessageBox.critical(self, "错误", "请指定目标文件路径！")
            return
        try:
            if os.path.exists(tgt):
                os.remove(tgt)
            shutil.copy2(src, tgt)
            self.lbl_status.setText(f"✅ 已复制: {os.path.basename(src)} → {tgt}")
            QMessageBox.information(self, "成功",
                f"文件已复制并保存为:\n{tgt}")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def _preview(self):
        src = self.src_edit.text().strip()
        if not os.path.isfile(src):
            QMessageBox.critical(self, "错误", "请先选择有效的 .db 文件！")
            return
        try:
            conn = sqlite3.connect(src)
            cur  = conn.cursor()
            cur.execute("SELECT start_index, end_index, Q1d, A8, dp_mean "
                        "FROM results LIMIT 200")
            rows = cur.fetchall()
            conn.close()
            self.table.setRowCount(0)
            for row in rows:
                r = self.table.rowCount()
                self.table.insertRow(r)
                for c, val in enumerate(row):
                    txt = f"{val:.6g}" if isinstance(val, float) else str(val)
                    item = QTableWidgetItem(txt)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(r, c, item)
            self.lbl_status.setText(
                f"预览 {len(rows)} 行（最多200行）来自 {os.path.basename(src)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取数据库出错：{e}")
