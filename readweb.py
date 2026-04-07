#!/usr/bin/env python3
import sys
import os
import xlrd
import sqlite3
from datetime import date, timedelta
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFileDialog, QDateEdit, QMessageBox, QProgressBar
)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QFont, QPalette, QColor

def read_excel_file(excel_file, time_offset):
    try:
        workbook = xlrd.open_workbook(excel_file)
    except Exception as e:
        raise Exception(f"无法打开文件 {excel_file}: {e}")

    sheet = workbook.sheet_by_index(0)
    data = []
    num_data_rows = sheet.nrows - 4
    for i in range(4, sheet.nrows):
        dp_cell = sheet.cell(i, 2)   # C列
        dvh_cell = sheet.cell(i, 14) # O列
        try:
            dp_value = float(dp_cell.value)
            dvh_value = float(dvh_cell.value)
        except (ValueError, TypeError):
            continue
        local_index = i - 4  # 从0开始
        time_val = time_offset + 0.5 * (local_index + 1)
        data.append((time_val, dvh_value, dp_value))
    new_offset = time_offset + 0.5 * num_data_rows
    return data, new_offset

def generate_file_names(start_date, end_date, dir_path):
    delta = timedelta(days=1)
    current = start_date
    file_names = []
    while current <= end_date:
        file_name = f"半小时计算数据报表2023年{current.month}月{current.day}日.xls"
        file_names.append(os.path.join(dir_path, file_name))
        current += delta
    return file_names

def save_to_sqlite(db_file, data):
    if os.path.exists(db_file):
        os.remove(db_file)
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data (
            time REAL,
            DVH REAL,
            DP REAL
        )
    """)
    cursor.executemany("INSERT INTO data (time, DVH, DP) VALUES (?, ?, ?)", data)
    conn.commit()
    conn.close()

class ExcelToDbApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🛰️ Excel 批量数据转SQLite数据库")
        self.setGeometry(400, 200, 540, 410)
        self.init_ui()
        self.set_dark_blue_style()

    def set_dark_blue_style(self):
        # 深蓝色高科技风格
        dark_blue = "#101532"
        mid_blue = "#142468"
        accent_blue = "#00d4ff"
        text_color = "#e9f1fb"
        hint_color = "#96b3f7"
        border_color = "#2659a8"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {dark_blue};
                color: {text_color};
                font-family: 'Segoe UI', 'Arial', 'Microsoft YaHei', sans-serif;
                font-size: 15px;
            }}
            QLabel {{
                color: {accent_blue};
                font-weight: bold;
                font-size: 15px;
            }}
            QLineEdit, QDateEdit {{
                background-color: {mid_blue};
                color: {text_color};
                border: 1.5px solid {border_color};
                border-radius: 7px;
                padding: 5px 9px;
                font-size: 15px;
            }}
            QLineEdit:focus, QDateEdit:focus {{
                border: 2px solid {accent_blue};
            }}
            QPushButton {{
                background-color: {accent_blue};
                color: {dark_blue};
                font-weight: bold;
                border-radius: 9px;
                padding: 8px 18px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: #0ab7e8;
                color: white;
            }}
            QProgressBar {{
                background-color: {mid_blue};
                border: 1px solid {border_color};
                border-radius: 7px;
                text-align: center;
                color: {text_color};
                font-size: 15px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3af1ff, stop:1 #0059c1
                );
                border-radius: 7px;
            }}
        """)
        self.setFont(QFont("Segoe UI", 12))

    def init_ui(self):
        # 日期选择
        self.start_label = QLabel("开始日期 (2023-04-01):")
        self.start_date = QDateEdit(self)
        self.start_date.setDate(QDate(2023, 4, 1))
        self.start_date.setDisplayFormat('yyyy-MM-dd')
        self.start_date.setCalendarPopup(True)
        self.start_date.setFont(QFont("Segoe UI", 12))

        self.end_label = QLabel("结束日期 (2023-10-30):")
        self.end_date = QDateEdit(self)
        self.end_date.setDate(QDate(2023, 10, 30))
        self.end_date.setDisplayFormat('yyyy-MM-dd')
        self.end_date.setCalendarPopup(True)
        self.end_date.setFont(QFont("Segoe UI", 12))

        # 选择文件夹
        self.dir_label = QLabel("Excel文件所在文件夹:")
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("请选择包含所有Excel的文件夹")
        self.dir_btn = QPushButton("选择文件夹")
        self.dir_btn.clicked.connect(self.choose_dir)

        # 选择数据库保存路径
        self.db_label = QLabel("保存的SQLite数据库文件名:")
        self.db_edit = QLineEdit("d1.db")
        self.db_edit.setPlaceholderText("如 d1.db")
        self.db_btn = QPushButton("选择保存位置")
        self.db_btn.clicked.connect(self.choose_db_file)

        # 进度条
        self.progress = QProgressBar(self)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setFixedHeight(26)

        # 执行按钮
        self.run_btn = QPushButton("🚀 开始处理")
        self.run_btn.setFont(QFont("Segoe UI", 15, QFont.Bold))
        self.run_btn.clicked.connect(self.run_processing)
        self.run_btn.setCursor(Qt.PointingHandCursor)

        # 布局
        layout = QVBoxLayout()
        layout.setSpacing(17)
        layout.addWidget(self.start_label)
        layout.addWidget(self.start_date)
        layout.addWidget(self.end_label)
        layout.addWidget(self.end_date)
        layout.addWidget(self.dir_label)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.dir_edit)
        dir_layout.addWidget(self.dir_btn)
        layout.addLayout(dir_layout)
        layout.addWidget(self.db_label)
        db_layout = QHBoxLayout()
        db_layout.addWidget(self.db_edit)
        db_layout.addWidget(self.db_btn)
        layout.addLayout(db_layout)
        layout.addWidget(self.progress)
        layout.addWidget(self.run_btn)
        self.setLayout(layout)

    def choose_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择包含Excel的文件夹", "")
        if directory:
            self.dir_edit.setText(directory)

    def choose_db_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存数据库为", "d1.db", "SQLite DB Files (*.db);;All Files (*)")
        if path:
            self.db_edit.setText(path)

    def run_processing(self):
        # 校验输入
        if not self.dir_edit.text() or not os.path.isdir(self.dir_edit.text()):
            QMessageBox.critical(self, "错误", "请输入有效的Excel文件夹路径！")
            return
        db_file = self.db_edit.text().strip()
        if not db_file:
            QMessageBox.critical(self, "错误", "请输入数据库文件名！")
            return
        start = self.start_date.date()
        end = self.end_date.date()
        if end < start:
            QMessageBox.critical(self, "错误", "结束日期不能早于开始日期！")
            return
        start_date = date(start.year(), start.month(), start.day())
        end_date = date(end.year(), end.month(), end.day())
        files = generate_file_names(start_date, end_date, self.dir_edit.text())
        total_files = len(files)
        self.progress.setMaximum(total_files)
        self.progress.setValue(0)
        all_data = []
        cumulative_time_offset = 0.0
        processed = 0

        for file in files:
            QApplication.processEvents()
            try:
                file_data, cumulative_time_offset = read_excel_file(file, cumulative_time_offset)
                all_data.extend(file_data)
            except Exception as e:
                print(f"处理文件 {file} 时出错: {e}")
            processed += 1
            self.progress.setValue(processed)

        if not all_data:
            QMessageBox.warning(self, "没有数据", "没有有效数据被读取。")
            return
        try:
            save_to_sqlite(db_file, all_data)
            self.progress.setValue(total_files)
            QMessageBox.information(
                self, "完成",
                f"所有数据已保存到数据库 {db_file}。\n总共 {len(all_data)} 行数据。"
            )
        except Exception as e:
            QMessageBox.critical(self, "数据库错误", f"保存到数据库时出错: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ExcelToDbApp()
    window.show()
    sys.exit(app.exec_())