import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import base64
import io
import os
import tempfile

try:
    from PIL import Image, ImageTk, ImageFilter
except ImportError:
    raise SystemExit("请先安装 Pillow: pip install Pillow")


def _load_svg(path: str) -> Image.Image:
    """读取 SVG 并转成 RGBA 图片（多后备，兼容更多环境）。"""
    errors = []

    # 方案 1：cairosvg（最推荐）
    try:
        import cairosvg

        with open(path, "rb") as f:
            svg_bytes = f.read()

        # 不强制 scale，优先保留原始尺寸；缺少尺寸时由库自行推断
        png_bytes = cairosvg.svg2png(bytestring=svg_bytes)
        return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except Exception as exc:
        errors.append(f"cairosvg: {exc}")

    # 方案 2：svglib + reportlab（某些环境需 rlPyCairo）
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM

        drawing = svg2rlg(path)
        if drawing is None:
            raise RuntimeError("svg2rlg 未能解析该 SVG 文件")

        try:
            png_bytes = renderPM.drawToString(drawing, fmt="PNG", dpi=144)
        except Exception:
            # 某些 reportlab 版本/环境需要显式指定 backend
            png_bytes = renderPM.drawToString(drawing, fmt="PNG", dpi=144, backend="rlPyCairo")

        return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except Exception as exc:
        errors.append(f"svglib/reportlab: {exc}")

    # 方案 3：inkscape 命令行（如果用户已安装）
    try:
        import subprocess

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            out_png = tmp.name
        try:
            cmd = ["inkscape", path, "--export-type=png", f"--export-filename={out_png}"]
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if p.returncode != 0:
                raise RuntimeError(p.stderr.strip() or p.stdout.strip() or "Inkscape 转换失败")
            return Image.open(out_png).convert("RGBA")
        finally:
            if os.path.exists(out_png):
                os.remove(out_png)
    except Exception as exc:
        errors.append(f"inkscape: {exc}")

    raise RuntimeError(
        "SVG 打开失败。请安装以下任一方案后重试：\n"
        "1) pip install cairosvg\n"
        "2) pip install svglib reportlab rlPyCairo\n"
        "3) 安装 Inkscape 并确保命令 inkscape 在 PATH 中\n\n"
        "详细错误：\n- " + "\n- ".join(errors)
    )


def _hq_resize(img: Image.Image, new_w: int, new_h: int) -> Image.Image:
    src_w, src_h = img.size
    if new_w >= src_w and new_h >= src_h:
        return img.resize((new_w, new_h), Image.LANCZOS)

    tmp = img
    while True:
        tw = max(new_w, tmp.width // 2)
        th = max(new_h, tmp.height // 2)
        tmp = tmp.resize((tw, th), Image.LANCZOS)
        if tw == new_w and th == new_h:
            break

    if tmp.mode == "RGBA":
        r, g, b, a = tmp.split()
        rgb = Image.merge("RGB", (r, g, b)).filter(ImageFilter.UnsharpMask(radius=0.6, percent=120, threshold=2))
        r2, g2, b2 = rgb.split()
        return Image.merge("RGBA", (r2, g2, b2, a))
    return tmp.filter(ImageFilter.UnsharpMask(radius=0.6, percent=120, threshold=2))


class ImageEditor:
    ZOOM_STEPS = [0.1, 0.15, 0.2, 0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0, 5.0]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("图片编辑器 — 裁剪 / 缩放 / 导出 SVG")
        self.root.geometry("1280x840")
        self.root.configure(bg="#1e1e2e")

        self.original_image = None
        self.edit_image = None
        self.file_path = ""
        self.zoom = 1.0
        self._tk_image = None
        self._undo_stack = []

        self._build_ui()

    def _build_ui(self):
        bar = tk.Frame(self.root, bg="#313244", pady=4)
        bar.pack(side=tk.TOP, fill=tk.X)
        btn = dict(bg="#45475a", fg="#cdd6f4", activebackground="#585b70", relief=tk.FLAT, font=("Helvetica", 10), padx=10, pady=4)
        tk.Button(bar, text="📂 打开图片", command=self.open_image, **btn).pack(side=tk.LEFT, padx=4)
        tk.Button(bar, text="⇲ 缩放 50%", command=lambda: self.resize_half(), **btn).pack(side=tk.LEFT, padx=4)
        tk.Button(bar, text="💾 保存 SVG", command=self.save_as_svg, **btn).pack(side=tk.LEFT, padx=4)

        self._status = tk.StringVar(value="请打开图片（支持 SVG）")
        tk.Label(self.root, textvariable=self._status, bg="#181825", fg="#a6adc8", anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(self.root, bg="#181825", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def open_image(self):
        path = filedialog.askopenfilename(filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.webp *.svg"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            if path.lower().endswith(".svg"):
                img = _load_svg(path)
            else:
                img = Image.open(path).convert("RGBA")
            self.file_path = path
            self.original_image = img.copy()
            self.edit_image = img
            self._refresh_canvas()
            self._status.set(f"已打开：{os.path.basename(path)}  {img.width}×{img.height}")
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def _refresh_canvas(self):
        if not self.edit_image:
            return
        w, h = self.edit_image.size
        self._tk_image = ImageTk.PhotoImage(self.edit_image.resize((int(w*self.zoom), int(h*self.zoom)), Image.LANCZOS))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._tk_image)

    def resize_half(self):
        if not self.edit_image:
            return
        self._undo_stack.append(self.edit_image.copy())
        self.edit_image = _hq_resize(self.edit_image, max(1, self.edit_image.width // 2), max(1, self.edit_image.height // 2))
        self._refresh_canvas()

    def save_as_svg(self):
        if self.edit_image is None:
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG", "*.svg")])
        if not save_path:
            return

        img = self.edit_image.convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=False, compress_level=1)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        w, h = img.size
        svg = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f'  <image xlink:href="data:image/png;base64,{b64}" x="0" y="0" width="{w}" height="{h}"/>\n'
            f'</svg>\n'
        )
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(svg)
        messagebox.showinfo("保存成功", save_path)


def main():
    root = tk.Tk()
    ImageEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
