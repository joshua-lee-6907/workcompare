import sqlite3
import os
import numpy as np
import json
from flask import Flask, render_template, jsonify, request
from threading import Thread

app = Flask(__name__)

# Database file names
SOURCE_DB = '2.db'
COMPUTED_DB = '5.db'
RESULTS_DB = '6.db'

progress_status = {"percent": 0, "message": "等待开始"}

def get_max_end_index():
    conn = sqlite3.connect(SOURCE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(end_index) FROM results")
    max_end_index = cursor.fetchone()[0]
    conn.close()
    return max_end_index

def fetch_data(lower_bound, upper_bound):
    conn = sqlite3.connect(SOURCE_DB)
    cursor = conn.cursor()
    query = f"SELECT start_index, end_index, Q1d, dp_mean, A8 FROM results WHERE start_index >= {lower_bound} AND end_index <= {upper_bound}"
    cursor.execute(query)
    data = cursor.fetchall()
    conn.close()
    return data

def calculate_statistics(data):
    if not data:
        return {}
    q1d = np.array([row[2] for row in data])
    dp_mean = np.array([row[3] for row in data])
    a8 = np.array([row[4] for row in data])
    stats = {
        'Q1d': {'max': np.max(q1d), 'min': np.min(q1d), 'mean': np.mean(q1d), 'std': np.std(q1d)},
        'dp_mean': {'max': np.max(dp_mean), 'min': np.min(dp_mean), 'mean': np.mean(dp_mean), 'std': np.std(dp_mean)},
        'A8': {'max': np.max(a8), 'min': np.min(a8), 'mean': np.mean(a8), 'std': np.std(a8)}
    }
    return stats

def compute_statistics(progress_callback=None):
    max_end_index = get_max_end_index()
    if os.path.exists(COMPUTED_DB):
        conn = sqlite3.connect(COMPUTED_DB)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS computed_results")
        conn.commit()
        conn.close()
    conn = sqlite3.connect(COMPUTED_DB)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS computed_results (step INTEGER, avg_q1d REAL, avg_dp_mean REAL, avg_a8 REAL, min_a8_row TEXT)")
    total_steps = max_end_index - 47
    for idx, step in enumerate(range(1, total_steps)):
        lower_bound = step
        upper_bound = step + 47
        data = fetch_data(lower_bound, upper_bound)
        stats = calculate_statistics(data)
        if stats:
            min_a8_row = min(data, key=lambda x: x[4])
            min_a8_row_str = json.dumps({
                "start_index": min_a8_row[0],
                "end_index": min_a8_row[1],
                "Q1d": min_a8_row[2],
                "dp_mean": min_a8_row[3],
                "A8": min_a8_row[4]
            })
            cursor.execute("INSERT INTO computed_results (step, avg_q1d, avg_dp_mean, avg_a8, min_a8_row) VALUES (?, ?, ?, ?, ?)",
                           (step, stats['Q1d']['mean'], stats['dp_mean']['mean'], stats['A8']['mean'], min_a8_row_str))
        if progress_callback:
            percent = int((idx + 1) / total_steps * 100)
            progress_callback(percent, f"正在统计数据 {idx+1}/{total_steps}")
    conn.commit()
    conn.close()

def get_steps():
    conn = sqlite3.connect(COMPUTED_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT step FROM computed_results")
    steps = [row[0] for row in cursor.fetchall()]
    conn.close()
    return steps

def get_summary_data(start_step, end_step):
    conn = sqlite3.connect(COMPUTED_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT step, avg_q1d, avg_dp_mean, avg_a8 FROM computed_results WHERE step BETWEEN ? AND ?", (start_step, end_step))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_min_a8_rows(start_step, end_step):
    conn = sqlite3.connect(COMPUTED_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT step, min_a8_row FROM computed_results WHERE step BETWEEN ? AND ?", (start_step, end_step))
    rows = cursor.fetchall()
    conn.close()
    # rows: (step, min_a8_row_json)
    result = []
    for row in rows:
        row_json = json.loads(row[1])
        row_json['step'] = row[0]
        result.append(row_json)
    return result

@app.route("/")
def index():
    max_end_index = get_max_end_index()
    return render_template("dashboard_gui.html", max_end_index=max_end_index)

@app.route("/api/progress")
def api_progress():
    return jsonify(progress_status)

@app.route("/api/start_compute", methods=["POST"])
def api_start_compute():
    global progress_status
    progress_status = {"percent": 0, "message": "启动中"}
    def run_compute():
        global progress_status
        compute_statistics(progress_callback=lambda percent, msg: progress_status.update({"percent": percent, "message": msg}))
        progress_status = {"percent": 100, "message": "完成"}
    Thread(target=run_compute).start()
    return jsonify({"status": "processing"})

@app.route("/api/steps")
def api_steps():
    steps = get_steps()
    return jsonify(steps)

@app.route("/api/statistics")
def api_statistics():
    # Returns summary statistics for a step interval
    start_step = int(request.args.get("start_step"))
    end_step = int(request.args.get("end_step"))
    rows = get_summary_data(start_step, end_step)
    result = []
    for row in rows:
        result.append({
            "step": row[0],
            "avg_q1d": row[1],
            "avg_dp_mean": row[2],
            "avg_a8": row[3],
        })
    return jsonify(result)

@app.route("/api/min_a8_rows")
def api_min_a8_rows():
    start_step = int(request.args.get("start_step"))
    end_step = int(request.args.get("end_step"))
    rows = get_min_a8_rows(start_step, end_step)
    return jsonify(rows)

if __name__ == "__main__":
    app.run(debug=True)