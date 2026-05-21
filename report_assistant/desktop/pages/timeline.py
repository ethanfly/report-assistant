"""时间线：按日期浏览本日所有工作记录（git + 截图），可按类型筛选。"""
from __future__ import annotations

from datetime import datetime, time as dtime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QPlainTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

if TYPE_CHECKING:
    from ..main_window import MainWindow

from ...generator import collect_data


FILTERS = [("全部", ""), ("Git 提交", "git"), ("屏幕截图", "screenshot")]


class LogDetailDialog(QDialog):
    """工作记录详情对话框：完整字段 + 复制按钮。"""

    def __init__(self, log: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("记录详情")
        self.resize(620, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        meta = log.get("meta") or {}
        ts = (log.get("ts") or "").replace("T", " ")[:19]
        src = log.get("source") or ""
        cat = log.get("category") or "-"
        head_html = (
            f"<div style='color:#475569; font-size:12px;'>"
            f"时间: <b>{ts}</b> &nbsp;·&nbsp; "
            f"来源: <b>{src}</b> &nbsp;·&nbsp; "
            f"分类: <b>{cat}</b>"
            f"</div>"
        )
        head_lbl = QLabel(head_html)
        head_lbl.setTextFormat(Qt.TextFormat.RichText)
        head_lbl.setWordWrap(True)
        layout.addWidget(head_lbl)

        title_lbl = QLabel(log.get("title") or "")
        title_lbl.setStyleSheet(
            "font-size: 16px; font-weight: 600; color: #0f172a; padding: 4px 0;"
        )
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        body_text = (log.get("content") or "").strip() or "(无详细内容)"
        if src == "git":
            extra = []
            if meta.get("repo"):
                extra.append(f"仓库: {meta.get('repo')}")
            if meta.get("hash"):
                extra.append(f"Hash: {meta.get('hash')}")
            if meta.get("author"):
                extra.append(f"作者: {meta.get('author')}")
            ins = meta.get("insertions") or 0
            dels = meta.get("deletions") or 0
            if ins or dels:
                extra.append(f"改动: +{ins} / -{dels}")
            files = meta.get("files") or []
            if files:
                extra.append("文件:\n  " + "\n  ".join(files))
            if extra:
                body_text = "\n".join(extra) + "\n\n" + body_text
        elif src == "screenshot":
            keywords = meta.get("keywords") or []
            if keywords:
                body_text += f"\n\n关键词: {', '.join(keywords)}"

        self.body = QPlainTextEdit()
        self.body.setPlainText(body_text)
        self.body.setReadOnly(True)
        layout.addWidget(self.body, 1)

        bb = QDialogButtonBox()
        btn_copy = bb.addButton("复制内容", QDialogButtonBox.ButtonRole.ActionRole)
        btn_copy.setObjectName("SecondaryButton")
        btn_copy.clicked.connect(self._copy)
        btn_close = bb.addButton(QDialogButtonBox.StandardButton.Close)
        btn_close.setObjectName("PrimaryButton")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(bb)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.body.toPlainText())


class TimelinePage(QWidget):
    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 20)
        root.setSpacing(14)

        title = QLabel("时间线")
        title.setObjectName("PageTitle")
        sub = QLabel("浏览每日的 git 提交与屏幕活动记录。这些记录会作为生成报告的素材。")
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        # 工具条
        tools = QFrame()
        tools.setObjectName("Card")
        th = QHBoxLayout(tools)
        th.setContentsMargins(16, 12, 16, 12)
        th.setSpacing(10)

        th.addWidget(QLabel("日期"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self.refresh)
        th.addWidget(self.date_edit)

        th.addSpacing(12)
        th.addWidget(QLabel("类型"))
        self.combo_filter = QComboBox()
        for label, _ in FILTERS:
            self.combo_filter.addItem(label)
        self.combo_filter.currentIndexChanged.connect(self.refresh)
        th.addWidget(self.combo_filter)

        th.addSpacing(12)
        btn_today = QPushButton("今天")
        btn_today.setObjectName("SecondaryButton")
        btn_today.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_today.clicked.connect(lambda: self.date_edit.setDate(QDate.currentDate()))
        th.addWidget(btn_today)

        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("SecondaryButton")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self.refresh)
        th.addWidget(btn_refresh)

        th.addStretch(1)
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("CardDesc")
        th.addWidget(self.summary_label)
        root.addWidget(tools)

        # 表格
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["时间", "来源", "分类", "标题", "详情"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.cellDoubleClicked.connect(self._show_detail)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        # 全局信号：截图入库后自动刷新（仅当前显示的是今天）
        self.main.capture_added.connect(self._on_capture_added)

    def _on_capture_added(self, _payload: dict) -> None:
        if self.date_edit.date() == QDate.currentDate():
            self.refresh()

    def refresh(self) -> None:
        d = self.date_edit.date().toPython()
        start = datetime.combine(d, dtime.min)
        end = datetime.combine(d, dtime.max)

        # Git 同步走异步，不阻塞 UI；完成后通过 git_synced 信号刷新
        if d == datetime.now().date():
            self.main.sync_git()

        idx = self.combo_filter.currentIndex()
        source = FILTERS[idx][1] if 0 <= idx < len(FILTERS) else ""

        logs = self.main.storage.list_work_logs(
            start, end, source=source if source else None,
        )
        logs = list(reversed(logs))  # 最新在上
        self._logs = logs  # 保存供双击查看

        self.table.setRowCount(0)
        for log in logs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            ts = (log.get("ts") or "")[:16].replace("T", " ")
            src = "Git" if log["source"] == "git" else ("屏幕" if log["source"] == "screenshot" else log["source"])
            cat = log.get("category") or "-"
            ttl = log.get("title") or ""
            detail = log.get("content") or ""
            meta = log.get("meta") or {}
            if log["source"] == "git" and meta.get("hash"):
                detail = f"[{meta.get('repo','')} {meta['hash']}] " + detail

            for col, val in enumerate([ts, src, cat, ttl, detail]):
                item = QTableWidgetItem(str(val))
                if col == 4:
                    item.setToolTip(str(val))
                self.table.setItem(row, col, item)

        commits = sum(1 for l in logs if l["source"] == "git")
        shots = sum(1 for l in logs if l["source"] == "screenshot")
        self.summary_label.setText(f"共 {len(logs)} 条 · Git {commits} · 屏幕 {shots}")

    def _show_detail(self, row: int, _col: int) -> None:
        if not hasattr(self, "_logs") or row < 0 or row >= len(self._logs):
            return
        dlg = LogDetailDialog(self._logs[row], parent=self)
        dlg.exec()

    # ── 生命周期钩子 ─────────────────────────────────
    def on_activated(self) -> None:
        self.refresh()

    def on_config_changed(self) -> None:
        self.refresh()
