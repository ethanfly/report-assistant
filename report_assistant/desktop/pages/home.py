"""首页：状态卡片 + 快速操作 + 最近工作流水。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from ...config import save_config
from ...generator import collect_data
from ...screenshot import list_monitors
from ..workers import CaptureWorker, start_in_thread

if TYPE_CHECKING:
    from ..main_window import MainWindow


def _stat_card(icon: str, label: str, value: str = "0", primary: bool = False) -> QFrame:
    """统计卡：左上图标 + 标签，下方大数字。"""
    f = QFrame()
    f.setObjectName("StatCard")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(10)

    head = QHBoxLayout()
    head.setSpacing(8)
    ico = QLabel(icon)
    ico.setObjectName("StatIcon")
    lab = QLabel(label)
    lab.setObjectName("StatLabel")
    head.addWidget(ico)
    head.addWidget(lab)
    head.addStretch(1)
    lay.addLayout(head)

    n = QLabel(value)
    n.setObjectName("StatNumberPrimary" if primary else "StatNumber")
    lay.addWidget(n)
    return f


class HomePage(QWidget):
    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 20)
        root.setSpacing(18)

        # 标题
        title = QLabel("首页")
        title.setObjectName("PageTitle")
        sub = QLabel("你只管工作，日报交给我。静默记录工作轨迹，AI 帮你写好每一份日报、周报、月报。")
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        # 数据卡片（4 列）
        cards_row = QGridLayout()
        cards_row.setSpacing(14)
        self.card_today_commits = _stat_card("🧬", "今日提交", "0", primary=True)
        self.card_today_shots = _stat_card("📸", "今日截图分析", "0", primary=True)
        self.card_total_reports = _stat_card("📄", "已生成报告", "0")
        self.card_status = _stat_card("⚡", "监听状态", "未启动")
        cards_row.addWidget(self.card_today_commits, 0, 0)
        cards_row.addWidget(self.card_today_shots, 0, 1)
        cards_row.addWidget(self.card_total_reports, 0, 2)
        cards_row.addWidget(self.card_status, 0, 3)
        for c in range(4):
            cards_row.setColumnStretch(c, 1)
        root.addLayout(cards_row)

        # 快速操作卡片
        quick = QFrame()
        quick.setObjectName("Card")
        ql = QVBoxLayout(quick)
        ql.setContentsMargins(22, 18, 22, 18)
        ql.setSpacing(14)
        head = QLabel("快速操作")
        head.setObjectName("CardTitle")
        head_desc = QLabel("一键开启监听 / 抓取当前屏幕 / 生成今日日报")
        head_desc.setObjectName("CardDesc")
        ql.addWidget(head)
        ql.addWidget(head_desc)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_watch = QPushButton("● 开始监听")
        self.btn_watch.setObjectName("PrimaryButton")
        self.btn_watch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_watch.clicked.connect(self._toggle_watch)

        self.btn_capture = QPushButton("📸 立即截图分析")
        self.btn_capture.setObjectName("SecondaryButton")
        self.btn_capture.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_capture.clicked.connect(self._capture_once)

        self.btn_quick_daily = QPushButton("📝 生成今日日报")
        self.btn_quick_daily.setObjectName("SecondaryButton")
        self.btn_quick_daily.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quick_daily.clicked.connect(self._quick_daily)

        self.btn_quick_weekly = QPushButton("📊 生成本周周报")
        self.btn_quick_weekly.setObjectName("SecondaryButton")
        self.btn_quick_weekly.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quick_weekly.clicked.connect(self._quick_weekly)

        self.btn_sync_git = QPushButton("🔄 立即同步 Git")
        self.btn_sync_git.setObjectName("SecondaryButton")
        self.btn_sync_git.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync_git.clicked.connect(self._sync_git_now)

        for b in (self.btn_watch, self.btn_capture, self.btn_sync_git,
                  self.btn_quick_daily, self.btn_quick_weekly):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        ql.addLayout(btn_row)
        root.addWidget(quick)

        # 显示器选择卡片
        mon_card = QFrame()
        mon_card.setObjectName("Card")
        ml = QVBoxLayout(mon_card)
        ml.setContentsMargins(22, 18, 22, 18)
        ml.setSpacing(10)
        mh = QHBoxLayout()
        mt = QLabel("显示器")
        mt.setObjectName("CardTitle")
        mh.addWidget(mt)
        mh.addStretch(1)
        md = QLabel("选择监控的屏幕。多显示器时只采集所选屏幕。")
        md.setObjectName("CardDesc")
        mh.addWidget(md)
        ml.addLayout(mh)
        self.monitor_row = QHBoxLayout()
        self.monitor_row.setSpacing(10)
        ml.addLayout(self.monitor_row)
        self._monitor_buttons: list[QPushButton] = []
        self._build_monitors()
        root.addWidget(mon_card)

        # 最近工作流水
        recent_card = QFrame()
        recent_card.setObjectName("Card")
        rl = QVBoxLayout(recent_card)
        rl.setContentsMargins(20, 16, 20, 16)
        rl.setSpacing(10)
        rh = QHBoxLayout()
        rt = QLabel("最近工作流水（今日）")
        rt.setObjectName("CardTitle")
        rh.addWidget(rt)
        rh.addStretch(1)
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setObjectName("SecondaryButton")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh)
        rh.addWidget(self.btn_refresh)
        rl.addLayout(rh)

        self.list_recent = QListWidget()
        self.list_recent.setMinimumHeight(220)
        rl.addWidget(self.list_recent)
        root.addWidget(recent_card, 1)

        # 全局信号联动
        self.main.capture_added.connect(lambda _p: self.refresh())
        self.main.git_synced.connect(lambda _n: self.refresh())

    # ── 数据刷新 ─────────────────────────────────────
    def refresh(self) -> None:
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        # 主动拉今天的 git（collect_data 内部幂等入库），
        # 让首页统计反映最新的 commit 而不是只看历史 SQLite。
        # git_collector 对单个仓库失败已有容错，这里再兜一层避免影响 UI。
        try:
            collect_data(self.main.cfg, self.main.storage, "daily", anchor=now,
                         include_screenshots=False)
        except Exception as e:
            self.main.statusBar().showMessage(f"Git 同步失败: {e}", 3000)

        logs = self.main.storage.list_work_logs(start, end)
        commits = [l for l in logs if l["source"] == "git"]
        shots = [l for l in logs if l["source"] == "screenshot"]
        reports = self.main.storage.list_reports(limit=999)

        self._set_stat(self.card_today_commits, str(len(commits)))
        self._set_stat(self.card_today_shots, str(len(shots)))
        self._set_stat(self.card_total_reports, str(len(reports)))
        self._set_stat(
            self.card_status,
            "监听中" if self.main.is_watching() else "未启动",
        )

        self.list_recent.clear()
        for log in reversed(logs[-30:]):
            ts = (log.get("ts") or "")[:16].replace("T", " ")
            cat = log.get("category") or ("Git" if log["source"] == "git" else "其他")
            tag = "[Git]" if log["source"] == "git" else "[屏幕]"
            text = f"{ts}  {tag} [{cat}] {log['title']}"
            QListWidgetItem(text, self.list_recent)
        if self.list_recent.count() == 0:
            QListWidgetItem("暂无记录。点击\"立即截图分析\"或\"开始监听\"采集数据。", self.list_recent)

        # 同步按钮状态
        self.btn_watch.setText("■ 停止监听" if self.main.is_watching() else "● 开始监听")

    def _set_stat(self, card: QFrame, value: str) -> None:
        for child in card.findChildren(QLabel):
            if child.objectName() in ("StatNumber", "StatNumberPrimary"):
                child.setText(value)
                return

    # ── 操作 ─────────────────────────────────────────
    def _toggle_watch(self) -> None:
        if self.main.is_watching():
            self.main.stop_watch()
        else:
            self.main.start_watch()
        self.refresh()

    def _capture_once(self) -> None:
        if not self.main.cfg.llm.api_key:
            QMessageBox.warning(self, "未配置", "请先到\"设置\"中填写 LLM API Key。")
            return
        self.btn_capture.setEnabled(False)
        self.btn_capture.setText("分析中…")
        worker = CaptureWorker(self.main.cfg, self.main.storage)
        worker.finished.connect(self._on_capture_ok)
        worker.failed.connect(self._on_capture_fail)
        start_in_thread(self.main, worker)

    def _on_capture_ok(self, payload: dict) -> None:
        self.btn_capture.setEnabled(True)
        self.btn_capture.setText("立即截图分析")
        self.refresh()
        self.main.statusBar().showMessage(
            f"已记录: [{payload['category']}] {payload['title']}", 4000
        )

    def _on_capture_fail(self, msg: str) -> None:
        self.btn_capture.setEnabled(True)
        self.btn_capture.setText("立即截图分析")
        QMessageBox.warning(self, "截图分析失败", msg)

    def _quick_daily(self) -> None:
        self.main.switch_page("reports")
        self.main.page_reports.trigger_quick_generate("daily")

    def _quick_weekly(self) -> None:
        self.main.switch_page("reports")
        self.main.page_reports.trigger_quick_generate("weekly")

    def _sync_git_now(self) -> None:
        self.main.sync_git()
        self.refresh()

    # ── 显示器选择 ────────────────────────────────
    def _build_monitors(self) -> None:
        while self.monitor_row.count():
            item = self.monitor_row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._monitor_buttons.clear()

        try:
            mons = list_monitors()
        except Exception:
            mons = []
        if not mons:
            tip = QLabel("无法枚举显示器（mss 未安装或当前环境不支持）")
            tip.setObjectName("CardDesc")
            self.monitor_row.addWidget(tip)
            self.monitor_row.addStretch(1)
            return

        current = int(getattr(self.main.cfg.screenshot, "monitor_index", 1) or 0)
        for m in mons:
            btn = QPushButton(m["label"])
            btn.setCheckable(True)
            btn.setObjectName("MonitorButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setChecked(m["index"] == current)
            btn.clicked.connect(lambda _=False, idx=m["index"]: self._select_monitor(idx))
            self.monitor_row.addWidget(btn)
            self._monitor_buttons.append(btn)
        self.monitor_row.addStretch(1)

    def _select_monitor(self, idx: int) -> None:
        self.main.cfg.screenshot.monitor_index = int(idx)
        try:
            save_config(self.main.cfg)
        except Exception as e:
            self.main.statusBar().showMessage(f"保存监视器配置失败: {e}", 4000)
            return
        self._build_monitors()
        self.main.statusBar().showMessage(
            f"已切换到 {self._monitor_label(idx)}", 3000,
        )

    def _monitor_label(self, idx: int) -> str:
        for m in list_monitors():
            if m["index"] == idx:
                return m["label"]
        return f"屏幕 {idx}"

    # ── 生命周期钩子 ─────────────────────────────────
    def on_activated(self) -> None:
        self.refresh()

    def on_config_changed(self) -> None:
        self.refresh()
