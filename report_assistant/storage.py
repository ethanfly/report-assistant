"""SQLite 本地存储：工作记录与已生成报告。

数据仅保存在用户本地。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS work_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,           -- ISO 时间戳
    source      TEXT    NOT NULL,           -- 'git' | 'screenshot' | 'manual'
    category    TEXT,                       -- 开发 / 会议 / 沟通 / 文档 / 其他
    title       TEXT    NOT NULL,
    content     TEXT,                       -- 详细内容/描述
    meta        TEXT,                       -- JSON 元数据（仓库、commit hash 等）
    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_work_logs_ts ON work_logs(ts);
CREATE INDEX IF NOT EXISTS idx_work_logs_source ON work_logs(source);

CREATE TABLE IF NOT EXISTS reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT    NOT NULL,           -- daily | weekly | monthly
    period_start TEXT   NOT NULL,
    period_end   TEXT   NOT NULL,
    template    TEXT,
    content     TEXT    NOT NULL,
    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reports_kind ON reports(kind);
CREATE INDEX IF NOT EXISTS idx_reports_period ON reports(period_start, period_end);
"""


class Storage:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(str(db_path)).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ── work_logs ──────────────────────────────────────────────
    def add_work_log(
        self,
        ts: datetime,
        source: str,
        title: str,
        content: str = "",
        category: str = "",
        meta: Optional[dict[str, Any]] = None,
        dedupe_key: Optional[str] = None,
    ) -> int:
        """写入一条工作记录。dedupe_key 用于幂等（如 git commit hash）。"""
        with self._conn() as c:
            if dedupe_key:
                cur = c.execute(
                    "SELECT id FROM work_logs WHERE source=? AND meta LIKE ?",
                    (source, f'%"dedupe_key": "{dedupe_key}"%'),
                )
                row = cur.fetchone()
                if row:
                    return int(row["id"])
            meta_dict = dict(meta or {})
            if dedupe_key:
                meta_dict["dedupe_key"] = dedupe_key
            cur = c.execute(
                """INSERT INTO work_logs (ts, source, category, title, content, meta)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    ts.isoformat(),
                    source,
                    category,
                    title,
                    content,
                    json.dumps(meta_dict, ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid)

    def list_work_logs(
        self,
        start: datetime,
        end: datetime,
        source: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM work_logs WHERE ts >= ? AND ts <= ?"
        params: list[Any] = [start.isoformat(), end.isoformat()]
        if source:
            sql += " AND source = ?"
            params.append(source)
        sql += " ORDER BY ts ASC"
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["meta"] = json.loads(d.get("meta") or "{}")
            except json.JSONDecodeError:
                d["meta"] = {}
            out.append(d)
        return out

    # ── reports ────────────────────────────────────────────────
    def add_report(
        self,
        kind: str,
        period_start: datetime,
        period_end: datetime,
        content: str,
        template: str = "",
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO reports (kind, period_start, period_end, template, content)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    kind,
                    period_start.isoformat(),
                    period_end.isoformat(),
                    template,
                    content,
                ),
            )
            return int(cur.lastrowid)

    def list_reports(self, kind: Optional[str] = None, limit: int = 20) -> list[dict[str, Any]]:
        sql = "SELECT * FROM reports"
        params: list[Any] = []
        if kind:
            sql += " WHERE kind = ?"
            params.append(kind)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_report(self, report_id: int) -> Optional[dict[str, Any]]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return dict(row) if row else None

    # ── 清理 ────────────────────────────────────────────────
    def purge_before(self, cutoff: datetime) -> dict[str, int]:
        """删除 cutoff 之前的 work_logs 和 reports，返回删除条数。"""
        with self._conn() as c:
            cur = c.execute(
                "DELETE FROM work_logs WHERE ts < ?", (cutoff.isoformat(),),
            )
            n_logs = cur.rowcount
            cur = c.execute(
                "DELETE FROM reports WHERE period_end < ?", (cutoff.isoformat(),),
            )
            n_reports = cur.rowcount
        self._vacuum()
        return {"work_logs": int(n_logs), "reports": int(n_reports)}

    def purge_all(self) -> dict[str, int]:
        """清空所有 work_logs 与 reports（保留表结构）。"""
        with self._conn() as c:
            cur = c.execute("DELETE FROM work_logs")
            n_logs = cur.rowcount
            cur = c.execute("DELETE FROM reports")
            n_reports = cur.rowcount
        self._vacuum()
        return {"work_logs": int(n_logs), "reports": int(n_reports)}

    def _vacuum(self) -> None:
        """VACUUM 必须在事务外执行；用 isolation_level=None 拿一个独立连接。"""
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            try:
                conn.execute("VACUUM")
            finally:
                conn.close()
        except sqlite3.Error:
            pass

    def stats(self) -> dict[str, int]:
        """汇总统计信息。"""
        with self._conn() as c:
            n_logs = c.execute("SELECT COUNT(*) FROM work_logs").fetchone()[0]
            n_reports = c.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        return {"work_logs": int(n_logs), "reports": int(n_reports)}
