import sys
import os
import sqlite3
import pandas as pd
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QProgressBar, QLabel, QMessageBox,
    QHBoxLayout, QLineEdit, QPushButton, QFileDialog
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont

class DatabaseApp(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = "30.db"  # Default database file
        self.init_ui()

    def set_dark_blue_style(self):
        dark_blue = "#101532"
        mid_blue = "#142468"
        accent_blue = "#00d4ff"
        text_color = "#e9f1fb"
        border_color = "#2659a8"
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {dark_blue};
                color: {text_color};
                font-family: 'Microsoft YaHei', 'Segoe UI', 'Arial', 'sans-serif';
                font-size: 15px;
            }}
            QLabel {{
                color: {accent_blue};
                font-weight: bold;
                font-size: 16px;
            }}
            QLineEdit {{
                background-color: {mid_blue};
                color: {text_color};
                border: 1.5px solid {border_color};
                border-radius: 7px;
                padding: 5px 9px;
                font-size: 15px;
            }}
            QLineEdit:focus {{
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
                font-size: 16px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3af1ff, stop:1 #0059c1
                );
                border-radius: 7px;
            }}
        """)
        self.setFont(QFont("Microsoft YaHei", 12))

    def init_ui(self):
        self.setWindowTitle('🛰️ 分段表批量计算器')
        self.resize(580, 220)
        self.set_dark_blue_style()

        self.layout = QVBoxLayout()
        self.layout.setSpacing(22)

        # 数据库路径选择
        db_row = QHBoxLayout()
        self.db_label = QLabel("源数据库文件:")
        self.db_edit = QLineEdit(self.db_path)
        self.db_btn = QPushButton("选择")
        self.db_btn.clicked.connect(self.choose_db)
        db_row.addWidget(self.db_edit)
        db_row.addWidget(self.db_btn)
        self.layout.addWidget(self.db_label)
        self.layout.addLayout(db_row)

        # 状态标签
        self.status_label = QLabel("等待开始...", self)
        self.status_label.setFont(QFont("Microsoft YaHei", 13))
        self.layout.addWidget(self.status_label)

        # 进度条
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(28)
        self.layout.addWidget(self.progress_bar)

        # 操作按钮
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("🚀 开始批量计算并保存")
        self.run_btn.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        self.run_btn.clicked.connect(self.process_all_segments)
        self.run_btn.setCursor(Qt.PointingHandCursor)
        btn_row.addWidget(self.run_btn)
        self.layout.addLayout(btn_row)

        self.setLayout(self.layout)

    def choose_db(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择数据库文件", "", "SQLite DB Files (*.db);;All Files (*)")
        if path:
            self.db_edit.setText(path)
            self.db_path = path

    def process_all_segments(self):
        self.db_path = self.db_edit.text().strip()
        if not self.db_path or not os.path.exists(self.db_path):
            QMessageBox.critical(self, "错误", "数据库文件不存在！")
            return

        try:
            conn = sqlite3.connect(self.db_path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开数据库: {e}")
            return

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()

        segment_tables = [table[0] for table in tables if table[0].startswith("Segment_")]
        total_tables = len(segment_tables)
        if total_tables == 0:
            QMessageBox.information(self, "信息", "未在数据库中找到Segment_表")
            return

        self.progress_bar.setMaximum(total_tables)
        self.progress_bar.setValue(0)

        for i, table_name in enumerate(segment_tables):
            self.status_label.setText(f"正在计算表: {table_name} ...")
            QApplication.processEvents()

            results = self.calculate_table(table_name)
            self.save_results_to_db(results, table_name)
            self.progress_bar.setValue(i + 1)

        QMessageBox.information(self, "完成", "计算和保存结果已完成")
        self.status_label.setText("计算完成")

    def calculate_table(self, table_name):
        conn = sqlite3.connect(self.db_path)
        query = f"SELECT COUNT(*) as total FROM {table_name};"
        total_df = pd.read_sql_query(query, conn)
        if total_df.empty or total_df['total'].iloc[0] == 0:
            conn.close()
            return []
        q1 = 1
        q2 = int(total_df['total'].iloc[0])

        query = f"PRAGMA table_info({table_name});"
        columns = pd.read_sql_query(query, conn)
        conn.close()

        dvh_col = [col for col in columns['name'] if 'DVH' in col]
        time_col = [col for col in columns['name'] if 'time' in col]
        dp_col = [col for col in columns['name'] if 'DP' in col]

        if not dvh_col or not time_col or not dp_col:
            return []

        conn = sqlite3.connect(self.db_path)
        query = f"SELECT {dvh_col[0]}, {time_col[0]}, {dp_col[0]} FROM {table_name} WHERE rowid BETWEEN {q1} AND {q2};"
        df = pd.read_sql_query(query, conn)
        conn.close()

        w0 = 48
        results = []
        for window_size in range(13, w0 + 1):
            for start in range(len(df) - window_size + 1):
                dvh_window = df[dvh_col[0]].iloc[start:start + window_size].reset_index(drop=True)
                time_window = df[time_col[0]].iloc[start:start + window_size].reset_index(drop=True)
                dp_window = df[dp_col[0]].iloc[start:start + window_size].reset_index(drop=True)
                result = self.calculate_Q1d_A82(dvh_window.to_numpy(),
                                                 time_window.to_numpy(),
                                                 dp_window.to_numpy())
                results.append((start, start + window_size - 1, result[2], result[3], result[4]))
        return results

    def calculate_Q1d_A82(self, dvh1, time1, dp1):
        window_size = len(dvh1)
        P1d = np.mean(dvh1)
        std_dvh1 = np.std(dvh1)
        min_dvh1 = np.min(dvh1)
        max_dvh1 = np.max(dvh1)

        BeforeSize = len(time1)
        if len(time1) < 2:
            Q1d = np.nan
            b_array = np.nan
        else:
            P = np.polyfit(time1, dvh1, 1)
            Q1d = P[0]
            b_array = P[1]

        disti = np.abs((Q1d * time1 - dvh1 + b_array) / np.sqrt(Q1d**2 + 1))
        tempavg = np.sum(disti) / (window_size + 1)
        Wi = np.abs(disti - tempavg)
        temperr = np.sqrt(np.sum((disti - tempavg)**2 / window_size))
        idx_outliers = np.where(Wi > 5 * temperr)[0]

        time1_clean = np.delete(time1, idx_outliers)
        dvh1_clean = np.delete(dvh1, idx_outliers)
        dp1_clean = np.delete(dp1, idx_outliers)
        AfterSize = len(time1_clean)
        num_removed_outliers = BeforeSize - AfterSize

        if len(time1_clean) >= 2:
            P = np.polyfit(time1_clean, dvh1_clean, 1)
            Q1d = P[0]
            b_array = P[1]
        else:
            Q1d = np.nan
            b_array = np.nan

        N = len(dvh1_clean)
        A0 = np.sum(time1_clean)
        A1 = np.sum(dvh1_clean)
        A2 = np.dot(time1_clean, dvh1_clean)
        A3 = np.dot(time1_clean, time1_clean)
        A4 = np.dot(dvh1_clean, dvh1_clean)
        if N >= 3 and (N * A3 - A0**2) != 0 and (A3 - (A0**2)/N) != 0:
            A5 = (A1 * A3 - A0 * A2) / (N * A3 - A0**2)
            A7 = (A2 - A1 * A0 / N) / (A3 - A0**2 / N)
            A6 = np.sqrt((A4 - A5 * A1 - A7 * A2) / (N - 2))
        else:
            A6 = np.nan

        if num_removed_outliers == 0:
            timen = time1_clean[-1] if len(time1_clean) > 0 else 0
            time1_first = time1_clean[0] if len(time1_clean) > 0 else 0
            Iins = 0.5
            denom = (timen - time1_first) ** 2
            A8 = np.sqrt((Iins / 100) ** 2 + 36 * A6 / denom) if denom != 0 else np.nan
        else:
            timen = (window_size - num_removed_outliers) / 2
            time1_first = 0
            Iins = 0.5
            denom = (timen - time1_first) ** 2
            A8 = np.sqrt((Iins / 100) ** 2 + 36 * A6 / denom) if denom != 0 else np.nan

        dp_mean = np.mean(dp1_clean) if len(dp1_clean) > 0 else np.nan
        return [0, window_size, Q1d, A8, dp_mean]

    def save_results_to_db(self, results, table_name):
        db_filename = f"{table_name}.db"
        conn = sqlite3.connect(db_filename)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                start_index INTEGER,
                end_index INTEGER,
                Q1d REAL,
                A8 REAL,
                dp_mean REAL
            )
        ''')

        cursor.executemany(
            'INSERT INTO results (start_index, end_index, Q1d, A8, dp_mean) VALUES (?, ?, ?, ?, ?)',
            results
        )

        conn.commit()
        conn.close()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DatabaseApp()
    window.show()
    sys.exit(app.exec_())