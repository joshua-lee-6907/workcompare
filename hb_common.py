"""hb_common.py - Shared styles, constants, and utilities for Hebing application."""

import hashlib
import json
import os

# Color Palette
BG_DARK   = "#0c1228"
BG_MID    = "#101d42"
BG_WIDGET = "#142468"
ACCENT    = "#00d4ff"
ACCENT2   = "#0059c1"
TEXT_MAIN = "#e9f1fb"
TEXT_DIM  = "#8ca8cc"
BORDER    = "#2659a8"
HIGHLIGHT = "#3af1ff"
DANGER    = "#ff3576"
SUCCESS   = "#00ffe0"
WARNING   = "#ff9000"

MAIN_STYLESHEET = (
    "QMainWindow, QDialog, QWidget {"
    "  background-color: #0c1228;"
    "  color: #e9f1fb;"
    "  font-family: 'Segoe UI', 'Microsoft YaHei', 'Arial', sans-serif;"
    "  font-size: 14px;"
    "}"
    "QLabel {"
    "  color: #00d4ff;"
    "  font-weight: bold;"
    "  background: transparent;"
    "}"
    "QLabel#subtext {"
    "  color: #8ca8cc;"
    "  font-weight: normal;"
    "}"
    "QLabel#status {"
    "  color: #00ffe0;"
    "  font-weight: bold;"
    "}"
    "QLineEdit, QDateEdit, QSpinBox, QDoubleSpinBox {"
    "  background-color: #142468;"
    "  color: #e9f1fb;"
    "  border: 1.5px solid #2659a8;"
    "  border-radius: 7px;"
    "  padding: 6px 10px;"
    "  font-size: 14px;"
    "}"
    "QLineEdit:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {"
    "  border: 2px solid #00d4ff;"
    "}"
    "QComboBox {"
    "  background-color: #142468;"
    "  color: #e9f1fb;"
    "  border: 1.5px solid #2659a8;"
    "  border-radius: 7px;"
    "  padding: 6px 10px;"
    "  font-size: 14px;"
    "}"
    "QComboBox::drop-down { border: none; background: #142468; }"
    "QComboBox QAbstractItemView {"
    "  background-color: #101d42;"
    "  color: #e9f1fb;"
    "  selection-background-color: #0059c1;"
    "}"
    "QPushButton {"
    "  background-color: #00d4ff;"
    "  color: #0c1228;"
    "  font-weight: bold;"
    "  border-radius: 9px;"
    "  padding: 8px 20px;"
    "  font-size: 14px;"
    "  min-height: 34px;"
    "  border: none;"
    "}"
    "QPushButton:hover { background-color: #3af1ff; }"
    "QPushButton:pressed { background-color: #0059c1; color: white; }"
    "QPushButton:disabled { background-color: #1e3060; color: #8ca8cc; }"
    "QPushButton#secondary {"
    "  background-color: #142468;"
    "  color: #00d4ff;"
    "  border: 1.5px solid #2659a8;"
    "}"
    "QPushButton#secondary:hover { border-color: #00d4ff; color: #3af1ff; }"
    "QPushButton#danger { background-color: #ff3576; color: white; }"
    "QPushButton#danger:hover { background-color: #ff5595; }"
    "QPushButton#reset {"
    "  background-color: #1a2d5a;"
    "  color: #ff9000;"
    "  border: 1.5px solid #ff9000;"
    "  font-size: 13px;"
    "  min-height: 28px;"
    "  padding: 4px 14px;"
    "  border-radius: 7px;"
    "}"
    "QPushButton#reset:hover { background-color: #2a3d6a; }"
    "QProgressBar {"
    "  background-color: #142468;"
    "  border: 1px solid #2659a8;"
    "  border-radius: 7px;"
    "  text-align: center;"
    "  color: #e9f1fb;"
    "  font-size: 13px;"
    "  min-height: 26px;"
    "}"
    "QProgressBar::chunk {"
    "  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
    "    stop:0 #3af1ff, stop:1 #0059c1);"
    "  border-radius: 7px;"
    "}"
    "QTabWidget::pane {"
    "  border: 1.5px solid #2659a8;"
    "  background-color: #101d42;"
    "  border-radius: 0 8px 8px 8px;"
    "  margin-top: -1px;"
    "}"
    "QTabBar::tab {"
    "  background: #0c1228;"
    "  color: #8ca8cc;"
    "  padding: 11px 24px;"
    "  font-size: 14px;"
    "  font-weight: bold;"
    "  border: 1px solid transparent;"
    "  border-bottom: none;"
    "  border-radius: 6px 6px 0 0;"
    "  margin-right: 2px;"
    "}"
    "QTabBar::tab:selected { background: #101d42; color: #00d4ff; border-color: #2659a8; }"
    "QTabBar::tab:hover:!selected { background: #0f1a38; color: #e9f1fb; }"
    "QGroupBox {"
    "  border: 1.5px solid #2659a8;"
    "  border-radius: 8px;"
    "  margin-top: 14px;"
    "  padding-top: 14px;"
    "  color: #00d4ff;"
    "  font-weight: bold;"
    "  font-size: 13px;"
    "}"
    "QGroupBox::title {"
    "  subcontrol-origin: margin;"
    "  subcontrol-position: top left;"
    "  padding: 0 8px;"
    "  color: #00d4ff;"
    "}"
    "QScrollBar:vertical {"
    "  border: none; background: #142468; width: 8px; border-radius: 4px; margin: 0;"
    "}"
    "QScrollBar::handle:vertical {"
    "  background: #2659a8; border-radius: 4px; min-height: 28px;"
    "}"
    "QScrollBar::handle:vertical:hover { background: #00d4ff; }"
    "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
    "QScrollBar:horizontal {"
    "  border: none; background: #142468; height: 8px; border-radius: 4px; margin: 0;"
    "}"
    "QScrollBar::handle:horizontal {"
    "  background: #2659a8; border-radius: 4px; min-width: 28px;"
    "}"
    "QScrollBar::handle:horizontal:hover { background: #00d4ff; }"
    "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
    "QTableWidget {"
    "  background-color: #142468;"
    "  color: #e9f1fb;"
    "  border: 1px solid #2659a8;"
    "  gridline-color: #2659a8;"
    "  selection-background-color: #0059c1;"
    "  selection-color: white;"
    "  font-size: 13px;"
    "}"
    "QHeaderView::section {"
    "  background-color: #101d42;"
    "  color: #00d4ff;"
    "  border: 1px solid #2659a8;"
    "  padding: 6px 8px;"
    "  font-weight: bold;"
    "  font-size: 13px;"
    "}"
    "QStatusBar {"
    "  background-color: #101d42;"
    "  color: #8ca8cc;"
    "  border-top: 1px solid #2659a8;"
    "  font-size: 12px;"
    "}"
    "QMenuBar {"
    "  background-color: #101d42;"
    "  color: #e9f1fb;"
    "  border-bottom: 1px solid #2659a8;"
    "  font-size: 13px;"
    "}"
    "QMenuBar::item:selected { background-color: #142468; color: #00d4ff; }"
    "QMenu {"
    "  background-color: #101d42;"
    "  color: #e9f1fb;"
    "  border: 1px solid #2659a8;"
    "  font-size: 13px;"
    "}"
    "QMenu::item:selected { background-color: #0059c1; color: white; }"
    "QCheckBox { color: #e9f1fb; spacing: 8px; }"
    "QCheckBox::indicator {"
    "  width: 16px; height: 16px;"
    "  border: 1.5px solid #2659a8;"
    "  border-radius: 4px;"
    "  background: #142468;"
    "}"
    "QCheckBox::indicator:checked { background: #00d4ff; border-color: #00d4ff; }"
    "QToolBar { background-color: #101d42; border: none; spacing: 4px; }"
    "QToolButton {"
    "  background-color: #142468;"
    "  color: #e9f1fb;"
    "  border: 1px solid #2659a8;"
    "  border-radius: 4px;"
    "  padding: 4px 8px;"
    "}"
    "QToolButton:hover { background-color: #101d42; border-color: #00d4ff; color: #00d4ff; }"
)

MPL_STYLE = {
    "figure.facecolor": BG_DARK,
    "axes.facecolor": "#0d1836",
    "axes.edgecolor": BORDER,
    "axes.labelcolor": TEXT_MAIN,
    "text.color": TEXT_MAIN,
    "xtick.color": "#70c6ff",
    "ytick.color": "#70c6ff",
    "grid.color": "#1e294f",
    "grid.alpha": 0.45,
    "grid.linestyle": "-.",
    "axes.grid": True,
    "lines.linewidth": 2.0,
    "font.family": "sans-serif",
    "axes.titlecolor": ACCENT,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "legend.facecolor": BG_MID,
    "legend.edgecolor": BORDER,
    "legend.labelcolor": TEXT_MAIN,
    "savefig.facecolor": BG_DARK,
    "savefig.edgecolor": BG_DARK,
}


def glow_plot(ax, x, y, color, label=None, linewidth=2.5):
    """Draw a line with subtle glow layers."""
    for lw, a in [(12, 0.05), (8, 0.09), (5, 0.14), (3, 0.20)]:
        ax.plot(x, y, color=color, linewidth=lw, alpha=a)
    ax.plot(x, y, color=color, linewidth=linewidth, alpha=0.92, label=label)


# User management
USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hb_users.json")


def _hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


def load_users():
    if not os.path.exists(USERS_FILE):
        users = {"admin": {"password": _hash("admin123"), "role": "admin"}}
        save_users(users)
        return users
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def verify_login(username, password):
    users = load_users()
    user  = users.get(username)
    return bool(user and user["password"] == _hash(password))


def register_user(username, password, role="user"):
    users = load_users()
    if username in users:
        return False
    users[username] = {"password": _hash(password), "role": role}
    save_users(users)
    return True


def change_password(username, old_password, new_password):
    users = load_users()
    user  = users.get(username)
    if user and user["password"] == _hash(old_password):
        users[username]["password"] = _hash(new_password)
        save_users(users)
        return True
    return False


def get_user_role(username):
    return load_users().get(username, {}).get("role", "user")
