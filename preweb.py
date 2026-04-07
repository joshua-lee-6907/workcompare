import sys
import os
import sqlite3
import matplotlib.pyplot as plt
from matplotlib import font_manager

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# --- Core Logic ---

def fetch_data_from_db(db_path):
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    try:
        query = "SELECT time, DVH, DP FROM data ORDER BY time"
        cursor.execute(query)
        data = cursor.fetchall()
        data = [(float(time), float(dvh), float(dp)) for time, dvh, dp in data]
        return data
    finally:
        connection.close()

def flag_outliers(data, window_size=12, threshold=15):
    flags = [False] * len(data)
    for start in range(0, len(data) - window_size + 1):
        window = data[start:start + window_size]
        _, _, dps = zip(*window)
        range_value = max(dps) - min(dps)
        if range_value > threshold:
            for i in range(start, start + window_size):
                flags[i] = True
    return flags

def segment_non_outlier_data(data, flags):
    segments = []
    current_seg = []
    for i, point in enumerate(data):
        if not flags[i]:
            current_seg.append(point)
        else:
            if current_seg:
                segments.append(current_seg)
                current_seg = []
    if current_seg:
        segments.append(current_seg)
    return segments

def save_segments_to_db(segments, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for idx, segment in enumerate(segments, start=1):
        table_name = f"Segment_{idx}"
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        cursor.execute(f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time REAL,
                DVH REAL,
                DP REAL
            )
        """)
        for time, dvh, dp in segment:
            cursor.execute(f"""
                INSERT INTO {table_name} (time, DVH, DP)
                VALUES (?, ?, ?)
            """, (time, dvh, dp))
    conn.commit()
    conn.close()

def get_chinese_font():
    # 优先选择常见的中英混合字体，若无则退回系统默认
    zh_fonts = [
        "Microsoft YaHei", "微软雅黑", 
        "SimHei", "黑体", 
        "PingFang SC", 
        "Hiragino Sans GB", 
        "WenQuanYi Micro Hei",
        "Arial Unicode MS"
    ]
    for fname in zh_fonts:
        if fname in set(f.name for f in font_manager.fontManager.ttflist):
            return fname
    return plt.rcParams['font.sans-serif'][0]

def plot_data(data, flags, segments):
    # 科技感配色
    bg_color = "#0c1533"
    grid_color = "#1e294f"
    all_line_color = "#00d4ff"
    outlier_color = "#ff3576"
    segment_colors = [
        "#00ffe0", "#fffb00", "#ff00f7", "#ff9000", "#3800ff", "#00ff57", "#ff0057"
    ]
    # 设置风格和字体
    plt.style.use("dark_background")
    plt.figure(figsize=(16, 9), facecolor=bg_color)
    ax = plt.gca()
    ax.set_facecolor(bg_color)
    font_name = get_chinese_font()
    plt.rcParams['font.sans-serif'] = [font_name]
    plt.rcParams['axes.unicode_minus'] = False

    # Glow grid lines
    ax.grid(True, color=grid_color, linewidth=1.6, alpha=0.35, linestyle='-.', zorder=0)

    # Glow effect for all data
    times_all, _, dps_all = zip(*data)
    for lw, alpha in zip([13, 9, 6, 3], [0.06, 0.10, 0.15, 0.23]):
        plt.plot(times_all, dps_all, marker='', linestyle='-', color=all_line_color, linewidth=lw, alpha=alpha, zorder=1)
    plt.plot(times_all, dps_all, marker='o', markersize=4, linestyle='-', color=all_line_color, linewidth=2.8, alpha=0.94, zorder=2)

    # Outliers with halo
    outlier_points = [data[i] for i, flagged in enumerate(flags) if flagged]
    if outlier_points:
        outlier_times, _, outlier_dps = zip(*outlier_points)
        for s in [26, 18, 10]:
            plt.scatter(outlier_times, outlier_dps, color=outlier_color, alpha=0.07, s=s, zorder=4)
        plt.scatter(outlier_times, outlier_dps, color=outlier_color, alpha=0.92, s=38, edgecolor='#fff', linewidth=1.2, zorder=5)

    # Segments: Overlay with alternating glow lines
    for i, seg in enumerate(segments):
        seg_times, _, seg_dps = zip(*seg)
        seg_col = segment_colors[i % len(segment_colors)]
        for lw, alpha in zip([7, 5, 3], [0.09, 0.13, 0.19]):
            plt.plot(seg_times, seg_dps, linestyle='-', color=seg_col, linewidth=lw, alpha=alpha, zorder=3)
        plt.plot(seg_times, seg_dps, linestyle='-', color=seg_col, linewidth=2.3, alpha=0.90, zorder=4)

    # 装饰性分割线
    plt.axhline(y=0, color='#1e294f', linewidth=1.2, alpha=0.48, linestyle='--', zorder=0)

    # Title/labels (中文)
    plt.title("DP随时间变化 · 分段与异常检测 · 科技感可视化", fontsize=22, color="#00d4ff", pad=24, fontweight="bold", family=font_name)
    plt.xlabel("时间", color="#e9f1fb", fontsize=17, labelpad=13, family=font_name)
    plt.ylabel("DP (压差)", color="#e9f1fb", fontsize=17, labelpad=13, family=font_name)

    # Tick styling
    plt.tick_params(axis='x', colors='#70c6ff', labelsize=12)
    plt.tick_params(axis='y', colors='#70c6ff', labelsize=12)

    # 去掉legend
    plt.tight_layout()
    plt.show()

# --- Tech Style GUI ---

class SegmentApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🛰️ 数据分段与异常检测")
        self.setGeometry(400, 200, 560, 340)
        self.init_ui()
        self.set_dark_blue_style()

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
                font-family: 'Segoe UI', 'Arial', 'Microsoft YaHei', sans-serif;
                font-size: 15px;
            }}
            QLabel {{
                color: {accent_blue};
                font-weight: bold;
            }}
            QLineEdit {{
                background-color: {mid_blue};
                color: {text_color};
                border: 1.5px solid {border_color};
                border-radius: 7px;
                padding: 5px 9px;
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
        """)
        self.setFont(QFont("Microsoft YaHei", 12))

    def init_ui(self):
        # 输入源数据库
        self.src_label = QLabel("源数据库文件:")
        self.src_edit = QLineEdit("d1.db")
        self.src_btn = QPushButton("选择")
        self.src_btn.clicked.connect(self.choose_src_db)

        # 输入目标数据库
        self.tgt_label = QLabel("保存分段后的数据库:")
        self.tgt_edit = QLineEdit("30.db")
        self.tgt_btn = QPushButton("选择")
        self.tgt_btn.clicked.connect(self.choose_tgt_db)

        # 操作按钮
        self.run_btn = QPushButton("🚀 执行分段与保存")
        self.run_btn.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        self.run_btn.clicked.connect(self.run_process)
        self.run_btn.setCursor(Qt.PointingHandCursor)

        self.plot_btn = QPushButton("📊 可视化结果")
        self.plot_btn.clicked.connect(self.plot_show)
        self.plot_btn.setCursor(Qt.PointingHandCursor)
        self.plot_btn.setEnabled(False)

        # 布局
        layout = QVBoxLayout()
        layout.setSpacing(24)
        # 源数据库
        src_layout = QHBoxLayout()
        src_layout.addWidget(self.src_edit)
        src_layout.addWidget(self.src_btn)
        layout.addWidget(self.src_label)
        layout.addLayout(src_layout)
        # 目标数据库
        tgt_layout = QHBoxLayout()
        tgt_layout.addWidget(self.tgt_edit)
        tgt_layout.addWidget(self.tgt_btn)
        layout.addWidget(self.tgt_label)
        layout.addLayout(tgt_layout)
        # 操作按钮
        layout.addWidget(self.run_btn)
        layout.addWidget(self.plot_btn)
        self.setLayout(layout)

        # 结果缓存
        self.last_data = None
        self.last_flags = None
        self.last_segments = None

    def choose_src_db(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择源数据库", "", "SQLite DB Files (*.db);;All Files (*)")
        if path:
            self.src_edit.setText(path)

    def choose_tgt_db(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存数据库为", "30.db", "SQLite DB Files (*.db);;All Files (*)")
        if path:
            self.tgt_edit.setText(path)

    def run_process(self):
        src = self.src_edit.text().strip()
        tgt = self.tgt_edit.text().strip()
        win = 12
        thresh = 15
        if not os.path.exists(src):
            QMessageBox.critical(self, "错误", "源数据库文件不存在！")
            return
        if not tgt:
            QMessageBox.critical(self, "错误", "请输入保存数据库文件名！")
            return

        try:
            data = fetch_data_from_db(src)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取源数据库出错: {e}")
            return

        if not data:
            QMessageBox.warning(self, "无数据", "未读取到数据。")
            return

        flags = flag_outliers(data, window_size=win, threshold=thresh)
        segments = segment_non_outlier_data(data, flags)
        try:
            save_segments_to_db(segments, tgt)
            QMessageBox.information(self, "完成", f"分段结果已保存到 {tgt}\n共分为 {len(segments)} 段。")
            self.plot_btn.setEnabled(True)
            self.last_data = data
            self.last_flags = flags
            self.last_segments = segments
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存到数据库出错: {e}")

    def plot_show(self):
        if self.last_data and self.last_flags and self.last_segments:
            plot_data(self.last_data, self.last_flags, self.last_segments)
        else:
            QMessageBox.information(self, "无数据", "请先执行分段操作。")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SegmentApp()
    window.show()
    sys.exit(app.exec_())