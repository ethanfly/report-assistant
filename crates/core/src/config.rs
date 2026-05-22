//! 应用配置：从 ``~/.report-assistant/config.yml`` 读写。

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::{Error, Result, paths};

fn default_true() -> bool {
    true
}
fn default_provider() -> String {
    "openai".to_string()
}
fn default_base_url() -> String {
    "https://api.openai.com/v1".to_string()
}
fn default_model() -> String {
    "gpt-4o-mini".to_string()
}
fn default_temperature() -> f32 {
    0.4
}
fn default_timeout() -> u64 {
    60
}
fn default_interval() -> u64 {
    600
}
fn default_idle() -> u64 {
    300
}
fn default_monitor() -> i32 {
    1
}
fn default_poll_git() -> u64 {
    600
}
fn default_template() -> String {
    "standard".to_string()
}
fn default_lang() -> String {
    "zh-CN".to_string()
}
fn default_cleanup_days() -> i64 {
    60
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmConfig {
    #[serde(default = "default_provider")]
    pub provider: String,
    #[serde(default = "default_base_url")]
    pub base_url: String,
    #[serde(default)]
    pub api_key: String,
    #[serde(default = "default_model")]
    pub model: String,
    /// 用于截图分析的多模态模型；为空则与 `model` 相同。
    #[serde(default = "default_model")]
    pub vision_model: String,
    #[serde(default = "default_temperature")]
    pub temperature: f32,
    /// 单次请求超时（秒）
    #[serde(default = "default_timeout")]
    pub timeout: u64,
}

impl Default for LlmConfig {
    fn default() -> Self {
        Self {
            provider: default_provider(),
            base_url: default_base_url(),
            api_key: String::new(),
            model: default_model(),
            vision_model: default_model(),
            temperature: default_temperature(),
            timeout: default_timeout(),
        }
    }
}

/// 一个 Git 仓库条目：路径 + 可选别名。
///
/// 序列化形式：
/// - 新格式：`{ path: "/foo", alias: "前端" }`
/// - 旧格式：纯字符串 `"/foo"`，由 `Deserialize` 自动兼容
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(from = "RepoEntryRaw")]
pub struct RepoEntry {
    pub path: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub alias: String,
}

impl RepoEntry {
    /// 仓库展示名：优先 alias，没有就用 path 末段。
    pub fn display_name(&self) -> String {
        let trimmed = self.alias.trim();
        if !trimmed.is_empty() {
            return trimmed.to_string();
        }
        std::path::Path::new(&self.path)
            .file_name()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_else(|| self.path.clone())
    }
}

/// 反序列化中介：兼容字符串与对象两种写法。
#[derive(Deserialize)]
#[serde(untagged)]
enum RepoEntryRaw {
    /// 旧格式：直接是字符串路径
    Path(String),
    /// 新格式：`{ path, alias? }`
    Full {
        path: String,
        #[serde(default)]
        alias: String,
    },
}

impl From<RepoEntryRaw> for RepoEntry {
    fn from(raw: RepoEntryRaw) -> Self {
        match raw {
            RepoEntryRaw::Path(p) => RepoEntry { path: p, alias: String::new() },
            RepoEntryRaw::Full { path, alias } => RepoEntry { path, alias },
        }
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct GitConfig {
    #[serde(default)]
    pub repos: Vec<RepoEntry>,
    #[serde(default)]
    pub author_emails: Vec<String>,
    #[serde(default)]
    pub author_names: Vec<String>,
    #[serde(default)]
    pub include_merges: bool,
    /// 桌面端定时同步 git 的间隔（秒），<=0 关闭
    #[serde(default = "default_poll_git")]
    pub poll_interval_seconds: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScreenshotConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_interval")]
    pub interval_seconds: u64,
    #[serde(default)]
    pub keep_after_analysis: bool,
    /// 截图保存目录；空表示用默认 (~/.report-assistant/screenshots)
    #[serde(default)]
    pub output_dir: String,
    #[serde(default)]
    pub auto_start: bool,
    #[serde(default = "default_monitor")]
    pub monitor_index: i32,
    /// 用户连续无操作超过该秒数时跳过截图，<=0 禁用
    #[serde(default = "default_idle")]
    pub idle_skip_seconds: u64,
}

impl Default for ScreenshotConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            interval_seconds: default_interval(),
            keep_after_analysis: false,
            output_dir: String::new(),
            auto_start: false,
            monitor_index: default_monitor(),
            idle_skip_seconds: default_idle(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReportConfig {
    #[serde(default = "default_template")]
    pub default_template: String,
    #[serde(default = "default_lang")]
    pub language: String,
    #[serde(default)]
    pub user_name: String,
    #[serde(default)]
    pub team: String,
}

impl Default for ReportConfig {
    fn default() -> Self {
        Self {
            default_template: default_template(),
            language: default_lang(),
            user_name: String::new(),
            team: String::new(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    #[serde(default)]
    pub auto_launch_on_boot: bool,
    #[serde(default = "default_cleanup_days")]
    pub cleanup_keep_days: i64,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            auto_launch_on_boot: false,
            cleanup_keep_days: default_cleanup_days(),
        }
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Config {
    #[serde(default)]
    pub llm: LlmConfig,
    #[serde(default)]
    pub git: GitConfig,
    #[serde(default)]
    pub screenshot: ScreenshotConfig,
    #[serde(default)]
    pub report: ReportConfig,
    #[serde(default)]
    pub app: AppConfig,
    /// 数据库路径；空表示用默认 (~/.report-assistant/data.sqlite)
    #[serde(default)]
    pub db_path: String,
}

impl Config {
    /// 数据库实际路径（处理 ``~`` 与默认值）。
    pub fn resolved_db_path(&self) -> Result<PathBuf> {
        if self.db_path.is_empty() {
            paths::db_path()
        } else {
            Ok(paths::expand_tilde(&self.db_path))
        }
    }

    /// 截图保存目录（处理默认值）。
    pub fn resolved_screenshot_dir(&self) -> Result<PathBuf> {
        if self.screenshot.output_dir.is_empty() {
            paths::screenshots_dir()
        } else {
            let p = paths::expand_tilde(&self.screenshot.output_dir);
            std::fs::create_dir_all(&p)?;
            Ok(p)
        }
    }
}

/// 加载配置；不存在时返回默认值并不报错。
pub fn load() -> Result<Config> {
    let path = paths::config_path()?;
    if !path.exists() {
        return Ok(Config::default());
    }
    let raw = std::fs::read_to_string(&path)?;
    if raw.trim().is_empty() {
        return Ok(Config::default());
    }
    let mut cfg: Config = serde_yaml::from_str(&raw)?;
    // 环境变量覆盖（CI / 临时使用）
    if let Ok(k) = std::env::var("REPORT_ASSISTANT_API_KEY") {
        cfg.llm.api_key = k;
    }
    if let Ok(b) = std::env::var("REPORT_ASSISTANT_BASE_URL") {
        cfg.llm.base_url = b;
    }
    if let Ok(m) = std::env::var("REPORT_ASSISTANT_MODEL") {
        cfg.llm.model = m;
    }
    Ok(cfg)
}

/// 持久化到默认路径（覆写）。
pub fn save(cfg: &Config) -> Result<PathBuf> {
    let path = paths::config_path()?;
    save_to(cfg, &path)?;
    Ok(path)
}

pub fn save_to(cfg: &Config, path: &Path) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let yaml = serde_yaml::to_string(cfg)?;
    std::fs::write(path, yaml)?;
    Ok(())
}

/// 写入一份带注释的初始模板（如已有同名文件不覆盖）。
pub fn init_default_if_absent() -> Result<PathBuf> {
    let path = paths::config_path()?;
    if path.exists() {
        return Ok(path);
    }
    let template = include_str!("config_template.yml");
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&path, template)?;
    Ok(path)
}

/// 帮助调用方判断"配置看起来已就绪"。
pub fn is_ready(cfg: &Config) -> bool {
    !cfg.llm.api_key.trim().is_empty()
}

#[allow(dead_code)]
fn _unused_error_marker(_: &Error) {}
