import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk
import imageio.v3 as iio
import numpy as np


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def extract_index(filename: str):
    """提取文件名末尾数字作为排序依据，如 xxx-12.png -> 12。"""
    stem = os.path.splitext(os.path.basename(filename))[0]
    m = re.search(r"(\d+)$", stem)
    if m:
        return int(m.group(1))
    return float("inf")


class ImageAnimatorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("图片序列动画生成器")
        self.root.geometry("960x700")

        self.folder_path = tk.StringVar()
        self.fps_var = tk.IntVar(value=12)
        self.status_var = tk.StringVar(value="请选择图片文件夹")

        self.frames_pil = []
        self.preview_frames = []
        self.animating = False
        self.current_frame_index = 0

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="图片文件夹:").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.folder_path, width=80).grid(
            row=0, column=1, padx=6, sticky="we"
        )
        ttk.Button(top, text="选择文件夹", command=self.choose_folder).grid(row=0, column=2)

        ttk.Label(top, text="FPS:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(top, from_=1, to=60, textvariable=self.fps_var, width=8).grid(
            row=1, column=1, sticky="w", pady=(8, 0)
        )

        button_bar = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        button_bar.pack(fill="x")

        ttk.Button(button_bar, text="加载并预览", command=self.load_images).pack(side="left")
        ttk.Button(button_bar, text="停止预览", command=self.stop_preview).pack(
            side="left", padx=8
        )
        ttk.Button(button_bar, text="保存为 MP4", command=self.save_mp4).pack(side="left")

        self.canvas = tk.Canvas(self.root, width=900, height=540, bg="black")
        self.canvas.pack(padx=10, pady=10, fill="both", expand=True)

        ttk.Label(self.root, textvariable=self.status_var, padding=(10, 0, 10, 12)).pack(
            anchor="w"
        )

        top.columnconfigure(1, weight=1)

    def choose_folder(self):
        folder = filedialog.askdirectory(title="选择包含图片序列的文件夹")
        if folder:
            self.folder_path.set(folder)

    def get_sorted_files(self, folder):
        files = []
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and os.path.splitext(name.lower())[1] in IMAGE_EXTS:
                files.append(path)

        files.sort(key=lambda p: (extract_index(p), p.lower()))
        return files

    def load_images(self):
        folder = self.folder_path.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("错误", "请选择有效文件夹")
            return

        img_files = self.get_sorted_files(folder)
        if not img_files:
            messagebox.showwarning("提示", "该文件夹未找到图片文件")
            return

        self.frames_pil = [Image.open(fp).convert("RGB") for fp in img_files]
        self.preview_frames = []

        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())

        for img in self.frames_pil:
            scaled = img.copy()
            scaled.thumbnail((canvas_w, canvas_h), Image.Resampling.LANCZOS)
            self.preview_frames.append(ImageTk.PhotoImage(scaled))

        self.current_frame_index = 0
        self.status_var.set(
            f"已加载 {len(self.frames_pil)} 张图片，按序号排序完成，正在预览..."
        )
        self.start_preview()

    def start_preview(self):
        if not self.preview_frames:
            return
        self.animating = True
        self._show_next_frame()

    def stop_preview(self):
        self.animating = False
        self.status_var.set("预览已停止")

    def _show_next_frame(self):
        if not self.animating or not self.preview_frames:
            return

        frame = self.preview_frames[self.current_frame_index]
        self.canvas.delete("all")
        x = self.canvas.winfo_width() // 2
        y = self.canvas.winfo_height() // 2
        self.canvas.create_image(x, y, image=frame, anchor="center")

        self.current_frame_index = (self.current_frame_index + 1) % len(self.preview_frames)
        interval = int(1000 / max(1, self.fps_var.get()))
        self.root.after(interval, self._show_next_frame)

    def save_mp4(self):
        if not self.frames_pil:
            messagebox.showwarning("提示", "请先加载图片")
            return

        out_file = filedialog.asksaveasfilename(
            title="保存 MP4",
            defaultextension=".mp4",
            filetypes=[("MP4 视频", "*.mp4")],
        )
        if not out_file:
            return

        fps = max(1, self.fps_var.get())

        # 导出时要求所有帧尺寸一致，这里统一到首帧尺寸
        base_w, base_h = self.frames_pil[0].size

        def normalize_frame_size(img: Image.Image) -> np.ndarray:
            """将任意尺寸帧缩放并居中贴到统一画布，保证 MP4 导出时 shape 一致。"""
            canvas = Image.new("RGB", (base_w, base_h), (0, 0, 0))
            frame = img.copy()
            frame.thumbnail((base_w, base_h), Image.Resampling.LANCZOS)
            x = (base_w - frame.width) // 2
            y = (base_h - frame.height) // 2
            canvas.paste(frame, (x, y))
            return np.array(canvas)

        def worker():
            try:
                self.status_var.set("正在导出 MP4，请稍候...")
                frames_np = [normalize_frame_size(img) for img in self.frames_pil]

                # 依次尝试多个编码参数，避免某些环境缺少 libx264 导致导出失败
                attempts = [
                    {"codec": "libx264", "pixelformat": "yuv420p"},
                    {"codec": "h264", "pixelformat": "yuv420p"},
                    {"codec": "mpeg4"},
                    {},
                ]

                last_error = None
                for params in attempts:
                    try:
                        iio.imwrite(out_file, frames_np, fps=fps, **params)
                        last_error = None
                        break
                    except Exception as err:
                        last_error = err

                if last_error is not None:
                    raise last_error

                self.status_var.set(f"导出完成: {out_file}")
                messagebox.showinfo("完成", f"MP4 已保存:\n{out_file}")
            except Exception as e:
                self.status_var.set("导出失败")
                messagebox.showerror(
                    "导出失败",
                    f"无法导出 MP4:\n{e}\n\n可尝试：\n"
                    "1) 安装完整 ffmpeg（包含 x264）\n"
                    "2) 或继续使用当前版本，程序会自动回退到 mpeg4 编码。",
                )

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    app = ImageAnimatorGUI(root)
    root.mainloop()
