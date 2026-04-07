"""
深蓝科技风主题样式模块
Deep-blue technology theme styles for hebing.py
"""

import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# ─── Color Palette ────────────────────────────────────────────────────────────
COLORS = {
    'bg_primary':    '#070d1f',
    'bg_secondary':  '#0c1530',
    'bg_card':       '#101c38',
    'bg_input':      '#152040',
    'border':        '#1a2d5a',
    'border_accent': '#0080ff',
    'text_primary':  '#d8eeff',
    'text_secondary':'#7a9ab8',
    'text_accent':   '#00d4ff',
    'accent_blue':   '#0080ff',
    'accent_cyan':   '#00d4ff',
    'accent_green':  '#00e88a',
    'accent_red':    '#ff3060',
    'accent_yellow': '#ffd700',
    'button_bg':     '#0a1e48',
    'button_hover':  '#0d2a5e',
    'button_active': '#1040a0',
    'sidebar_bg':    '#060c1a',
    'sidebar_active':'#0a1e48',
    'chart_bg':      '#070d1f',
    'header_bg':     '#050a16',
}

# ─── Main Application Stylesheet ──────────────────────────────────────────────
MAIN_STYLESHEET = """
QWidget {
    background-color: #070d1f;
    color: #d8eeff;
    font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMainWindow { background-color: #070d1f; }

/* ── Buttons ── */
QPushButton {
    background-color: #0a1e48;
    color: #00d4ff;
    border: 1px solid #0080ff;
    border-radius: 5px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: bold;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #0d2a5e;
    border-color: #00d4ff;
    color: #ffffff;
}
QPushButton:pressed { background-color: #1040a0; }
QPushButton:disabled {
    background-color: #0a1020;
    color: #2a4060;
    border-color: #1a2d5a;
}
QPushButton#btn_primary {
    background-color: #0060c0;
    color: #ffffff;
    border: 1px solid #00a0ff;
    font-size: 14px;
    padding: 9px 18px;
}
QPushButton#btn_primary:hover { background-color: #0080e0; }
QPushButton#btn_danger {
    background-color: #3a0010;
    color: #ff6080;
    border: 1px solid #800020;
}
QPushButton#btn_danger:hover {
    background-color: #500020;
    border-color: #ff3060;
}
QPushButton#btn_success {
    background-color: #003820;
    color: #00e88a;
    border: 1px solid #006040;
}
QPushButton#btn_success:hover { background-color: #005030; }
QPushButton#btn_reset {
    background-color: #1a1000;
    color: #ffd700;
    border: 1px solid #806000;
}
QPushButton#btn_reset:hover {
    background-color: #2a1800;
    border-color: #ffd700;
}

/* ── Inputs ── */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #152040;
    color: #d8eeff;
    border: 1px solid #1a2d5a;
    border-radius: 4px;
    padding: 6px 8px;
    selection-background-color: #0060c0;
}
QLineEdit:focus, QTextEdit:focus { border: 1px solid #00a8ff; }

/* ── Labels ── */
QLabel { color: #d8eeff; background: transparent; }
QLabel#lbl_title  { color: #00d4ff; font-size: 16px; font-weight: bold; }
QLabel#lbl_subtitle { color: #7a9ab8; font-size: 12px; }
QLabel#lbl_accent { color: #00d4ff; font-weight: bold; }
QLabel#lbl_info   { color: #00e88a; font-size: 12px; }
QLabel#lbl_warn   { color: #ffd700; font-size: 12px; }

/* ── Progress Bar ── */
QProgressBar {
    background-color: #0c1530;
    border: 1px solid #1a2d5a;
    border-radius: 4px;
    text-align: center;
    color: #00d4ff;
    height: 22px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0040a0, stop:0.5 #0080ff, stop:1 #00d4ff);
    border-radius: 3px;
}

/* ── Date/Spin/Combo ── */
QDateEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #152040;
    color: #d8eeff;
    border: 1px solid #1a2d5a;
    border-radius: 4px;
    padding: 5px 8px;
    min-height: 26px;
}
QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #00a8ff;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox::down-arrow {
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #00a8ff;
    margin-right: 4px;
}
QComboBox QAbstractItemView {
    background-color: #0c1530;
    color: #d8eeff;
    border: 1px solid #1a2d5a;
    selection-background-color: #0060c0;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QDateEdit::up-button, QDateEdit::down-button {
    background-color: #1a2d5a;
    border: none;
    width: 18px;
}

/* ── GroupBox ── */
QGroupBox {
    border: 1px solid #1a2d5a;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 6px;
    color: #00d4ff;
    font-weight: bold;
    font-size: 13px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #00d4ff;
}

/* ── Table ── */
QTableWidget {
    background-color: #0c1530;
    color: #d8eeff;
    border: 1px solid #1a2d5a;
    gridline-color: #1a2d5a;
    selection-background-color: #0a3060;
    alternate-background-color: #0e1b38;
}
QTableWidget::item { padding: 4px 8px; }
QTableWidget::item:selected { background-color: #0a3060; color: #00d4ff; }
QHeaderView::section {
    background-color: #0a1428;
    color: #00d4ff;
    border: 1px solid #1a2d5a;
    padding: 6px 8px;
    font-weight: bold;
}

/* ── ScrollBars ── */
QScrollBar:vertical {
    background-color: #070d1f; width: 8px; border: none;
}
QScrollBar::handle:vertical {
    background-color: #1a2d5a; border-radius: 4px; min-height: 20px;
}
QScrollBar::handle:vertical:hover { background-color: #0080ff; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal {
    background-color: #070d1f; height: 8px; border: none;
}
QScrollBar::handle:horizontal {
    background-color: #1a2d5a; border-radius: 4px; min-width: 20px;
}
QScrollBar::handle:horizontal:hover { background-color: #0080ff; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }

/* ── Menu ── */
QMenuBar {
    background-color: #050a16;
    color: #d8eeff;
    border-bottom: 1px solid #1a2d5a;
}
QMenuBar::item:selected { background-color: #152040; color: #00d4ff; }
QMenu {
    background-color: #0c1530;
    color: #d8eeff;
    border: 1px solid #1a2d5a;
}
QMenu::item:selected { background-color: #0a3060; color: #00d4ff; }
QMenu::separator { height: 1px; background-color: #1a2d5a; margin: 4px 0; }

/* ── Status bar ── */
QStatusBar {
    background-color: #050a16;
    color: #7a9ab8;
    border-top: 1px solid #1a2d5a;
}

/* ── Splitter ── */
QSplitter::handle { background-color: #1a2d5a; }
QSplitter::handle:horizontal { width: 2px; }

/* ── Tabs ── */
QTabWidget::pane {
    border: 1px solid #1a2d5a;
    background-color: #0c1530;
    border-top: none;
}
QTabBar::tab {
    background-color: #070d1f;
    color: #7a9ab8;
    padding: 8px 16px;
    border: 1px solid #1a2d5a;
    border-bottom: none;
    margin-right: 2px;
    min-width: 80px;
}
QTabBar::tab:selected {
    background-color: #0c1530;
    color: #00d4ff;
    border-top: 2px solid #0080ff;
}
QTabBar::tab:hover { background-color: #0a1428; color: #d8eeff; }

/* ── CheckBox ── */
QCheckBox { color: #d8eeff; spacing: 6px; }
QCheckBox::indicator {
    background-color: #152040;
    border: 1px solid #1a2d5a;
    border-radius: 3px;
    width: 14px; height: 14px;
}
QCheckBox::indicator:checked { background-color: #0080ff; border-color: #00a8ff; }

/* ── Frames ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] { color: #1a2d5a; }

/* ── ToolTip ── */
QToolTip {
    background-color: #0c1530;
    color: #d8eeff;
    border: 1px solid #0080ff;
    padding: 4px;
}

/* ── Dialog ── */
QDialog { background-color: #070d1f; color: #d8eeff; }
"""

LOGIN_STYLESHEET = """
QWidget {
    background-color: #04080f;
    color: #d8eeff;
    font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif;
}
QLineEdit {
    background-color: #0a1428;
    color: #d8eeff;
    border: 1px solid #1a3060;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 14px;
    selection-background-color: #0060c0;
}
QLineEdit:focus { border: 1px solid #00a8ff; }
QPushButton {
    background-color: #0060c0;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 10px;
    font-size: 14px;
    font-weight: bold;
    min-height: 38px;
}
QPushButton:hover { background-color: #0080e0; }
QPushButton:pressed { background-color: #0040a0; }
QPushButton#btn_register {
    background-color: transparent;
    color: #00a8ff;
    border: 1px solid #00a8ff;
    font-size: 13px;
    min-height: 32px;
}
QPushButton#btn_register:hover { background-color: #0a2040; }
QLabel { background: transparent; }
"""


# ─── Shared Chart Dialog ───────────────────────────────────────────────────────
class ChartDialog(QDialog):
    """Reusable dialog for embedding matplotlib figures with export support."""

    def __init__(self, parent=None, title="图表", figsize=(11, 7)):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(900, 650)
        self.resize(1050, 720)
        self.setStyleSheet(MAIN_STYLESHEET)
        self.fig = None
        self.canvas = None
        self._figsize = figsize
        self._setup_ui()

    def _setup_ui(self):
        from matplotlib.backends.backend_qt5agg import (
            FigureCanvasQTAgg as FigureCanvas,
            NavigationToolbar2QT as NavigationToolbar,
        )
        from matplotlib.figure import Figure

        self.fig = Figure(figsize=self._figsize, facecolor=COLORS['chart_bg'])
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet("background-color: #070d1f;")

        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.setStyleSheet(
            "QToolBar { background-color: #0c1530; border: none; }"
            "QToolButton { color: #00d4ff; background-color: #0a1e48; "
            "border: 1px solid #1a2d5a; border-radius: 3px; padding: 3px; }"
            "QToolButton:hover { background-color: #0d2a5e; }"
        )

        export_btn = QPushButton("导出图表")
        export_btn.setObjectName("btn_success")
        export_btn.setFixedWidth(120)
        export_btn.clicked.connect(self.export_chart)

        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(close_btn)

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(toolbar)
        layout.addWidget(self.canvas, stretch=1)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def get_figure(self):
        """Return the Figure for plotting."""
        return self.fig

    def refresh(self):
        """Redraw canvas after plotting."""
        self.canvas.draw()

    def export_chart(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出图表", "chart",
            "PNG图片 (*.png);;PDF文档 (*.pdf);;SVG矢量图 (*.svg)"
        )
        if path:
            try:
                self.fig.savefig(path, dpi=150, bbox_inches='tight',
                                 facecolor=COLORS['chart_bg'], edgecolor='none')
                QMessageBox.information(self, "导出成功", f"图表已保存至:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))


def style_axes(ax):
    """Apply dark-tech style to a matplotlib Axes object."""
    ax.set_facecolor(COLORS['chart_bg'])
    ax.tick_params(colors='#7a9ab8', labelsize=10)
    for spine in ax.spines.values():
        spine.set_color('#1a2d5a')
    ax.grid(True, color='#1a2d5a', alpha=0.6, linestyle='--', linewidth=0.8)
    ax.title.set_color('#00d4ff')
    ax.xaxis.label.set_color('#7a9ab8')
    ax.yaxis.label.set_color('#7a9ab8')
