"""桌面客户端入口：单例守卫 + 应用图标 + 主窗口。"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from ..config import load_config
from ..storage import Storage
from .assets import icon_path
from .main_window import MainWindow
from .singleton import SingleInstance
from .theme import QSS


def _load_app_icon() -> QIcon:
    """加载多尺寸应用图标。

    若资源缺失（首次拉取代码还没生成 logo），返回空 QIcon，主窗口会回退到
    运行时画的占位图。
    """
    icon = QIcon()
    found = False
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        p = icon_path(f"logo_{size}.png")
        if p.exists():
            icon.addFile(str(p))
            found = True
    ico = icon_path("logo.ico")
    if ico.exists():
        icon.addFile(str(ico))
        found = True
    return icon if found else QIcon()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("report-assistant")
    app.setOrganizationName("report-assistant")
    app.setQuitOnLastWindowClosed(False)

    # ── 单例守卫 ──────────────────────────────────
    guard = SingleInstance(parent=app)
    holder: dict = {}  # 用 dict 持有 win 引用，供 lambda 闭包访问

    def _activate_existing() -> None:
        win = holder.get("win")
        if win is None:
            return
        win.show()
        win.setWindowState(
            (win.windowState() & ~Qt.WindowState.WindowMinimized)
            | Qt.WindowState.WindowActive
        )
        win.raise_()
        win.activateWindow()

    if not guard.try_acquire(on_second_instance=_activate_existing):
        print("已有实例在运行，已激活既有窗口。")
        return 0

    # ── 应用级配置 ────────────────────────────────
    icon = _load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    f = QFont()
    f.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
    app.setFont(f)
    app.setStyleSheet(QSS)

    cfg = load_config()
    storage = Storage(Path(cfg.db_path).expanduser())

    win = MainWindow(cfg, storage, app_icon=icon)
    holder["win"] = win
    win.resize(1200, 780)
    win.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
