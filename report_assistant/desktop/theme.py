"""全局 QSS：参考小黑日报助手风格的精致版。

配色策略：
- 主色：emerald 系（#10b981 ~ #059669）
- 中性色：slate 系（更冷一点，干净）
- 8px 网格间距、圆角统一 8/12px
"""
from __future__ import annotations

from pathlib import Path

from .assets import ASSETS_DIR


# ── 主色系 ─────────────────────────────────────
PRIMARY = "#10b981"
PRIMARY_HOVER = "#059669"
PRIMARY_ACTIVE = "#047857"
PRIMARY_SOFT = "#ecfdf5"
PRIMARY_SOFT_2 = "#d1fae5"

# ── 中性色 ─────────────────────────────────────
BG = "#ffffff"
BG_APP = "#fafbfc"
BG_ELEVATED = "#ffffff"
BG_ALT = "#f4f6f8"
BG_HOVER = "#f8fafc"

TEXT = "#0f172a"
TEXT_SECONDARY = "#475569"
TEXT_MUTED = "#94a3b8"
TEXT_PLACEHOLDER = "#cbd5e1"

BORDER = "#e2e8f0"
BORDER_STRONG = "#cbd5e1"

DANGER = "#ef4444"
DANGER_SOFT = "#fef2f2"


def _icon(name: str) -> str:
    """把资源路径转成 QSS 可用的 url。Qt 接受 forward slash 路径。"""
    p = Path(ASSETS_DIR) / f"{name}.png"
    return f"url({p.as_posix()})"


# 图标 url（注入到 QSS f-string）
ICON_DOWN = _icon("chevron_down")
ICON_DOWN_ACTIVE = _icon("chevron_down_active")
ICON_UP = _icon("chevron_up")
ICON_UP_ACTIVE = _icon("chevron_up_active")
ICON_PLUS = _icon("plus")
ICON_PLUS_ACTIVE = _icon("plus_active")
ICON_MINUS = _icon("minus")
ICON_MINUS_ACTIVE = _icon("minus_active")


QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", "Inter",
                 -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

QMainWindow, QWidget#MainWindow {{
    background-color: {BG_APP};
}}

QToolTip {{
    background: {TEXT};
    color: white;
    border: none;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
}}

/* ── 侧边栏 ─────────────────────────────── */
QWidget#Sidebar {{
    background-color: {BG};
    border-right: 1px solid {BORDER};
}}
QLabel#SidebarLogo {{
    font-size: 17px;
    font-weight: 800;
    padding: 22px 22px 4px;
    color: {TEXT};
    letter-spacing: -0.01em;
}}
QLabel#SidebarLogoSub {{
    font-size: 11px;
    color: {TEXT_MUTED};
    padding: 0 22px 22px;
    letter-spacing: 0.04em;
}}
QPushButton#NavButton {{
    text-align: left;
    padding: 11px 18px;
    margin: 2px 12px;
    border: none;
    background: transparent;
    color: {TEXT_SECONDARY};
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#NavButton:hover {{
    background: {BG_ALT};
    color: {TEXT};
}}
QPushButton#NavButton:checked {{
    background: {PRIMARY_SOFT};
    color: {PRIMARY_ACTIVE};
    font-weight: 600;
}}

/* ── 卡片 ──────────────────────────────── */
QFrame#Card {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#CardAlt {{
    background: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#StatCard {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#StatCard:hover {{
    border-color: {PRIMARY};
}}

/* ── 文字层级 ───────────────────────────── */
QLabel#PageTitle {{
    font-size: 24px;
    font-weight: 700;
    color: {TEXT};
    letter-spacing: -0.02em;
}}
QLabel#PageSubtitle {{
    font-size: 13px;
    color: {TEXT_MUTED};
}}
QLabel#SectionLabel {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {PRIMARY};
}}
QLabel#CardTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT};
    letter-spacing: -0.01em;
}}
QLabel#CardDesc {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#StatNumber {{
    font-size: 30px;
    font-weight: 700;
    color: {TEXT};
    letter-spacing: -0.02em;
}}
QLabel#StatNumberPrimary {{
    font-size: 30px;
    font-weight: 700;
    color: {PRIMARY_HOVER};
    letter-spacing: -0.02em;
}}
QLabel#StatLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 500;
}}
QLabel#StatIcon {{
    font-size: 20px;
}}
QLabel#FormLabel {{
    color: {TEXT_SECONDARY};
    font-weight: 600;
    font-size: 12px;
}}

/* ── 按钮 ──────────────────────────────── */
QPushButton#PrimaryButton {{
    background: {PRIMARY};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 9px 20px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#PrimaryButton:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton#PrimaryButton:pressed {{ background: {PRIMARY_ACTIVE}; }}
QPushButton#PrimaryButton:disabled {{ background: {PRIMARY_SOFT_2}; color: white; }}

QPushButton#SecondaryButton {{
    background: {BG};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 500;
}}
QPushButton#SecondaryButton:hover {{
    border-color: {PRIMARY};
    color: {PRIMARY_HOVER};
    background: {PRIMARY_SOFT};
}}
QPushButton#SecondaryButton:pressed {{ background: {PRIMARY_SOFT_2}; }}
QPushButton#SecondaryButton:disabled {{
    color: {TEXT_PLACEHOLDER};
    border-color: {BORDER};
    background: {BG_ALT};
}}

QPushButton#DangerButton {{
    background: {BG};
    color: {DANGER};
    border: 1px solid #fecaca;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 500;
}}
QPushButton#DangerButton:hover {{
    background: {DANGER_SOFT};
    border-color: {DANGER};
}}

QPushButton#GhostButton {{
    background: transparent;
    color: {TEXT_SECONDARY};
    border: none;
    padding: 6px 12px;
    border-radius: 6px;
}}
QPushButton#GhostButton:hover {{
    background: {BG_ALT};
    color: {TEXT};
}}

/* 监视器选择按钮：可勾选状态 */
QPushButton#MonitorButton {{
    background: {BG};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 500;
}}
QPushButton#MonitorButton:hover {{
    border-color: {PRIMARY};
    background: {BG_HOVER};
}}
QPushButton#MonitorButton:checked {{
    background: {PRIMARY_SOFT};
    color: {PRIMARY_ACTIVE};
    border-color: {PRIMARY};
    font-weight: 600;
}}

/* ── 输入控件 ──────────────────────────── */
QLineEdit, QPlainTextEdit, QTextEdit {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    background: {BG};
    color: {TEXT};
    selection-background-color: {PRIMARY_SOFT_2};
    selection-color: {TEXT};
}}
QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover {{
    border-color: {BORDER_STRONG};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {PRIMARY};
}}
QLineEdit:disabled, QPlainTextEdit:disabled {{
    background: {BG_ALT};
    color: {TEXT_MUTED};
}}

QComboBox, QDateEdit, QSpinBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    background: {BG};
    color: {TEXT};
    min-height: 20px;
}}
QComboBox:hover, QDateEdit:hover, QSpinBox:hover {{
    border-color: {BORDER_STRONG};
}}
QComboBox:focus, QDateEdit:focus, QSpinBox:focus {{
    border-color: {PRIMARY};
}}
QComboBox QAbstractItemView {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {BG};
    selection-background-color: {PRIMARY_SOFT};
    selection-color: {TEXT};
    outline: none;
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    border-radius: 4px;
}}

/* ComboBox / DateEdit 下拉按钮：自定义 chevron */
QComboBox::drop-down, QDateEdit::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    background: transparent;
}}
QComboBox::drop-down:hover, QDateEdit::drop-down:hover {{
    background: {PRIMARY_SOFT};
}}
QComboBox::down-arrow, QDateEdit::down-arrow {{
    image: {ICON_DOWN};
    width: 14px;
    height: 14px;
}}
QComboBox::down-arrow:hover, QDateEdit::down-arrow:hover {{
    image: {ICON_DOWN_ACTIVE};
}}
QComboBox::down-arrow:on, QDateEdit::down-arrow:on {{
    image: {ICON_DOWN_ACTIVE};
}}

/* NumberInput 自定义控件样式 */
QFrame#NumberInput {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {BG};
}}
QLineEdit#NumberInputEdit {{
    border: none;
    border-radius: 0;
    padding: 6px 10px;
    background: transparent;
    min-height: 22px;
}}
QLineEdit#NumberInputEdit:hover {{
    border: none;
}}
QLineEdit#NumberInputEdit:focus {{
    border: none;
}}
QToolButton#NumberInputBtnMinus, QToolButton#NumberInputBtnPlus {{
    border: none;
    border-left: 1px solid {BORDER};
    background: transparent;
    width: 30px;
    min-height: 28px;
    padding: 0;
}}
QToolButton#NumberInputBtnPlus {{
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
}}
QToolButton#NumberInputBtnMinus:hover, QToolButton#NumberInputBtnPlus:hover {{
    background: {PRIMARY_SOFT};
}}
QToolButton#NumberInputBtnMinus:pressed, QToolButton#NumberInputBtnPlus:pressed {{
    background: {PRIMARY_SOFT_2};
}}
QToolButton#NumberInputBtnMinus:disabled, QToolButton#NumberInputBtnPlus:disabled {{
    background: transparent;
}}

/* ── ScrollArea：viewport 透明，让页面背景透出 ── */
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QWidget#SettingsWrapper {{
    background: transparent;
}}

QCheckBox {{ spacing: 8px; color: {TEXT}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1.5px solid {BORDER_STRONG};
    border-radius: 4px;
    background: {BG};
}}
QCheckBox::indicator:hover {{ border-color: {PRIMARY}; }}
QCheckBox::indicator:checked {{
    background: {PRIMARY};
    border-color: {PRIMARY};
}}

/* ── 列表 / 表格 ──────────────────────── */
QListWidget, QTableWidget, QTreeWidget {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    background: {BG};
    outline: none;
    gridline-color: transparent;
}}
QListWidget::item {{
    padding: 11px 14px;
    border-bottom: 1px solid {BG_ALT};
    color: {TEXT_SECONDARY};
}}
QListWidget::item:hover {{
    background: {BG_HOVER};
}}
QListWidget::item:selected {{
    background: {PRIMARY_SOFT};
    color: {TEXT};
}}

QTableWidget {{
    selection-background-color: {PRIMARY_SOFT};
    selection-color: {TEXT};
}}
QTableWidget::item {{
    padding: 10px 8px;
    border-bottom: 1px solid {BG_ALT};
}}
QTableWidget::item:selected {{
    background: {PRIMARY_SOFT};
    color: {TEXT};
}}
QHeaderView::section {{
    background: {BG_ALT};
    color: {TEXT_SECONDARY};
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-weight: 600;
    font-size: 12px;
}}
QHeaderView::section:first {{ border-top-left-radius: 10px; }}
QHeaderView::section:last {{ border-top-right-radius: 10px; }}

/* ── 状态徽章 ────────────────────────── */
QLabel#BadgeOn {{
    background: {PRIMARY_SOFT};
    color: {PRIMARY_ACTIVE};
    border: 1px solid {PRIMARY_SOFT_2};
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#BadgeOff {{
    background: {BG_ALT};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
}}

/* ── 滚动条 ───────────────────────────── */
QScrollBar:vertical {{
    border: none; background: transparent; width: 10px; margin: 4px 2px;
}}
QScrollBar::handle:vertical {{
    background: #cbd5e1;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #94a3b8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QScrollBar:horizontal {{
    border: none; background: transparent; height: 10px; margin: 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background: #cbd5e1;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: #94a3b8; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── 状态栏 ───────────────────────────── */
QStatusBar {{
    background: {BG};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
    padding: 4px 12px;
    font-size: 12px;
}}
QStatusBar::item {{ border: none; }}

/* ── Tab ──────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 12px;
    top: 8px;
    background: {BG};
}}
QTabWidget::tab-bar {{
    left: 4px;
}}
QTabBar {{
    qproperty-drawBase: 0;
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    padding: 10px 18px;
    color: {TEXT_MUTED};
    border-bottom: 2px solid transparent;
    font-weight: 500;
    margin-right: 4px;
    margin-bottom: 8px;
}}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTabBar::tab:selected {{
    color: {PRIMARY_HOVER};
    border-bottom: 2px solid {PRIMARY};
    font-weight: 600;
}}

/* ── Splitter ─────────────────────────── */
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QSplitter::handle:hover {{ background: {PRIMARY_SOFT_2}; }}

/* ── Form 标签 ────────────────────────── */
QFormLayout QLabel {{
    color: {TEXT_SECONDARY};
    font-weight: 500;
}}

/* ── 日历弹窗 ────────────────────────── */
QCalendarWidget QToolButton {{
    color: {TEXT};
    background: transparent;
    padding: 6px;
    border-radius: 6px;
}}
QCalendarWidget QToolButton:hover {{
    background: {PRIMARY_SOFT};
}}
QCalendarWidget QAbstractItemView:enabled {{
    color: {TEXT};
    selection-background-color: {PRIMARY};
    selection-color: white;
    outline: none;
}}
"""
