import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox

# 深蓝科技风格
DEEPBLUE_BG = "#101D42"
DEEPBLUE_FG = "#00CFFF"
DEEPBLUE_BTN_BG = "#1E2746"
DEEPBLUE_BTN_FG = "#ffffff"
DEEPBLUE_ENTRY_BG = "#18244a"
DEEPBLUE_ENTRY_FG = "#00CFFF"

def select_db_file():
    file_path = filedialog.askopenfilename(
        title="选择db文件",
        filetypes=[("Database Files", "*.db"), ("All Files", "*.*")]
    )
    if file_path:
        entry_file.delete(0, tk.END)
        entry_file.insert(0, file_path)

def copy_and_rename_db():
    src = entry_file.get()
    if not os.path.isfile(src):
        messagebox.showerror("错误", "请选择一个有效的db文件。")
        return
    dst = os.path.join(os.path.dirname(src), "2.db")
    try:
        if os.path.exists(dst):
            os.remove(dst)
        shutil.copy2(src, dst)
        messagebox.showinfo("成功", f"文件已复制并重命名为: {dst}")
    except Exception as e:
        messagebox.showerror("复制失败", str(e))

# GUI主窗口
root = tk.Tk()
root.title("深蓝科技风DB文件复制器")
root.configure(bg=DEEPBLUE_BG)
root.geometry("520x180")
root.resizable(False, False)

# 文件选择部分
lbl_file = tk.Label(root, text="选择DB文件：", bg=DEEPBLUE_BG, fg=DEEPBLUE_FG, font=("微软雅黑", 12))
lbl_file.place(x=30, y=35)

entry_file = tk.Entry(root, width=38, bg=DEEPBLUE_ENTRY_BG, fg=DEEPBLUE_ENTRY_FG, font=("Consolas", 11))
entry_file.place(x=130, y=38)

btn_browse = tk.Button(
    root, text="浏览…", command=select_db_file,
    bg=DEEPBLUE_BTN_BG, fg=DEEPBLUE_BTN_FG, font=("微软雅黑", 11), borderwidth=0, activebackground=DEEPBLUE_BG
)
btn_browse.place(x=410, y=35, width=80, height=30)

# 执行按钮
btn_copy = tk.Button(
    root, text="复制并另存为2.db", command=copy_and_rename_db,
    bg=DEEPBLUE_FG, fg=DEEPBLUE_BTN_BG, font=("微软雅黑", 13, "bold"), borderwidth=0, activebackground=DEEPBLUE_BTN_BG
)
btn_copy.place(x=160, y=100, width=200, height=40)

root.mainloop()