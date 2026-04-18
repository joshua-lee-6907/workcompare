#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全壳综合监测系统 - 后端控制程序
依赖: pip install flask flask-cors
"""
import os, sys, json, time, threading, sqlite3, webbrowser, math
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from flask import Flask, jsonify, send_file
    from flask_cors import CORS
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

# ═══════════════ 路径 ═══════════════
BASE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE, "config.json")
STATUS_FILE = os.path.join(BASE, "status.json")
HTML_FILE   = os.path.join(BASE, "dashboard.html")

# ═══════════════ 默认配置 ═══════════════
DEFAULT_CFG = {
    "title": "安全壳综合监测系统",
    "server_port": 5000,
    "read_interval": 10,
    "databases": [],
    "variables": [],
    "pressure_chart": {"monitor_var": None, "target_var": None},
    "temp_humidity_chart": {
        "temp_vars": [], "humidity_vars": [],
        "highlight_temp": None, "highlight_humidity": None
    },
    "sensor_layout": {"layers": []}
}

# ═══════════════ 全局状态 ═══════════════
cfg   = {}
store = {
    "current": {}, "history": {}, "timestamps": [],
    "target": {}, "row_index": 0, "total_rows": 0,
    "running": False, "last_update": ""
}
lock = threading.Lock()

# ═══════════════ 配置管理 ═══════════════
def load_cfg():
    global cfg
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = {**DEFAULT_CFG, **json.load(f)}
        except Exception:
            cfg = DEFAULT_CFG.copy()
    else:
        cfg = DEFAULT_CFG.copy()

def save_cfg():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ═══════════════ 数据库工具 ═══════════════
def db_tables(path):
    try:
        with sqlite3.connect(path) as c:
            return [r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    except Exception:
        return []

def db_cols(path, tbl):
    try:
        with sqlite3.connect(path) as c:
            return [r[1] for r in c.execute(f'PRAGMA table_info("{tbl}")')]
    except Exception:
        return []

def db_count(path, tbl):
    try:
        with sqlite3.connect(path) as c:
            return c.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]
    except Exception:
        return 0

def db_row(path, tbl, col, idx):
    try:
        with sqlite3.connect(path) as c:
            r = c.execute(
                f'SELECT "{col}" FROM "{tbl}" LIMIT 1 OFFSET {idx}').fetchone()
            return r[0] if r else None
    except Exception:
        return None

def db_all(path, tbl, col):
    try:
        with sqlite3.connect(path) as c:
            return [r[0] for r in c.execute(f'SELECT "{col}" FROM "{tbl}"')]
    except Exception:
        return []


# ═══════════════ Flask API ═══════════════
if HAS_FLASK:
    flask_app = Flask(__name__)
    CORS(flask_app)

    @flask_app.route("/")
    def r_index():
        return send_file(HTML_FILE)

    @flask_app.route("/api/config")
    def r_config():
        with lock:
            return jsonify({
                "title": cfg.get("title", "监测系统"),
                "sensor_layout": cfg.get("sensor_layout", {"layers": []}),
                "variables": cfg.get("variables", []),
                "pressure_chart": cfg.get("pressure_chart", {}),
                "temp_humidity_chart": cfg.get("temp_humidity_chart", {}),
            })

    @flask_app.route("/api/data")
    def r_data():
        with lock:
            return jsonify({
                "current":    dict(store["current"]),
                "history":    {k: list(v) for k, v in store["history"].items()},
                "timestamps": list(store["timestamps"]),
                "target":     {k: list(v) for k, v in store["target"].items()},
                "row_index":  store["row_index"],
                "total_rows": store["total_rows"],
                "last_update": store["last_update"],
                "running":    store["running"],
            })

    @flask_app.route("/api/status")
    def r_status():
        try:
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, encoding="utf-8") as f:
                    return jsonify(json.load(f))
        except Exception:
            pass
        return jsonify({})

    def run_flask():
        port = cfg.get("server_port", 5000)
        flask_app.run("127.0.0.1", port,
                      debug=False, use_reloader=False, threaded=True)

# ═══════════════ 数据读取线程 ═══════════════
def reader_loop():
    """等间隔逐行读取 SQLite 数据并推送到 store"""
    while True:
        with lock:
            running = store["running"]
        if not running:
            time.sleep(0.5)
            continue

        interval  = cfg.get("read_interval", 10)
        variables = cfg.get("variables", [])

        with lock:
            idx = store["row_index"]

        new_vals = {}
        for v in variables:
            val = db_row(v["db_path"], v["table"], v["column"], idx)
            if val is not None:
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    pass
                new_vals[v["var_id"]] = val

        ts = datetime.now().strftime("%H:%M:%S")
        with lock:
            store["current"].update(new_vals)
            store["timestamps"].append(ts)
            for vid, val in new_vals.items():
                store["history"].setdefault(vid, []).append(val)
            # 保留最近 200 个点
            if len(store["timestamps"]) > 200:
                store["timestamps"] = store["timestamps"][-200:]
                for vid in store["history"]:
                    store["history"][vid] = store["history"][vid][-200:]
            n = store["total_rows"]
            store["row_index"] = (idx + 1) % n if n > 0 else idx + 1
            store["last_update"] = ts

        time.sleep(interval)


def preload_target():
    """预加载压力目标曲线的全部数据"""
    tid = cfg.get("pressure_chart", {}).get("target_var")
    if not tid:
        return
    v = next((x for x in cfg.get("variables", []) if x["var_id"] == tid), None)
    if not v:
        return
    vals = db_all(v["db_path"], v["table"], v["column"])
    try:
        vals = [float(x) for x in vals]
    except (TypeError, ValueError):
        pass
    with lock:
        store["target"][tid] = vals


def start_reading():
    variables = cfg.get("variables", [])
    total = db_count(variables[0]["db_path"], variables[0]["table"]) if variables else 0
    with lock:
        store.update({
            "running": True, "row_index": 0,
            "history": {}, "timestamps": [], "current": {},
            "total_rows": total
        })
    threading.Thread(target=preload_target, daemon=True).start()


def stop_reading():
    with lock:
        store["running"] = False


# ═══════════════ GUI 样式常量 ═══════════════
C = {
    "bg":     "#0f1329", "panel":  "#151d38", "card":   "#1c2447",
    "accent": "#00d4ff", "accent2":"#0077ee", "text":   "#c8e6f8",
    "dim":    "#6688aa", "ok":     "#00cc88", "warn":   "#ffaa00",
    "err":    "#ff4455", "border": "#263456",
}
FONT_N  = ("Microsoft YaHei UI", 10)
FONT_B  = ("Microsoft YaHei UI", 10, "bold")
FONT_T  = ("Microsoft YaHei UI", 14, "bold")
FONT_H2 = ("Microsoft YaHei UI", 11, "bold")
FONT_S  = ("Microsoft YaHei UI", 9)


def mk_style(root):
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except Exception:
        pass
    bg, panel, card = C["bg"], C["panel"], C["card"]
    text, dim, acc  = C["text"], C["dim"], C["accent"]
    border          = C["border"]

    s.configure(".",              background=bg,    foreground=text, font=FONT_N)
    s.configure("TFrame",         background=bg)
    s.configure("TLabel",         background=bg,    foreground=text)
    s.configure("TButton",        background=card,  foreground=acc,
                font=FONT_N, relief="flat", padding=(8, 4))
    s.map("TButton",
          background=[("active", acc)],
          foreground=[("active", bg)])
    s.configure("Accent.TButton", background=acc,   foreground=bg, font=FONT_B)
    s.map("Accent.TButton",
          background=[("active", "#33c9ff")],
          foreground=[("active", bg)])
    s.configure("TNotebook",      background=bg,    borderwidth=0)
    s.configure("TNotebook.Tab",  background=panel, foreground=dim,
                font=FONT_N, padding=[14, 7], borderwidth=0)
    s.map("TNotebook.Tab",
          background=[("selected", card)],
          foreground=[("selected", acc)])
    s.configure("TEntry",         fieldbackground=card,  foreground=text,
                insertcolor=text, borderwidth=1, relief="flat")
    s.configure("TCombobox",      fieldbackground=card,  foreground=text,
                selectbackground=acc, selectforeground=bg)
    s.map("TCombobox",            fieldbackground=[("readonly", card)])
    s.configure("TSpinbox",       fieldbackground=card,  foreground=text,
                arrowcolor=acc, borderwidth=1)
    s.configure("TLabelframe",    background=bg,    bordercolor=border,
                relief="flat", borderwidth=1)
    s.configure("TLabelframe.Label", background=bg, foreground=acc, font=FONT_B)
    s.configure("Treeview",       background=card,  foreground=text,
                fieldbackground=card, font=FONT_S, rowheight=22)
    s.configure("Treeview.Heading", background=panel, foreground=acc,
                font=FONT_B, relief="flat")
    s.map("Treeview",
          background=[("selected", acc)],
          foreground=[("selected", bg)])
    s.configure("TScrollbar",     background=panel, troughcolor=bg,
                arrowcolor=acc, borderwidth=0)
    s.configure("TCheckbutton",   background=bg,    foreground=text)


# ═══════════════ 主窗口 ═══════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("安全壳监测系统 · 配置控制台")
        self.geometry("950x700")
        self.minsize(800, 600)
        self.configure(bg=C["bg"])
        mk_style(self)
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self):
        # ── 顶栏 ──
        hdr = tk.Frame(self, bg="#0a0f22", height=52)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⚙  安全壳综合监测系统 · 配置控制台",
                 bg="#0a0f22", fg=C["accent"], font=FONT_T).pack(
                     side="left", padx=20, pady=10)
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(hdr, textvariable=self.status_var,
                 bg="#0a0f22", fg=C["dim"], font=FONT_S).pack(
                     side="right", padx=20)

        # ── Notebook ──
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        self.tab_basic  = BasicTab(nb, self)
        self.tab_db     = DatabaseTab(nb, self)
        self.tab_press  = PressureTab(nb, self)
        self.tab_th     = TempHumTab(nb, self)
        self.tab_sensor = SensorTab(nb, self)

        nb.add(self.tab_basic,  text="  基本设置  ")
        nb.add(self.tab_db,     text="  数据源配置  ")
        nb.add(self.tab_press,  text="  压力曲线  ")
        nb.add(self.tab_th,     text="  温湿度曲线  ")
        nb.add(self.tab_sensor, text="  测点布局  ")

        # ── 底部操作栏 ──
        bot = tk.Frame(self, bg=C["panel"], height=50)
        bot.pack(fill="x", side="bottom")
        bot.pack_propagate(False)

        self.row_lbl = tk.Label(bot, text="行: 0 / 0",
                                bg=C["panel"], fg=C["dim"], font=FONT_S)
        self.row_lbl.pack(side="left", padx=16, pady=14)

        btn_f = tk.Frame(bot, bg=C["panel"])
        btn_f.pack(side="right", padx=10, pady=8)
        ttk.Button(btn_f, text="保存配置",
                   command=self._save).pack(side="left", padx=4)
        ttk.Button(btn_f, text="▶  开始读取", style="Accent.TButton",
                   command=self._start).pack(side="left", padx=4)
        ttk.Button(btn_f, text="■  停止读取",
                   command=self._stop).pack(side="left", padx=4)
        ttk.Button(btn_f, text="🌐  打开大屏",
                   command=self._open_dash).pack(side="left", padx=4)

        self._tick()

    # ── 定时刷新状态 ──
    def _tick(self):
        with lock:
            ri, n, running, lu = (store["row_index"], store["total_rows"],
                                  store["running"], store["last_update"])
        self.row_lbl.config(text=f"行: {ri} / {n or '?'}")
        if running:
            self.status_var.set(f"▶ 运行中  {lu}")
        self.after(1000, self._tick)

    def _save(self):
        self.tab_basic.apply()
        self.tab_db.apply()
        self.tab_press.apply()
        self.tab_th.apply()
        self.tab_sensor.apply()
        save_cfg()
        self.status_var.set("✓ 配置已保存")
        messagebox.showinfo("保存成功", "配置已保存到 config.json")

    def _start(self):
        self._save()
        if not cfg.get("variables"):
            messagebox.showwarning("提示", "请先在【数据源配置】中添加变量")
            return
        start_reading()
        self.status_var.set("▶ 正在读取数据…")

    def _stop(self):
        stop_reading()
        self.status_var.set("■ 已停止")

    def _open_dash(self):
        port = cfg.get("server_port", 5000)
        webbrowser.open(f"http://127.0.0.1:{port}")

    def refresh_var_lists(self):
        self.tab_press.refresh()
        self.tab_th.refresh()
        self.tab_sensor.refresh()

    def _on_close(self):
        stop_reading()
        self.destroy()


# ═══════════════ Tab 1 – 基本设置 ═══════════════
class BasicTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        f = ttk.Frame(self)
        f.pack(padx=30, pady=30, fill="both", expand=True)

        ttk.Label(f, text="基本设置", font=FONT_T).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 20))

        rows = [
            ("项目名称",      "title",          "str"),
            ("服务器端口",    "server_port",     "int"),
            ("读取间隔 (秒)", "read_interval",   "int"),
        ]
        self.vars = {}
        for i, (label, key, typ) in enumerate(rows, start=1):
            ttk.Label(f, text=label + ":").grid(
                row=i, column=0, sticky="w", pady=8, padx=(0, 15))
            v = tk.StringVar(value=str(cfg.get(key, "")))
            self.vars[key] = (v, typ)
            ttk.Entry(f, textvariable=v, width=45).grid(
                row=i, column=1, sticky="w", pady=8)

        info = tk.Frame(f, bg=C["card"], pady=10, padx=12)
        info.grid(row=10, column=0, columnspan=2, sticky="ew", pady=20)
        tk.Label(info,
                 text="说明：读取间隔指逐行读取的时间步长，例如设为 10 则每 10 秒推进一行数据。\n"
                      "服务器端口默认 5000，修改后需重启程序。",
                 bg=C["card"], fg=C["dim"], font=FONT_S,
                 wraplength=480, justify="left").pack(anchor="w")

    def apply(self):
        for key, (v, typ) in self.vars.items():
            val = v.get().strip()
            if typ == "int":
                try:
                    cfg[key] = int(val)
                except ValueError:
                    pass
            else:
                if val:
                    cfg[key] = val


# ═══════════════ Tab 2 – 数据源配置 ═══════════════
class DatabaseTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()
        self._refresh_tree()
        self._refresh_vars()

    def _build(self):
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=5, pady=5)

        # 左侧：数据库树
        left = ttk.Frame(pw)
        pw.add(left, weight=1)

        ttk.Label(left, text="数据库 / 表 / 列", font=FONT_H2).pack(
            anchor="w", padx=5, pady=(5, 3))

        btns = ttk.Frame(left)
        btns.pack(fill="x", padx=5, pady=3)
        ttk.Button(btns, text="＋ 添加数据库",
                   command=self._add_db).pack(side="left", padx=2)
        ttk.Button(btns, text="－ 移除数据库",
                   command=self._remove_db).pack(side="left", padx=2)

        tf = ttk.Frame(left)
        tf.pack(fill="both", expand=True, padx=5, pady=3)
        self.tree = ttk.Treeview(tf, columns=("type",),
                                  show="tree headings", selectmode="browse")
        self.tree.heading("#0",    text="名称")
        self.tree.heading("type",  text="类型")
        self.tree.column("#0",    width=200)
        self.tree.column("type",  width=70)
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_sel)

        ttk.Button(left, text="→ 添加选中列为变量",
                   command=self._add_var).pack(padx=5, pady=5)

        # 右侧：已配置变量
        right = ttk.Frame(pw)
        pw.add(right, weight=1)

        ttk.Label(right, text="已配置变量", font=FONT_H2).pack(
            anchor="w", padx=5, pady=(5, 3))

        vbtns = ttk.Frame(right)
        vbtns.pack(fill="x", padx=5, pady=3)
        ttk.Button(vbtns, text="－ 移除变量",
                   command=self._remove_var).pack(side="left", padx=2)

        vf = ttk.Frame(right)
        vf.pack(fill="both", expand=True, padx=5, pady=3)
        cols = ("var_id", "display_name", "db", "table", "column")
        self.vlist = ttk.Treeview(vf, columns=cols,
                                   show="headings", selectmode="browse")
        heads = [("var_id", "ID", 65), ("display_name", "显示名称", 120),
                 ("db", "数据库", 100), ("table", "表", 80), ("column", "列", 100)]
        for col, h, w in heads:
            self.vlist.heading(col, text=h)
            self.vlist.column(col, width=w)
        vsb2 = ttk.Scrollbar(vf, orient="vertical", command=self.vlist.yview)
        self.vlist.configure(yscrollcommand=vsb2.set)
        self.vlist.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")
        self.vlist.bind("<Double-1>", self._edit_name)

        ttk.Label(right, text="双击变量可修改显示名称",
                  foreground=C["dim"], font=FONT_S).pack(padx=5, pady=3, anchor="w")

        self._sel_db = self._sel_tbl = self._sel_col = None

    # ── 数据库树操作 ──
    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for db in cfg.get("databases", []):
            path  = db["path"]
            alias = db.get("alias", os.path.basename(path))
            dn = self.tree.insert("", "end", text=alias,
                                   values=("数据库",), tags=("db", path))
            for tbl in db_tables(path):
                tn = self.tree.insert(dn, "end", text=tbl,
                                       values=("表",), tags=("tbl", path, tbl))
                for col in db_cols(path, tbl):
                    self.tree.insert(tn, "end", text=col,
                                      values=("列",),
                                      tags=("col", path, tbl, col))

    def _refresh_vars(self):
        self.vlist.delete(*self.vlist.get_children())
        for v in cfg.get("variables", []):
            self.vlist.insert("", "end", iid=v["var_id"],
                               values=(v["var_id"], v["display_name"],
                                       os.path.basename(v["db_path"]),
                                       v["table"], v["column"]))

    def _on_sel(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        tags = self.tree.item(sel[0], "tags")
        if tags and tags[0] == "col":
            self._sel_db, self._sel_tbl, self._sel_col = tags[1], tags[2], tags[3]
        else:
            self._sel_db = self._sel_tbl = self._sel_col = None

    def _add_db(self):
        path = filedialog.askopenfilename(
            title="选择 SQLite 数据库文件",
            filetypes=[("SQLite 数据库", "*.db *.sqlite *.sqlite3"),
                       ("所有文件", "*.*")])
        if not path:
            return
        dbs = cfg.setdefault("databases", [])
        if any(d["path"] == path for d in dbs):
            messagebox.showinfo("提示", "该数据库已添加"); return
        dbs.append({"path": path, "alias": os.path.basename(path)})
        self._refresh_tree()

    def _remove_db(self):
        sel = self.tree.selection()
        if not sel:
            return
        tags = self.tree.item(sel[0], "tags")
        if not tags or tags[0] != "db":
            messagebox.showwarning("提示", "请选择数据库节点"); return
        path = tags[1]
        cfg["databases"] = [d for d in cfg.get("databases", [])
                             if d["path"] != path]
        cfg["variables"] = [v for v in cfg.get("variables", [])
                             if v["db_path"] != path]
        self._refresh_tree(); self._refresh_vars()
        self.app.refresh_var_lists()

    def _add_var(self):
        if not self._sel_col:
            messagebox.showwarning("提示", "请在左侧选择一个列节点"); return
        existing = {v["var_id"] for v in cfg.get("variables", [])}
        i = 1
        while f"var_{i:03d}" in existing:
            i += 1
        var_id = f"var_{i:03d}"
        cfg.setdefault("variables", []).append({
            "var_id":       var_id,
            "db_path":      self._sel_db,
            "table":        self._sel_tbl,
            "column":       self._sel_col,
            "display_name": self._sel_col,
        })
        self._refresh_vars()
        self.app.refresh_var_lists()

    def _remove_var(self):
        sel = self.vlist.selection()
        if not sel:
            return
        cfg["variables"] = [v for v in cfg.get("variables", [])
                             if v["var_id"] != sel[0]]
        self._refresh_vars()
        self.app.refresh_var_lists()

    def _edit_name(self, _):
        sel = self.vlist.selection()
        if not sel:
            return
        var = next((v for v in cfg.get("variables", [])
                    if v["var_id"] == sel[0]), None)
        if not var:
            return
        dlg = tk.Toplevel(self)
        dlg.title("修改显示名称")
        dlg.geometry("320x130")
        dlg.configure(bg=C["bg"])
        dlg.resizable(False, False)
        dlg.grab_set()
        ttk.Label(dlg, text="显示名称:").pack(pady=(20, 5))
        sv = tk.StringVar(value=var["display_name"])
        e  = ttk.Entry(dlg, textvariable=sv, width=32)
        e.pack(); e.focus()
        def ok():
            var["display_name"] = sv.get().strip() or var["column"]
            dlg.destroy(); self._refresh_vars(); self.app.refresh_var_lists()
        ttk.Button(dlg, text="确定", style="Accent.TButton",
                   command=ok).pack(pady=10)
        dlg.bind("<Return>", lambda _: ok())

    def apply(self):
        pass  # 已实时写入 cfg


# ═══════════════ Tab 3 – 压力曲线配置 ═══════════════
class PressureTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        f = ttk.Frame(self)
        f.pack(padx=30, pady=30, fill="both", expand=True)
        ttk.Label(f, text="压力曲线配置", font=FONT_T).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 20))

        labels = [("监测变量（实时逐行读取）:", "monitor"),
                  ("目标变量（虚线全量显示）:", "target")]
        self.cb = {}
        self.sv = {}
        for i, (lbl, key) in enumerate(labels, start=1):
            ttk.Label(f, text=lbl, font=FONT_B).grid(
                row=i, column=0, sticky="w", pady=10, padx=(0, 15))
            sv = tk.StringVar()
            cb = ttk.Combobox(f, textvariable=sv, state="readonly", width=45)
            cb.grid(row=i, column=1, sticky="w", pady=10)
            self.cb[key] = cb
            self.sv[key] = sv

        info = tk.Frame(f, bg=C["card"], pady=10, padx=12)
        info.grid(row=10, column=0, columnspan=2, sticky="ew", pady=20)
        tk.Label(info,
                 text="监测变量：按读取间隔逐行推进并绘制实时曲线（蓝色实线）。\n"
                      "目标变量：一次性全量读取，以虚线显示为参考曲线（橙色虚线）。",
                 bg=C["card"], fg=C["dim"], font=FONT_S,
                 wraplength=480, justify="left").pack(anchor="w")
        self.refresh()

    def _choices(self):
        return [""] + [f"{v['var_id']} – {v['display_name']}"
                       for v in cfg.get("variables", [])]

    def refresh(self):
        ch = self._choices()
        for cb in self.cb.values():
            cb["values"] = ch
        vlist = cfg.get("variables", [])
        pc    = cfg.get("pressure_chart", {})
        for key, field in (("monitor", "monitor_var"), ("target", "target_var")):
            vid = pc.get(field)
            if vid:
                v = next((x for x in vlist if x["var_id"] == vid), None)
                if v:
                    self.sv[key].set(f"{v['var_id']} – {v['display_name']}")

    def _extract(self, s):
        return s.split(" – ")[0].strip() if " – " in s else (s.strip() or None)

    def apply(self):
        cfg["pressure_chart"] = {
            "monitor_var": self._extract(self.sv["monitor"].get()),
            "target_var":  self._extract(self.sv["target"].get()),
        }


# ═══════════════ Tab 4 – 温湿度曲线配置 ═══════════════
class TempHumTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        f = ttk.Frame(self)
        f.pack(padx=20, pady=20, fill="both", expand=True)
        ttk.Label(f, text="温度与湿度曲线配置", font=FONT_T).pack(
            anchor="w", pady=(0, 15))

        cols = ttk.Frame(f)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)
        cols.rowconfigure(0, weight=1)

        # 温度框
        tf = ttk.LabelFrame(cols, text=" 温度变量 ", padding=10)
        tf.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=5)
        ttk.Label(tf, text="多选温度变量 (Ctrl/Shift 多选):",
                  font=FONT_B).pack(anchor="w", pady=(0, 5))
        tlbf = ttk.Frame(tf)
        tlbf.pack(fill="both", expand=True)
        self.t_lb = tk.Listbox(tlbf, selectmode="extended",
                                bg=C["card"], fg=C["text"],
                                selectbackground=C["accent"],
                                selectforeground=C["bg"],
                                font=FONT_S, height=8, activestyle="none")
        tsb = ttk.Scrollbar(tlbf, command=self.t_lb.yview)
        self.t_lb.configure(yscrollcommand=tsb.set)
        self.t_lb.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")
        ttk.Label(tf, text="高亮曲线:").pack(anchor="w", pady=(8, 3))
        self.hl_t = tk.StringVar()
        self.hl_t_cb = ttk.Combobox(tf, textvariable=self.hl_t,
                                     state="readonly", width=35)
        self.hl_t_cb.pack(anchor="w")

        # 湿度框
        hf = ttk.LabelFrame(cols, text=" 湿度变量 ", padding=10)
        hf.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=5)
        ttk.Label(hf, text="多选湿度变量 (Ctrl/Shift 多选):",
                  font=FONT_B).pack(anchor="w", pady=(0, 5))
        hlbf = ttk.Frame(hf)
        hlbf.pack(fill="both", expand=True)
        self.h_lb = tk.Listbox(hlbf, selectmode="extended",
                                bg=C["card"], fg=C["text"],
                                selectbackground=C["accent"],
                                selectforeground=C["bg"],
                                font=FONT_S, height=8, activestyle="none")
        hsb = ttk.Scrollbar(hlbf, command=self.h_lb.yview)
        self.h_lb.configure(yscrollcommand=hsb.set)
        self.h_lb.pack(side="left", fill="both", expand=True)
        hsb.pack(side="right", fill="y")
        ttk.Label(hf, text="高亮曲线:").pack(anchor="w", pady=(8, 3))
        self.hl_h = tk.StringVar()
        self.hl_h_cb = ttk.Combobox(hf, textvariable=self.hl_h,
                                     state="readonly", width=35)
        self.hl_h_cb.pack(anchor="w")
        self.refresh()

    def _choices(self):
        return [""] + [f"{v['var_id']} – {v['display_name']}"
                       for v in cfg.get("variables", [])]

    def refresh(self):
        vlist  = cfg.get("variables", [])
        labels = [f"{v['var_id']} – {v['display_name']}" for v in vlist]
        ids    = [v["var_id"] for v in vlist]

        self.t_lb.delete(0, "end")
        self.h_lb.delete(0, "end")
        for lbl in labels:
            self.t_lb.insert("end", lbl)
            self.h_lb.insert("end", lbl)

        thc  = cfg.get("temp_humidity_chart", {})
        t_vs = thc.get("temp_vars", [])
        h_vs = thc.get("humidity_vars", [])
        for i, vid in enumerate(ids):
            if vid in t_vs:
                self.t_lb.selection_set(i)
            if vid in h_vs:
                self.h_lb.selection_set(i)

        ch = self._choices()
        self.hl_t_cb["values"] = ch
        self.hl_h_cb["values"] = ch
        for sv, field in ((self.hl_t, "highlight_temp"),
                          (self.hl_h, "highlight_humidity")):
            vid = thc.get(field)
            if vid:
                v = next((x for x in vlist if x["var_id"] == vid), None)
                if v:
                    sv.set(f"{v['var_id']} – {v['display_name']}")

    def _extract(self, s):
        return s.split(" – ")[0].strip() if " – " in s else (s.strip() or None)

    def apply(self):
        vlist = cfg.get("variables", [])
        ids   = [v["var_id"] for v in vlist]
        t_sel = [ids[i] for i in self.t_lb.curselection() if i < len(ids)]
        h_sel = [ids[i] for i in self.h_lb.curselection() if i < len(ids)]
        cfg["temp_humidity_chart"] = {
            "temp_vars":         t_sel,
            "humidity_vars":     h_sel,
            "highlight_temp":    self._extract(self.hl_t.get()),
            "highlight_humidity": self._extract(self.hl_h.get()),
        }


# ═══════════════ Tab 5 – 测点布局配置 ═══════════════
class SensorTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app   = app
        self.lframes = []
        self._build()
        self._load()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 5))
        ttk.Label(top, text="测点布局配置", font=FONT_T).pack(side="left")

        ctrl = ttk.Frame(top)
        ctrl.pack(side="right")
        ttk.Label(ctrl, text="层数:").pack(side="left", padx=(0, 5))
        self.n_layers = tk.IntVar(value=3)
        ttk.Spinbox(ctrl, from_=1, to=20, textvariable=self.n_layers,
                    width=5, command=self._apply_count).pack(side="left")
        ttk.Button(ctrl, text="应用层数",
                   command=self._apply_count).pack(side="left", padx=5)

        # 滚动区域
        cont = ttk.Frame(self)
        cont.pack(fill="both", expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(cont, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(cont, orient="vertical",
                             command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.inner = ttk.Frame(self.canvas)
        self._win  = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
            lambda _: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
            lambda e: self.canvas.itemconfig(self._win, width=e.width))
        self.canvas.bind_all("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"))

    def _apply_count(self):
        n = self.n_layers.get()
        while len(self.lframes) < n:
            lf = LayerFrame(self.inner, len(self.lframes) + 1,
                            {}, self._var_choices)
            lf.pack(fill="x", padx=5, pady=4)
            self.lframes.append(lf)
        while len(self.lframes) > n:
            self.lframes[-1].destroy()
            self.lframes.pop()

    def _var_choices(self):
        return [""] + [f"{v['var_id']} – {v['display_name']}"
                       for v in cfg.get("variables", [])]

    def _load(self):
        layers = cfg.get("sensor_layout", {}).get("layers", [])
        for lf in self.lframes:
            lf.destroy()
        self.lframes = []
        if not layers:
            self.n_layers.set(3)
            layers = [{} for _ in range(3)]
        else:
            self.n_layers.set(len(layers))
        for i, ld in enumerate(layers):
            lf = LayerFrame(self.inner, i + 1, ld, self._var_choices)
            lf.pack(fill="x", padx=5, pady=4)
            self.lframes.append(lf)

    def refresh(self):
        ch = self._var_choices()
        for lf in self.lframes:
            lf.update_choices(ch)

    def apply(self):
        cfg["sensor_layout"] = {
            "layers": [lf.get_data() for lf in self.lframes]
        }


class LayerFrame(ttk.LabelFrame):
    """单层测点配置卡片"""
    def __init__(self, parent, num, data, get_choices):
        super().__init__(parent, text=f" 第 {num} 层 ", padding=8)
        self.num         = num
        self.data        = data
        self.get_choices = get_choices
        self.sensor_svs  = []
        self._build()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x")

        ttk.Label(top, text="层标签:").pack(side="left", padx=(0, 3))
        self.lbl_sv = tk.StringVar(
            value=self.data.get("label", f"L{self.num}"))
        ttk.Entry(top, textvariable=self.lbl_sv, width=8).pack(
            side="left", padx=(0, 12))

        ttk.Label(top, text="高度 (Y):").pack(side="left", padx=(0, 3))
        default_h = round(-1.2 + (self.num - 1) * 0.8, 1)
        self.h_sv = tk.StringVar(
            value=str(self.data.get("height", default_h)))
        ttk.Entry(top, textvariable=self.h_sv, width=7).pack(
            side="left", padx=(0, 12))

        ttk.Label(top, text="测点数:").pack(side="left", padx=(0, 3))
        self.cnt_v = tk.IntVar(value=self.data.get("count", 4))
        ttk.Spinbox(top, from_=1, to=24, textvariable=self.cnt_v,
                    width=5, command=self._rebuild).pack(
                        side="left", padx=(0, 6))
        ttk.Button(top, text="刷新", command=self._rebuild).pack(side="left")

        self.sf = ttk.Frame(self)
        self.sf.pack(fill="x", pady=(6, 0))
        self._rebuild()

    def _rebuild(self):
        for w in self.sf.winfo_children():
            w.destroy()
        self.sensor_svs = []
        n       = self.cnt_v.get()
        exist   = self.data.get("vars", [])
        choices = self.get_choices()

        for i in range(n):
            row, col = divmod(i, 4)
            cell = ttk.Frame(self.sf)
            cell.grid(row=row, column=col, padx=4, pady=2, sticky="w")
            ttk.Label(cell, text=f"#{i+1}:", font=FONT_S).pack(side="left")
            sv  = tk.StringVar()
            vid = exist[i] if i < len(exist) else None
            if vid:
                match = next(
                    (c for c in choices if c.startswith(vid + " – ")), vid)
                sv.set(match)
            ttk.Combobox(cell, textvariable=sv, values=choices,
                         width=22, state="readonly",
                         font=FONT_S).pack(side="left")
            self.sensor_svs.append(sv)

    def update_choices(self, choices):
        for w in self.sf.winfo_children():
            for child in w.winfo_children():
                if isinstance(child, ttk.Combobox):
                    child["values"] = choices

    def get_data(self):
        def eid(s):
            return s.split(" – ")[0].strip() if " – " in s else (s.strip() or None)
        try:
            h = float(self.h_sv.get())
        except ValueError:
            h = 0.0
        return {
            "label":  self.lbl_sv.get(),
            "height": h,
            "count":  self.cnt_v.get(),
            "vars":   [eid(sv.get()) for sv in self.sensor_svs],
        }


# ═══════════════ 主入口 ═══════════════
def main():
    load_cfg()
    if HAS_FLASK:
        threading.Thread(target=run_flask, daemon=True).start()
    else:
        print("警告: Flask 未安装，大屏无法连接后端。\n"
              "请运行: pip install flask flask-cors")
    threading.Thread(target=reader_loop, daemon=True).start()
    App().mainloop()


if __name__ == "__main__":
    main()
