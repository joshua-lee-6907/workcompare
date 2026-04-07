import sqlite3
import os
import math
import numpy as np
import json
from flask import Flask, render_template, jsonify, request
from threading import Thread
import time

CONFIG = {
    "num_subsets": 20,
    "num_exclude": 12,
    "min_points_for_regression": 5
}

class DataProcessor:
    def __init__(self, progress_callback=None):
        self.source_db = '2.db'
        self.intermediate_db = '20.db'
        self.final_db = '21.db'
        self.window_size = 300
        self.slide = 30
        self.progress_callback = progress_callback
        self.max_end_index = self.get_max_end_index()

    def update_progress(self, percent, message=""):
        if self.progress_callback:
            self.progress_callback(percent, message)

    def get_max_end_index(self):
        conn = sqlite3.connect(self.source_db)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(end_index) FROM results")
        max_val = cursor.fetchone()[0]
        conn.close()
        return max_val

    def fetch_data(self, lower_bound, upper_bound):
        conn = sqlite3.connect(self.source_db)
        cursor = conn.cursor()
        query = (f"SELECT start_index, end_index, Q1d, dp_mean, A8 FROM results "
                 f"WHERE start_index >= {lower_bound} AND end_index <= {upper_bound}")
        cursor.execute(query)
        data = cursor.fetchall()
        conn.close()
        return data

    def process_windows(self):
        if os.path.exists(self.intermediate_db):
            os.remove(self.intermediate_db)

        conn_results = sqlite3.connect(self.intermediate_db)
        cursor_results = conn_results.cursor()

        current_lower = 1
        processed_windows = []
        total_windows = math.ceil((self.max_end_index - self.window_size + 1) / self.slide) + 1
        window_count = 0

        while True:
            if current_lower + self.window_size - 1 > self.max_end_index:
                current_lower = self.max_end_index - self.window_size + 1
                current_upper = self.max_end_index
                if (current_lower, current_upper) in processed_windows:
                    break
            else:
                current_upper = current_lower + self.window_size - 1

            data = self.fetch_data(current_lower, current_upper)
            table_name = f"window_{current_lower}_{current_upper}"
            cursor_results.execute(f"DROP TABLE IF EXISTS {table_name}")
            cursor_results.execute(f"""
                CREATE TABLE {table_name} (
                    start_index INTEGER,
                    end_index INTEGER,
                    Q1d REAL,
                    dp_mean REAL,
                    A8 REAL
                )
            """)
            for row in data:
                cursor_results.execute(
                    f"INSERT INTO {table_name} (start_index, end_index, Q1d, dp_mean, A8) VALUES (?, ?, ?, ?, ?)",
                    row
                )
            conn_results.commit()
            processed_windows.append((current_lower, current_upper))
            window_count += 1
            self.update_progress(window_count / total_windows * 50, f"正在处理滑动窗口 {window_count}/{total_windows}")
            if current_upper == self.max_end_index:
                break
            next_lower = current_lower + self.slide
            if next_lower + self.window_size - 1 > self.max_end_index:
                current_lower = self.max_end_index - self.window_size + 1
            else:
                current_lower = next_lower
        conn_results.close()

    def partition_list(self, data, num_parts):
        n = len(data)
        if n == 0:
            return [[] for _ in range(num_parts)]
        part_sizes = []
        base = n // num_parts
        remainder = n % num_parts
        for i in range(num_parts):
            size = base + (1 if i < remainder else 0)
            part_sizes.append(size)
        subsets = []
        index = 0
        for size in part_sizes:
            subsets.append(data[index:index+size])
            index += size
        return subsets

    def linear_regression_std(self, candidate):
        x = np.array([row[3] for row in candidate])
        y = np.array([row[2] for row in candidate])
        slope, intercept = np.polyfit(x, y, 1)
        predicted = slope * x + intercept
        residuals = y - predicted
        return np.std(residuals)

    def process_final_results_to_final_db(self):
        if os.path.exists(self.final_db):
            os.remove(self.final_db)

        conn_inter = sqlite3.connect(self.intermediate_db)
        cursor_inter = conn_inter.cursor()
        cursor_inter.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'window_%'")
        window_tables = [row[0] for row in cursor_inter.fetchall()]
        conn_inter.close()

        conn_final = sqlite3.connect(self.final_db)
        cursor_final = conn_final.cursor()
        cursor_final.execute("DROP TABLE IF EXISTS total_summary")
        cursor_final.execute("""
            CREATE TABLE total_summary (
                table_identifier TEXT,
                slope REAL,
                slope_times_60 REAL,
                intercept REAL,
                residual_std REAL
            )
        """)
        conn_final.commit()

        total_windows = len(window_tables)
        for idx, wtable in enumerate(window_tables):
            conn_inter = sqlite3.connect(self.intermediate_db)
            cursor_inter = conn_inter.cursor()
            cursor_inter.execute(f"SELECT start_index, end_index, Q1d, dp_mean, A8 FROM {wtable}")
            rows = cursor_inter.fetchall()
            conn_inter.close()

            if not rows:
                continue

            sorted_rows = sorted(rows, key=lambda r: r[3])
            subsets = self.partition_list(sorted_rows, CONFIG["num_subsets"])
            subset_stats = []
            for idx2, sub in enumerate(subsets):
                if sub:
                    std_val = np.std([r[2] for r in sub])
                else:
                    std_val = float('inf')
                subset_stats.append((idx2, sub, std_val))
            nonempty = [item for item in subset_stats if item[1]]
            if len(nonempty) > CONFIG["num_exclude"]:
                nonempty_sorted = sorted(nonempty, key=lambda x: x[2])
                selected = nonempty_sorted[:len(nonempty_sorted) - CONFIG["num_exclude"]]
            else:
                selected = []

            final_points = []
            for item in selected:
                idx3, sub, std_val = item
                final_point = None
                best_residual_std = None
                if len(sub) >= CONFIG["min_points_for_regression"]:
                    best_std = float('inf')
                    best_candidate = None
                    for i in range(0, len(sub) - CONFIG["min_points_for_regression"] + 1):
                        candidate = sub[i:i+CONFIG["min_points_for_regression"]]
                        candidate_std = self.linear_regression_std(candidate)
                        if candidate_std < best_std:
                            best_std = candidate_std
                            best_candidate = candidate
                    if best_candidate is not None:
                        med_index = CONFIG["min_points_for_regression"] // 2
                        final_point = best_candidate[med_index]
                        best_residual_std = best_std
                else:
                    if len(sub) > 0:
                        med_index = len(sub) // 2
                        final_point = sub[med_index]
                        best_residual_std = None
                if final_point is not None:
                    final_points.append((final_point[0], final_point[1], final_point[2], final_point[3], final_point[4], best_residual_std))

            final_table = "final_" + wtable
            cursor_final.execute(f"DROP TABLE IF EXISTS {final_table}")
            cursor_final.execute(f"""
                CREATE TABLE {final_table} (
                    start_index INTEGER,
                    end_index INTEGER,
                    Q1d REAL,
                    dp_mean REAL,
                    A8 REAL,
                    residual_std REAL
                )
            """)
            for point in final_points:
                cursor_final.execute(f"""
                    INSERT INTO {final_table} (start_index, end_index, Q1d, dp_mean, A8, residual_std)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, point)
            conn_final.commit()

            if len(final_points) >= 2:
                dp_means = np.array([pt[3] for pt in final_points])
                Q1ds = np.array([pt[2] for pt in final_points])
                slope, intercept = np.polyfit(dp_means, Q1ds, 1)
                predicted = slope * dp_means + intercept
                residual_std = np.std(Q1ds - predicted)
            else:
                slope, intercept, residual_std = None, None, None

            slope_times_60 = slope * 60 if slope is not None else None
            cursor_final.execute("""
                INSERT INTO total_summary (table_identifier, slope, slope_times_60, intercept, residual_std)
                VALUES (?, ?, ?, ?, ?)
            """, (wtable, slope, slope_times_60, intercept, residual_std))
            conn_final.commit()
            self.update_progress(50 + (idx+1) / total_windows * 48, f"窗口 {idx+1}/{total_windows} 回归处理完成")
        conn_final.close()
        self.update_progress(100, "所有数据处理完成")

# Flask Web App
app = Flask(__name__)

progress_status = {"percent": 0, "message": "等待开始"}

def set_progress(percent, message=""):
    global progress_status
    progress_status["percent"] = percent
    progress_status["message"] = message

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/start_process", methods=["POST"])
def start_process():
    global progress_status
    progress_status = {"percent": 0, "message": "启动中"}
    def run_process():
        processor = DataProcessor(progress_callback=set_progress)
        processor.process_windows()
        processor.process_final_results_to_final_db()
    thread = Thread(target=run_process)
    thread.start()
    return jsonify({"status": "processing"})

@app.route("/api/progress")
def get_progress():
    return jsonify(progress_status)

@app.route("/api/window_tables")
def api_window_tables():
    conn = sqlite3.connect('20.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'window_%'")
    window_tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(window_tables)

@app.route("/api/raw_data/<window_table>")
def api_raw_data(window_table):
    conn = sqlite3.connect('20.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT start_index, end_index, Q1d, dp_mean, A8 FROM {window_table}")
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)

@app.route("/api/final_points/<window_table>")
def api_final_points(window_table):
    final_table = "final_" + window_table
    conn = sqlite3.connect('21.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT start_index, end_index, Q1d, dp_mean, A8, residual_std FROM {final_table}")
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)

@app.route("/api/summary/<window_table>")
def api_summary(window_table):
    conn = sqlite3.connect('21.db')
    cursor = conn.cursor()
    cursor.execute("SELECT slope, intercept, residual_std, slope_times_60 FROM total_summary WHERE table_identifier=?", (window_table,))
    summary = cursor.fetchone()
    conn.close()
    if summary:
        return jsonify({
            "slope": summary[0],
            "intercept": summary[1],
            "residual_std": summary[2],
            "slope_times_60": summary[3]
        })
    else:
        return jsonify({})

if __name__ == "__main__":
    app.run(debug=True)