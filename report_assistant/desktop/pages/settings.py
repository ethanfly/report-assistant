"""设置页：分 Tab 显示各模块（LLM / Git / 截图 / 报告）。

保存写入 ~/.report-assistant/config.yml。
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from ...autostart import is_autostart_enabled, set_autostart
from ...config import LLMConfig, save_config
from ...screenshot import list_monitors
from ...templates import TEMPLATES
from ..widgets import NumberInput
from ..workers import TestConnectionWorker, start_in_thread

if TYPE_CHECKING:
    from ..main_window import MainWindow


def _wrap_tab(form: QFormLayout, *extra_layouts) -> QWidget:
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(24, 22, 24, 22)
    outer.setSpacing(14)
    outer.addLayout(form)
    for lay in extra_layouts:
        outer.addLayout(lay)
    outer.addStretch(1)
    return page


class SettingsPage(QWidget):
    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        wrapper = QWidget()
        wrapper.setObjectName("SettingsWrapper")
        wl = QHBoxLayout(wrapper)
        wl.setContentsMargins(28, 28, 28, 28)
        wl.setSpacing(0)
        wl.addStretch(1)
        inner = QWidget()
        inner.setMaximumWidth(880)
        wl.addWidget(inner, 4)
        wl.addStretch(1)
        scroll.setWidget(wrapper)

        root = QVBoxLayout(inner)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        title = QLabel("设置")
        title.setObjectName("PageTitle")
        sub = QLabel("数据仅保存在本地。API Key 写入配置文件，截图分析后默认立即删除。")
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_llm_tab(), "LLM")
        self.tabs.addTab(self._build_git_tab(), "Git")
        self.tabs.addTab(self._build_screenshot_tab(), "截图")
        self.tabs.addTab(self._build_report_tab(), "报告 & 个人")
        self.tabs.addTab(self._build_system_tab(), "系统")

        # 底部操作
        action_row = QHBoxLayout()
        self.btn_save = QPushButton("保存配置")
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self._save)
        action_row.addWidget(self.btn_save)

        self.btn_reload = QPushButton("放弃修改")
        self.btn_reload.setObjectName("SecondaryButton")
        self.btn_reload.clicked.connect(self._load_from_cfg)
        action_row.addWidget(self.btn_reload)

        action_row.addStretch(1)
        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("CardDesc")
        action_row.addWidget(self.lbl_status)
        root.addLayout(action_row)

        self._load_from_cfg()

    # ── Tab 构造 ──────────────────────────────────
    def _build_llm_tab(self) -> QWidget:
        form = QFormLayout()
        form.setSpacing(12)
        self.ed_provider = QLineEdit()
        self.ed_base_url = QLineEdit()
        self.ed_api_key = QLineEdit()
        self.ed_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_model = QLineEdit()
        self.ed_vision_model = QLineEdit()
        form.addRow("Provider", self.ed_provider)
        form.addRow("Base URL", self.ed_base_url)
        form.addRow("API Key", self.ed_api_key)
        form.addRow("文本模型", self.ed_model)
        form.addRow("视觉模型", self.ed_vision_model)

        test_row = QHBoxLayout()
        self.btn_test_llm = QPushButton("测试连接")
        self.btn_test_llm.setObjectName("SecondaryButton")
        self.btn_test_llm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test_llm.clicked.connect(self._test_llm_connection)
        test_row.addWidget(self.btn_test_llm)
        self.lbl_test_result = QLabel("")
        self.lbl_test_result.setObjectName("CardDesc")
        self.lbl_test_result.setWordWrap(True)
        test_row.addWidget(self.lbl_test_result, 1)
        form.addRow("", test_row)

        return _wrap_tab(form)

    def _build_git_tab(self) -> QWidget:
        form = QFormLayout()
        form.setSpacing(12)

        repo_row = QHBoxLayout()
        self.list_repos = QListWidget()
        self.list_repos.setMinimumHeight(120)
        self.list_repos.setMaximumHeight(180)
        repo_row.addWidget(self.list_repos, 1)
        col = QVBoxLayout()
        btn_add = QPushButton("添加仓库…")
        btn_add.setObjectName("SecondaryButton")
        btn_add.clicked.connect(self._add_repo)
        btn_remove = QPushButton("移除")
        btn_remove.setObjectName("DangerButton")
        btn_remove.clicked.connect(self._remove_repo)
        col.addWidget(btn_add)
        col.addWidget(btn_remove)
        col.addStretch(1)
        repo_row.addLayout(col)
        form.addRow("仓库", repo_row)

        self.ed_emails = QLineEdit()
        self.ed_emails.setPlaceholderText("多个邮箱用逗号分隔")
        self.ed_names = QLineEdit()
        self.ed_names.setPlaceholderText("多个姓名用逗号分隔")
        self.spin_git_poll = NumberInput(
            minimum=0, maximum=7200, value=600, suffix=" 秒",
            special_value_text="已关闭",
        )
        self.chk_merges = QCheckBox("包含 merge commits")
        form.addRow("作者邮箱", self.ed_emails)
        form.addRow("作者姓名", self.ed_names)
        form.addRow("自动同步间隔", self.spin_git_poll)
        form.addRow("", self.chk_merges)

        return _wrap_tab(form)

    def _build_screenshot_tab(self) -> QWidget:
        form = QFormLayout()
        form.setSpacing(12)
        self.chk_shot_enabled = QCheckBox("启用截图分析")
        self.spin_interval = NumberInput(
            minimum=30, maximum=7200, value=600, suffix=" 秒",
        )
        self.spin_idle = NumberInput(
            minimum=0, maximum=7200, value=300, suffix=" 秒",
            special_value_text="不检测",
        )
        self.chk_keep = QCheckBox("分析后保留原始图片（默认关闭，分析完即删）")
        self.chk_auto_start = QCheckBox("应用启动后自动开始监听")
        self.ed_shot_dir = QLineEdit()

        self.combo_monitor = QComboBox()
        self._refresh_monitor_combo()

        form.addRow("", self.chk_shot_enabled)
        form.addRow("监听间隔", self.spin_interval)
        form.addRow("空闲跳过阈值", self.spin_idle)
        form.addRow("监控显示器", self.combo_monitor)
        form.addRow("", self.chk_keep)
        form.addRow("", self.chk_auto_start)
        form.addRow("截图目录", self.ed_shot_dir)

        tip = QLabel("空闲跳过：用户连续 N 秒无键鼠活动时自动跳过本轮截图，"
                     "判定为不在工作中，节省调用成本。仅 Windows 可靠。")
        tip.setObjectName("CardDesc")
        tip.setWordWrap(True)
        tip_row = QVBoxLayout()
        tip_row.addWidget(tip)
        return _wrap_tab(form, tip_row)

    def _build_report_tab(self) -> QWidget:
        form = QFormLayout()
        form.setSpacing(12)
        self.combo_default_tpl = QComboBox()
        for name, tpl in TEMPLATES.items():
            self.combo_default_tpl.addItem(f"{tpl.title}（{name}）", name)
        self.ed_user = QLineEdit()
        self.ed_team = QLineEdit()
        form.addRow("默认模板", self.combo_default_tpl)
        form.addRow("汇报人", self.ed_user)
        form.addRow("团队", self.ed_team)
        return _wrap_tab(form)

    def _build_system_tab(self) -> QWidget:
        form = QFormLayout()
        form.setSpacing(12)
        self.chk_autostart = QCheckBox("开机自启（登录系统时自动启动日报助手）")
        self.spin_keep_days = NumberInput(
            minimum=0, maximum=3650, value=60, suffix=" 天",
            special_value_text="不自动清理",
        )
        form.addRow("", self.chk_autostart)
        form.addRow("自动清理 N 天前的数据", self.spin_keep_days)

        self.lbl_db_stats = QLabel("")
        self.lbl_db_stats.setObjectName("CardDesc")
        form.addRow("当前数据库", self.lbl_db_stats)

        cleanup_row = QHBoxLayout()
        self.btn_cleanup_old = QPushButton("立即清理（按上方天数）")
        self.btn_cleanup_old.setObjectName("SecondaryButton")
        self.btn_cleanup_old.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cleanup_old.clicked.connect(self._cleanup_old)
        cleanup_row.addWidget(self.btn_cleanup_old)

        self.btn_cleanup_all = QPushButton("清空所有缓存")
        self.btn_cleanup_all.setObjectName("DangerButton")
        self.btn_cleanup_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cleanup_all.clicked.connect(self._cleanup_all)
        cleanup_row.addWidget(self.btn_cleanup_all)
        cleanup_row.addStretch(1)
        form.addRow("", cleanup_row)

        tip = QLabel("说明：开机自启写入用户级配置（Windows 注册表 / macOS LaunchAgent /"
                     " Linux XDG autostart），不需要管理员权限。手动清理立即生效；"
                     "自动清理在每次启动时检查。")
        tip.setObjectName("CardDesc")
        tip.setWordWrap(True)
        tip_row = QVBoxLayout()
        tip_row.addWidget(tip)
        return _wrap_tab(form, tip_row)

    def _refresh_db_stats(self) -> None:
        try:
            stats = self.main.storage.stats()
            self.lbl_db_stats.setText(
                f"{stats['work_logs']} 条工作记录 · {stats['reports']} 份报告"
            )
        except Exception:
            self.lbl_db_stats.setText("(无法读取)")

    def _refresh_monitor_combo(self) -> None:
        self.combo_monitor.clear()
        try:
            mons = list_monitors()
        except Exception:
            mons = []
        if not mons:
            self.combo_monitor.addItem("（无法枚举显示器）", -1)
            return
        for m in mons:
            self.combo_monitor.addItem(m["label"], m["index"])

    # ── 加载 / 保存 ────────────────────────────────
    def _load_from_cfg(self) -> None:
        cfg = self.main.cfg
        self.ed_provider.setText(cfg.llm.provider)
        self.ed_base_url.setText(cfg.llm.base_url)
        self.ed_api_key.setText(cfg.llm.api_key)
        self.ed_model.setText(cfg.llm.model)
        self.ed_vision_model.setText(cfg.llm.vision_model)

        self.list_repos.clear()
        for r in cfg.git.repos:
            QListWidgetItem(r, self.list_repos)
        self.ed_emails.setText(", ".join(cfg.git.author_emails))
        self.ed_names.setText(", ".join(cfg.git.author_names))
        self.chk_merges.setChecked(cfg.git.include_merges)
        self.spin_git_poll.setValue(
            int(getattr(cfg.git, "poll_interval_seconds", 600) or 0)
        )

        self.chk_shot_enabled.setChecked(cfg.screenshot.enabled)
        self.spin_interval.setValue(int(cfg.screenshot.interval_seconds))
        self.spin_idle.setValue(
            int(getattr(cfg.screenshot, "idle_skip_seconds", 0) or 0)
        )
        self.chk_keep.setChecked(cfg.screenshot.keep_after_analysis)
        self.chk_auto_start.setChecked(cfg.screenshot.auto_start)
        self.ed_shot_dir.setText(cfg.screenshot.output_dir)
        self._refresh_monitor_combo()
        target_idx = int(getattr(cfg.screenshot, "monitor_index", 1) or 0)
        for i in range(self.combo_monitor.count()):
            if self.combo_monitor.itemData(i) == target_idx:
                self.combo_monitor.setCurrentIndex(i)
                break

        idx = self.combo_default_tpl.findData(cfg.report.default_template)
        if idx >= 0:
            self.combo_default_tpl.setCurrentIndex(idx)
        self.ed_user.setText(cfg.report.user_name)
        self.ed_team.setText(cfg.report.team)

        # 系统 Tab
        self.chk_autostart.setChecked(
            bool(getattr(cfg.app, "auto_launch_on_boot", False))
            or is_autostart_enabled()
        )
        self.spin_keep_days.setValue(
            int(getattr(cfg.app, "cleanup_keep_days", 60) or 0)
        )
        self._refresh_db_stats()

        self.lbl_status.setText("")

    def _save(self) -> None:
        cfg = self.main.cfg
        cfg.llm.provider = self.ed_provider.text().strip()
        cfg.llm.base_url = self.ed_base_url.text().strip() or "https://api.openai.com/v1"
        cfg.llm.api_key = self.ed_api_key.text().strip()
        cfg.llm.model = self.ed_model.text().strip() or "gpt-4o-mini"
        cfg.llm.vision_model = self.ed_vision_model.text().strip() or cfg.llm.model

        cfg.git.repos = [
            self.list_repos.item(i).text().strip()
            for i in range(self.list_repos.count())
            if self.list_repos.item(i).text().strip()
        ]
        cfg.git.author_emails = [s.strip() for s in self.ed_emails.text().split(",") if s.strip()]
        cfg.git.author_names = [s.strip() for s in self.ed_names.text().split(",") if s.strip()]
        cfg.git.include_merges = self.chk_merges.isChecked()
        cfg.git.poll_interval_seconds = int(self.spin_git_poll.value())

        cfg.screenshot.enabled = self.chk_shot_enabled.isChecked()
        cfg.screenshot.interval_seconds = int(self.spin_interval.value())
        cfg.screenshot.idle_skip_seconds = int(self.spin_idle.value())
        cfg.screenshot.keep_after_analysis = self.chk_keep.isChecked()
        cfg.screenshot.auto_start = self.chk_auto_start.isChecked()
        cfg.screenshot.output_dir = self.ed_shot_dir.text().strip() or cfg.screenshot.output_dir
        mon_idx = self.combo_monitor.currentData()
        if isinstance(mon_idx, int) and mon_idx >= 0:
            cfg.screenshot.monitor_index = mon_idx

        cfg.report.default_template = self.combo_default_tpl.currentData()
        cfg.report.user_name = self.ed_user.text().strip()
        cfg.report.team = self.ed_team.text().strip()

        # 系统：开机自启 + 清理保留天数
        cfg.app.auto_launch_on_boot = self.chk_autostart.isChecked()
        cfg.app.cleanup_keep_days = int(self.spin_keep_days.value())
        try:
            set_autostart(cfg.app.auto_launch_on_boot)
        except Exception as e:
            QMessageBox.warning(self, "开机自启设置失败", str(e))

        try:
            path = save_config(cfg)
            self.lbl_status.setText(f"已保存到 {path}")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))
            return

        self.main.config_changed.emit()

    # ── 仓库管理 ────────────────────────────────
    def _add_repo(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 Git 仓库根目录")
        if not path:
            return
        if not (Path(path) / ".git").exists():
            ret = QMessageBox.question(
                self, "确认", f"{path} 似乎不是 git 仓库根目录（未发现 .git/）。仍要添加吗？",
            )
            if ret != QMessageBox.StandardButton.Yes:
                return
        existing = {self.list_repos.item(i).text() for i in range(self.list_repos.count())}
        if path in existing:
            return
        QListWidgetItem(path, self.list_repos)

    def _remove_repo(self) -> None:
        for item in self.list_repos.selectedItems():
            self.list_repos.takeItem(self.list_repos.row(item))

    # ── LLM 连通性测试 ──────────────────────────────
    def _test_llm_connection(self) -> None:
        cfg = LLMConfig(
            provider=self.ed_provider.text().strip(),
            base_url=self.ed_base_url.text().strip() or "https://api.openai.com/v1",
            api_key=self.ed_api_key.text().strip(),
            model=self.ed_model.text().strip() or "gpt-4o-mini",
            vision_model=self.ed_vision_model.text().strip() or "gpt-4o-mini",
            temperature=self.main.cfg.llm.temperature,
            timeout=self.main.cfg.llm.timeout,
        )
        if not cfg.api_key:
            self.lbl_test_result.setText("⚠ 请先填写 API Key")
            return
        self.btn_test_llm.setEnabled(False)
        self.btn_test_llm.setText("测试中…")
        self.lbl_test_result.setText("正在请求…")

        worker = TestConnectionWorker(cfg)
        worker.finished.connect(self._on_test_done)
        start_in_thread(self.main, worker)

    def _on_test_done(self, ok: bool, msg: str) -> None:
        self.btn_test_llm.setEnabled(True)
        self.btn_test_llm.setText("测试连接")
        prefix = "✓ " if ok else "✗ "
        self.lbl_test_result.setText(prefix + msg)

    # ── 数据清理 ──────────────────────────────────
    def _cleanup_old(self) -> None:
        days = int(self.spin_keep_days.value())
        if days <= 0:
            QMessageBox.information(self, "无需操作", "保留天数为 0，按定义不清理任何数据。")
            return
        ret = QMessageBox.question(
            self, "确认清理",
            f"将永久删除 {days} 天之前的所有工作记录与报告。继续？",
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            stats = self.main.cleanup_storage(before_days=days)
        except Exception as e:
            QMessageBox.warning(self, "清理失败", str(e))
            return
        self._refresh_db_stats()
        QMessageBox.information(
            self, "清理完成",
            f"已删除 {stats['work_logs']} 条工作记录 + {stats['reports']} 份报告。",
        )

    def _cleanup_all(self) -> None:
        ret = QMessageBox.warning(
            self, "危险操作",
            "将清空所有工作记录和已生成报告，且不可撤销。继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            stats = self.main.cleanup_storage(all_data=True)
        except Exception as e:
            QMessageBox.warning(self, "清理失败", str(e))
            return
        self._refresh_db_stats()
        QMessageBox.information(
            self, "已清空",
            f"删除 {stats['work_logs']} 条工作记录 + {stats['reports']} 份报告。",
        )

    # ── 生命周期钩子 ─────────────────────────────────
    def on_activated(self) -> None:
        self._load_from_cfg()

    def on_config_changed(self) -> None:
        self._load_from_cfg()
