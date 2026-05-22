//! 所有 `#[tauri::command]` 实现。
//!
//! 设计要点：
//! - 错误统一通过 `map_err(|e| e.to_string())` 转字符串返回给前端；
//! - parking_lot 的 `Mutex` guard 不允许跨 await，因此遇到异步操作时
//!   先短锁拷贝出需要的数据，再 drop guard 再 await；
//! - 涉及阻塞 IO（git / SQLite 大查询）已通过 `tokio::task::spawn_blocking`
//!   或同步 API 直接调用，均在 tokio runtime 上执行不会阻塞 UI；
//! - `start_watch` 会把事件桥接到前端的 `watch-event` 全局事件。

use std::path::PathBuf;
use std::sync::Arc;

use chrono::{DateTime, Local};
use report_assistant_core::{
    config::{self, Config, LlmConfig},
    exporters::{self, ExportFormat},
    generator::{self, GenerateRequest, GenerateResult},
    llm::{self, LlmClient},
    paths,
    screenshot::{self, MonitorInfo},
    storage::{PurgeStats, Report, StorageStats, WorkLog},
    templates::{self, ReportTemplate},
    watch::{self, WatchEvent, VISION_PROMPT},
};
use serde_json::json;
use tauri::{AppHandle, Emitter, State};

use crate::state::AppStateHandle;

// ---------------------------------------------------------------------------
// 配置
// ---------------------------------------------------------------------------

/// 读取当前内存中的配置（克隆一份返回）。
#[tauri::command]
pub async fn load_config(state: State<'_, AppStateHandle>) -> Result<Config, String> {
    let cfg = state.config.lock().clone();
    Ok(cfg)
}

/// 持久化配置到磁盘并替换内存副本。
#[tauri::command]
pub async fn save_config(state: State<'_, AppStateHandle>, cfg: Config) -> Result<(), String> {
    config::save(&cfg).map_err(|e| e.to_string())?;
    *state.config.lock() = cfg;
    Ok(())
}

// ---------------------------------------------------------------------------
// 存储查询
// ---------------------------------------------------------------------------

/// 列出 [start, end] 范围的工作日志。`start` / `end` 为 RFC3339 字符串。
#[tauri::command]
pub async fn list_work_logs(
    state: State<'_, AppStateHandle>,
    start: String,
    end: String,
    source: Option<String>,
) -> Result<Vec<WorkLog>, String> {
    let start_dt = parse_rfc3339(&start)?;
    let end_dt = parse_rfc3339(&end)?;
    let storage = state.storage.clone();
    tokio::task::spawn_blocking(move || {
        storage.list_work_logs(start_dt, end_dt, source.as_deref())
    })
    .await
    .map_err(|e| e.to_string())?
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn list_reports(
    state: State<'_, AppStateHandle>,
    limit: usize,
) -> Result<Vec<Report>, String> {
    let storage = state.storage.clone();
    tokio::task::spawn_blocking(move || storage.list_reports(limit))
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn get_report(
    state: State<'_, AppStateHandle>,
    id: i64,
) -> Result<Option<Report>, String> {
    let storage = state.storage.clone();
    tokio::task::spawn_blocking(move || storage.get_report(id))
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn delete_report(state: State<'_, AppStateHandle>, id: i64) -> Result<bool, String> {
    let storage = state.storage.clone();
    tokio::task::spawn_blocking(move || storage.delete_report(id))
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn delete_work_log(state: State<'_, AppStateHandle>, id: i64) -> Result<bool, String> {
    let storage = state.storage.clone();
    tokio::task::spawn_blocking(move || storage.delete_work_log(id))
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn storage_stats(state: State<'_, AppStateHandle>) -> Result<StorageStats, String> {
    let storage = state.storage.clone();
    tokio::task::spawn_blocking(move || storage.stats())
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn purge_before(
    state: State<'_, AppStateHandle>,
    days: i64,
) -> Result<PurgeStats, String> {
    let cutoff = Local::now() - chrono::Duration::days(days.max(0));
    let storage = state.storage.clone();
    tokio::task::spawn_blocking(move || storage.purge_before(cutoff))
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn purge_all(state: State<'_, AppStateHandle>) -> Result<PurgeStats, String> {
    let storage = state.storage.clone();
    tokio::task::spawn_blocking(move || storage.purge_all())
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())
}

// ---------------------------------------------------------------------------
// 截图与监听
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn list_monitors() -> Result<Vec<MonitorInfo>, String> {
    // 同步快速调用，跑在阻塞线程避免极端情况下卡 UI。
    tokio::task::spawn_blocking(screenshot::list_monitors)
        .await
        .map_err(|e| e.to_string())
}

/// 触发一次"截图 + 视觉分析 + 入库"，返回新建的 WorkLog。
#[tauri::command]
pub async fn capture_once(state: State<'_, AppStateHandle>) -> Result<WorkLog, String> {
    // 1) 拷贝所需配置
    let (llm_cfg, screenshot_dir, monitor_index, keep) = {
        let cfg = state.config.lock();
        let dir = cfg.resolved_screenshot_dir().map_err(|e| e.to_string())?;
        (
            cfg.llm.clone(),
            dir,
            cfg.screenshot.monitor_index,
            cfg.screenshot.keep_after_analysis,
        )
    };

    // 2) 构造 LLM 客户端
    let llm = LlmClient::new(llm_cfg).map_err(|e| e.to_string())?;

    // 3) 截图（阻塞）
    let dir_for_blk = screenshot_dir.clone();
    let path = tokio::task::spawn_blocking(move || {
        screenshot::capture_screen(dir_for_blk, monitor_index)
    })
    .await
    .map_err(|e| e.to_string())?
    .map_err(|e| e.to_string())?;

    // 4) 视觉分析
    let analyze = llm.analyze_image(&path, VISION_PROMPT).await;

    // 不保留或失败时删图
    let parsed_ok = analyze.is_ok();
    if !keep || !parsed_ok {
        let _ = std::fs::remove_file(&path);
    }
    let raw = analyze.map_err(|e| e.to_string())?;

    // 5) 解析 JSON
    let (category, title, summary, keywords) = parse_vision_text(&raw);

    // 6) 入库（同步）
    let now = Local::now();
    let storage = state.storage.clone();
    let meta = json!({
        "keywords": keywords,
        "image_path": if keep { path.to_string_lossy().to_string() } else { String::new() },
    });

    let id = {
        let storage = storage.clone();
        let title = title.clone();
        let summary = summary.clone();
        let category = category.clone();
        let meta = meta.clone();
        tokio::task::spawn_blocking(move || {
            storage.add_work_log(
                now,
                "screenshot",
                &title,
                &summary,
                Some(&category),
                meta,
                None,
            )
        })
        .await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())?
    };

    Ok(WorkLog {
        id,
        ts: now,
        source: "screenshot".to_string(),
        category: Some(category),
        title,
        content: summary,
        meta,
        created_at: now,
    })
}

#[tauri::command]
pub async fn start_watch(
    app: AppHandle,
    state: State<'_, AppStateHandle>,
) -> Result<(), String> {
    launch_watch(&app, &state)
}

/// 内部启动逻辑：被 start_watch 命令和应用启动时的 auto_start 共用。
/// 已在跑则幂等返回 Ok。订阅 broadcast 事件后桥接到前端 watch-event。
pub fn launch_watch(app: &AppHandle, state: &AppStateHandle) -> Result<(), String> {
    // 已在跑：幂等返回。
    {
        let g = state.watch.lock();
        if let Some(h) = g.as_ref() {
            if h.is_running() {
                return Ok(());
            }
        }
    }

    let cfg = state.config.lock().clone();
    let storage = state.storage.clone();
    let handle = watch::start(cfg, storage);

    // 订阅广播事件并桥接到前端。
    let mut rx = handle.subscribe();
    let app_for_task = app.clone();
    tokio::spawn(async move {
        loop {
            match rx.recv().await {
                Ok(ev) => {
                    let payload = serde_json::to_value(&ev).unwrap_or(serde_json::Value::Null);
                    let _ = app_for_task.emit("watch-event", payload);
                    if matches!(ev, WatchEvent::Stopped) {
                        break;
                    }
                }
                Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => {
                    // 订阅落后：继续 recv；不视为退出。
                    continue;
                }
                Err(_) => break,
            }
        }
    });

    *state.watch.lock() = Some(handle);
    Ok(())
}

#[tauri::command]
pub async fn stop_watch(state: State<'_, AppStateHandle>) -> Result<(), String> {
    let handle_opt = state.watch.lock().take();
    if let Some(h) = handle_opt {
        h.stop();
        h.join().await;
    }
    Ok(())
}

#[tauri::command]
pub async fn is_watching(state: State<'_, AppStateHandle>) -> Result<bool, String> {
    let g = state.watch.lock();
    Ok(g.as_ref().map(|h| h.is_running()).unwrap_or(false))
}

// ---------------------------------------------------------------------------
// Git
// ---------------------------------------------------------------------------

/// 拉取最近一段时间的 Git 提交并入库（dedupe），返回本次 commits 总条数。
///
/// 时间窗口对齐自动清理保留天数 `cfg.app.cleanup_keep_days`：
/// 自动清理会删 N 天前的所有记录，再去同步更老的提交毫无意义；
/// `<= 0` 表示不限制（保底兜到 365 天，避免全仓库扫描过慢）。
#[tauri::command]
pub async fn sync_git(state: State<'_, AppStateHandle>) -> Result<usize, String> {
    let cfg = state.config.lock().clone();
    let storage = state.storage.clone();
    // git 收集是同步阻塞操作，扔到 blocking thread 上执行。
    let kind = templates::Kind::Daily;
    let count = tokio::task::spawn_blocking(move || {
        let keep_days = cfg.app.cleanup_keep_days;
        let span_days = if keep_days > 0 { keep_days } else { 365 };
        let since = Local::now() - chrono::Duration::days(span_days);
        let until = Local::now();
        let commits = report_assistant_core::git::collect_for_user(&cfg.git, since, until)?;
        for c in &commits {
            let title = if c.subject.is_empty() {
                c.message.lines().next().unwrap_or("").to_string()
            } else {
                c.subject.clone()
            };
            let meta = serde_json::json!({
                "dedupe_key": c.hash,
                "hash": c.hash,
                "short_hash": c.short_hash,
                "author_name": c.author_name,
                "author_email": c.author_email,
                "repo": c.repo,
                "repo_name": c.repo_name,
                "is_merge": c.is_merge,
            });
            let _ = storage.add_work_log(
                c.time,
                "git",
                &title,
                &c.message,
                Some("commit"),
                meta,
                Some(&c.hash),
            );
        }
        // kind 引入避免编译器警告并保持兼容（未来可换 collect_data）。
        let _ = kind;
        Ok::<usize, report_assistant_core::Error>(commits.len())
    })
    .await
    .map_err(|e| e.to_string())?
    .map_err(|e| e.to_string())?;

    Ok(count)
}

// ---------------------------------------------------------------------------
// 报告
// ---------------------------------------------------------------------------

#[tauri::command(rename_all = "camelCase")]
pub async fn generate_report(
    state: State<'_, AppStateHandle>,
    request: GenerateRequest,
) -> Result<GenerateResult, String> {
    let cfg = state.config.lock().clone();
    let storage = state.storage.clone();
    let llm = LlmClient::new(cfg.llm.clone()).map_err(|e| e.to_string())?;

    generator::generate_report(&cfg, &storage, &llm, request)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn list_templates() -> Result<Vec<ReportTemplate>, String> {
    Ok(templates::all())
}

#[tauri::command(rename_all = "camelCase")]
pub async fn export_report(
    state: State<'_, AppStateHandle>,
    id: i64,
    format: String,
    out_dir: String,
) -> Result<String, String> {
    let fmt = match format.to_ascii_lowercase().as_str() {
        "md" | "markdown" => ExportFormat::Md,
        "html" | "htm" => ExportFormat::Html,
        "txt" | "text" => ExportFormat::Txt,
        "docx" | "word" => ExportFormat::Docx,
        other => return Err(format!("不支持的导出格式: {}", other)),
    };

    let storage = state.storage.clone();
    let dir = expand_dir(&out_dir);

    let path = tokio::task::spawn_blocking(move || -> Result<PathBuf, String> {
        let report = storage
            .get_report(id)
            .map_err(|e| e.to_string())?
            .ok_or_else(|| format!("报告 id={} 不存在", id))?;
        exporters::export_report(&report, &dir, fmt).map_err(|e| e.to_string())
    })
    .await
    .map_err(|e| e.to_string())??;

    Ok(path.to_string_lossy().to_string())
}

// ---------------------------------------------------------------------------
// LLM
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn test_llm_connection(cfg: LlmConfig) -> Result<(bool, String), String> {
    Ok(llm::check_connection(&cfg).await)
}

// ---------------------------------------------------------------------------
// 路径 / 杂项
// ---------------------------------------------------------------------------

/// 在系统文件管理器中打开日志目录。
#[tauri::command]
pub async fn open_log_dir(app: AppHandle) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    let dir = paths::log_dir().map_err(|e| e.to_string())?;
    app.opener()
        .open_path(dir.to_string_lossy().to_string(), None::<&str>)
        .map_err(|e| e.to_string())
}

// ---------------------------------------------------------------------------
// 辅助
// ---------------------------------------------------------------------------

fn parse_rfc3339(s: &str) -> Result<DateTime<Local>, String> {
    DateTime::parse_from_rfc3339(s)
        .map(|dt| dt.with_timezone(&Local))
        .map_err(|e| format!("无效 RFC3339 时间 `{}`: {}", s, e))
}

fn expand_dir(s: &str) -> PathBuf {
    let trimmed = s.trim();
    if trimmed.is_empty() {
        return std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    }
    paths::expand_tilde(trimmed)
}

/// 简化版的 vision JSON 解析（与 watch 模块逻辑等价，但不复用 private 函数）。
fn parse_vision_text(text: &str) -> (String, String, String, Vec<String>) {
    let mut s = text.trim().to_string();
    if s.starts_with("```") {
        let lines: Vec<&str> = s.lines().collect();
        let body: Vec<&str> = lines
            .iter()
            .skip_while(|l| l.starts_with("```"))
            .take_while(|l| l.trim() != "```")
            .copied()
            .collect();
        s = body.join("\n").trim().to_string();
    }
    if !s.starts_with('{') {
        if let (Some(i), Some(j)) = (s.find('{'), s.rfind('}')) {
            if j > i {
                s = s[i..=j].to_string();
            }
        }
    }
    match serde_json::from_str::<serde_json::Value>(&s) {
        Ok(v) => {
            let category = v
                .get("category")
                .and_then(|x| x.as_str())
                .unwrap_or("其他")
                .to_string();
            let title: String = v
                .get("title")
                .and_then(|x| x.as_str())
                .unwrap_or("屏幕内容")
                .chars()
                .take(60)
                .collect();
            let summary: String = v
                .get("summary")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .chars()
                .take(500)
                .collect();
            let keywords = v
                .get("keywords")
                .and_then(|x| x.as_array())
                .map(|a| {
                    a.iter()
                        .filter_map(|x| x.as_str().map(|s| s.to_string()))
                        .take(10)
                        .collect()
                })
                .unwrap_or_default();
            (category, title, summary, keywords)
        }
        Err(_) => (
            "其他".to_string(),
            text.trim().chars().take(30).collect(),
            text.trim().chars().take(300).collect(),
            vec![],
        ),
    }
}

// 让 `Arc` 在 doc 测试 / 文档示例中可见，避免未使用 import 的警告。
#[allow(dead_code)]
fn _arc_marker(_: Arc<()>) {}
