"""报告页：生成日报/周报/月报，右侧实时预览；历史报告管理。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from ...templates import KIND_TITLE, TEMPLATES
from ...exporters import build_save_filter, export_report
from ..workers import ReportWorker, start_in_thread

if TYPE_CHECKING:
    from ..main_window import MainWindow


KIND_LABELS = [("日报", "daily"), ("周报", "weekly"), ("月报", "monthly")]

# Markdown 预览的内排版样式（通过 QTextDocument.setDefaultStyleSheet 注入）
_PREVIEW_CSS = """
body { font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
       color: #0f172a; line-height: 1.7; font-size: 14px; }
h1 { font-size: 22px; font-weight: 700; margin: 18px 0 12px;
     color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; }
h2 { font-size: 17px; font-weight: 700; margin: 18px 0 8px;
     color: #047857; }
h3 { font-size: 15px; font-weight: 600; margin: 14px 0 6px; color: #334155; }
p  { margin: 6px 0; color: #334155; }
ul, ol { margin: 6px 0 6px 18px; padding-left: 8px; color: #334155; }
li { margin: 4px 0; }
strong, b { color: #0f172a; font-weight: 600; }
code { background: #f1f5f9; color: #0f172a;
       padding: 1px 6px; border-radius: 4px;
       font-family: "Consolas", "Menlo", monospace; font-size: 12.5px; }
pre  { background: #f8fafc; border: 1px solid #e2e8f0;
       border-radius: 8px; padding: 12px; }
pre code { background: transparent; padding: 0; }
blockquote { border-left: 3px solid #10b981; background: #ecfdf5;
             padding: 8px 14px; margin: 8px 0; color: #047857;
             border-radius: 0 8px 8px 0; }
hr { border: 0; height: 1px; background: #e2e8f0; margin: 16px 0; }
a { color: #059669; text-decoration: none; }
"""


def _make_preview() -> QTextBrowser:
    """统一构造一个带美化样式的 Markdown 预览。"""
    pv = QTextBrowser()
    pv.setOpenExternalLinks(True)
    pv.document().setDefaultStyleSheet(_PREVIEW_CSS)
    pv.setStyleSheet(
        "QTextBrowser { border: 1px solid #e2e8f0; border-radius: 10px;"
        " padding: 8px 12px; background: #ffffff; }"
    )
    return pv


class GenerateTab(QWidget):
    """生成 Tab：左表单，右预览。"""

    def __init__(self, main: "MainWindow", parent_page: "ReportsPage"):
        super().__init__()
        self.main = main
        self.parent_page = parent_page

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # ── 左：表单 ───────────────────────────────
        form_wrap = QWidget()
        form_lay = QVBoxLayout(form_wrap)
        form_lay.setContentsMargins(20, 16, 20, 16)
        form_lay.setSpacing(12)

        form_card = QFrame()
        form_card.setObjectName("Card")
        fl = QVBoxLayout(form_card)
        fl.setContentsMargins(18, 16, 18, 16)
        fl.setSpacing(12)

        ttl = QLabel("生成报告")
        ttl.setObjectName("CardTitle")
        fl.addWidget(ttl)

        # 类型
        fl.addWidget(QLabel("类型"))
        self.combo_kind = QComboBox()
        for label, _ in KIND_LABELS:
            self.combo_kind.addItem(label)
        self.combo_kind.currentIndexChanged.connect(self._on_kind_changed)
        fl.addWidget(self.combo_kind)

        # 模板
        fl.addWidget(QLabel("模板"))
        self.combo_template = QComboBox()
        for name, tpl in TEMPLATES.items():
            self.combo_template.addItem(f"{tpl.title}（{name}）", name)
        idx = max(0, list(TEMPLATES.keys()).index(self.main.cfg.report.default_template))
        self.combo_template.setCurrentIndex(idx)
        fl.addWidget(self.combo_template)

        # 日期：日报选具体日期；周报点周内任意日期会自动定位到那一周；月报选月份
        self.lbl_date = QLabel("日期")
        fl.addWidget(self.lbl_date)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._update_period_hint)
        fl.addWidget(self.date_edit)

        # 实际时间范围提示
        self.lbl_period = QLabel("")
        self.lbl_period.setObjectName("CardDesc")
        fl.addWidget(self.lbl_period)
        self._on_kind_changed(0)

        # 备注
        fl.addWidget(QLabel("补充备注（可选）"))
        self.txt_notes = QPlainTextEdit()
        self.txt_notes.setPlaceholderText("用一句话补充未在 git 或截图里体现的工作（如线下会议、口头沟通…）")
        self.txt_notes.setMinimumHeight(80)
        fl.addWidget(self.txt_notes)

        # 操作行
        btn_row = QHBoxLayout()
        self.btn_generate = QPushButton("生成报告")
        self.btn_generate.setObjectName("PrimaryButton")
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate.clicked.connect(self.generate)
        btn_row.addWidget(self.btn_generate)

        self.btn_copy = QPushButton("复制")
        self.btn_copy.setObjectName("SecondaryButton")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        self.btn_copy.setEnabled(False)
        btn_row.addWidget(self.btn_copy)

        self.btn_export = QPushButton("导出…")
        self.btn_export.setObjectName("SecondaryButton")
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self._export_md)
        self.btn_export.setEnabled(False)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch(1)
        fl.addLayout(btn_row)

        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("CardDesc")
        self.lbl_status.setWordWrap(True)
        fl.addWidget(self.lbl_status)

        form_lay.addWidget(form_card)
        form_lay.addStretch(1)

        # ── 右：预览 ───────────────────────────────
        preview_wrap = QWidget()
        pv = QVBoxLayout(preview_wrap)
        pv.setContentsMargins(20, 16, 20, 16)
        pv.setSpacing(10)

        pv_head = QHBoxLayout()
        pvt = QLabel("预览")
        pvt.setObjectName("CardTitle")
        pv_head.addWidget(pvt)
        pv_head.addStretch(1)
        pv.addLayout(pv_head)

        self.preview = _make_preview()
        self.preview.setMarkdown("> 点击左侧 \"生成报告\" 开始。")
        pv.addWidget(self.preview, 1)

        splitter.addWidget(form_wrap)
        splitter.addWidget(preview_wrap)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 720])

        self._last_content: str = ""

    def _on_kind_changed(self, _idx: int) -> None:
        """根据 kind 调整日期选择器的标签和显示格式。"""
        kind = KIND_LABELS[self.combo_kind.currentIndex()][1]
        if kind == "daily":
            self.lbl_date.setText("日期")
            self.date_edit.setDisplayFormat("yyyy-MM-dd")
        elif kind == "weekly":
            self.lbl_date.setText("周（点选周内任一天）")
            self.date_edit.setDisplayFormat("yyyy-MM-dd（'第'W'周'）")
        else:  # monthly
            self.lbl_date.setText("月份")
            self.date_edit.setDisplayFormat("yyyy-MM")
        self._update_period_hint()

    def _update_period_hint(self) -> None:
        from datetime import datetime as _dt
        from ...generator import resolve_period
        kind = KIND_LABELS[self.combo_kind.currentIndex()][1]
        d = self.date_edit.date().toPython()
        anchor = _dt.combine(d, _dt.min.time())
        try:
            start, end = resolve_period(kind, anchor)
        except Exception:
            self.lbl_period.setText("")
            return
        if kind == "daily":
            txt = f"实际范围: {start:%Y-%m-%d}"
        elif kind == "weekly":
            iso_year, iso_week, _ = d.isocalendar()
            txt = (
                f"实际范围: {start:%Y-%m-%d}（周一）~ {end:%Y-%m-%d}（周日）  "
                f"· {iso_year} 年第 {iso_week} 周"
            )
        else:
            txt = f"实际范围: {start:%Y-%m-%d} ~ {end:%Y-%m-%d}（{start:%Y-%m}）"
        self.lbl_period.setText(txt)

    def trigger_quick_generate(self, kind: str) -> None:
        idx = next((i for i, (_, k) in enumerate(KIND_LABELS) if k == kind), 0)
        self.combo_kind.setCurrentIndex(idx)
        self.date_edit.setDate(QDate.currentDate())
        self.generate()

    def generate(self) -> None:
        if not self.main.cfg.llm.api_key:
            QMessageBox.warning(self, "未配置", "请先到\"设置\"中填写 LLM API Key。")
            return
        kind = KIND_LABELS[self.combo_kind.currentIndex()][1]
        template = self.combo_template.currentData()
        anchor = datetime.combine(self.date_edit.date().toPython(), datetime.min.time())
        notes = self.txt_notes.toPlainText().strip()

        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("生成中…")
        self.lbl_status.setText("正在调用 LLM 生成报告，请稍候…")
        self.preview.setMarkdown("（生成中…）")

        worker = ReportWorker(
            self.main.cfg, self.main.storage,
            kind=kind, anchor=anchor, template=template, notes=notes,
        )
        worker.finished.connect(self._on_done)
        worker.failed.connect(self._on_fail)
        start_in_thread(self.main, worker)

    def _on_done(self, result: dict) -> None:
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("生成报告")
        content = result.get("content", "")
        self._last_content = content
        self.preview.setMarkdown(content)
        stats = result.get("stats", {})
        self.lbl_status.setText(
            f"已生成 {KIND_TITLE.get(result['kind'], result['kind'])} "
            f"（id={result.get('id')}, commits={stats.get('commits', 0)}, "
            f"screenshots={stats.get('screenshots', 0)}）"
        )
        self.btn_copy.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.parent_page.refresh_history()

    def _on_fail(self, msg: str) -> None:
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("生成报告")
        self.lbl_status.setText("生成失败")
        self.preview.setMarkdown(f"```\n{msg}\n```")
        QMessageBox.warning(self, "生成失败", msg[:1000])

    def _copy_to_clipboard(self) -> None:
        if not self._last_content:
            return
        QGuiApplication.clipboard().setText(self._last_content)
        self.main.statusBar().showMessage("已复制到剪贴板", 2000)

    def _export_md(self) -> None:
        if not self._last_content:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出报告", "report.md", build_save_filter(),
        )
        if not path:
            return
        try:
            export_report(self._last_content, path)
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))
            return
        self.main.statusBar().showMessage(f"已导出: {path}", 4000)


class HistoryTab(QWidget):
    """历史报告 Tab。"""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # 列表
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(20, 16, 20, 16)
        ll.setSpacing(8)
        head = QHBoxLayout()
        h = QLabel("历史报告")
        h.setObjectName("CardTitle")
        head.addWidget(h)
        head.addStretch(1)
        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("SecondaryButton")
        btn_refresh.clicked.connect(self.refresh)
        head.addWidget(btn_refresh)
        ll.addLayout(head)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "类型", "周期", "生成时间"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_select)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        ll.addWidget(self.table, 1)

        # 详情
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(20, 16, 20, 16)
        rl.setSpacing(8)
        rh = QHBoxLayout()
        rt = QLabel("详情")
        rt.setObjectName("CardTitle")
        rh.addWidget(rt)
        rh.addStretch(1)
        self.btn_copy = QPushButton("复制")
        self.btn_copy.setObjectName("SecondaryButton")
        self.btn_copy.clicked.connect(self._copy)
        self.btn_copy.setEnabled(False)
        rh.addWidget(self.btn_copy)
        self.btn_export = QPushButton("导出")
        self.btn_export.setObjectName("SecondaryButton")
        self.btn_export.clicked.connect(self._export)
        self.btn_export.setEnabled(False)
        rh.addWidget(self.btn_export)
        rl.addLayout(rh)

        self.preview = _make_preview()
        self.preview.setMarkdown("> 选择左侧一份报告查看详情。")
        rl.addWidget(self.preview, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 700])

        self._reports: list[dict] = []
        self._selected: Optional[dict] = None

    def refresh(self) -> None:
        self._reports = self.main.storage.list_reports(limit=200)
        self.table.setRowCount(0)
        for r in self._reports:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(r["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(KIND_TITLE.get(r["kind"], r["kind"])))
            period = f"{r['period_start'][:10]} ~ {r['period_end'][:10]}"
            self.table.setItem(row, 2, QTableWidgetItem(period))
            self.table.setItem(row, 3, QTableWidgetItem(r.get("created_at") or ""))
        if not self._reports:
            self.preview.setMarkdown("> 暂无历史报告。先去\"生成\" Tab 生成一份吧。")
            self._selected = None
            self.btn_copy.setEnabled(False)
            self.btn_export.setEnabled(False)

    def _on_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._reports):
            return
        r = self._reports[idx]
        self._selected = r
        self.preview.setMarkdown(r.get("content") or "")
        self.btn_copy.setEnabled(True)
        self.btn_export.setEnabled(True)

    def _copy(self) -> None:
        if self._selected:
            QGuiApplication.clipboard().setText(self._selected.get("content", ""))
            self.main.statusBar().showMessage("已复制到剪贴板", 2000)

    def _export(self) -> None:
        if not self._selected:
            return
        kind = self._selected.get("kind", "report")
        period = (self._selected.get("period_start") or "")[:10]
        default_name = f"{kind}-{period}.md"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出报告", default_name, build_save_filter(),
        )
        if not path:
            return
        try:
            export_report(self._selected.get("content", ""), path)
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))
            return
        self.main.statusBar().showMessage(f"已导出: {path}", 4000)


class ReportsPage(QWidget):
    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 12)
        root.setSpacing(14)

        title = QLabel("报告")
        title.setObjectName("PageTitle")
        sub = QLabel("基于本期 git 提交、屏幕分析和你的备注，一键生成日报、周报、月报。")
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        self.tabs = QTabWidget()
        self.tab_generate = GenerateTab(main, self)
        self.tab_history = HistoryTab(main)
        self.tabs.addTab(self.tab_generate, "生成")
        self.tabs.addTab(self.tab_history, "历史")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, 1)

    def _on_tab_changed(self, idx: int) -> None:
        if self.tabs.widget(idx) is self.tab_history:
            self.tab_history.refresh()

    def refresh_history(self) -> None:
        self.tab_history.refresh()

    def trigger_quick_generate(self, kind: str) -> None:
        self.tabs.setCurrentWidget(self.tab_generate)
        self.tab_generate.trigger_quick_generate(kind)

    # ── 生命周期钩子 ─────────────────────────────────
    def on_activated(self) -> None:
        if self.tabs.currentWidget() is self.tab_history:
            self.tab_history.refresh()

    def on_config_changed(self) -> None:
        idx = self.tab_generate.combo_template.findData(self.main.cfg.report.default_template)
        if idx >= 0:
            self.tab_generate.combo_template.setCurrentIndex(idx)
