//! 待办一体弹窗 + 全局快捷键。
//!
//! 单一窗口 `todo-popup`：顶部 Markdown 输入 + 下方待办列表。
//! 默认全局热键 `Alt+Space`（主窗最小化/托盘时同样生效）。

use report_assistant_core::config::TodoConfig;
use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

use crate::state::AppStateHandle;

pub const POPUP_LABEL: &str = "todo-popup";

/// 创建（若不存在）并显示一体弹窗。
pub fn show_todo_popup(app: &AppHandle) -> tauri::Result<()> {
    // 清理旧版拆分窗口（若仍存在）
    for old in ["todo-quick", "todo-list"] {
        if let Some(w) = app.get_webview_window(old) {
            let _ = w.close();
        }
    }

    if let Some(w) = app.get_webview_window(POPUP_LABEL) {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.center();
        let _ = w.set_focus();
        let _ = app.emit("todo-popup-focus", ());
        return Ok(());
    }
    build_popup(app)?;
    Ok(())
}

fn build_popup(app: &AppHandle) -> tauri::Result<()> {
    let url = WebviewUrl::App("index.html?window=todo-popup".into());
    let win = WebviewWindowBuilder::new(app, POPUP_LABEL, url)
        .title("待办")
        .inner_size(480.0, 560.0)
        .min_inner_size(400.0, 420.0)
        .max_inner_size(640.0, 800.0)
        .resizable(true)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .visible(true)
        .focused(true)
        .center()
        .build()?;
    let _ = win.set_focus();
    Ok(())
}

/// 注册全局快捷键（按配置）。空字符串跳过。
pub fn register_hotkeys(app: &AppHandle, todo: &TodoConfig) {
    unregister_all(app);
    let hotkey = todo.effective_hotkey();
    if let Err(e) = try_register(app, &hotkey) {
        tracing::warn!(hotkey = %hotkey, "注册待办热键失败: {e}");
    } else if !hotkey.trim().is_empty() {
        tracing::info!(hotkey = %hotkey, "已注册待办热键");
    }
}

pub fn reregister_hotkeys(app: &AppHandle, todo: &TodoConfig) {
    register_hotkeys(app, todo);
}

fn unregister_all(app: &AppHandle) {
    if let Err(e) = app.global_shortcut().unregister_all() {
        tracing::debug!("unregister_all hotkeys: {e}");
    }
}

fn try_register(app: &AppHandle, hotkey: &str) -> Result<(), String> {
    let s = hotkey.trim();
    if s.is_empty() {
        return Ok(());
    }
    let shortcut: Shortcut = s
        .parse()
        .map_err(|e| format!("无效快捷键 `{s}`: {e}"))?;
    app.global_shortcut()
        .register(shortcut)
        .map_err(|e| e.to_string())
}

fn parse_hotkey(s: &str) -> Option<Shortcut> {
    let s = s.trim();
    if s.is_empty() {
        return None;
    }
    s.parse().ok()
}

/// 构建 global-shortcut 插件。
pub fn init_plugin() -> tauri::plugin::TauriPlugin<tauri::Wry> {
    tauri_plugin_global_shortcut::Builder::new()
        .with_handler(move |app, shortcut, event| {
            if event.state() != ShortcutState::Pressed {
                return;
            }

            let hotkey = match app.try_state::<AppStateHandle>() {
                Some(state) => state.config.lock().todo.effective_hotkey(),
                None => return,
            };

            if let Some(s) = parse_hotkey(&hotkey) {
                if s.id() == shortcut.id() {
                    if let Err(e) = show_todo_popup(app) {
                        tracing::warn!("热键打开待办弹窗失败: {e}");
                    }
                }
            }
        })
        .build()
}
