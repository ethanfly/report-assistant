//! 应用全局状态：跨 Tauri command 共享的存储、配置、监听句柄、日志保护对象。

use parking_lot::Mutex;
use report_assistant_core::{config::Config, storage::Storage, watch::WatchHandle};
use std::sync::Arc;
use tracing_appender::non_blocking::WorkerGuard;

/// 应用状态。`Arc<AppState>` 通过 `tauri::Builder::manage` 注入，
/// 之后所有 `#[tauri::command]` 用 `State<'_, AppStateHandle>` 取出。
pub struct AppState {
    /// SQLite 存储入口；内部已是 `Arc<Pool>`，clone 廉价。
    pub storage: Storage,
    /// 当前配置；写入时整体替换，不持有过 await。
    pub config: Mutex<Config>,
    /// 后台监听句柄，启动后存入；停止后置 None。
    pub watch: Mutex<Option<WatchHandle>>,
    /// 日志 worker guard。drop 后日志后台线程会停止，必须随 AppState 一起活到进程退出。
    /// 用 `Mutex<Option<…>>` 是为了与启动失败时回退 None 兼容。
    pub _log_guard: Mutex<Option<WorkerGuard>>,
}

pub type AppStateHandle = Arc<AppState>;
