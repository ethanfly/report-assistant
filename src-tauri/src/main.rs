// release 构建时禁用控制台窗口（仅 Windows 生效），避免 GUI 程序闪一个黑色 cmd。
// debug 构建仍保留 console，便于看 stderr/println。
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! 小T日报助手 Tauri 主进程入口。

mod commands;
mod state;
mod tray;

use std::path::PathBuf;
use std::sync::Arc;

use parking_lot::Mutex;
use report_assistant_core::{config, logging, storage::Storage};
use tauri::Manager;

use crate::state::AppState;

fn main() {
    // 1) 日志：失败也要让 UI 起来，错误打印到 stderr。
    let log_guard = match logging::init() {
        Ok(g) => Some(g),
        Err(e) => {
            eprintln!("日志初始化失败: {e}");
            None
        }
    };

    // 2) 配置 + 数据库：失败回退到默认配置 + 临时数据库，避免阻塞启动。
    let cfg = config::load().unwrap_or_else(|e| {
        eprintln!("加载配置失败，将使用默认配置: {e}");
        config::Config::default()
    });

    let db_path = cfg
        .resolved_db_path()
        .unwrap_or_else(|_| PathBuf::from("data.sqlite"));
    let storage = Storage::open(&db_path).expect("打开数据库失败");

    // 3) 组装 AppState
    let app_state: Arc<AppState> = Arc::new(AppState {
        storage,
        config: Mutex::new(cfg),
        watch: Mutex::new(None),
        _log_guard: Mutex::new(log_guard),
    });

    // 4) Tauri Builder
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            // 二开实例：激活既有主窗口。
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.show();
                let _ = w.unminimize();
                let _ = w.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            commands::load_config,
            commands::save_config,
            commands::list_work_logs,
            commands::list_reports,
            commands::get_report,
            commands::delete_report,
            commands::delete_work_log,
            commands::storage_stats,
            commands::purge_before,
            commands::purge_all,
            commands::list_monitors,
            commands::capture_once,
            commands::start_watch,
            commands::stop_watch,
            commands::is_watching,
            commands::sync_git,
            commands::generate_report,
            commands::add_manual_log,
            commands::list_templates,
            commands::export_report,
            commands::test_llm_connection,
            commands::open_log_dir,
        ])
        .setup(|app| {
            tray::setup(app.handle())?;

            // 启动时检查 auto_start：开启且 LLM 已配置则自动启用监听。
            // 延迟 1.5s 让 webview 先初始化，避免 watch-event 早于前端订阅丢事件。
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                tokio::time::sleep(std::time::Duration::from_millis(1500)).await;
                let state: tauri::State<'_, crate::state::AppStateHandle> = app_handle.state();
                let (auto_start, has_vision, auto_launch_on_boot) = {
                    let cfg = state.config.lock();
                    let has = cfg
                        .llm
                        .resolve_vision()
                        .map(|p| !p.api_key.trim().is_empty())
                        .unwrap_or(false);
                    (
                        cfg.screenshot.auto_start,
                        has,
                        cfg.app.auto_launch_on_boot,
                    )
                };
                // 把系统级开机自启状态同步为配置期望值
                commands::sync_autostart(&app_handle, auto_launch_on_boot);
                if auto_start && has_vision {
                    tracing::info!("auto_start 已启用，自动开始监听");
                    if let Err(e) = commands::launch_watch(&app_handle, &state) {
                        tracing::warn!("auto_start 启动失败: {}", e);
                    }
                } else if auto_start && !has_vision {
                    tracing::warn!("auto_start 已启用但默认视觉 provider 未配置，跳过");
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            // 关闭按钮：隐藏到托盘，保持后台监听存活。
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("运行 Tauri 应用失败");
}
