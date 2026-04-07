import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import platform
import tempfile
import io
import unicodedata
from datetime import datetime, date
import fitz # PyMuPDF
from PIL import Image, ImageTk, ImageDraw, ImageFont
import openpyxl
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, Alignment, PatternFill
# ─── Unicode Font Detection ───────────────────────────────────────────────────
def find_unicode_font():
    system = platform.system()
    if system == "Windows":
        paths = [
            "C:/Windows/Fonts/seguiemj.ttf",
            "C:/Windows/Fonts/segoeuisym.ttf",
            "C:/Windows/Fonts/seguisym.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/arialuni.ttf",
            "C:/Windows/Fonts/cambria.ttc",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]
    elif system == "Darwin":
        paths = [
            "/System/Library/Fonts/Apple Color Emoji.ttc",
            "/System/Library/Fonts/Apple Symbols.ttf",
            "/Library/Fonts/Arial Unicode MS.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        paths = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansMath-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/stix/STIXGeneral.ttf",
        ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None
UNICODE_FONT_PATH = find_unicode_font()

# ─── UI Font Detection ────────────────────────────────────────────────────────
def _ui_font_family():
    system = platform.system()
    if system == "Windows":
        for f in ("Microsoft YaHei UI", "Segoe UI", "Arial"):
            return f
    elif system == "Darwin":
        return "PingFang SC"
    return "sans-serif"

_FF = _ui_font_family()

class PDFMarkerApp:
    # ── colour palette ────────────────────────────────────────────────────
    C_BG       = "#f0f2f5"
    C_CARD     = "#ffffff"
    C_PRIMARY  = "#2563eb"
    C_ACCENT   = "#059669"
    C_DANGER   = "#dc2626"
    C_WARN     = "#d97706"
    C_TEXT     = "#1e293b"
    C_MUTED    = "#64748b"
    C_BORDER   = "#cbd5e1"
    C_CANVAS   = "#334155"
    C_TREE_OK  = "#d1fae5"
    C_TREE_NG  = "#fee2e2"

    def __init__(self, root):
        self.root = root
        self.root.title("PDF 标记与核对工具")
        self.root.geometry("1520x940")
        self.root.configure(bg=self.C_BG)
        self.root.minsize(1000, 600)

        # ── ttk theme ─────────────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")
        _f9  = (_FF, 9)
        _f9b = (_FF, 9, "bold")
        _f10 = (_FF, 10)
        _f10b = (_FF, 10, "bold")
        _f11b = (_FF, 11, "bold")
        style.configure(".", background=self.C_BG, foreground=self.C_TEXT, font=_f9)
        style.configure("TNotebook", background=self.C_BG, tabmargins=[6, 6, 6, 0])
        style.configure("TNotebook.Tab", background="#e2e8f0", foreground=self.C_TEXT,
                         padding=[18, 7], font=_f10b)
        style.map("TNotebook.Tab",
                  background=[("selected", self.C_CARD)],
                  foreground=[("selected", self.C_PRIMARY)])
        style.configure("TFrame", background=self.C_BG)
        style.configure("Card.TFrame", background=self.C_CARD)
        style.configure("TLabel", background=self.C_BG, foreground=self.C_TEXT, font=_f9)
        style.configure("Heading.TLabel", font=_f11b)
        style.configure("Muted.TLabel", foreground=self.C_MUTED, font=_f9)
        style.configure("Status.TLabel", background="#e2e8f0", foreground=self.C_MUTED,
                         font=_f9, padding=[10, 5])
        style.configure("TButton", padding=[10, 4], font=_f9)
        style.configure("Primary.TButton", foreground=self.C_PRIMARY, font=_f9b)
        style.configure("Accent.TButton",  foreground=self.C_ACCENT,  font=_f9b)
        style.configure("Danger.TButton",  foreground=self.C_DANGER,  font=_f9b)
        style.configure("Warn.TButton",    foreground=self.C_WARN,    font=_f9b)
        style.configure("TLabelframe", background=self.C_BG)
        style.configure("TLabelframe.Label", font=_f9b, foreground=self.C_TEXT)
        style.configure("Treeview", font=_f9, rowheight=28, fieldbackground=self.C_CARD)
        style.configure("Treeview.Heading", font=_f9b, background="#e2e8f0",
                         foreground=self.C_TEXT)
        style.map("Treeview", background=[("selected", "#dbeafe")],
                  foreground=[("selected", self.C_PRIMARY)])
        style.configure("TSeparator", background=self.C_BORDER)
        style.configure("TPanedwindow", background=self.C_BG)
        style.configure("TSpinbox", font=_f9)

        # ── notebook ──────────────────────────────────────────────────────
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 8))
        self.mark_frame   = ttk.Frame(self.notebook)
        self.apply_frame  = ttk.Frame(self.notebook)
        self.verify_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.mark_frame,   text="  标记 PDF  ")
        self.notebook.add(self.apply_frame,  text="  应用标记  ")
        self.notebook.add(self.verify_frame, text="  Excel 核对  ")
        self._setup_mark_tab()
        self._setup_apply_tab()
        self._setup_verify_tab()
    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — MARK
    # ══════════════════════════════════════════════════════════════════════
    def _setup_mark_tab(self):
        self.mark_pdf_path = None
        self.mark_doc = None
        self.mark_page_index = 0
        self.mark_zoom = 1.5
        self.mark_photo = None
        self.mark_sx = 1.0
        self.mark_sy = 1.0
        self.mark_baselines = {}
        self.markers = []
        self.mark_mode = "idle"
        self.drag_start = None
        self.rubber_band = None
        # ── toolbar ────────────────────────────────────────────────────────
        r1 = ttk.Frame(self.mark_frame)
        r1.pack(fill=tk.X, padx=12, pady=(10, 3))
        ttk.Button(r1, text="选择 PDF", style="Primary.TButton",
                   command=self._mark_open_pdf).pack(side=tk.LEFT, padx=(0, 4))
        self.lbl_mark_pdf = ttk.Label(r1, text="未选择文件", style="Muted.TLabel")
        self.lbl_mark_pdf.pack(side=tk.LEFT, padx=6)
        ttk.Separator(r1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        self.btn_m_baseline = ttk.Button(r1, text="设置基准点",
                   command=self._mark_enter_baseline_mode, state=tk.DISABLED)
        self.btn_m_baseline.pack(side=tk.LEFT, padx=3)
        self.btn_m_start = ttk.Button(r1, text="开始标记", style="Accent.TButton",
                   command=self._mark_start, state=tk.DISABLED)
        self.btn_m_start.pack(side=tk.LEFT, padx=3)
        self.btn_m_finish = ttk.Button(r1, text="完成标记", style="Accent.TButton",
                   command=self._mark_finish, state=tk.DISABLED)
        self.btn_m_finish.pack(side=tk.LEFT, padx=3)
        self.btn_m_undo = ttk.Button(r1, text="撤销",
                   command=self._mark_undo, state=tk.DISABLED)
        self.btn_m_undo.pack(side=tk.LEFT, padx=3)
        self.btn_m_clear = ttk.Button(r1, text="清空", style="Danger.TButton",
                   command=self._mark_clear, state=tk.DISABLED)
        self.btn_m_clear.pack(side=tk.LEFT, padx=3)

        # ── page nav + status ─────────────────────────────────────────────
        r2 = ttk.Frame(self.mark_frame)
        r2.pack(fill=tk.X, padx=12, pady=3)
        ttk.Button(r2, text="<", width=3, command=self._mark_prev_page).pack(side=tk.LEFT)
        self.lbl_mark_page = ttk.Label(r2, text=" — / — ")
        self.lbl_mark_page.pack(side=tk.LEFT, padx=2)
        ttk.Button(r2, text=">", width=3, command=self._mark_next_page).pack(side=tk.LEFT)
        self.lbl_mark_status = ttk.Label(r2, text="请先选择 PDF 文件",
                                          foreground=self.C_PRIMARY)
        self.lbl_mark_status.pack(side=tk.LEFT, padx=20)

        # ── canvas ────────────────────────────────────────────────────────
        cf = ttk.Frame(self.mark_frame)
        cf.pack(fill=tk.BOTH, expand=True, padx=12, pady=(3, 8))
        self.mark_canvas = tk.Canvas(cf, bg=self.C_CANVAS, cursor="crosshair",
                                      highlightthickness=0)
        self.mark_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(cf, orient=tk.VERTICAL, command=self.mark_canvas.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(self.mark_frame, orient=tk.HORIZONTAL, command=self.mark_canvas.xview)
        hsb.pack(fill=tk.X, padx=10, pady=(0, 4))
        self.mark_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.mark_canvas.bind("<ButtonPress-1>", self._mc_press)
        self.mark_canvas.bind("<B1-Motion>", self._mc_motion)
        self.mark_canvas.bind("<ButtonRelease-1>", self._mc_release)
    def _mark_open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF 文件", "*.pdf")])
        if not path:
            return
        self.mark_pdf_path = path
        self.mark_doc = fitz.open(path)
        self.mark_page_index = 0
        self.markers.clear()
        self.mark_baselines.clear()
        self.lbl_mark_pdf.config(text=os.path.basename(path), foreground="black")
        self.btn_m_baseline.config(state=tk.NORMAL)
        self.btn_m_start.config(state=tk.DISABLED)
        self.btn_m_finish.config(state=tk.DISABLED)
        self.btn_m_undo.config(state=tk.DISABLED)
        self.btn_m_clear.config(state=tk.DISABLED)
        self.mark_mode = "idle"
        self._mark_render()
        self._mark_status("PDF 已加载, 每页可单独设置基准点")
    def _mark_prev_page(self):
        if self.mark_doc and self.mark_page_index > 0:
            self.mark_page_index -= 1
            self.mark_mode = "idle"
            self._mark_render()
    def _mark_next_page(self):
        if self.mark_doc and self.mark_page_index < len(self.mark_doc) - 1:
            self.mark_page_index += 1
            self.mark_mode = "idle"
            self._mark_render()
    def _mark_enter_baseline_mode(self):
        if not self.mark_doc:
            return
        self.mark_mode = "set_baseline"
        self.mark_canvas.config(cursor="tcross")
        self._mark_status(f"基准点模式: 请在第 {self.mark_page_index + 1} 页点击一个参考位置")
    def _mark_start(self):
        if not self.mark_doc:
            return
        if self.mark_page_index not in self.mark_baselines:
            messagebox.showwarning("提示", f"请先为第 {self.mark_page_index + 1} 页设置基准点！")
            return
        self.mark_mode = "marking"
        self.mark_canvas.config(cursor="crosshair")
        self.btn_m_start.config(state=tk.DISABLED)
        self.btn_m_finish.config(state=tk.NORMAL)
        self.btn_m_undo.config(state=tk.NORMAL)
        self.btn_m_clear.config(state=tk.NORMAL)
        self._mark_status(f"标记模式: 第 {self.mark_page_index + 1} 页 — 拖拽画出矩形区域")
    def _mark_undo(self):
        if self.markers:
            self.markers.pop()
            self._mark_render()
            self._mark_status(f"已撤销，当前共 {len(self.markers)} 个标记")
    def _mark_clear(self):
        self.markers.clear()
        self._mark_render()
        self._mark_status("已清空所有标记")
    def _mc_press(self, event):
        if not self.mark_doc:
            return
        cx = self.mark_canvas.canvasx(event.x)
        cy = self.mark_canvas.canvasy(event.y)
        if self.mark_mode == "set_baseline":
            pdf_x = cx / self.mark_sx
            pdf_y = cy / self.mark_sy
            self.mark_baselines[self.mark_page_index] = (pdf_x, pdf_y)
            self.mark_mode = "idle"
            self.mark_canvas.config(cursor="crosshair")
            self._mark_render()
            self.btn_m_start.config(state=tk.NORMAL)
            self._mark_status(f"第 {self.mark_page_index + 1} 页基准点已设置 ({pdf_x:.1f}, {pdf_y:.1f})")
        elif self.mark_mode == "marking":
            self.drag_start = (cx, cy)
            self.rubber_band = self.mark_canvas.create_rectangle(
                cx, cy, cx, cy, outline="#e74c3c", width=2, dash=(5, 3), tags="rubber"
            )
    def _mc_motion(self, event):
        if self.mark_mode != "marking" or self.drag_start is None:
            return
        cx = self.mark_canvas.canvasx(event.x)
        cy = self.mark_canvas.canvasy(event.y)
        self.mark_canvas.coords(self.rubber_band, *self.drag_start, cx, cy)
    def _mc_release(self, event):
        if self.mark_mode != "marking" or self.drag_start is None:
            return
        cx = self.mark_canvas.canvasx(event.x)
        cy = self.mark_canvas.canvasy(event.y)
        x0, y0 = self.drag_start
        x1, y1 = cx, cy
        self.mark_canvas.delete("rubber")
        self.rubber_band = None
        self.drag_start = None
        if abs(x1 - x0) < 6 or abs(y1 - y0) < 6:
            return
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        if self.mark_page_index not in self.mark_baselines:
            messagebox.showwarning("提示", f"第 {self.mark_page_index + 1} 页还没有基准点")
            return
        ax = x0 / self.mark_sx
        ay = y0 / self.mark_sy
        aw = (x1 - x0) / self.mark_sx
        ah = (y1 - y0) / self.mark_sy
        bx, by = self.mark_baselines[self.mark_page_index]
        self.markers.append({
            "id": len(self.markers) + 1,
            "page": self.mark_page_index,
            "x": round(ax - bx, 3),
            "y": round(ay - by, 3),
            "width": round(aw, 3),
            "height": round(ah, 3),
        })
        self._mark_render()
        self._mark_status(f"已添加标记 {len(self.markers)}")
    def _mark_render(self):
        if not self.mark_doc:
            self.mark_canvas.delete("all")
            self.lbl_mark_page.config(text=" — / — ")
            return
        page = self.mark_doc[self.mark_page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(self.mark_zoom, self.mark_zoom), alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.mark_photo = ImageTk.PhotoImage(img)
        pr = page.rect
        self.mark_sx = pix.width / pr.width
        self.mark_sy = pix.height / pr.height
        self.mark_canvas.config(scrollregion=(0, 0, pix.width, pix.height))
        self.mark_canvas.delete("all")
        self.mark_canvas.create_image(0, 0, anchor=tk.NW, image=self.mark_photo)
        self.lbl_mark_page.config(text=f" {self.mark_page_index + 1} / {len(self.mark_doc)} ")
        baseline = self.mark_baselines.get(self.mark_page_index)
        if baseline:
            bx, by = baseline[0] * self.mark_sx, baseline[1] * self.mark_sy
            r = 9
            self.mark_canvas.create_oval(bx - r, by - r, bx + r, by + r, outline="#f0b429", width=2, tags="base")
            self.mark_canvas.create_line(bx - r - 5, by, bx + r + 5, by, fill="#f0b429", width=2, tags="base")
            self.mark_canvas.create_line(bx, by - r - 5, bx, by + r + 5, fill="#f0b429", width=2, tags="base")
        bx_pdf, by_pdf = baseline if baseline else (0, 0)
        for m in self.markers:
            if m["page"] != self.mark_page_index:
                continue
            sx = (bx_pdf + m["x"]) * self.mark_sx
            sy = (by_pdf + m["y"]) * self.mark_sy
            sw = m["width"] * self.mark_sx
            sh = m["height"] * self.mark_sy
            self._draw_marker_on_canvas(self.mark_canvas, sx, sy, sw, sh, m["id"], "#e74c3c")
        self._update_mark_controls()
    def _update_mark_controls(self):
        if not self.mark_doc:
            self.btn_m_start.config(state=tk.DISABLED)
            self.btn_m_finish.config(state=tk.DISABLED)
            self.btn_m_undo.config(state=tk.DISABLED)
            self.btn_m_clear.config(state=tk.DISABLED)
            return
        has_baseline = self.mark_page_index in self.mark_baselines
        has_markers = len(self.markers) > 0
        if self.mark_mode == "marking":
            self.btn_m_start.config(state=tk.DISABLED)
            self.btn_m_finish.config(state=tk.NORMAL)
        else:
            self.btn_m_start.config(state=tk.NORMAL if has_baseline else tk.DISABLED)
            self.btn_m_finish.config(state=tk.DISABLED)
        self.btn_m_undo.config(state=tk.NORMAL if has_markers else tk.DISABLED)
        self.btn_m_clear.config(state=tk.NORMAL if has_markers else tk.DISABLED)
    def _mark_finish(self):
        if not self.markers:
            messagebox.showwarning("提示", "还没有任何标记！")
            return
        save_dir = filedialog.askdirectory(title="选择保存目录")
        if not save_dir:
            return
        base = os.path.splitext(os.path.basename(self.mark_pdf_path))[0]
        data = {
            "baselines": {str(k): {"x": round(v[0], 3), "y": round(v[1], 3)} for k, v in self.mark_baselines.items()},
            "markers": self.markers,
        }
        json_path = os.path.join(save_dir, f"{base}_markers.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        xlsx_path = os.path.join(save_dir, f"{base}_markers.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "标记信息"
        header = ["序号", "坐标信息 (相对基准点)", "内容（第3列）", "截图（第4列）"]
        ws.append(header)
        for cell in ws[1]:
            cell.font = Font(bold=True, name="Arial")
            cell.fill = PatternFill("solid", fgColor="D6EAF8")
            cell.alignment = Alignment(horizontal="center")
        for m in self.markers:
            coord = f"x={m['x']}, y={m['y']}, w={m['width']}, h={m['height']}, page={m['page'] + 1}"
            ws.append([m["id"], coord, "", ""])
        ws.column_dimensions["A"].width = 8
        ws.column_dimensions["B"].width = 52
        ws.column_dimensions["C"].width = 24
        ws.column_dimensions["D"].width = 28
        wb.save(xlsx_path)
        self.mark_mode = "idle"
        self.btn_m_start.config(state=tk.NORMAL if self.mark_page_index in self.mark_baselines else tk.DISABLED)
        self.btn_m_finish.config(state=tk.DISABLED)
        self._update_mark_controls()
        messagebox.showinfo("保存成功",
            f"{len(self.markers)} 个标记已保存:\n\nJSON: {json_path}\nExcel: {xlsx_path}")
        self._mark_status(f"已保存 {len(self.markers)} 个标记")
    def _mark_status(self, text):
        self.lbl_mark_status.config(text=text)
    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — APPLY
    # ══════════════════════════════════════════════════════════════════════
    def _setup_apply_tab(self):
        self.apply_pdf_path = None
        self.apply_json_path = None
        self.apply_xlsx_path = None
        self.apply_doc = None
        self.apply_markers = []
        self.apply_orig_baselines = {}
        self.apply_new_baselines = {}
        self.apply_excel_data = []
        self.apply_page_index = 0
        self.apply_zoom = 1.5
        self.apply_photo = None
        self.apply_sx = 1.0
        self.apply_sy = 1.0
        self.apply_mode = "idle"
        self._tmp_files = []
        self.apply_selected_id = None
        self.apply_font_sizes = {}
        # ── toolbar row 1: file selection ─────────────────────────────────
        r1 = ttk.Frame(self.apply_frame)
        r1.pack(fill=tk.X, padx=12, pady=(10, 3))
        ttk.Button(r1, text="选择 PDF", style="Primary.TButton",
                   command=self._apply_open_pdf).pack(side=tk.LEFT, padx=(0, 4))
        self.lbl_apply_pdf = ttk.Label(r1, text="未选择", style="Muted.TLabel")
        self.lbl_apply_pdf.pack(side=tk.LEFT, padx=4)
        ttk.Separator(r1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(r1, text="选择标记 JSON", style="Primary.TButton",
                   command=self._apply_open_json).pack(side=tk.LEFT, padx=3)
        self.lbl_apply_json = ttk.Label(r1, text="未选择", style="Muted.TLabel")
        self.lbl_apply_json.pack(side=tk.LEFT, padx=4)
        ttk.Separator(r1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(r1, text="选择 Excel (可选)",
                   command=self._apply_open_xlsx).pack(side=tk.LEFT, padx=3)
        self.lbl_apply_xlsx = ttk.Label(r1, text="未选择", style="Muted.TLabel")
        self.lbl_apply_xlsx.pack(side=tk.LEFT, padx=4)

        # ── toolbar row 2: actions ────────────────────────────────────────
        r2 = ttk.Frame(self.apply_frame)
        r2.pack(fill=tk.X, padx=12, pady=3)
        self.btn_a_baseline = ttk.Button(r2, text="设置基准点",
                   command=self._apply_enter_baseline_mode, state=tk.DISABLED)
        self.btn_a_baseline.pack(side=tk.LEFT, padx=(0, 4))
        self.lbl_a_baseline = ttk.Label(r2, text="未设置基准点", style="Muted.TLabel")
        self.lbl_a_baseline.pack(side=tk.LEFT, padx=6)
        ttk.Separator(r2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(r2, text="<", width=3, command=self._apply_prev_page).pack(side=tk.LEFT)
        self.lbl_apply_page = ttk.Label(r2, text=" — / — ")
        self.lbl_apply_page.pack(side=tk.LEFT, padx=2)
        ttk.Button(r2, text=">", width=3, command=self._apply_next_page).pack(side=tk.LEFT)
        ttk.Separator(r2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(r2, text="导出带标记 PDF", style="Accent.TButton",
                   command=self._apply_export_pdf).pack(side=tk.LEFT, padx=3)
        ttk.Button(r2, text="截图存入 Excel 第4列",
                   command=self._apply_screenshot_to_excel).pack(side=tk.LEFT, padx=3)
        self.lbl_apply_status = ttk.Label(r2, text="请选择 PDF 和标记 JSON",
                                           foreground=self.C_PRIMARY)
        self.lbl_apply_status.pack(side=tk.LEFT, padx=14)

        # ── main pane ─────────────────────────────────────────────────────
        main_pane = ttk.Panedwindow(self.apply_frame, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=12, pady=(3, 8))
        left = ttk.Frame(main_pane)
        right = ttk.Frame(main_pane, width=420)
        main_pane.add(left, weight=4)
        main_pane.add(right, weight=1)
        cf = ttk.Frame(left)
        cf.pack(fill=tk.BOTH, expand=True)
        self.apply_canvas = tk.Canvas(cf, bg=self.C_CANVAS, highlightthickness=0)
        self.apply_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(cf, orient=tk.VERTICAL, command=self.apply_canvas.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(left, orient=tk.HORIZONTAL, command=self.apply_canvas.xview)
        hsb.pack(fill=tk.X, pady=(0, 4))
        self.apply_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.apply_canvas.bind("<ButtonPress-1>", self._ac_press)
        # Right editor panel
        ttk.Label(right, text="第3列手动修正", style="Heading.TLabel").pack(anchor="w", pady=(0, 6))
        top_tools = ttk.Frame(right)
        top_tools.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(top_tools, text="刷新列表", command=self._refresh_apply_tree).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_tools, text="清空当前", command=self._apply_clear_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_tools, text="删除当前", command=self._apply_delete_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_tools, text="应用修改", command=self._apply_save_selected).pack(side=tk.LEFT, padx=2)
        tree_frame = ttk.Frame(right)
        tree_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 6))
        cols = ("id", "page", "preview")
        self.apply_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12, selectmode="browse")
        self.apply_tree.heading("id", text="序号")
        self.apply_tree.heading("page", text="页")
        self.apply_tree.heading("preview", text="第3列内容预览")
        self.apply_tree.column("id", width=50, anchor="center")
        self.apply_tree.column("page", width=45, anchor="center")
        self.apply_tree.column("preview", width=250, anchor="w")
        ysb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.apply_tree.yview)
        self.apply_tree.configure(yscrollcommand=ysb.set)
        self.apply_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)
        self.apply_tree.bind("<<TreeviewSelect>>", self._on_apply_tree_select)
        self.apply_tree.bind("<Button-1>", self._on_tree_click)
        edit_box = ttk.LabelFrame(right, text="内容编辑")
        edit_box.pack(fill=tk.BOTH, expand=True)
        self.apply_text = tk.Text(edit_box, height=7, wrap="word")
        self.apply_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        symbol_bar1 = ttk.Frame(edit_box)
        symbol_bar1.pack(fill=tk.X, padx=4, pady=(0, 4))
        symbol_bar2 = ttk.Frame(edit_box)
        symbol_bar2.pack(fill=tk.X, padx=4, pady=(0, 4))
        symbols = [
            ("空心圆", "○"), ("圈杠", "⊘"), ("空框", "☐"), ("勾框", "☑"),
            ("叉框", "☒"), ("打勾", "✓"), ("粗勾", "✔"), ("实心圆", "●"),
        ]
        for i, (name, sym) in enumerate(symbols):
            parent = symbol_bar1 if i < 4 else symbol_bar2
            ttk.Button(parent, text=name, width=8, command=lambda s=sym: self._insert_symbol(s)).pack(side=tk.LEFT, padx=2, pady=1)
        # ─── 字号调节（每条标记单独调节） ───
        font_frame = ttk.Frame(edit_box)
        font_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Label(font_frame, text="字号:").pack(side=tk.LEFT)
        self.apply_font_spin = ttk.Spinbox(font_frame, from_=4, to=72, width=6, command=self._apply_font_size_changed)
        self.apply_font_spin.pack(side=tk.LEFT, padx=2)
        ttk.Label(font_frame, text="pt").pack(side=tk.LEFT)
        bottom_tools = ttk.Frame(edit_box)
        bottom_tools.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(bottom_tools, text="← 载入到编辑框", command=self._load_selected_to_editor).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom_tools, text="保存到当前项", command=self._apply_save_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom_tools, text="上一项", command=self._select_prev_tree_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom_tools, text="下一项", command=self._select_next_tree_item).pack(side=tk.LEFT, padx=2)
    def _apply_open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF 文件", "*.pdf")])
        if not path:
            return
        self.apply_pdf_path = path
        self.apply_doc = fitz.open(path)
        self.apply_page_index = 0
        self.apply_new_baselines.clear()
        self.lbl_apply_pdf.config(text=os.path.basename(path), foreground="black")
        self._apply_refresh_baseline_btn()
        self._apply_render()
        self._apply_status("PDF 已加载")
    def _apply_open_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.apply_markers = data.get("markers", [])
        self.apply_orig_baselines = {}
        if "baselines" in data and isinstance(data["baselines"], dict):
            for k, v in data["baselines"].items():
                try:
                    self.apply_orig_baselines[int(k)] = (float(v["x"]), float(v["y"]))
                except Exception:
                    pass
        elif "baseline" in data:
            try:
                self.apply_orig_baselines[0] = (float(data["baseline"]["x"]), float(data["baseline"]["y"]))
            except Exception:
                pass
        self.apply_font_sizes = {}
        for m in self.apply_markers:
            mid = m.get("id")
            if mid is not None:
                self.apply_font_sizes[mid] = 12
        self.apply_json_path = path
        self.lbl_apply_json.config(text=os.path.basename(path), foreground="black")
        self._apply_refresh_baseline_btn()
        self._refresh_apply_tree()
        self._apply_render()
        self._apply_status(f"JSON 已加载, {len(self.apply_markers)} 个标记 — 可手动修正第3列内容")
    def _apply_open_xlsx(self):
        path = filedialog.askopenfilename(filetypes=[("Excel 文件", "*.xlsx *.xls")])
        if not path:
            return
        wb = openpyxl.load_workbook(path, data_only=False)
        ws = wb.active
        self.apply_excel_data = []
        for row in ws.iter_rows(min_row=2):
            cell = row[2] if len(row) >= 3 else None
            self.apply_excel_data.append(self._cell_display_text(cell) if cell else "")
        self.apply_xlsx_path = path
        self.lbl_apply_xlsx.config(text=os.path.basename(path), foreground="black")
        self._refresh_apply_tree()
        self._apply_render()
        self._apply_status(f"Excel 已加载，读取第3列 {len(self.apply_excel_data)} 行")
    def _apply_refresh_baseline_btn(self):
        if self.apply_doc and self.apply_markers:
            self.btn_a_baseline.config(state=tk.NORMAL)
        else:
            self.btn_a_baseline.config(state=tk.DISABLED)
    def _apply_enter_baseline_mode(self):
        if not self.apply_doc:
            return
        self.apply_mode = "set_baseline"
        self.apply_canvas.config(cursor="tcross")
        self._apply_status(f"基准点模式: 点击第 {self.apply_page_index + 1} 页对应的基准点位置")
    def _ac_press(self, event):
        if self.apply_mode != "set_baseline" or not self.apply_doc:
            return
        cx = self.apply_canvas.canvasx(event.x)
        cy = self.apply_canvas.canvasy(event.y)
        px = cx / self.apply_sx
        py = cy / self.apply_sy
        self.apply_new_baselines[self.apply_page_index] = (px, py)
        self.apply_mode = "idle"
        self.apply_canvas.config(cursor="arrow")
        self._apply_render()
        self._apply_status(f"第 {self.apply_page_index + 1} 页基准点已设置, 标记已对齐")
    def _marker_abs_pdf(self, m):
        pidx = m["page"]
        if pidx in self.apply_new_baselines:
            nx, ny = self.apply_new_baselines[pidx]
        elif pidx in self.apply_orig_baselines:
            nx, ny = self.apply_orig_baselines[pidx]
        else:
            nx, ny = 0, 0
        return nx + m["x"], ny + m["y"]
    @classmethod
    def _font_candidates(cls):
        candidates = []
        if UNICODE_FONT_PATH:
            candidates.append(UNICODE_FONT_PATH)
        system = platform.system()
        if system == "Windows":
            candidates.extend([
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/seguisym.ttf",
                "C:/Windows/Fonts/segoeuisym.ttf",
                "C:/Windows/Fonts/seguiemj.ttf",
                "C:/Windows/Fonts/cambria.ttc",
                "C:/Windows/Fonts/arialuni.ttf",
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/calibri.ttf",
            ])
        elif system == "Darwin":
            candidates.extend([
                "/System/Library/Fonts/Apple Color Emoji.ttc",
                "/System/Library/Fonts/Apple Symbols.ttf",
                "/Library/Fonts/Arial Unicode MS.ttf",
                "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ])
        else:
            candidates.extend([
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansMath-Regular.ttf",
                "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/stix/STIXGeneral.ttf",
            ])
        seen, out = set(), []
        for p in candidates:
            if p and p not in seen and os.path.exists(p):
                seen.add(p)
                out.append(p)
        return out
    @classmethod
    def _font_pool(cls, size):
        pool = {"regular": [], "cjk": [], "symbol": [], "emoji": []}
        for p in cls._font_candidates():
            try:
                f = ImageFont.truetype(p, size=size)
            except Exception:
                continue
            name = os.path.basename(p).lower()
            if "emoji" in name:
                pool["emoji"].append(f)
            elif any(x in name for x in ("sym", "symbol", "math", "stix", "cambria")):
                pool["symbol"].append(f)
            elif any(x in name for x in ("cjk", "msyh", "simhei", "wqy", "noto")):
                pool["cjk"].append(f)
            else:
                pool["regular"].append(f)
        for key in pool:
            if not pool[key]:
                pool[key] = [ImageFont.load_default()]
        return pool
    @staticmethod
    def _font_support_category(ch):
        cp = ord(ch)
        cat = unicodedata.category(ch)
        if ch in "\n\r\t":
            return "regular"
        if 0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF:
            return "emoji"
        if 0x2500 <= cp <= 0x259F or 0x2190 <= cp <= 0x22FF or 0x2300 <= cp <= 0x23FF:
            return "symbol"
        if 0x2000 <= cp <= 0x206F or 0x2070 <= cp <= 0x209F or 0x2100 <= cp <= 0x214F:
            return "symbol"
        if 0x3000 <= cp <= 0x303F or 0x3040 <= cp <= 0x30FF or 0x3400 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF:
            return "cjk"
        if cat in {"So", "Sm", "Sk"}:
            return "symbol"
        return "regular"
    @classmethod
    def _pick_font_for_char(cls, pool, ch):
        key = cls._font_support_category(ch)
        for f in pool.get(key, []):
            return f
        for key2 in ("regular", "cjk", "symbol", "emoji"):
            if pool.get(key2):
                return pool[key2][0]
        return ImageFont.load_default()
    @staticmethod
    def _cell_display_text(cell):
        if cell is None or cell.value is None:
            return ""
        v = cell.value
        if isinstance(v, (datetime, date)):
            try:
                if isinstance(v, datetime):
                    if v.hour == 0 and v.minute == 0 and v.second == 0 and v.microsecond == 0:
                        return v.strftime("%Y-%m-%d")
                    return v.strftime("%Y-%m-%d %H:%M:%S")
                return v.strftime("%Y-%m-%d")
            except Exception:
                return str(v)
        try:
            if isinstance(v, float) and v.is_integer():
                return str(int(v))
        except Exception:
            pass
        return str(v)
    @classmethod
    def _wrap_text(cls, draw, text, pool, max_width):
        text = "" if text is None else str(text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = []
        for paragraph in text.split("\n"):
            if paragraph == "":
                lines.append("")
                continue
            cur = ""
            cur_w = 0
            for ch in paragraph:
                font = cls._pick_font_for_char(pool, ch)
                ch_text = " " if ch == "\t" else ch
                bbox = draw.textbbox((0, 0), ch_text, font=font)
                ch_w = bbox[2] - bbox[0]
                if cur and cur_w + ch_w > max_width:
                    lines.append(cur)
                    cur = ch
                    cur_w = ch_w
                else:
                    cur += ch
                    cur_w += ch_w
            if cur:
                lines.append(cur)
        return lines
    @classmethod
    def _draw_text_line(cls, draw, x, y, line, pool, max_width, fg):
        cx = x
        for ch in line:
            font = cls._pick_font_for_char(pool, ch)
            ch_text = " " if ch == "\t" else ch
            bbox = draw.textbbox((0, 0), ch_text, font=font)
            ch_w = bbox[2] - bbox[0]
            if ch != "\r":
                draw.text((cx, y), ch_text, font=font, fill=fg)
            cx += ch_w
            if cx - x > max_width + 50:
                break
    @classmethod
    def _make_text_image(cls, text, box_w, box_h, bg=(214, 234, 248, 255), fg=(26, 37, 47, 255), fixed_font_size=None):
        box_w = max(12, int(box_w))
        box_h = max(12, int(box_h))
        padding = 4
        max_text_w = max(4, box_w - padding * 2)
        max_text_h = max(4, box_h - padding * 2)
        probe = Image.new("RGBA", (max(20, box_w), max(20, box_h)), (0, 0, 0, 0))
        draw = ImageDraw.Draw(probe)
        if fixed_font_size is not None:
            size = max(4, int(fixed_font_size))
            pool = cls._font_pool(size)
            lines = cls._wrap_text(draw, text, pool, max_text_w)
            metrics = []
            max_line_w = 0
            total_h = 0
            line_gap = max(1, size // 5)
            for ln in lines:
                if ln == "":
                    bbox = draw.textbbox((0, 0), "A", font=cls._pick_font_for_char(pool, "A"))
                    lw = 0
                    lh = bbox[3] - bbox[1]
                else:
                    temp_w = 0
                    temp_h = 0
                    for ch in ln:
                        font = cls._pick_font_for_char(pool, ch)
                        ch_text = " " if ch == "\t" else ch
                        bbox = draw.textbbox((0, 0), ch_text, font=font)
                        temp_w += bbox[2] - bbox[0]
                        temp_h = max(temp_h, bbox[3] - bbox[1])
                    lw = temp_w
                    lh = max(temp_h, size)
                metrics.append((lw, lh))
                max_line_w = max(max_line_w, lw)
                total_h += lh
            total_h += line_gap * max(0, len(lines) - 1)
            img = Image.new("RGBA", (box_w, box_h), bg)
            d = ImageDraw.Draw(img)
            y = max(0, (box_h - total_h) // 2)
            for ln, (lw, lh) in zip(lines, metrics):
                x = padding if lw >= max_text_w else max(0, (box_w - lw) // 2)
                cls._draw_text_line(d, x, y, ln, pool, max_text_w, fg)
                y += lh + line_gap
            return img
        for size in range(min(24, max(8, box_h // 2)), 5, -1):
            pool = cls._font_pool(size)
            lines = cls._wrap_text(draw, text, pool, max_text_w)
            metrics = []
            max_line_w = 0
            total_h = 0
            line_gap = max(1, size // 5)
            for ln in lines:
                if ln == "":
                    bbox = draw.textbbox((0, 0), "A", font=cls._pick_font_for_char(pool, "A"))
                    lw = 0
                    lh = bbox[3] - bbox[1]
                else:
                    temp_w = 0
                    temp_h = 0
                    for ch in ln:
                        font = cls._pick_font_for_char(pool, ch)
                        ch_text = " " if ch == "\t" else ch
                        bbox = draw.textbbox((0, 0), ch_text, font=font)
                        temp_w += bbox[2] - bbox[0]
                        temp_h = max(temp_h, bbox[3] - bbox[1])
                    lw = temp_w
                    lh = max(temp_h, size)
                metrics.append((lw, lh))
                max_line_w = max(max_line_w, lw)
                total_h += lh
            total_h += line_gap * max(0, len(lines) - 1)
            if max_line_w <= max_text_w and total_h <= max_text_h:
                img = Image.new("RGBA", (box_w, box_h), bg)
                d = ImageDraw.Draw(img)
                y = (box_h - total_h) // 2
                for ln, (lw, lh) in zip(lines, metrics):
                    x = padding if lw >= max_text_w else max(0, (box_w - lw) // 2)
                    cls._draw_text_line(d, x, y, ln, pool, max_text_w, fg)
                    y += lh + line_gap
                return img
        size = 6
        pool = cls._font_pool(size)
        img = Image.new("RGBA", (box_w, box_h), bg)
        d = ImageDraw.Draw(img)
        lines = cls._wrap_text(d, text, pool, max_text_w)
        y = padding
        for ln in lines:
            line_h = 0
            for ch in ln:
                font = cls._pick_font_for_char(pool, ch)
                ch_text = " " if ch == "\t" else ch
                bbox = d.textbbox((0, 0), ch_text, font=font)
                line_h = max(line_h, bbox[3] - bbox[1])
            if y + line_h > box_h - padding:
                break
            cls._draw_text_line(d, padding, y, ln, pool, max_text_w, fg)
            y += line_h + 1
        return img
    def _compose_page_image(self, page_index, zoom=None):
        if not self.apply_doc:
            return None, 1.0, 1.0
        z = self.apply_zoom if zoom is None else zoom
        page = self.apply_doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
        base = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")
        pr = page.rect
        sx = pix.width / pr.width
        sy = pix.height / pr.height
        draw = ImageDraw.Draw(base, "RGBA")
        baseline = self.apply_new_baselines.get(page_index) or self.apply_orig_baselines.get(page_index)
        if baseline:
            bx = baseline[0] * sx
            by = baseline[1] * sy
            r = 9
            draw.ellipse((bx - r, by - r, bx + r, by + r), outline=(240, 180, 41, 255), width=2)
            draw.line((bx - r - 5, by, bx + r + 5, by), fill=(240, 180, 41, 255), width=2)
            draw.line((bx, by - r - 5, bx, by + r + 5), fill=(240, 180, 41, 255), width=2)
        badge_font = self._load_font(9)
        for m in self.apply_markers:
            if m.get("page") != page_index:
                continue
            ax, ay = self._marker_abs_pdf(m)
            x = int(round(ax * sx))
            y = int(round(ay * sy))
            w = max(1, int(round(m["width"] * sx)))
            h = max(1, int(round(m["height"] * sy)))
            mid = m["id"]
            draw.rectangle((x, y, x + w, y + h), outline=(41, 128, 185, 255), width=2)
            badge_w = max(22, len(str(mid)) * 7 + 6)
            draw.rectangle((x, y - 18, x + badge_w, y), fill=(41, 128, 185, 255), outline=(41, 128, 185, 255))
            if badge_font:
                tb = draw.textbbox((0, 0), str(mid), font=badge_font)
                tw = tb[2] - tb[0]
                th = tb[3] - tb[1]
                draw.text((x + (badge_w - tw) / 2, y - 18 + (18 - th) / 2 - tb[1]), str(mid), font=badge_font, fill=(255, 255, 255, 255))
            else:
                draw.text((x + 4, y - 16), str(mid), fill=(255, 255, 255, 255))
            idx = mid - 1
            if self.apply_excel_data and 0 <= idx < len(self.apply_excel_data):
                text = self.apply_excel_data[idx]
                if text:
                    font_size = self.apply_font_sizes.get(mid, 12)
                    txt_img = self._make_text_image(text, max(12, w - 2), max(12, h - 2), fixed_font_size=font_size)
                    base.alpha_composite(txt_img, (x + 1, y + 1))
        return base.convert("RGB"), sx, sy
    @classmethod
    def _load_font(cls, size):
        for p in cls._font_candidates():
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue
        try:
            return ImageFont.load_default()
        except Exception:
            return None
    def _refresh_apply_tree(self):
        if not hasattr(self, "apply_tree"):
            return
        for item in self.apply_tree.get_children():
            self.apply_tree.delete(item)
        if not self.apply_markers:
            return
        markers_sorted = sorted(self.apply_markers, key=lambda x: x.get("id", 0))
        for m in markers_sorted:
            mid = m.get("id", 0)
            idx = mid - 1
            content = self.apply_excel_data[idx] if 0 <= idx < len(self.apply_excel_data) else ""
            preview = content.replace("\n", " ⏎ ").strip()
            if len(preview) > 40:
                preview = preview[:40] + "…"
            self.apply_tree.insert("", "end", iid=str(mid), values=(mid, m.get("page", 0) + 1, preview))
        self._sync_tree_selection_after_refresh()
    def _sync_tree_selection_after_refresh(self):
        if self.apply_selected_id and self.apply_tree.exists(str(self.apply_selected_id)):
            self.apply_tree.selection_set(str(self.apply_selected_id))
            self.apply_tree.see(str(self.apply_selected_id))
    def _on_apply_tree_select(self, event=None):
        sel = self.apply_tree.selection()
        if not sel:
            return
        try:
            self.apply_selected_id = int(sel[0])
        except Exception:
            self.apply_selected_id = None
            return
        self._load_selected_to_editor()
    def _load_selected_to_editor(self):
        if self.apply_selected_id is None:
            sel = self.apply_tree.selection()
            if not sel:
                return
            self.apply_selected_id = int(sel[0])
        idx = self.apply_selected_id - 1
        text = self.apply_excel_data[idx] if 0 <= idx < len(self.apply_excel_data) else ""
        self.apply_text.delete("1.0", tk.END)
        self.apply_text.insert("1.0", text)
        fsize = self.apply_font_sizes.get(self.apply_selected_id, 12)
        self.apply_font_spin.set(fsize)
    def _insert_symbol(self, sym):
        try:
            self.apply_text.insert(tk.INSERT, sym)
        except Exception:
            pass
    def _selected_tree_id(self):
        sel = self.apply_tree.selection()
        if sel:
            try:
                return int(sel[0])
            except Exception:
                return None
        return self.apply_selected_id
    def _apply_save_selected(self):
        mid = self._selected_tree_id()
        if not mid:
            messagebox.showwarning("提示", "请先在右侧列表中选中一个标记")
            return
        content = self.apply_text.get("1.0", tk.END).rstrip("\n")
        idx = mid - 1
        while len(self.apply_excel_data) <= idx:
            self.apply_excel_data.append("")
        self.apply_excel_data[idx] = content
        try:
            fsize = int(self.apply_font_spin.get())
            self.apply_font_sizes[mid] = fsize
        except:
            pass
        self.apply_selected_id = mid
        self._refresh_apply_tree()
        self._apply_render()
        self._apply_status(f"已更新第 {mid} 项内容")
    def _apply_clear_selected(self):
        self.apply_text.delete("1.0", tk.END)
    def _apply_delete_selected(self):
        mid = self._selected_tree_id()
        if not mid:
            return
        if messagebox.askyesno("确认", f"确定清空第 {mid} 项内容吗？"):
            idx = mid - 1
            while len(self.apply_excel_data) <= idx:
                self.apply_excel_data.append("")
            self.apply_excel_data[idx] = ""
            self.apply_text.delete("1.0", tk.END)
            self._refresh_apply_tree()
            self._apply_render()
            self._apply_status(f"已清空第 {mid} 项内容")
    def _select_prev_tree_item(self):
        items = self.apply_tree.get_children()
        if not items:
            return
        cur = self.apply_selected_id
        if cur is None:
            self.apply_tree.selection_set(items[0])
            self.apply_tree.see(items[0])
            self._on_apply_tree_select()
            return
        ids = [int(i) for i in items]
        if cur in ids:
            pos = ids.index(cur)
            pos = max(0, pos - 1)
            iid = str(ids[pos])
            self.apply_tree.selection_set(iid)
            self.apply_tree.see(iid)
            self._on_apply_tree_select()
    def _select_next_tree_item(self):
        items = self.apply_tree.get_children()
        if not items:
            return
        cur = self.apply_selected_id
        ids = [int(i) for i in items]
        if cur is None:
            self.apply_tree.selection_set(items[0])
            self.apply_tree.see(items[0])
            self._on_apply_tree_select()
            return
        if cur in ids:
            pos = ids.index(cur)
            pos = min(len(ids) - 1, pos + 1)
            iid = str(ids[pos])
            self.apply_tree.selection_set(iid)
            self.apply_tree.see(iid)
            self._on_apply_tree_select()
    def _apply_font_size_changed(self):
        if self.apply_selected_id is None:
            return
        mid = self.apply_selected_id
        try:
            fsize = int(self.apply_font_spin.get())
            self.apply_font_sizes[mid] = fsize
            self._apply_render()
            self._apply_status(f"已更新第 {mid} 项字号为 {fsize} pt")
        except ValueError:
            pass
    def _on_tree_click(self, event):
        col = self.apply_tree.identify_column(event.x)
        if col == "#1":  # 序号列
            item = self.apply_tree.identify_row(event.y)
            if item:
                try:
                    mid = int(item)
                    for m in self.apply_markers:
                        if m.get("id") == mid:
                            page = m.get("page", 0)
                            if self.apply_page_index != page:
                                self.apply_page_index = page
                                self.apply_mode = "idle"
                                self.apply_canvas.config(cursor="arrow")
                                self._apply_render()
                            self.apply_tree.selection_set(item)
                            self.apply_tree.see(item)
                            self._on_apply_tree_select()
                            break
                except Exception:
                    pass
    def _apply_render(self):
        if not self.apply_doc:
            self.apply_canvas.delete("all")
            self.lbl_apply_page.config(text=" — / — ")
            self.lbl_a_baseline.config(text="未设置基准点", foreground=self.C_MUTED)
            return
        composed, sx, sy = self._compose_page_image(self.apply_page_index, zoom=self.apply_zoom)
        if composed is None:
            return
        self.apply_sx = sx
        self.apply_sy = sy
        self.apply_photo = ImageTk.PhotoImage(composed)
        w, h = composed.size
        self.apply_canvas.config(scrollregion=(0, 0, w, h))
        self.apply_canvas.delete("all")
        self.apply_canvas.create_image(0, 0, anchor=tk.NW, image=self.apply_photo)
        self.lbl_apply_page.config(text=f" {self.apply_page_index + 1} / {len(self.apply_doc)} ")
        baseline = self.apply_new_baselines.get(self.apply_page_index) or self.apply_orig_baselines.get(self.apply_page_index)
        if baseline:
            self.lbl_a_baseline.config(text=f"当前页基准点: ({baseline[0]:.1f}, {baseline[1]:.1f})", foreground=self.C_TEXT)
        else:
            self.lbl_a_baseline.config(text="未设置基准点", foreground=self.C_MUTED)
        self._refresh_apply_tree()
    def _apply_prev_page(self):
        if self.apply_doc and self.apply_page_index > 0:
            self.apply_page_index -= 1
            self.apply_mode = "idle"
            self.apply_canvas.config(cursor="arrow")
            self._apply_render()
    def _apply_next_page(self):
        if self.apply_doc and self.apply_page_index < len(self.apply_doc) - 1:
            self.apply_page_index += 1
            self.apply_mode = "idle"
            self.apply_canvas.config(cursor="arrow")
            self._apply_render()
    def _apply_status(self, text):
        self.lbl_apply_status.config(text=text)
    def _apply_export_pdf(self):
        if not self.apply_doc or not self.apply_markers:
            messagebox.showwarning("提示", "请先加载 PDF 和 JSON")
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF 文件", "*.pdf")])
        if not save_path:
            return
        out = fitz.open()
        for pidx in range(len(self.apply_doc)):
            composed, _, _ = self._compose_page_image(pidx, zoom=self.apply_zoom)
            if composed is None:
                continue
            buf = io.BytesIO()
            composed.save(buf, format="PNG")
            page = out.new_page(width=composed.width, height=composed.height)
            page.insert_image(page.rect, stream=buf.getvalue(), keep_proportion=False, overlay=True)
        out.save(save_path)
        out.close()
        messagebox.showinfo("导出成功", f"带标记 PDF 已保存：\n{save_path}")
    def _apply_screenshot_to_excel(self):
        if not self.apply_doc or not self.apply_markers:
            messagebox.showwarning("提示", "请先加载 PDF 和 JSON")
            return
        xlsx_src = filedialog.askopenfilename(title="选择要更新的 Excel 文件", filetypes=[("Excel 文件", "*.xlsx")])
        if not xlsx_src:
            return
        wb = openpyxl.load_workbook(xlsx_src)
        ws = wb.active
        ZOOM = 3.0
        page_imgs = {}
        for m in self.apply_markers:
            pidx = m["page"]
            if pidx not in page_imgs:
                composed, sx, sy = self._compose_page_image(pidx, zoom=ZOOM)
                page_imgs[pidx] = (composed, sx, sy)
        for m in self.apply_markers:
            pidx = m["page"]
            img, sx, sy = page_imgs[pidx]
            ax, ay = self._marker_abs_pdf(m)
            x0 = max(0, int(ax * sx))
            y0 = max(0, int(ay * sy))
            x1 = min(img.width, int((ax + m["width"]) * sx))
            y1 = min(img.height, int((ay + m["height"]) * sy))
            if x1 <= x0 or y1 <= y0:
                continue
            cropped = img.crop((x0, y0, x1, y1))
            draw = ImageDraw.Draw(cropped)
            draw.rectangle([0, 0, cropped.width - 1, cropped.height - 1], outline=(41, 128, 185), width=3)
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp_path = tmp.name
            tmp.close()
            cropped.save(tmp_path, format="PNG")
            self._tmp_files.append(tmp_path)
            row_num = m["id"] + 1
            while ws.max_row < row_num:
                ws.append(["", "", "", ""])
            xl_img = XLImage(tmp_path)
            orig_w, orig_h = cropped.size
            target_h = 80
            scale = min(target_h / orig_h, 240 / orig_w)
            xl_img.width = int(orig_w * scale)
            xl_img.height = int(orig_h * scale)
            xl_img.anchor = f"D{row_num}"
            ws.add_image(xl_img)
            ws.row_dimensions[row_num].height = xl_img.height * 0.75 + 4
        ws.column_dimensions["D"].width = 34
        save_path = filedialog.asksaveasfilename(title="保存更新后的 Excel", defaultextension=".xlsx", filetypes=[("Excel 文件", "*.xlsx")], initialfile=os.path.basename(xlsx_src))
        if save_path:
            wb.save(save_path)
            messagebox.showinfo("完成", f"截图已写入 Excel 第4列：\n{save_path}")
        for p in self._tmp_files:
            try:
                os.unlink(p)
            except Exception:
                pass
        self._tmp_files.clear()
    @staticmethod
    def _draw_marker_on_canvas(canvas, sx, sy, sw, sh, mid, color):
        canvas.create_rectangle(sx, sy, sx + sw, sy + sh, outline=color, width=2, tags="marker")
        badge_w = max(22, len(str(mid)) * 7 + 6)
        canvas.create_rectangle(sx, sy - 18, sx + badge_w, sy, fill=color, outline=color, tags="marker")
        canvas.create_text(sx + badge_w / 2, sy - 9, text=str(mid), fill="white", font=("Arial", 9, "bold"), tags="marker")
    def __del__(self):
        for p in getattr(self, "_tmp_files", []):
            try:
                os.unlink(p)
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — VERIFY EXCEL
    # ══════════════════════════════════════════════════════════════════════
    def _setup_verify_tab(self):
        self.verify_pdf_path = None
        self.verify_doc = None
        self.verify_json_path = None
        self.verify_markers = []
        self.verify_orig_baselines = {}
        self.verify_new_baselines = {}
        self.verify_xlsx_path = None
        self.verify_excel_rows = []    # list of list-of-str, data rows (header skipped)
        self.verify_images = {}        # {mid (1-based): PIL.Image} — col 4 screenshots
        self.verify_results = {}       # {mid: 'correct'|'incorrect'|None}
        self.verify_page_index = 0
        self.verify_zoom = 1.5
        self.verify_sx = 1.0
        self.verify_sy = 1.0
        self.verify_selected_id = None
        self.verify_mode = "idle"
        self.verify_pdf_window = None  # Toplevel reference
        self.verify_canvas = None      # Canvas inside Toplevel
        self.verify_pdf_photo = None
        self.verify_col4_photo = None  # PhotoImage kept to prevent GC
        self._current_verify_col4_mid = None

        # ── Row 1: file selection ─────────────────────────────────────────
        r1 = ttk.Frame(self.verify_frame)
        r1.pack(fill=tk.X, padx=12, pady=(10, 3))
        ttk.Button(r1, text="选择 Excel", style="Primary.TButton",
                   command=self._verify_open_xlsx).pack(side=tk.LEFT, padx=(0, 4))
        self.lbl_verify_xlsx = ttk.Label(r1, text="未选择", style="Muted.TLabel")
        self.lbl_verify_xlsx.pack(side=tk.LEFT, padx=4)
        ttk.Separator(r1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(r1, text="选择 PDF", style="Primary.TButton",
                   command=self._verify_open_pdf).pack(side=tk.LEFT, padx=3)
        self.lbl_verify_pdf = ttk.Label(r1, text="未选择", style="Muted.TLabel")
        self.lbl_verify_pdf.pack(side=tk.LEFT, padx=4)
        ttk.Separator(r1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(r1, text="选择标记 JSON", style="Primary.TButton",
                   command=self._verify_open_json).pack(side=tk.LEFT, padx=3)
        self.lbl_verify_json = ttk.Label(r1, text="未选择", style="Muted.TLabel")
        self.lbl_verify_json.pack(side=tk.LEFT, padx=4)
        ttk.Separator(r1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(r1, text="打开 PDF 预览",
                   command=self._open_verify_pdf_window).pack(side=tk.LEFT, padx=3)

        # ── Row 2: status bar ─────────────────────────────────────────────
        self.lbl_verify_status = ttk.Label(self.verify_frame, text="请先选择 Excel 文件",
                                            style="Status.TLabel")
        self.lbl_verify_status.pack(fill=tk.X, padx=12, pady=(0, 4))

        # ── Main area: vertical split ─────────────────────────────────────
        main_v = ttk.PanedWindow(self.verify_frame, orient=tk.VERTICAL)
        main_v.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        list_frame = ttk.Frame(main_v)
        main_v.add(list_frame, weight=1)

        tree_hdr = ttk.Frame(list_frame)
        tree_hdr.pack(fill=tk.X, pady=(2, 4))
        ttk.Label(tree_hdr, text="核对列表", style="Heading.TLabel").pack(side=tk.LEFT)
        ttk.Label(tree_hdr, text="  点击行: 展开第3/4列对比;  已打开预览时自动定位到标记",
                  style="Muted.TLabel").pack(side=tk.LEFT, padx=8)

        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "preview", "status")
        self.verify_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                         selectmode="browse", height=8)
        self.verify_tree.heading("id",      text="序号")
        self.verify_tree.heading("preview", text="内容预览（第3列）")
        self.verify_tree.heading("status",  text="状态")
        self.verify_tree.column("id",      width=46,  anchor="center", stretch=False)
        self.verify_tree.column("preview", width=500, anchor="w")
        self.verify_tree.column("status",  width=80,  anchor="center", stretch=False)

        ysb_vt = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.verify_tree.yview)
        self.verify_tree.configure(yscrollcommand=ysb_vt.set)
        self.verify_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb_vt.pack(side=tk.RIGHT, fill=tk.Y)

        self.verify_tree.tag_configure("correct",   background=self.C_TREE_OK, foreground=self.C_ACCENT)
        self.verify_tree.tag_configure("incorrect", background=self.C_TREE_NG, foreground=self.C_DANGER)
        self.verify_tree.tag_configure("normal",    background=self.C_CARD,    foreground=self.C_TEXT)
        self.verify_tree.bind("<<TreeviewSelect>>", self._on_verify_tree_select)

        # Bottom: comparison panel (col3 text vs col4 image)
        cmp_outer = ttk.LabelFrame(main_v, text="当前行核对 (第3列文字 vs 第4列截图)")
        main_v.add(cmp_outer, weight=2)

        act_bar = ttk.Frame(cmp_outer)
        act_bar.pack(fill=tk.X, padx=8, pady=(6, 3))
        self.lbl_verify_row = ttk.Label(act_bar, text="未选择行", style="Heading.TLabel")
        self.lbl_verify_row.pack(side=tk.LEFT)
        ttk.Button(act_bar, text="< 上一行",
                   command=self._verify_prev_row).pack(side=tk.RIGHT, padx=3)
        ttk.Button(act_bar, text="下一行 >",
                   command=self._verify_next_row).pack(side=tk.RIGHT, padx=3)
        ttk.Separator(act_bar, orient=tk.VERTICAL).pack(side=tk.RIGHT, fill=tk.Y, padx=8)
        ttk.Button(act_bar, text="标记错误", style="Danger.TButton",
                   command=lambda: self._verify_set_result("incorrect")).pack(side=tk.RIGHT, padx=4)
        ttk.Button(act_bar, text="标记正确", style="Accent.TButton",
                   command=lambda: self._verify_set_result("correct")).pack(side=tk.RIGHT, padx=4)

        sides = ttk.Frame(cmp_outer)
        sides.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 8))
        sides.columnconfigure(0, weight=1)
        sides.columnconfigure(1, weight=1)
        sides.rowconfigure(0, weight=1)

        col3_frame = ttk.LabelFrame(sides, text="第3列 - 文字内容")
        col3_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.verify_col3_text = tk.Text(col3_frame, wrap="word", state="disabled",
                                         bg=self.C_CARD, font=(_FF, 13),
                                         relief="flat", padx=8, pady=6)
        col3_sb = ttk.Scrollbar(col3_frame, orient=tk.VERTICAL,
                                 command=self.verify_col3_text.yview)
        self.verify_col3_text.configure(yscrollcommand=col3_sb.set)
        self.verify_col3_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        col3_sb.pack(side=tk.RIGHT, fill=tk.Y)

        col4_frame = ttk.LabelFrame(sides, text="第4列 - 截图")
        col4_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.verify_col4_canvas = tk.Canvas(col4_frame, bg="#f1f5f9", highlightthickness=0)
        self.verify_col4_canvas.pack(fill=tk.BOTH, expand=True)
        self.verify_col4_canvas.bind("<Configure>", self._on_verify_col4_resize)

    # ── file loaders ──────────────────────────────────────────────────────
    def _verify_open_xlsx(self):
        path = filedialog.askopenfilename(filetypes=[("Excel 文件", "*.xlsx *.xls")])
        if not path:
            return
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        self.verify_excel_rows = []
        for row in ws.iter_rows(min_row=2):          # skip header row
            row_data = [self._cell_display_text(cell) for cell in row]
            self.verify_excel_rows.append(row_data)
        self.verify_images  = self._extract_excel_images(ws)
        self.verify_results = {}
        self.verify_xlsx_path = path
        self.lbl_verify_xlsx.config(text=os.path.basename(path), foreground="black")
        self._refresh_verify_tree()
        self._verify_status(
            f"Excel 已加载，{len(self.verify_excel_rows)} 行数据，{len(self.verify_images)} 张截图"
        )

    @staticmethod
    def _extract_excel_images(ws):
        """Return {mid: PIL.Image} for column-4 screenshot images embedded in the worksheet.

        openpyxl stores images in ws._images.  Each image's anchor._from.row is
        0-based, so row 0 = header row (Excel row 1), row 1 = first data row
        (Excel row 2) = marker 1, etc.
        """
        result = {}
        for ximg in getattr(ws, '_images', []):
            try:
                anchor  = ximg.anchor
                row0    = None
                if hasattr(anchor, '_from'):
                    row0 = anchor._from.row        # 0-based Excel row
                elif hasattr(anchor, 'row'):
                    row0 = anchor.row
                if row0 is None or row0 < 1:       # skip header (row0 == 0)
                    continue
                mid = row0                         # row0=1 → marker 1
                raw = ximg._data()
                pil = Image.open(io.BytesIO(raw)).convert("RGBA")
                result[mid] = pil
            except Exception:
                pass
        return result

    def _verify_open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF 文件", "*.pdf")])
        if not path:
            return
        self.verify_pdf_path = path
        self.verify_doc = fitz.open(path)
        self.verify_page_index = 0
        self.verify_new_baselines.clear()
        self.lbl_verify_pdf.config(text=os.path.basename(path), foreground="black")
        if self.verify_pdf_window and self.verify_pdf_window.winfo_exists():
            self._verify_render()
        self._verify_status("PDF 已加载")

    def _verify_open_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.verify_markers = data.get("markers", [])
        self.verify_orig_baselines = {}
        if "baselines" in data and isinstance(data["baselines"], dict):
            for k, v in data["baselines"].items():
                try:
                    self.verify_orig_baselines[int(k)] = (float(v["x"]), float(v["y"]))
                except Exception:
                    pass
        elif "baseline" in data:
            try:
                self.verify_orig_baselines[0] = (float(data["baseline"]["x"]),
                                                  float(data["baseline"]["y"]))
            except Exception:
                pass
        self.verify_json_path = path
        self.lbl_verify_json.config(text=os.path.basename(path), foreground="black")
        if self.verify_pdf_window and self.verify_pdf_window.winfo_exists():
            self._verify_render()
        self._verify_status(f"JSON 已加载，{len(self.verify_markers)} 个标记")

    # ── standalone PDF preview window ─────────────────────────────────────
    def _open_verify_pdf_window(self):
        if self.verify_pdf_window and self.verify_pdf_window.winfo_exists():
            self.verify_pdf_window.lift()
            self.verify_pdf_window.focus_force()
            return
        win = tk.Toplevel(self.root)
        win.title("PDF 预览 — 核对结果")
        win.geometry("960x760")
        win.configure(bg=self.C_BG)
        win.protocol("WM_DELETE_WINDOW", self._on_verify_pdf_window_close)
        self.verify_pdf_window = win

        tb = ttk.Frame(win)
        tb.pack(fill=tk.X, padx=10, pady=(8, 4))
        ttk.Button(tb, text="设置基准点",
                   command=self._verify_enter_baseline_mode).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(tb, text="<", width=3, command=self._verify_prev_page).pack(side=tk.LEFT)
        self.lbl_verify_page = ttk.Label(tb, text=" — / — ")
        self.lbl_verify_page.pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text=">", width=3, command=self._verify_next_page).pack(side=tk.LEFT)
        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(tb, text="放大", command=self._verify_zoom_in).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="缩小", command=self._verify_zoom_out).pack(side=tk.LEFT, padx=2)
        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(tb, text="导出核对结果 PDF", style="Accent.TButton",
                   command=self._verify_export_pdf).pack(side=tk.LEFT, padx=3)

        cf = ttk.Frame(win)
        cf.pack(fill=tk.BOTH, expand=True, padx=10)
        self.verify_canvas = tk.Canvas(cf, bg=self.C_CANVAS, highlightthickness=0,
                                        cursor="arrow")
        self.verify_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(cf, orient=tk.VERTICAL, command=self.verify_canvas.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(win, orient=tk.HORIZONTAL, command=self.verify_canvas.xview)
        hsb.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.verify_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.verify_canvas.bind("<ButtonPress-1>", self._vc_press)
        self.verify_mode = "idle"
        self._verify_render()

    def _on_verify_pdf_window_close(self):
        if self.verify_pdf_window:
            self.verify_pdf_window.destroy()
        self.verify_pdf_window = None
        self.verify_canvas = None

    def _verify_enter_baseline_mode(self):
        if not self.verify_doc or not self.verify_canvas:
            return
        self.verify_mode = "set_baseline"
        self.verify_canvas.config(cursor="tcross")
        self._verify_status(f"基准点模式: 请点击第 {self.verify_page_index + 1} 页的基准点位置")

    def _vc_press(self, event):
        if self.verify_mode != "set_baseline" or not self.verify_doc or not self.verify_canvas:
            return
        cx = self.verify_canvas.canvasx(event.x)
        cy = self.verify_canvas.canvasy(event.y)
        px = cx / self.verify_sx
        py = cy / self.verify_sy
        self.verify_new_baselines[self.verify_page_index] = (px, py)
        self.verify_mode = "idle"
        self.verify_canvas.config(cursor="arrow")
        self._verify_render()
        self._verify_status(f"第 {self.verify_page_index + 1} 页基准点已设置, 标记已对齐")

    def _verify_zoom_in(self):
        self.verify_zoom = min(4.0, self.verify_zoom + 0.25)
        self._verify_render()

    def _verify_zoom_out(self):
        self.verify_zoom = max(0.5, self.verify_zoom - 0.25)
        self._verify_render()

    def _verify_export_pdf(self):
        """Export all pages with colour-coded verification markers as a new PDF."""
        if not self.verify_doc:
            messagebox.showwarning("提示", "请先加载 PDF 文件")
            return
        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF 文件", "*.pdf")],
            title="保存核对结果 PDF"
        )
        if not save_path:
            return
        out = fitz.open()
        for pidx in range(len(self.verify_doc)):
            composed = self._verify_compose_page(pidx)
            if composed is None:
                continue
            buf = io.BytesIO()
            composed.save(buf, format="PNG")
            page = out.new_page(width=composed.width, height=composed.height)
            page.insert_image(page.rect, stream=buf.getvalue(),
                              keep_proportion=False, overlay=True)
        out.save(save_path)
        out.close()
        messagebox.showinfo("导出成功", f"核对结果 PDF 已保存:\n{save_path}")
        self._verify_status(f"已导出核对结果 PDF")

    def _verify_compose_page(self, page_index):
        """Render a single page with coloured verification markers (PIL Image)."""
        if not self.verify_doc:
            return None
        page = self.verify_doc[page_index]
        z = self.verify_zoom
        pix  = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
        base = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")
        pr   = page.rect
        sx = pix.width  / pr.width
        sy = pix.height / pr.height
        draw = ImageDraw.Draw(base, "RGBA")
        badge_font = self._load_font(9)

        baseline = (self.verify_new_baselines.get(page_index) or
                    self.verify_orig_baselines.get(page_index))
        if baseline:
            bx, by = baseline[0] * sx, baseline[1] * sy
            r = 9
            draw.ellipse((bx - r, by - r, bx + r, by + r), outline=(240, 180, 41, 255), width=2)
            draw.line((bx - r - 5, by, bx + r + 5, by), fill=(240, 180, 41, 255), width=2)
            draw.line((bx, by - r - 5, bx, by + r + 5), fill=(240, 180, 41, 255), width=2)

        for m in self.verify_markers:
            if m.get("page") != page_index:
                continue
            ax, ay = self._verify_marker_abs_pdf(m)
            x = int(round(ax * sx))
            y = int(round(ay * sy))
            w = max(1, int(round(m["width"]  * sx)))
            h = max(1, int(round(m["height"] * sy)))
            mid    = m["id"]
            result = self.verify_results.get(mid)
            if result == "correct":
                color = (39, 174, 96, 255)
            elif result == "incorrect":
                color = (231, 76, 60, 255)
            else:
                color = (41, 128, 185, 255)
            draw.rectangle((x, y, x + w, y + h), outline=color, width=2)
            badge_w = max(22, len(str(mid)) * 7 + 6)
            draw.rectangle((x, y - 18, x + badge_w, y), fill=color, outline=color)
            if badge_font:
                tb = draw.textbbox((0, 0), str(mid), font=badge_font)
                tw, th = tb[2] - tb[0], tb[3] - tb[1]
                draw.text((x + (badge_w - tw) / 2, y - 18 + (18 - th) / 2 - tb[1]),
                          str(mid), font=badge_font, fill=(255, 255, 255, 255))
            else:
                draw.text((x + 4, y - 16), str(mid), fill=(255, 255, 255, 255))
            if result in ("correct", "incorrect") and w > 12 and h > 12:
                sym      = "✓" if result == "correct" else "✗"
                sym_size = max(10, min(h - 4, w - 4, 28))
                sym_font = self._load_font(sym_size)
                if sym_font:
                    tb  = draw.textbbox((0, 0), sym, font=sym_font)
                    tw2, th2 = tb[2] - tb[0], tb[3] - tb[1]
                    draw.text((x + (w - tw2) // 2, y + (h - th2) // 2 - tb[1]),
                              sym, font=sym_font, fill=color)
        return base.convert("RGB")

    # ── verify tree ───────────────────────────────────────────────────────
    def _refresh_verify_tree(self):
        if not hasattr(self, "verify_tree"):
            return
        sel = self.verify_selected_id
        for item in self.verify_tree.get_children():
            self.verify_tree.delete(item)
        for i, row_data in enumerate(self.verify_excel_rows):
            mid = i + 1
            col3 = row_data[2] if len(row_data) > 2 else ""
            preview = col3.replace("\n", " ").strip()
            if len(preview) > 70:
                preview = preview[:70] + "…"
            result  = self.verify_results.get(mid)
            status  = "✓ 正确" if result == "correct" else ("✗ 错误" if result == "incorrect" else "—")
            tag     = "correct" if result == "correct" else ("incorrect" if result == "incorrect" else "normal")
            self.verify_tree.insert("", "end", iid=str(mid),
                                     values=(mid, preview, status), tags=(tag,))
        if sel and self.verify_tree.exists(str(sel)):
            self.verify_tree.selection_set(str(sel))
            self.verify_tree.see(str(sel))

    def _on_verify_tree_select(self, event=None):
        sel = self.verify_tree.selection()
        if not sel:
            return
        try:
            mid = int(sel[0])
        except Exception:
            return
        self.verify_selected_id = mid
        self._show_verify_comparison(mid)
        self._navigate_verify_to_marker(mid)

    # ── comparison panel ──────────────────────────────────────────────────
    def _show_verify_comparison(self, mid):
        idx      = mid - 1
        row_data = self.verify_excel_rows[idx] if 0 <= idx < len(self.verify_excel_rows) else []
        col3_txt = row_data[2] if len(row_data) > 2 else ""

        self.verify_col3_text.config(state="normal")
        self.verify_col3_text.delete("1.0", tk.END)
        self.verify_col3_text.insert("1.0", col3_txt)
        self.verify_col3_text.config(state="disabled")

        self._current_verify_col4_mid = mid
        self._render_verify_col4(mid)

        result     = self.verify_results.get(mid)
        status_txt = "✓ 正确" if result == "correct" else ("✗ 错误" if result == "incorrect" else "待核对")
        self.lbl_verify_row.config(
            text=f"第 {mid} 行  [{status_txt}]  / 共 {len(self.verify_excel_rows)} 行"
        )

    def _render_verify_col4(self, mid):
        self.verify_col4_canvas.delete("all")
        self.verify_col4_photo = None
        img = self.verify_images.get(mid)
        self.verify_col4_canvas.update_idletasks()
        cw = max(10, self.verify_col4_canvas.winfo_width())
        ch = max(10, self.verify_col4_canvas.winfo_height())
        if img:
            iw, ih = img.size
            scale  = min(cw / iw, ch / ih)
            nw     = max(1, int(iw * scale))
            nh     = max(1, int(ih * scale))
            resized = img.resize((nw, nh), Image.LANCZOS)
            self.verify_col4_photo = ImageTk.PhotoImage(resized)
            self.verify_col4_canvas.create_image(
                (cw - nw) // 2, (ch - nh) // 2, anchor=tk.NW, image=self.verify_col4_photo
            )
        else:
            self.verify_col4_canvas.create_text(
                cw // 2, ch // 2, text="（无截图）", fill="gray", font=("Arial", 12)
            )

    def _on_verify_col4_resize(self, event=None):
        mid = self._current_verify_col4_mid
        if mid is not None:
            self._render_verify_col4(mid)

    # ── verify actions ────────────────────────────────────────────────────
    def _verify_set_result(self, result):
        mid = self.verify_selected_id
        if mid is None:
            return
        cur = self.verify_results.get(mid)
        self.verify_results[mid] = None if cur == result else result
        self._refresh_verify_tree()
        self._verify_render()
        self._show_verify_comparison(mid)    # refresh status label

    def _verify_prev_row(self):
        items = self.verify_tree.get_children()
        if not items:
            return
        ids = [int(i) for i in items]
        cur = self.verify_selected_id
        if cur is None:
            nid = ids[0]
        elif cur in ids:
            nid = ids[max(0, ids.index(cur) - 1)]
        else:
            nid = ids[0]
        self.verify_tree.selection_set(str(nid))
        self.verify_tree.see(str(nid))
        self._on_verify_tree_select()

    def _verify_next_row(self):
        items = self.verify_tree.get_children()
        if not items:
            return
        ids = [int(i) for i in items]
        cur = self.verify_selected_id
        if cur is None:
            nid = ids[0]
        elif cur in ids:
            nid = ids[min(len(ids) - 1, ids.index(cur) + 1)]
        else:
            nid = ids[0]
        self.verify_tree.selection_set(str(nid))
        self.verify_tree.see(str(nid))
        self._on_verify_tree_select()

    # ── PDF navigation ────────────────────────────────────────────────────
    def _verify_marker_abs_pdf(self, m):
        pidx = m["page"]
        if pidx in self.verify_new_baselines:
            nx, ny = self.verify_new_baselines[pidx]
        elif pidx in self.verify_orig_baselines:
            nx, ny = self.verify_orig_baselines[pidx]
        else:
            nx, ny = 0, 0
        return nx + m["x"], ny + m["y"]

    def _navigate_verify_to_marker(self, mid):
        """If the PDF preview window is already open, switch to marker page and centre."""
        if not self.verify_doc or not self.verify_markers:
            return
        # Only navigate if PDF window is already open — never auto-open
        if not self.verify_pdf_window or not self.verify_pdf_window.winfo_exists():
            return
        self.verify_pdf_window.lift()

        for m in self.verify_markers:
            if m.get("id") != mid:
                continue
            page = m.get("page", 0)
            if self.verify_page_index != page:
                self.verify_page_index = page
                self._verify_render()
            if not self.verify_canvas:
                break
            ax, ay = self._verify_marker_abs_pdf(m)
            cx = ax * self.verify_sx
            cy = ay * self.verify_sy
            mw = m["width"]  * self.verify_sx
            mh = m["height"] * self.verify_sy
            self.verify_canvas.update_idletasks()
            sr = self.verify_canvas.cget("scrollregion")
            try:
                _, _, total_w, total_h = (float(v) for v in str(sr).split())
            except Exception:
                break
            vw = self.verify_canvas.winfo_width()
            vh = self.verify_canvas.winfo_height()
            target_x = cx + mw / 2 - vw / 2
            target_y = cy + mh / 2 - vh / 2
            xf = max(0.0, min(1.0, target_x / total_w)) if total_w > 0 else 0.0
            yf = max(0.0, min(1.0, target_y / total_h)) if total_h > 0 else 0.0
            self.verify_canvas.xview_moveto(xf)
            self.verify_canvas.yview_moveto(yf)
            self._verify_status(f"已定位到标记 {mid}（第 {page + 1} 页）")
            break

    # ── rendering ─────────────────────────────────────────────────────────
    def _verify_render(self):
        if not self.verify_canvas:
            return
        try:
            alive = self.verify_canvas.winfo_exists()
        except Exception:
            alive = False
        if not alive:
            return
        if not self.verify_doc:
            self.verify_canvas.delete("all")
            try:
                self.lbl_verify_page.config(text=" — / — ")
            except Exception:
                pass
            return
        page = self.verify_doc[self.verify_page_index]
        pix  = page.get_pixmap(matrix=fitz.Matrix(self.verify_zoom, self.verify_zoom), alpha=False)
        base = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")
        pr   = page.rect
        self.verify_sx = pix.width  / pr.width
        self.verify_sy = pix.height / pr.height
        sx, sy = self.verify_sx, self.verify_sy

        draw = ImageDraw.Draw(base, "RGBA")
        badge_font = self._load_font(9)

        baseline = (self.verify_new_baselines.get(self.verify_page_index) or
                    self.verify_orig_baselines.get(self.verify_page_index))
        if baseline:
            bx, by = baseline[0] * sx, baseline[1] * sy
            r = 9
            draw.ellipse((bx - r, by - r, bx + r, by + r), outline=(240, 180, 41, 255), width=2)
            draw.line((bx - r - 5, by, bx + r + 5, by), fill=(240, 180, 41, 255), width=2)
            draw.line((bx, by - r - 5, bx, by + r + 5), fill=(240, 180, 41, 255), width=2)

        for m in self.verify_markers:
            if m.get("page") != self.verify_page_index:
                continue
            ax, ay = self._verify_marker_abs_pdf(m)
            x = int(round(ax * sx))
            y = int(round(ay * sy))
            w = max(1, int(round(m["width"]  * sx)))
            h = max(1, int(round(m["height"] * sy)))
            mid    = m["id"]
            result = self.verify_results.get(mid)

            if result == "correct":
                color = (39, 174, 96, 255)
            elif result == "incorrect":
                color = (231, 76, 60, 255)
            else:
                color = (41, 128, 185, 255)

            draw.rectangle((x, y, x + w, y + h), outline=color, width=2)
            badge_w = max(22, len(str(mid)) * 7 + 6)
            draw.rectangle((x, y - 18, x + badge_w, y), fill=color, outline=color)
            if badge_font:
                tb = draw.textbbox((0, 0), str(mid), font=badge_font)
                tw, th = tb[2] - tb[0], tb[3] - tb[1]
                draw.text(
                    (x + (badge_w - tw) / 2, y - 18 + (18 - th) / 2 - tb[1]),
                    str(mid), font=badge_font, fill=(255, 255, 255, 255)
                )
            else:
                draw.text((x + 4, y - 16), str(mid), fill=(255, 255, 255, 255))

            if result in ("correct", "incorrect") and w > 12 and h > 12:
                sym      = "✓" if result == "correct" else "✗"
                sym_size = max(10, min(h - 4, w - 4, 28))
                sym_font = self._load_font(sym_size)
                if sym_font:
                    tb  = draw.textbbox((0, 0), sym, font=sym_font)
                    tw2, th2 = tb[2] - tb[0], tb[3] - tb[1]
                    draw.text(
                        (x + (w - tw2) // 2, y + (h - th2) // 2 - tb[1]),
                        sym, font=sym_font, fill=color
                    )

        composed = base.convert("RGB")
        self.verify_pdf_photo = ImageTk.PhotoImage(composed)
        self.verify_canvas.config(scrollregion=(0, 0, composed.width, composed.height))
        self.verify_canvas.delete("all")
        self.verify_canvas.create_image(0, 0, anchor=tk.NW, image=self.verify_pdf_photo)
        try:
            self.lbl_verify_page.config(text=f" {self.verify_page_index + 1} / {len(self.verify_doc)} ")
        except Exception:
            pass

    def _verify_prev_page(self):
        if self.verify_doc and self.verify_page_index > 0:
            self.verify_page_index -= 1
            self._verify_render()

    def _verify_next_page(self):
        if self.verify_doc and self.verify_page_index < len(self.verify_doc) - 1:
            self.verify_page_index += 1
            self._verify_render()

    def _verify_status(self, text):
        self.lbl_verify_status.config(text=text)

def main():
    root = tk.Tk()
    PDFMarkerApp(root)
    root.mainloop()
if __name__ == "__main__":
    main()