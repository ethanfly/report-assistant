//! 跨平台截图与系统空闲检测。
//!
//! - 截图：基于 [`xcap`] 抓取屏幕像素，等比例缩放后以 PNG 形式落盘，
//!   返回文件路径供上层（视觉模型 / 报告生成）使用。
//! - 空闲检测：用于"无操作时跳过截图"等节能策略。
//!   - Windows：调用 `GetLastInputInfo` + `GetTickCount` 计算自上次输入后的秒数。
//!   - 其他平台：当前未实现，返回 0（即"不空闲"，不影响业务流程）。
//!
//! 模块对外 API 为同步函数，调用方按需放在 `tokio::task::spawn_blocking` 中。

use std::path::{Path, PathBuf};

use chrono::Local;
use image::{DynamicImage, ImageFormat, RgbaImage, imageops::FilterType};
use serde::{Deserialize, Serialize};
use tracing::{debug, warn};
use xcap::Monitor;

use crate::{Error, Result};

/// 截图缩放后长边的最大像素值。
///
/// 多模态模型对超大图分辨率不敏感，限制长边可以显著降低 base64 体积，
/// 同时仍保留足够的可识别细节。
const MAX_LONG_EDGE: u32 = 1600;

/// 显示器条目。
///
/// `index = 0` 是合并条目（"全部屏幕"），`1+` 对应 [`Monitor::all`] 中的具体显示器，
/// 与历史 Python 版本保持一致，方便已有配置无缝迁移。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MonitorInfo {
    /// 0 = 全部合并；1+ = 具体屏幕（即 `Monitor::all()[index - 1]`）。
    pub index: i32,
    /// 展示给用户的标签，例如 `"屏幕 1 · 1920×1080"`。
    pub label: String,
    pub width: u32,
    pub height: u32,
}

/// 列出所有可用的显示器。
///
/// 失败时（xcap 异常 / 平台不支持）返回空 `Vec`，不会 panic，方便 UI 渲染。
pub fn list_monitors() -> Vec<MonitorInfo> {
    let monitors = match Monitor::all() {
        Ok(v) => v,
        Err(e) => {
            warn!("枚举显示器失败: {}", e);
            return Vec::new();
        }
    };

    let mut out: Vec<MonitorInfo> = Vec::with_capacity(monitors.len() + 1);

    // 合并条目：宽高取所有屏幕的最大值，便于 UI 估算
    let max_w = monitors.iter().map(|m| m.width()).max().unwrap_or(0);
    let max_h = monitors.iter().map(|m| m.height()).max().unwrap_or(0);
    out.push(MonitorInfo {
        index: 0,
        label: format!("全部屏幕（{} 个）", monitors.len()),
        width: max_w,
        height: max_h,
    });

    for (i, m) in monitors.iter().enumerate() {
        let w = m.width();
        let h = m.height();
        out.push(MonitorInfo {
            index: (i as i32) + 1,
            label: format!("屏幕 {} · {}×{}", i + 1, w, h),
            width: w,
            height: h,
        });
    }

    out
}

/// 截屏到指定目录，返回保存后的文件路径。
///
/// - `monitor_index = 0`：取 [`Monitor::all`] 中的主屏；若没有标记 primary 的，
///   则退化为第一个屏幕。
/// - `monitor_index >= 1`：取 `Monitor::all()[(monitor_index - 1) as usize]`，
///   越界时回退到第一个屏幕。
/// - 长边大于 [`MAX_LONG_EDGE`] 时按比例缩放（`Lanczos3`）。
/// - 输出文件名形如 `shot_20240131_120000.png`。
pub fn capture_screen(output_dir: impl AsRef<Path>, monitor_index: i32) -> Result<PathBuf> {
    let dir = output_dir.as_ref();
    std::fs::create_dir_all(dir)?;

    let monitors = Monitor::all().map_err(|e| Error::screenshot(e.to_string()))?;
    if monitors.is_empty() {
        return Err(Error::screenshot("未找到可用的显示器"));
    }

    let monitor = pick_monitor(&monitors, monitor_index);

    // 抓取像素 → DynamicImage 以便走 image 的缩放 / 编码管线
    let rgba: RgbaImage = monitor
        .capture_image()
        .map_err(|e| Error::screenshot(format!("抓取屏幕像素失败: {}", e)))?;
    let mut img = DynamicImage::ImageRgba8(rgba);

    // 等比缩放：长边超出阈值时再做，避免无谓的滤波开销
    let (w, h) = (img.width(), img.height());
    let long_edge = w.max(h);
    if long_edge > MAX_LONG_EDGE {
        let scale = MAX_LONG_EDGE as f32 / long_edge as f32;
        let nw = ((w as f32) * scale).round().max(1.0) as u32;
        let nh = ((h as f32) * scale).round().max(1.0) as u32;
        debug!("缩放截图 {}x{} -> {}x{}", w, h, nw, nh);
        img = img.resize(nw, nh, FilterType::Lanczos3);
    }

    // 文件名按本地时间戳；冲突时（同秒重复触发）由调用方负责，这里直接覆盖
    let ts = Local::now().format("%Y%m%d_%H%M%S");
    let filename = format!("shot_{}.png", ts);
    let path = dir.join(filename);

    img.save_with_format(&path, ImageFormat::Png)?;
    debug!("截图已保存: {}", path.display());
    Ok(path)
}

/// 在 `monitors` 中选出目标显示器，封装 0 / 越界等边界。
fn pick_monitor(monitors: &[Monitor], monitor_index: i32) -> Monitor {
    if monitor_index <= 0 {
        // 0 = 主屏；找不到 primary 则退到第一个
        if let Some(m) = monitors.iter().find(|m| m.is_primary()) {
            return m.clone();
        }
        return monitors[0].clone();
    }

    let idx = (monitor_index - 1) as usize;
    if idx >= monitors.len() {
        warn!(
            "monitor_index={} 越界（共 {} 个），回退到第一个屏幕",
            monitor_index,
            monitors.len()
        );
        return monitors[0].clone();
    }
    monitors[idx].clone()
}

/// 用户系统的空闲秒数（自上次键鼠输入起）。
///
/// - Windows：`GetTickCount - LASTINPUTINFO.dwTime`，结果以毫秒计，转为秒返回。
/// - 其他平台：暂无可移植的实现，返回 0；调用方据此跳过空闲检测即可。
#[cfg(windows)]
pub fn idle_seconds() -> u64 {
    use windows::Win32::System::SystemInformation::GetTickCount;
    use windows::Win32::UI::Input::KeyboardAndMouse::{GetLastInputInfo, LASTINPUTINFO};

    let mut lii = LASTINPUTINFO {
        cbSize: std::mem::size_of::<LASTINPUTINFO>() as u32,
        dwTime: 0,
    };

    // 两个调用都是简单的 syscall，不会挂起；唯一风险是 cbSize 不正确，
    // 上面已用 size_of 保证。
    unsafe {
        if GetLastInputInfo(&mut lii).as_bool() {
            let now = GetTickCount();
            // GetTickCount 约 49.7 天回绕一次；用 saturating_sub 避免回绕后短暂返回巨大值
            let elapsed_ms = now.saturating_sub(lii.dwTime);
            return (elapsed_ms / 1000) as u64;
        }
    }
    0
}

/// 非 Windows 平台的占位实现：返回 0 表示"未空闲"。
#[cfg(not(windows))]
pub fn idle_seconds() -> u64 {
    0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn list_monitors_does_not_panic() {
        // 不强求结果非空（CI 可能无显示器），只要不 panic 即可
        let _ = list_monitors();
    }

    #[test]
    fn idle_seconds_returns_some_value() {
        // 保证在所有平台都能调用，且数值落在合理量级（< 10 年）
        let s = idle_seconds();
        assert!(s < 10 * 365 * 24 * 3600);
    }
}
