//! SQLite 持久化层。
//!
//! 设计要点：
//! - 通过 [`r2d2`] + [`r2d2_sqlite`] 维护连接池（默认 size = 4），所有读写都从池里拿连接。
//! - 启用 WAL 日志模式 + `synchronous=NORMAL` + 10s `busy_timeout`，配合连接池
//!   可以在多线程 / 多任务场景下获得较好的并发表现。
//! - 表结构与旧版 Python 实现保持兼容：字段名、类型、索引完全一致，
//!   时间统一用 ISO 8601 字符串存放（`TEXT`），`meta` 字段存 JSON 字符串。
//! - 写入 work_log 时支持基于 `dedupe_key` 的幂等写入，方便 git 采集
//!   反复调用而不会插入重复数据。
//!
//! 模块本身只暴露同步 API；调用方若需放在 async 上下文里，可用
//! `tokio::task::spawn_blocking` 包一层。

use std::path::Path;

use chrono::{DateTime, Local, NaiveDateTime, TimeZone, Utc};
use r2d2_sqlite::SqliteConnectionManager;
use rusqlite::{params, OptionalExtension};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{Error, Result};

/// 连接池大小。SQLite 在 WAL 模式下允许多个读 + 单个写并发，
/// 4 个连接在桌面端足够使用。
const POOL_SIZE: u32 = 4;

/// `busy_timeout` (ms)。等待锁的最大时长。
const BUSY_TIMEOUT_MS: i64 = 10_000;

// ---------------------------------------------------------------------------
// 数据模型
// ---------------------------------------------------------------------------

/// 一条工作日志条目。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkLog {
    pub id: i64,
    /// 业务时间戳（事件发生时刻）。
    pub ts: DateTime<Local>,
    /// 来源：`git` / `screenshot` / `manual`。
    pub source: String,
    /// 业务分类，可空。
    pub category: Option<String>,
    pub title: String,
    pub content: String,
    /// 任意扩展元数据，存 JSON。
    pub meta: Value,
    /// 入库时间戳。
    pub created_at: DateTime<Local>,
}

/// 一篇生成好的报告。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Report {
    pub id: i64,
    /// 报告类型：`daily` / `weekly` / `monthly`。
    pub kind: String,
    pub period_start: DateTime<Local>,
    pub period_end: DateTime<Local>,
    pub template: Option<String>,
    pub content: String,
    pub created_at: DateTime<Local>,
}

/// 一条待办事项（备忘录）。
///
/// - `status`: `pending` 未完成 / `done` 已完成
/// - 完成时会同步写入一条 `source = "todo"` 的 work_log，并把其 id 记到 `work_log_id`
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Todo {
    pub id: i64,
    pub content: String,
    /// `pending` | `done`
    pub status: String,
    pub created_at: DateTime<Local>,
    pub completed_at: Option<DateTime<Local>>,
    /// 完成后关联的 work_logs.id；未完成时为 None
    pub work_log_id: Option<i64>,
}

/// 清理操作结果。
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
pub struct PurgeStats {
    pub work_logs: u64,
    pub reports: u64,
}

/// 数据库统计信息。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageStats {
    pub work_logs_total: u64,
    pub reports_total: u64,
    pub earliest_log: Option<DateTime<Local>>,
    pub latest_log: Option<DateTime<Local>>,
    #[serde(default)]
    pub todos_pending: u64,
    #[serde(default)]
    pub todos_done: u64,
}

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const SCHEMA_SQL: &str = r#"
CREATE TABLE IF NOT EXISTS work_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    source TEXT NOT NULL,
    category TEXT,
    title TEXT NOT NULL,
    content TEXT,
    meta TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_work_logs_ts ON work_logs(ts);
CREATE INDEX IF NOT EXISTS idx_work_logs_source ON work_logs(source);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    template TEXT,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_reports_kind ON reports(kind);
CREATE INDEX IF NOT EXISTS idx_reports_period ON reports(period_start, period_end);

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    work_log_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_created_at ON todos(created_at);
"#;

// ---------------------------------------------------------------------------
// Storage
// ---------------------------------------------------------------------------

/// SQLite 存储入口。`Clone` 廉价：底层就是一个 `Arc` 化的连接池。
#[derive(Clone)]
pub struct Storage {
    pool: r2d2::Pool<SqliteConnectionManager>,
}

impl Storage {
    /// 打开（或创建）数据库文件。
    ///
    /// 会确保父目录存在，然后构造连接池，并在每个新连接上应用
    /// WAL / synchronous / busy_timeout 三个 PRAGMA。
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        if let Some(parent) = path.parent() {
            if !parent.as_os_str().is_empty() {
                std::fs::create_dir_all(parent)?;
            }
        }

        // 每条新连接都需要的 PRAGMA。放到 with_init 里以便池里所有连接生效。
        let manager = SqliteConnectionManager::file(path).with_init(|conn| {
            conn.execute_batch(
                "PRAGMA journal_mode=WAL;\
                 PRAGMA synchronous=NORMAL;\
                 PRAGMA busy_timeout=10000;",
            )
        });

        let pool = r2d2::Pool::builder()
            .max_size(POOL_SIZE)
            .build(manager)?;

        // 用一条连接执行 schema 初始化。
        {
            let conn = pool.get()?;
            // busy_timeout 在 with_init 已设；这里再显式设一次以防万一。
            conn.busy_timeout(std::time::Duration::from_millis(
                BUSY_TIMEOUT_MS as u64,
            ))?;
            conn.execute_batch(SCHEMA_SQL)?;
        }

        Ok(Self { pool })
    }

    // -------------------- work_logs --------------------

    /// 插入一条工作日志；若提供 `dedupe_key` 且数据库里已存在
    /// `source` 相同 + `meta` 包含 `"dedupe_key":"<value>"` 的记录，
    /// 则跳过插入并返回已有记录的 id。
    pub fn add_work_log(
        &self,
        ts: DateTime<Local>,
        source: &str,
        title: &str,
        content: &str,
        category: Option<&str>,
        meta: Value,
        dedupe_key: Option<&str>,
    ) -> Result<i64> {
        let conn = self.pool.get()?;

        if let Some(key) = dedupe_key {
            // 与 Python 旧版完全一致：用 LIKE 匹配 JSON 子串。
            // git commit hash 不含 LIKE 通配符，无需额外转义。
            let pattern = format!("%\"dedupe_key\":\"{}\"%", key);
            let existing: Option<i64> = conn
                .query_row(
                    "SELECT id FROM work_logs \
                     WHERE source = ?1 AND meta LIKE ?2 \
                     ORDER BY id DESC LIMIT 1",
                    params![source, pattern],
                    |row| row.get(0),
                )
                .optional()?;
            if let Some(id) = existing {
                tracing::debug!(
                    target: "storage",
                    id,
                    source,
                    dedupe_key = key,
                    "命中 dedupe，跳过 work_log 插入"
                );
                return Ok(id);
            }
        }

        let meta_str = serde_json::to_string(&meta)?;
        conn.execute(
            "INSERT INTO work_logs (ts, source, category, title, content, meta) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![
                ts.to_rfc3339(),
                source,
                category,
                title,
                content,
                meta_str,
            ],
        )?;
        Ok(conn.last_insert_rowid())
    }

    /// 列出 `[start, end]` 闭区间内的 work_log，按 `ts` 倒序（最新在前）。
    pub fn list_work_logs(
        &self,
        start: DateTime<Local>,
        end: DateTime<Local>,
        source: Option<&str>,
    ) -> Result<Vec<WorkLog>> {
        let conn = self.pool.get()?;
        let start_s = start.to_rfc3339();
        let end_s = end.to_rfc3339();

        let mut stmt;
        let rows_iter = if let Some(src) = source {
            stmt = conn.prepare(
                "SELECT id, ts, source, category, title, content, meta, created_at \
                 FROM work_logs \
                 WHERE ts >= ?1 AND ts <= ?2 AND source = ?3 \
                 ORDER BY ts DESC",
            )?;
            stmt.query(params![start_s, end_s, src])?
        } else {
            stmt = conn.prepare(
                "SELECT id, ts, source, category, title, content, meta, created_at \
                 FROM work_logs \
                 WHERE ts >= ?1 AND ts <= ?2 \
                 ORDER BY ts DESC",
            )?;
            stmt.query(params![start_s, end_s])?
        };

        let mut rows = rows_iter;
        let mut out = Vec::new();
        while let Some(row) = rows.next()? {
            out.push(row_to_work_log(row)?);
        }
        Ok(out)
    }

    /// 删除指定 id 的 work_log。返回是否真的删除了一行。
    pub fn delete_work_log(&self, id: i64) -> Result<bool> {
        let conn = self.pool.get()?;
        let n = conn.execute("DELETE FROM work_logs WHERE id = ?1", params![id])?;
        Ok(n > 0)
    }

    /// 按 source 删除所有 work_log，返回删除条数。
    /// 用于"全量覆盖"式的同步：先清空指定来源，再重新导入。
    pub fn delete_work_logs_by_source(&self, source: &str) -> Result<u64> {
        let conn = self.pool.get()?;
        let n = conn.execute(
            "DELETE FROM work_logs WHERE source = ?1",
            params![source],
        )?;
        Ok(n as u64)
    }

    // -------------------- reports --------------------

    /// 写入一篇报告，返回新 id。
    pub fn add_report(
        &self,
        kind: &str,
        period_start: DateTime<Local>,
        period_end: DateTime<Local>,
        template: Option<&str>,
        content: &str,
    ) -> Result<i64> {
        let conn = self.pool.get()?;
        conn.execute(
            "INSERT INTO reports (kind, period_start, period_end, template, content) \
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![
                kind,
                period_start.to_rfc3339(),
                period_end.to_rfc3339(),
                template,
                content,
            ],
        )?;
        Ok(conn.last_insert_rowid())
    }

    /// 列出最新 `limit` 篇报告，按 `created_at` 倒序。
    /// `limit == 0` 时回退为默认 50。
    pub fn list_reports(&self, limit: usize) -> Result<Vec<Report>> {
        let limit = if limit == 0 { 50 } else { limit };
        let conn = self.pool.get()?;
        let mut stmt = conn.prepare(
            "SELECT id, kind, period_start, period_end, template, content, created_at \
             FROM reports \
             ORDER BY datetime(created_at) DESC, id DESC \
             LIMIT ?1",
        )?;
        let mut rows = stmt.query(params![limit as i64])?;
        let mut out = Vec::new();
        while let Some(row) = rows.next()? {
            out.push(row_to_report(row)?);
        }
        Ok(out)
    }

    /// 按 id 取一篇报告。
    pub fn get_report(&self, id: i64) -> Result<Option<Report>> {
        let conn = self.pool.get()?;
        let mut stmt = conn.prepare(
            "SELECT id, kind, period_start, period_end, template, content, created_at \
             FROM reports WHERE id = ?1",
        )?;
        let mut rows = stmt.query(params![id])?;
        if let Some(row) = rows.next()? {
            Ok(Some(row_to_report(row)?))
        } else {
            Ok(None)
        }
    }

    /// 删除指定 id 的报告。
    pub fn delete_report(&self, id: i64) -> Result<bool> {
        let conn = self.pool.get()?;
        let n = conn.execute("DELETE FROM reports WHERE id = ?1", params![id])?;
        Ok(n > 0)
    }

    // -------------------- todos --------------------

    /// 新增一条待办，状态固定为 `pending`。
    pub fn add_todo(&self, content: &str) -> Result<Todo> {
        let content = content.trim();
        if content.is_empty() {
            return Err(Error::internal("待办内容不能为空"));
        }
        let now = Local::now();
        let now_s = now.to_rfc3339();
        let conn = self.pool.get()?;
        conn.execute(
            "INSERT INTO todos (content, status, created_at, completed_at, work_log_id) \
             VALUES (?1, 'pending', ?2, NULL, NULL)",
            params![content, now_s],
        )?;
        let id = conn.last_insert_rowid();
        Ok(Todo {
            id,
            content: content.to_string(),
            status: "pending".to_string(),
            created_at: now,
            completed_at: None,
            work_log_id: None,
        })
    }

    /// 列出待办。`status` 为 `Some("pending"|"done")` 时过滤；`None` 返回全部。
    /// 排序：pending 在前，同状态按 created_at 倒序。
    pub fn list_todos(&self, status: Option<&str>) -> Result<Vec<Todo>> {
        let conn = self.pool.get()?;
        let mut stmt;
        let rows_iter = if let Some(st) = status {
            stmt = conn.prepare(
                "SELECT id, content, status, created_at, completed_at, work_log_id \
                 FROM todos WHERE status = ?1 \
                 ORDER BY datetime(created_at) DESC, id DESC",
            )?;
            stmt.query(params![st])?
        } else {
            stmt = conn.prepare(
                "SELECT id, content, status, created_at, completed_at, work_log_id \
                 FROM todos \
                 ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, \
                          datetime(created_at) DESC, id DESC",
            )?;
            stmt.query([])?
        };
        let mut rows = rows_iter;
        let mut out = Vec::new();
        while let Some(row) = rows.next()? {
            out.push(row_to_todo(row)?);
        }
        Ok(out)
    }

    /// 按 id 取一条待办。
    pub fn get_todo(&self, id: i64) -> Result<Option<Todo>> {
        let conn = self.pool.get()?;
        let mut stmt = conn.prepare(
            "SELECT id, content, status, created_at, completed_at, work_log_id \
             FROM todos WHERE id = ?1",
        )?;
        let mut rows = stmt.query(params![id])?;
        if let Some(row) = rows.next()? {
            Ok(Some(row_to_todo(row)?))
        } else {
            Ok(None)
        }
    }

    /// 删除待办。不级联删除已写入的 work_log（历史记录保留）。
    pub fn delete_todo(&self, id: i64) -> Result<bool> {
        let conn = self.pool.get()?;
        let n = conn.execute("DELETE FROM todos WHERE id = ?1", params![id])?;
        Ok(n > 0)
    }

    /// 更新待办正文（支持 Markdown）。已完成的待办也可改文案，不改状态。
    pub fn update_todo(&self, id: i64, content: &str) -> Result<Todo> {
        let content = content.trim();
        if content.is_empty() {
            return Err(Error::internal("待办内容不能为空"));
        }
        let conn = self.pool.get()?;
        let n = conn.execute(
            "UPDATE todos SET content = ?1 WHERE id = ?2",
            params![content, id],
        )?;
        if n == 0 {
            return Err(Error::internal(format!("待办不存在: {id}")));
        }
        // 若已关联 work_log，同步标题/正文，保持时间线一致
        let todo = self
            .get_todo(id)?
            .ok_or_else(|| Error::internal(format!("待办不存在: {id}")))?;
        if let Some(lid) = todo.work_log_id {
            let _ = conn.execute(
                "UPDATE work_logs SET title = ?1, content = ?2 WHERE id = ?3 AND source = 'todo'",
                params![content, content, lid],
            );
        }
        Ok(todo)
    }

    /// 完成待办：标记 done，并同步写入一条 `source="todo"` 的 work_log。
    ///
    /// 已完成的待办再次调用会返回现有记录（幂等）。
    /// 返回 `(todo, 新写入的 work_log 或 None)`。
    pub fn complete_todo(&self, id: i64) -> Result<(Todo, Option<WorkLog>)> {
        let mut conn = self.pool.get()?;
        let existing = {
            let mut stmt = conn.prepare(
                "SELECT id, content, status, created_at, completed_at, work_log_id \
                 FROM todos WHERE id = ?1",
            )?;
            let mut rows = stmt.query(params![id])?;
            match rows.next()? {
                Some(row) => row_to_todo(row)?,
                None => return Err(Error::internal(format!("待办不存在: {id}"))),
            }
        };

        if existing.status == "done" {
            // 幂等：已完成则直接返回；若有关联 work_log 再读出
            let log = if let Some(lid) = existing.work_log_id {
                self.get_work_log(lid)?
            } else {
                None
            };
            return Ok((existing, log));
        }

        let now = Local::now();
        let now_s = now.to_rfc3339();
        let meta = serde_json::json!({
            "todo_id": id,
            "todo_content": existing.content,
        });
        let meta_str = serde_json::to_string(&meta)?;

        let tx = conn.transaction()?;
        // 1) 写 work_log
        tx.execute(
            "INSERT INTO work_logs (ts, source, category, title, content, meta) \
             VALUES (?1, 'todo', '待办', ?2, ?3, ?4)",
            params![
                now_s.clone(),
                existing.content,
                existing.content,
                meta_str,
            ],
        )?;
        let work_log_id = tx.last_insert_rowid();

        // 2) 更新 todo
        tx.execute(
            "UPDATE todos SET status = 'done', completed_at = ?1, work_log_id = ?2 \
             WHERE id = ?3",
            params![now_s, work_log_id, id],
        )?;
        tx.commit()?;

        let todo = Todo {
            id,
            content: existing.content.clone(),
            status: "done".to_string(),
            created_at: existing.created_at,
            completed_at: Some(now),
            work_log_id: Some(work_log_id),
        };
        let log = WorkLog {
            id: work_log_id,
            ts: now,
            source: "todo".to_string(),
            category: Some("待办".to_string()),
            title: existing.content.clone(),
            content: existing.content,
            meta,
            created_at: now,
        };
        Ok((todo, Some(log)))
    }

    /// 按 id 取一条 work_log。
    pub fn get_work_log(&self, id: i64) -> Result<Option<WorkLog>> {
        let conn = self.pool.get()?;
        let mut stmt = conn.prepare(
            "SELECT id, ts, source, category, title, content, meta, created_at \
             FROM work_logs WHERE id = ?1",
        )?;
        let mut rows = stmt.query(params![id])?;
        if let Some(row) = rows.next()? {
            Ok(Some(row_to_work_log(row)?))
        } else {
            Ok(None)
        }
    }

    /// 列出 `[start, end]` 闭区间内已完成的待办（按 completed_at）。
    pub fn list_completed_todos(
        &self,
        start: DateTime<Local>,
        end: DateTime<Local>,
    ) -> Result<Vec<Todo>> {
        let conn = self.pool.get()?;
        let start_s = start.to_rfc3339();
        let end_s = end.to_rfc3339();
        let mut stmt = conn.prepare(
            "SELECT id, content, status, created_at, completed_at, work_log_id \
             FROM todos \
             WHERE status = 'done' AND completed_at IS NOT NULL \
               AND completed_at >= ?1 AND completed_at <= ?2 \
             ORDER BY completed_at DESC",
        )?;
        let mut rows = stmt.query(params![start_s, end_s])?;
        let mut out = Vec::new();
        while let Some(row) = rows.next()? {
            out.push(row_to_todo(row)?);
        }
        Ok(out)
    }

    // -------------------- 维护 --------------------

    /// 清理 `cutoff` 之前的 work_logs（按 `ts`）和 reports（按 `period_end`）。
    /// 已完成且 completed_at 早于 cutoff 的 todos 一并清理；pending 保留。
    pub fn purge_before(&self, cutoff: DateTime<Local>) -> Result<PurgeStats> {
        let mut conn = self.pool.get()?;
        let cutoff_s = cutoff.to_rfc3339();
        let tx = conn.transaction()?;
        let logs = tx.execute(
            "DELETE FROM work_logs WHERE ts < ?1",
            params![cutoff_s.clone()],
        )?;
        let reports = tx.execute(
            "DELETE FROM reports WHERE period_end < ?1",
            params![cutoff_s.clone()],
        )?;
        let _todos = tx.execute(
            "DELETE FROM todos WHERE status = 'done' AND completed_at IS NOT NULL AND completed_at < ?1",
            params![cutoff_s],
        )?;
        tx.commit()?;
        Ok(PurgeStats {
            work_logs: logs as u64,
            reports: reports as u64,
        })
    }

    /// 清空所有业务数据。AUTOINCREMENT 序列不重置，主键继续递增。
    pub fn purge_all(&self) -> Result<PurgeStats> {
        let mut conn = self.pool.get()?;
        let tx = conn.transaction()?;
        let logs = tx.execute("DELETE FROM work_logs", [])?;
        let reports = tx.execute("DELETE FROM reports", [])?;
        let _ = tx.execute("DELETE FROM todos", [])?;
        tx.commit()?;
        Ok(PurgeStats {
            work_logs: logs as u64,
            reports: reports as u64,
        })
    }

    /// 数据库整体统计。
    pub fn stats(&self) -> Result<StorageStats> {
        let conn = self.pool.get()?;
        let (work_logs_total, earliest, latest): (i64, Option<String>, Option<String>) = conn
            .query_row(
                "SELECT COUNT(*), MIN(ts), MAX(ts) FROM work_logs",
                [],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )?;
        let reports_total: i64 =
            conn.query_row("SELECT COUNT(*) FROM reports", [], |row| row.get(0))?;
        let todos_pending: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM todos WHERE status = 'pending'",
                [],
                |row| row.get(0),
            )
            .unwrap_or(0);
        let todos_done: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM todos WHERE status = 'done'",
                [],
                |row| row.get(0),
            )
            .unwrap_or(0);

        Ok(StorageStats {
            work_logs_total: work_logs_total.max(0) as u64,
            reports_total: reports_total.max(0) as u64,
            earliest_log: earliest.as_deref().and_then(|s| parse_dt(s).ok()),
            latest_log: latest.as_deref().and_then(|s| parse_dt(s).ok()),
            todos_pending: todos_pending.max(0) as u64,
            todos_done: todos_done.max(0) as u64,
        })
    }
}

// ---------------------------------------------------------------------------
// 行映射 / 时间解析
// ---------------------------------------------------------------------------

fn row_to_work_log(row: &rusqlite::Row<'_>) -> Result<WorkLog> {
    let id: i64 = row.get(0)?;
    let ts: String = row.get(1)?;
    let source: String = row.get(2)?;
    let category: Option<String> = row.get(3)?;
    let title: String = row.get(4)?;
    let content: Option<String> = row.get(5)?;
    let meta: Option<String> = row.get(6)?;
    let created_at: String = row.get(7)?;

    let meta_value = meta
        .as_deref()
        .map(|s| serde_json::from_str::<Value>(s).unwrap_or(Value::Null))
        .unwrap_or(Value::Null);

    Ok(WorkLog {
        id,
        ts: parse_dt(&ts)?,
        source,
        category,
        title,
        content: content.unwrap_or_default(),
        meta: meta_value,
        created_at: parse_dt(&created_at)?,
    })
}

fn row_to_report(row: &rusqlite::Row<'_>) -> Result<Report> {
    let id: i64 = row.get(0)?;
    let kind: String = row.get(1)?;
    let period_start: String = row.get(2)?;
    let period_end: String = row.get(3)?;
    let template: Option<String> = row.get(4)?;
    let content: String = row.get(5)?;
    let created_at: String = row.get(6)?;

    Ok(Report {
        id,
        kind,
        period_start: parse_dt(&period_start)?,
        period_end: parse_dt(&period_end)?,
        template,
        content,
        created_at: parse_dt(&created_at)?,
    })
}

fn row_to_todo(row: &rusqlite::Row<'_>) -> Result<Todo> {
    let id: i64 = row.get(0)?;
    let content: String = row.get(1)?;
    let status: String = row.get(2)?;
    let created_at: String = row.get(3)?;
    let completed_at: Option<String> = row.get(4)?;
    let work_log_id: Option<i64> = row.get(5)?;

    Ok(Todo {
        id,
        content,
        status,
        created_at: parse_dt(&created_at)?,
        completed_at: completed_at
            .as_deref()
            .filter(|s| !s.trim().is_empty())
            .map(parse_dt)
            .transpose()?,
        work_log_id,
    })
}

/// 容错解析时间戳：依次尝试 RFC3339 / 带 T 的 naive 格式 /
/// SQLite `CURRENT_TIMESTAMP` 默认的 `YYYY-MM-DD HH:MM:SS`（视为 UTC）。
fn parse_dt(s: &str) -> Result<DateTime<Local>> {
    let s = s.trim();
    if s.is_empty() {
        return Err(Error::internal("空时间戳"));
    }

    if let Ok(dt) = DateTime::parse_from_rfc3339(s) {
        return Ok(dt.with_timezone(&Local));
    }

    // ISO 但没带时区：当作本地时间。
    for fmt in ["%Y-%m-%dT%H:%M:%S%.f", "%Y-%m-%dT%H:%M:%S"] {
        if let Ok(ndt) = NaiveDateTime::parse_from_str(s, fmt) {
            if let Some(local) = Local.from_local_datetime(&ndt).single() {
                return Ok(local);
            }
        }
    }

    // SQLite CURRENT_TIMESTAMP：'YYYY-MM-DD HH:MM:SS'，UTC。
    for fmt in ["%Y-%m-%d %H:%M:%S%.f", "%Y-%m-%d %H:%M:%S"] {
        if let Ok(ndt) = NaiveDateTime::parse_from_str(s, fmt) {
            return Ok(Utc.from_utc_datetime(&ndt).with_timezone(&Local));
        }
    }

    Err(Error::internal(format!("无法解析时间戳: {s}")))
}
