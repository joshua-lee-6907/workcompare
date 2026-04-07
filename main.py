import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import webbrowser
import os
import signal
import psutil  # 需要安装：pip install psutil

# 定义按钮和对应的exe文件名
button_info = [
    ("读取网页", "readweb.exe"),
    ("预处理网页", "preweb.exe"),
    ("计算网页", "calweb.exe"),
    ("数据网页", "dataweb.exe"),
    ("Q1D网页", "q1dweb.exe"),
    ("Q60网页", "q60web.exe"),
]

# 用于保存已运行的exe进程
running_procs = {}

def run_exe(exe_name):
    try:
        # 启动exe，并保存进程对象
        proc = subprocess.Popen([exe_name])
        running_procs[exe_name] = proc
    except Exception as e:
        messagebox.showerror("错误", f"无法启动 {exe_name}\n{e}")

def terminate_procs():
    fail = []
    for exe, proc in running_procs.items():
        # 检查进程是否还在
        if proc.poll() is None:
            try:
                # 使用 psutil 终止进程及其子进程
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
            except Exception as e:
                fail.append(exe)
    running_procs.clear()
    if fail:
        messagebox.showwarning("警告", f"部分进程未能关闭: {fail}")
    else:
        messagebox.showinfo("提示", "所有已启动的进程已终止。")

def jump_to_web():
    webbrowser.open("http://127.0.0.1:5000")

def create_gui():
    root = tk.Tk()
    root.title("科技感深蓝风GUI")
    root.geometry("420x420")
    root.configure(bg="#0c143d")

    style = ttk.Style()
    style.theme_use('clam')
    style.configure('Tech.TButton',
                    font=('Segoe UI', 14, 'bold'),
                    background='#113366',
                    foreground='#40a9ff',
                    borderwidth=2,
                    focusthickness=3,
                    focuscolor='none')
    style.map('Tech.TButton',
              background=[('active', '#1b2557')],
              foreground=[('active', '#61dafb')])

    title = tk.Label(root, text="深蓝科技感工具面板", bg="#0c143d",
                     fg="#61dafb", font=("Segoe UI", 20, "bold"))
    title.pack(pady=20)

    btn_frame = tk.Frame(root, bg="#0c143d")
    btn_frame.pack(pady=8)

    for i, (label, exe) in enumerate(button_info):
        btn = ttk.Button(btn_frame, text=label, style='Tech.TButton',
                         command=lambda exe=exe: run_exe(exe), width=16)
        btn.grid(row=i//2, column=i%2, padx=18, pady=14)

    # 终止进程按钮
    stop_btn = ttk.Button(root, text="终止所有进程", style='Tech.TButton',
                          command=terminate_procs, width=20)
    stop_btn.pack(pady=12)

    # 跳转网页按钮
    jump_btn = ttk.Button(root, text="打开Web界面", style='Tech.TButton',
                          command=jump_to_web, width=20)
    jump_btn.pack(pady=4)

    root.mainloop()

if __name__ == "__main__":
    create_gui()