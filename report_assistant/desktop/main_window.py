"""主窗口：左侧导航 + 右侧多页面 + 全局监听状态 + 系统托盘。"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QPainter, QPixmap, QColor
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox,
    QPushButton, QStackedWidget, QStatusBar, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from ..config import Config
from ..storage import Storage
from ..generator import collect_data
from .assets import icon_path
from .pages.home import HomePage
from .pages.reports import ReportsPage
from .pages.settings import SettingsPage
from .pages.timeline import TimelinePage
from .theme import PRIMARY
from .workers import WatchWorker, start_in_thread


NAV_ITEMS = [
    ("home", "🏠  首页", "概览与快速操作"),
    ("timeline", "🕒  时间线", "Git 提交与截图记录"),
    ("reports", "📄  报告", "生成日报/周报/月报"),
    ("settings", "⚙  设置", "LLM、Git、截图与个人信息"),
]


def _make_dot_icon(color: str = PRIMARY, size: int = 32) -> QIcon:
    """没有 logo 资源时，用纯色圆点作为应用图标。"""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 2, size - 4, size - 4)
    p.end()
    return QIcon(pix)


class Sidebar(QWidget):
    """左侧导航。"""

    nav_changed = Signal(str)  # 发出页面 key

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo 区：真实 logo 图片 + 标题 + 副标题
        logo_row = QWidget()
        lr = QHBoxLayout(logo_row)
        lr.setContentsMargins(22, 22, 22, 0)
        lr.setSpacing(10)
        logo_label = QLabel()
        logo_label.setFixedSize(28, 28)
        logo_png = icon_path("logo_64.png")
        if logo_png.exists():
            pix = QPixmap(str(logo_png)).scaled(
                28, 28,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_label.setPixmap(pix)
        else:
            logo_label.setStyleSheet(f"background:{PRIMARY}; border-radius:8px;")
        title = QLabel("日报助手")
        title.setObjectName("SidebarLogo")
        title.setStyleSheet("padding: 0;")
        lr.addWidget(logo_label)
        lr.addWidget(title)
        lr.addStretch(1)
        layout.addWidget(logo_row)

        sub = QLabel("AI Daily Report")
        sub.setObjectName("SidebarLogoSub")
        layout.addWidget(sub)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for key, label, _desc in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.nav_changed.emit(k))
            layout.addWidget(btn)
            self._group.addButton(btn)
            self._buttons[key] = btn

        layout.addStretch(1)

        # 底部状态
        self.status_label = QLabel("监听已停止")
        self.status_label.setObjectName("BadgeOff")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(18, 12, 18, 18)
        wl.addWidget(self.status_label)
        layout.addWidget(wrap)

    def select(self, key: str) -> None:
        if key in self._buttons:
            self._buttons[key].setChecked(True)

    def set_watching(self, on: bool) -> None:
        if on:
            self.status_label.setText("● 监听中")
            self.status_label.setObjectName("BadgeOn")
        else:
            self.status_label.setText("○ 监听已停止")
            self.status_label.setObjectName("BadgeOff")
        # 重新应用样式
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)


class MainWindow(QMainWindow):
    """全局状态：cfg / storage / watch 状态。"""

    config_changed = Signal()  # 配置在 SettingsPage 保存后
    capture_added = Signal(dict)  # 单条截图记录入库后
    git_synced = Signal(int)  # 一次 git 同步完成后，附带本次入库的提交数

    def __init__(self, cfg: Config, storage: Storage, app_icon: Optional[QIcon] = None):
        super().__init__()
        self.setObjectName("MainWindow")
        self.setWindowTitle("日报助手 — AI 工作日报生成工具")
        self.app_icon = app_icon if (app_icon and not app_icon.isNull()) else _make_dot_icon()
        self.setWindowIcon(self.app_icon)

        self.cfg = cfg
        self.storage = storage
        self._watch_worker: Optional[WatchWorker] = None
        self._watch_thread = None

        # 中央：侧边栏 + 内容
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.nav_changed.connect(self.switch_page)
        root.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # 页面
        self.page_home = HomePage(self)
        self.page_timeline = TimelinePage(self)
        self.page_reports = ReportsPage(self)
        self.page_settings = SettingsPage(self)
        self._pages = {
            "home": self.page_home,
            "timeline": self.page_timeline,
            "reports": self.page_reports,
            "settings": self.page_settings,
        }
        for p in self._pages.values():
            self.stack.addWidget(p)

        # 状态栏
        self.setStatusBar(QStatusBar())
        self._update_status_hint()

        # 系统托盘
        self._init_tray()

        # 默认显示首页
        self.switch_page("home")

        # 配置变更通知
        self.config_changed.connect(self._on_config_changed)

        # Git 定时同步
        self._git_timer = QTimer(self)
        self._git_timer.timeout.connect(self.sync_git)
        self._restart_git_timer()

        # 启动后行为：自动清理过期数据
        self._auto_cleanup()

        # 启动后行为：若没配 API Key，引导到设置页；否则按用户设置自动开监听
        if not self.cfg.llm.api_key:
            self.switch_page("settings")
            self.statusBar().showMessage(
                "欢迎！请先填写 LLM API Key 并点击\"测试连接\"。", 0,
            )
        elif self.cfg.screenshot.auto_start:
            QTimer.singleShot(1000, self.start_watch)

    # ── 页面 ──────────────────────────────────────────
    def switch_page(self, key: str) -> None:
        if key not in self._pages:
            return
        self.stack.setCurrentWidget(self._pages[key])
        self.sidebar.select(key)
        # 给页面一次"激活"机会刷新数据
        page = self._pages[key]
        if hasattr(page, "on_activated"):
            page.on_activated()

    # ── Watch（全局，跨页面）────────────────────────────
    def is_watching(self) -> bool:
        return self._watch_worker is not None

    def start_watch(self, interval: Optional[int] = None) -> bool:
        if self.is_watching():
            return True
        if not self.cfg.llm.api_key:
            QMessageBox.warning(
                self, "未配置 API Key",
                "请先到\"设置\"中填写 LLM API Key。",
            )
            return False
        iv = interval or self.cfg.screenshot.interval_seconds
        worker = WatchWorker(self.cfg, self.storage, iv)
        worker.captured.connect(self._on_watch_captured)
        worker.failed.connect(self._on_watch_failed)
        worker.idle_skipped.connect(self._on_idle_skip)
        worker.stopped.connect(self._on_watch_stopped)
        self._watch_worker = worker
        self._watch_thread = start_in_thread(self, worker)
        self.sidebar.set_watching(True)
        if self.tray_action_toggle:
            self.tray_action_toggle.setText("停止监听")
        self.statusBar().showMessage(f"已开始监听，每 {iv}s 截图分析一次", 4000)
        return True

    def stop_watch(self) -> None:
        if self._watch_worker:
            self._watch_worker.stop()

    def _on_watch_captured(self, payload: dict) -> None:
        self.capture_added.emit(payload)
        self.statusBar().showMessage(
            f"已记录: [{payload['category']}] {payload['title']}", 3000,
        )

    def _on_watch_failed(self, msg: str) -> None:
        self.statusBar().showMessage(f"截图分析失败: {msg[:120]}", 6000)

    def _on_idle_skip(self, idle: int) -> None:
        mins = idle // 60
        self.statusBar().showMessage(
            f"检测到空闲 {mins} 分钟，已跳过本轮截图（用户可能不在工作中）", 5000,
        )

    def _on_watch_stopped(self) -> None:
        self._watch_worker = None
        self._watch_thread = None
        self.sidebar.set_watching(False)
        if self.tray_action_toggle:
            self.tray_action_toggle.setText("开始监听")
        self.statusBar().showMessage("监听已停止", 3000)

    def _on_config_changed(self) -> None:
        if self.is_watching():
            self.stop_watch()
        self._restart_git_timer()
        self._update_status_hint()
        for p in self._pages.values():
            if hasattr(p, "on_config_changed"):
                p.on_config_changed()

    def _update_status_hint(self) -> None:
        if not self.cfg.llm.api_key:
            self.statusBar().showMessage("提示：请先到\"设置\"中配置 LLM API Key")

    # ── Git 定时同步 ─────────────────────────────────
    def _restart_git_timer(self) -> None:
        """根据 cfg.git.poll_interval_seconds 启停定时器。"""
        self._git_timer.stop()
        interval = int(getattr(self.cfg.git, "poll_interval_seconds", 0) or 0)
        if interval > 0 and self.cfg.git.repos:
            # 最小 30s 防止刷屏
            self._git_timer.start(max(30, interval) * 1000)

    def sync_git(self) -> None:
        """主动同步今日 git 提交。失败不抛错，仅状态栏提示。"""
        from datetime import datetime
        try:
            _, _, commits, _ = collect_data(
                self.cfg, self.storage, "daily", anchor=datetime.now(),
                include_screenshots=False,
            )
            count = len(commits)
            self.git_synced.emit(count)
            if count:
                self.statusBar().showMessage(
                    f"Git 同步完成：今日 {count} 条提交", 3000,
                )
        except Exception as e:
            self.statusBar().showMessage(f"Git 同步失败: {e}", 5000)

    # ── 数据清理 ─────────────────────────────────────
    def _auto_cleanup(self) -> None:
        """启动时按 cfg.app.cleanup_keep_days 自动清理过期数据。"""
        from datetime import datetime, timedelta
        days = int(getattr(self.cfg.app, "cleanup_keep_days", 0) or 0)
        if days <= 0:
            return
        cutoff = datetime.now() - timedelta(days=days)
        try:
            stats = self.storage.purge_before(cutoff)
            total = stats["work_logs"] + stats["reports"]
            if total:
                self.statusBar().showMessage(
                    f"已自动清理 {days} 天前的数据："
                    f"{stats['work_logs']} 条记录 + {stats['reports']} 份报告",
                    5000,
                )
        except Exception as e:
            self.statusBar().showMessage(f"自动清理失败: {e}", 4000)

    def cleanup_storage(self, *, before_days: Optional[int] = None,
                        all_data: bool = False) -> dict:
        """手动清理数据库。返回删除条数。"""
        from datetime import datetime, timedelta
        if all_data:
            return self.storage.purge_all()
        if before_days is None or before_days <= 0:
            before_days = int(getattr(self.cfg.app, "cleanup_keep_days", 60) or 60)
        cutoff = datetime.now() - timedelta(days=before_days)
        return self.storage.purge_before(cutoff)

    # ── 系统托盘 ──────────────────────────────────────
    def _init_tray(self) -> None:
        self.tray_action_toggle: Optional[QAction] = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        self.tray = QSystemTrayIcon(self.app_icon, self)
        self.tray.setToolTip("日报助手")

        menu = QMenu(self)
        a_show = QAction("显示主窗口", self)
        a_show.triggered.connect(self._show_from_tray)
        menu.addAction(a_show)

        self.tray_action_toggle = QAction("开始监听", self)
        self.tray_action_toggle.triggered.connect(self._tray_toggle_watch)
        menu.addAction(self.tray_action_toggle)

        menu.addSeparator()
        a_quit = QAction("退出", self)
        a_quit.triggered.connect(self._quit_app)
        menu.addAction(a_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_toggle_watch(self) -> None:
        if self.is_watching():
            self.stop_watch()
        else:
            self.start_watch()

    def _quit_app(self) -> None:
        if self.is_watching():
            self.stop_watch()
        if self.tray:
            self.tray.hide()
        QGuiApplication.instance().quit()

    # ── 关闭：默认最小化到托盘 ─────────────────────────
    def closeEvent(self, event) -> None:
        if self.tray and self.tray.isVisible():
            self.hide()
            self.tray.showMessage(
                "日报助手", "已最小化到托盘，监听仍在后台运行。",
                QSystemTrayIcon.MessageIcon.Information, 2500,
            )
            event.ignore()
        else:
            self._quit_app()
            event.accept()
