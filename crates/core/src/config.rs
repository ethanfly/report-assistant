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

/// 单个 LLM 端点配置。
///
/// 一个 provider 对应一条 OpenAI 兼容（或类似协议）的 API 端点 + 模型 + 凭据。
/// `id` 必须在 `LlmConfig.providers` 内唯一，会被 `default_text_id` /
/// `default_vision_id` 引用。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmProvider {
    #[serde(default)]
    pub id: String,
    /// 显示名称（UI 用）；空则前端 fallback 到 `provider + model`。
    #[serde(default)]
    pub name: String,
    /// 协议家族：当前都按 OpenAI 兼容处理；保留字段以便日后区分 anthropic native 等。
    #[serde(default = "default_provider")]
    pub provider: String,
    #[serde(default = "default_base_url")]
    pub base_url: String,
    #[serde(default)]
    pub api_key: String,
    #[serde(default = "default_model")]
    pub model: String,
    #[serde(default = "default_temperature")]
    pub temperature: f32,
    #[serde(default = "default_timeout")]
    pub timeout: u64,
}

impl Default for LlmProvider {
    fn default() -> Self {
        Self {
            id: String::new(),
            name: String::new(),
            provider: default_provider(),
            base_url: default_base_url(),
            api_key: String::new(),
            model: default_model(),
            temperature: default_temperature(),
            timeout: default_timeout(),
        }
    }
}

/// 多 provider LLM 配置。
///
/// - 自动迁移旧扁平配置（单 provider）：参见 `From<LlmConfigRaw>`
/// - 默认文本 / 视觉模型通过 id 引用 providers 中的某一条
/// - 找不到对应 provider 时返回 None，调用方应据此报错
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(from = "LlmConfigRaw")]
pub struct LlmConfig {
    #[serde(default)]
    pub providers: Vec<LlmProvider>,
    #[serde(default)]
    pub default_text_id: String,
    #[serde(default)]
    pub default_vision_id: String,
}

impl LlmConfig {
    /// 解析"默认文本 provider"。无匹配返回 None。
    pub fn resolve_text(&self) -> Option<&LlmProvider> {
        if self.default_text_id.trim().is_empty() {
            return None;
        }
        self.providers
            .iter()
            .find(|p| p.id == self.default_text_id)
    }

    /// 解析"默认视觉 provider"。无匹配返回 None。
    pub fn resolve_vision(&self) -> Option<&LlmProvider> {
        if self.default_vision_id.trim().is_empty() {
            return None;
        }
        self.providers
            .iter()
            .find(|p| p.id == self.default_vision_id)
    }
}

/// 反序列化中介：兼容旧扁平结构。
///
/// 通过把所有字段都做成 Option，再在 `From` 里根据 `providers` 是否存在
/// 区分新旧两种 yaml 写法，避免 `#[serde(untagged)]` 在带默认值时的歧义。
#[derive(Deserialize, Default)]
struct LlmConfigRaw {
    // 新结构
    #[serde(default)]
    providers: Option<Vec<LlmProvider>>,
    #[serde(default)]
    default_text_id: Option<String>,
    #[serde(default)]
    default_vision_id: Option<String>,

    // 旧扁平结构（仅在 providers 缺失时启用）
    #[serde(default)]
    provider: Option<String>,
    #[serde(default)]
    base_url: Option<String>,
    #[serde(default)]
    api_key: Option<String>,
    #[serde(default)]
    model: Option<String>,
    #[serde(default)]
    vision_model: Option<String>,
    #[serde(default)]
    temperature: Option<f32>,
    #[serde(default)]
    timeout: Option<u64>,
}

impl From<LlmConfigRaw> for LlmConfig {
    fn from(raw: LlmConfigRaw) -> Self {
        // Case 1: 新结构
        if let Some(providers) = raw.providers {
            return LlmConfig {
                providers,
                default_text_id: raw.default_text_id.unwrap_or_default(),
                default_vision_id: raw.default_vision_id.unwrap_or_default(),
            };
        }

        // Case 2: 旧扁平结构
        // 仅当至少有一个旧字段非空时才迁移；都为空（含纯空对象）时返回 default。
        let has_legacy = raw.provider.is_some()
            || raw.base_url.is_some()
            || raw.api_key.is_some()
            || raw.model.is_some()
            || raw.vision_model.is_some()
            || raw.temperature.is_some()
            || raw.timeout.is_some();
        if !has_legacy {
            return LlmConfig::default();
        }

        let provider_str = raw.provider.unwrap_or_else(default_provider);
        let base_url = raw.base_url.unwrap_or_else(default_base_url);
        let api_key = raw.api_key.unwrap_or_default();
        let model = raw.model.unwrap_or_else(default_model);
        let vision_model = raw.vision_model.unwrap_or_default();
        let temperature = raw.temperature.unwrap_or_else(default_temperature);
        let timeout = raw.timeout.unwrap_or_else(default_timeout);

        let text_id = "legacy".to_string();
        let mut providers = vec![LlmProvider {
            id: text_id.clone(),
            name: "默认".to_string(),
            provider: provider_str.clone(),
            base_url: base_url.clone(),
            api_key: api_key.clone(),
            model: model.clone(),
            temperature,
            timeout,
        }];

        // 旧的 vision_model 与文本模型不同 → 迁移成独立的 provider。
        // 否则视觉直接复用文本那条。
        let trimmed_vision = vision_model.trim();
        let default_vision_id = if !trimmed_vision.is_empty() && trimmed_vision != model {
            let vid = "legacy-vision".to_string();
            providers.push(LlmProvider {
                id: vid.clone(),
                name: "默认（视觉）".to_string(),
                provider: provider_str,
                base_url,
                api_key,
                model: trimmed_vision.to_string(),
                temperature,
                timeout,
            });
            vid
        } else {
            text_id.clone()
        };

        LlmConfig {
            providers,
            default_text_id: text_id,
            default_vision_id,
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
    #[serde(default)]
    pub silent_launch: bool,
    #[serde(default = "default_cleanup_days")]
    pub cleanup_keep_days: i64,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            auto_launch_on_boot: false,
            silent_launch: false,
            cleanup_keep_days: default_cleanup_days(),
        }
    }
}

fn default_todo_hotkey() -> String {
    // Alt+Space：轻量唤起「输入 + 列表」一体弹窗（托盘/最小化同样生效）
    "Alt+Space".to_string()
}

/// 待办 / 备忘录相关配置。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TodoConfig {
    /// 全局快捷键：弹出「输入 + 列表」一体窗口。
    /// 使用 tauri-plugin-global-shortcut 格式，默认 `Alt+Space`。
    /// 空字符串表示禁用。
    #[serde(default = "default_todo_hotkey")]
    pub hotkey: String,

    // —— 兼容旧配置字段（读写时忽略语义，仅迁移用）——
    /// 已弃用：请使用 `hotkey`。反序列化时若 `hotkey` 缺省会回退到此字段。
    #[serde(default, skip_serializing)]
    pub quick_add_hotkey: Option<String>,
    /// 已弃用。
    #[serde(default, skip_serializing)]
    pub list_hotkey: Option<String>,
}

impl Default for TodoConfig {
    fn default() -> Self {
        Self {
            hotkey: default_todo_hotkey(),
            quick_add_hotkey: None,
            list_hotkey: None,
        }
    }
}

impl TodoConfig {
    /// 解析实际生效的快捷键：优先 `hotkey`，否则回退旧字段，再否则默认。
    pub fn effective_hotkey(&self) -> String {
        let h = self.hotkey.trim();
        if !h.is_empty() {
            return h.to_string();
        }
        if let Some(q) = self.quick_add_hotkey.as_deref() {
            let q = q.trim();
            if !q.is_empty() {
                return q.to_string();
            }
        }
        default_todo_hotkey()
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
    #[serde(default)]
    pub todo: TodoConfig,
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
    // 环境变量覆盖（CI / 临时使用）：仅作用于"默认文本 provider"对应那条。
    apply_env_overrides(&mut cfg);
    Ok(cfg)
}

/// 把 REPORT_ASSISTANT_* 环境变量写到默认文本 provider 上。
/// 找不到时尝试写到 providers[0]；providers 为空则忽略。
fn apply_env_overrides(cfg: &mut Config) {
    let key = std::env::var("REPORT_ASSISTANT_API_KEY").ok();
    let base = std::env::var("REPORT_ASSISTANT_BASE_URL").ok();
    let model = std::env::var("REPORT_ASSISTANT_MODEL").ok();
    if key.is_none() && base.is_none() && model.is_none() {
        return;
    }
    let id = cfg.llm.default_text_id.clone();
    // 先定位 index（不可变借用），再做可变写入；避免 iter_mut + or_else 的二次借用。
    let idx = cfg
        .llm
        .providers
        .iter()
        .position(|p| p.id == id)
        .or(if cfg.llm.providers.is_empty() { None } else { Some(0) });
    if let Some(i) = idx {
        let p = &mut cfg.llm.providers[i];
        if let Some(k) = key { p.api_key = k; }
        if let Some(b) = base { p.base_url = b; }
        if let Some(m) = model { p.model = m; }
    }
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
/// 至少需要：默认文本 provider 存在且其 api_key 非空。
pub fn is_ready(cfg: &Config) -> bool {
    cfg.llm
        .resolve_text()
        .map(|p| !p.api_key.trim().is_empty())
        .unwrap_or(false)
}

#[allow(dead_code)]
fn _unused_error_marker(_: &Error) {}
