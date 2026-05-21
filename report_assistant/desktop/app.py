"""桌面客户端入口：单例守卫 + 应用图标 + 主窗口。"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, qInstallMessageHandler, QtMsgType
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from ..config import load_config
from ..logging_setup import bootstrap
from ..storage import Storage
from .assets import icon_path
from .main_window import MainWindow
from .singleton import SingleInstance
from .theme import QSS


logger = logging.getLogger("desktop.app")


def _qt_message_handler(mode: QtMsgType, ctx, message: str) -> None:
    """把 Qt 内部的消息也接到 Python logging。"""
    level = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
        QtMsgType.QtSystemMsg: logging.WARNING,
    }.get(mode, logging.INFO)
    logging.getLogger("qt").log(level, "%s", message)


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
    # 源码直跑时也需要日志/异常钩子；entry.py 已经调过一次，bootstrap 是幂等的
    bootstrap()
    qInstallMessageHandler(_qt_message_handler)
    logger.info("应用启动 (frozen=%s)", getattr(sys, "frozen", False))

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("report-assistant")
    app.setApplicationDisplayName("小T日报助手")
    app.setOrganizationName("report-assistant")
    # 关键：托盘运行时即使所有窗口都关了，事件循环也不能退出
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
        logger.info("已有实例在运行，已发送激活请求并退出。")
        return 0

    # ── 应用级配置 ────────────────────────────────
    icon = _load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    f = QFont()
    f.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
    app.setFont(f)
    app.setStyleSheet(QSS)

    try:
        cfg = load_config()
    except Exception:
        logger.exception("加载配置失败，使用默认配置启动")
        from ..config import Config
        cfg = Config()

    try:
        storage = Storage(Path(cfg.db_path).expanduser())
    except Exception:
        logger.exception("初始化存储失败")
        raise

    win = MainWindow(cfg, storage, app_icon=icon)
    holder["win"] = win
    win.resize(1200, 780)
    win.show()

    try:
        return app.exec()
    except Exception:
        logger.exception("Qt 事件循环异常退出")
        return 1


if __name__ == "__main__":
    sys.exit(main())
