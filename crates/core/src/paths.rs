//! 用户数据目录。
//!
//! Windows: ``%USERPROFILE%/.report-assistant``
//! macOS / Linux: ``~/.report-assistant``

use std::path::PathBuf;

use crate::{Error, Result};

const APP_DIR: &str = ".report-assistant";

/// 应用根目录（``~/.report-assistant``）。不存在会创建。
pub fn app_dir() -> Result<PathBuf> {
    let home = dirs::home_dir().ok_or_else(|| Error::config("无法定位用户主目录"))?;
    let p = home.join(APP_DIR);
    std::fs::create_dir_all(&p)?;
    Ok(p)
}

pub fn config_path() -> Result<PathBuf> {
    Ok(app_dir()?.join("config.yml"))
}

pub fn db_path() -> Result<PathBuf> {
    Ok(app_dir()?.join("data.sqlite"))
}

pub fn screenshots_dir() -> Result<PathBuf> {
    let p = app_dir()?.join("screenshots");
    std::fs::create_dir_all(&p)?;
    Ok(p)
}

pub fn log_dir() -> Result<PathBuf> {
    let p = app_dir()?.join("logs");
    std::fs::create_dir_all(&p)?;
    Ok(p)
}

/// 把 ``~`` 展开成绝对路径，用于配置中用户填的路径。
pub fn expand_tilde(p: impl AsRef<str>) -> PathBuf {
    let s = p.as_ref();
    if let Some(rest) = s.strip_prefix("~/") {
        if let Some(home) = dirs::home_dir() {
            return home.join(rest);
        }
    } else if s == "~" {
        if let Some(home) = dirs::home_dir() {
            return home;
        }
    }
    PathBuf::from(s)
}
