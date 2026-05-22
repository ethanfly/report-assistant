//! 系统托盘：显示主窗口、切换监听、打开日志目录、退出。

use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Manager};

use crate::state::AppStateHandle;

/// 在 `setup` 阶段调用一次即可。失败会向上冒泡阻止启动。
pub fn setup(app: &AppHandle) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "显示主窗口", true, None::<&str>)?;
    let toggle = MenuItem::with_id(app, "toggle_watch", "切换监听", true, None::<&str>)?;
    let logs = MenuItem::with_id(app, "open_logs", "打开日志目录", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &toggle, &logs, &quit])?;

    let mut builder = TrayIconBuilder::new()
        .menu(&menu)
        .tooltip("小T日报助手")
        .on_menu_event(|app, ev| match ev.id.as_ref() {
            "show" => {
                if let Some(w) = app.get_webview_window("main") {
                    let _ = w.show();
                    let _ = w.unminimize();
                    let _ = w.set_focus();
                }
            }
            "toggle_watch" => {
                // 在异步里切换：避免阻塞菜单事件回调。
                let app = app.clone();
                tauri::async_runtime::spawn(async move {
                    if let Some(state) = app.try_state::<AppStateHandle>() {
                        let running = state
                            .watch
                            .lock()
                            .as_ref()
                            .map(|h| h.is_running())
                            .unwrap_or(false);
                        if running {
                            let _ = crate::commands::stop_watch(state).await;
                        } else {
                            let _ = crate::commands::start_watch(app.clone(), state).await;
                        }
                    }
                });
            }
            "open_logs" => {
                use tauri_plugin_opener::OpenerExt;
                if let Ok(dir) = report_assistant_core::paths::log_dir() {
                    let _ = app
                        .opener()
                        .open_path(dir.to_string_lossy().to_string(), None::<&str>);
                }
            }
            "quit" => {
                app.exit(0);
            }
            _ => {}
        });

    // 默认窗口图标在打包模式下由 bundle 生成；开发期可能拿不到，做兼容回退。
    if let Some(icon) = app.default_window_icon().cloned() {
        builder = builder.icon(icon);
    }

    let _tray = builder.build(app)?;
    Ok(())
}
