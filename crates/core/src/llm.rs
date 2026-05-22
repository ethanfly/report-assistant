//! OpenAI 兼容协议的 LLM 客户端：支持文本对话与图片视觉分析。
//!
//! 设计目标：
//! - 异步、非阻塞，全部基于 reqwest async API
//! - 错误统一收敛到 [`crate::Error::Llm`] / [`crate::Error::Http`]
//! - 视觉模型走 `image_url` data URL，与 OpenAI / 兼容服务一致

use std::path::Path;
use std::time::Duration;

use base64::Engine;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::{Error, Result, config::LlmProvider};

/// 角色枚举（保留供调用方按强类型构造，序列化时仍以小写字符串呈现）。
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ChatRole {
    System,
    User,
    Assistant,
}

impl ChatRole {
    pub fn as_str(&self) -> &'static str {
        match self {
            ChatRole::System => "system",
            ChatRole::User => "user",
            ChatRole::Assistant => "assistant",
        }
    }
}

/// 一条聊天消息。
///
/// `content` 既可能是字符串，也可能是多模态数组（视觉），因此用 `serde_json::Value`。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: Value,
}

impl ChatMessage {
    /// 文本消息便捷构造器。
    pub fn text(role: impl Into<String>, content: impl Into<String>) -> Self {
        Self {
            role: role.into(),
            content: Value::String(content.into()),
        }
    }
}

/// LLM 客户端：基于单个 provider 构造。
///
/// 文本生成用 `cfg.llm.resolve_text()` 拿到的 provider；
/// 视觉分析用 `cfg.llm.resolve_vision()`。同一个 client 不再混用两种模型，
/// 避免之前 `vision_model` 共用 base_url/api_key 的耦合。
pub struct LlmClient {
    provider: LlmProvider,
    http: reqwest::Client,
}

impl LlmClient {
    /// 构造客户端。`api_key` 为空时返回错误。
    pub fn new(provider: LlmProvider) -> Result<Self> {
        if provider.api_key.trim().is_empty() {
            return Err(Error::llm(format!(
                "LLM provider 「{}」未配置 api_key",
                if provider.name.is_empty() { provider.id.as_str() } else { provider.name.as_str() }
            )));
        }
        let http = build_client(&provider, provider.timeout)?;
        Ok(Self { provider, http })
    }

    /// 当前 provider 的可读名（优先 name，回退 id，再回退 model）。
    pub fn label(&self) -> String {
        if !self.provider.name.is_empty() {
            self.provider.name.clone()
        } else if !self.provider.id.is_empty() {
            self.provider.id.clone()
        } else {
            self.provider.model.clone()
        }
    }

    /// 文本对话，返回助手回复内容。
    pub async fn chat(
        &self,
        messages: Vec<ChatMessage>,
        model: Option<&str>,
        temperature: Option<f32>,
    ) -> Result<String> {
        let model = model.unwrap_or(&self.provider.model);
        let temp = temperature.unwrap_or(self.provider.temperature);
        chat_request(&self.http, &self.provider.base_url, model, temp, &messages).await
    }

    /// 图片视觉分析：读取本地图片转 base64 data URL，使用当前 provider 的 model。
    pub async fn analyze_image(
        &self,
        image_path: impl AsRef<Path>,
        prompt: &str,
    ) -> Result<String> {
        let path = image_path.as_ref();
        let bytes = tokio::fs::read(path).await?;
        let ext = guess_image_ext(path);
        let b64 = base64::engine::general_purpose::STANDARD.encode(&bytes);
        let data_url = format!("data:image/{};base64,{}", ext, b64);

        let content = json!([
            { "type": "text", "text": prompt },
            { "type": "image_url", "image_url": { "url": data_url } },
        ]);
        let messages = vec![ChatMessage {
            role: "user".to_string(),
            content,
        }];

        chat_request(
            &self.http,
            &self.provider.base_url,
            &self.provider.model,
            self.provider.temperature,
            &messages,
        )
        .await
    }
}

/// 一次性快速连通性检查：发送一个简短 ping，限定较短超时；绝不 panic。
///
/// 返回：(是否成功, 描述信息)
pub async fn check_connection(provider: &LlmProvider) -> (bool, String) {
    if provider.api_key.trim().is_empty() {
        return (false, "未配置 api_key".to_string());
    }
    let timeout = provider.timeout.min(15).max(1);
    let http = match build_client(provider, timeout) {
        Ok(c) => c,
        Err(e) => return (false, format!("初始化 HTTP 客户端失败: {e}")),
    };
    let messages = vec![ChatMessage::text("user", "ping")];
    match chat_request(
        &http,
        &provider.base_url,
        &provider.model,
        provider.temperature,
        &messages,
    )
    .await
    {
        Ok(reply) => {
            let snippet: String = reply.chars().take(40).collect();
            (
                true,
                format!("连接成功（model={}）: {}", provider.model, snippet),
            )
        }
        Err(e) => (false, format!("连接失败: {e}")),
    }
}

// ---------------- 内部辅助 ----------------

/// 构造带鉴权头与超时的 reqwest::Client。
fn build_client(cfg: &LlmProvider, timeout_secs: u64) -> Result<reqwest::Client> {
    use reqwest::header::{AUTHORIZATION, CONTENT_TYPE, HeaderMap, HeaderValue};

    let mut headers = HeaderMap::new();
    let bearer = format!("Bearer {}", cfg.api_key);
    let mut auth_val = HeaderValue::from_str(&bearer)
        .map_err(|e| Error::llm(format!("无效的 api_key: {e}")))?;
    auth_val.set_sensitive(true);
    headers.insert(AUTHORIZATION, auth_val);
    headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(timeout_secs.max(1)))
        .default_headers(headers)
        .build()?;
    Ok(client)
}

/// 发起一次 chat/completions 请求并解析 `choices[0].message.content`。
async fn chat_request(
    http: &reqwest::Client,
    base_url: &str,
    model: &str,
    temperature: f32,
    messages: &[ChatMessage],
) -> Result<String> {
    let url = format!("{}/chat/completions", base_url.trim_end_matches('/'));
    let body = json!({
        "model": model,
        "messages": messages,
        "temperature": temperature,
    });

    let resp = http.post(&url).json(&body).send().await?;
    let status = resp.status();
    if !status.is_success() {
        let snippet = resp
            .text()
            .await
            .unwrap_or_default()
            .chars()
            .take(500)
            .collect::<String>();
        return Err(Error::llm(format!("HTTP {}: {}", status, snippet)));
    }

    let json: Value = resp.json().await?;
    let content = json
        .get("choices")
        .and_then(|c| c.get(0))
        .and_then(|c| c.get("message"))
        .and_then(|m| m.get("content"));

    match content {
        Some(Value::String(s)) => Ok(s.clone()),
        // 部分兼容服务返回数组形式 content（多段文本）：拼接 text 字段
        Some(Value::Array(arr)) => {
            let mut buf = String::new();
            for item in arr {
                if let Some(t) = item.get("text").and_then(|v| v.as_str()) {
                    buf.push_str(t);
                }
            }
            Ok(buf)
        }
        Some(other) => Ok(other.to_string()),
        None => Err(Error::llm(format!(
            "响应缺少 choices[0].message.content: {}",
            json
        ))),
    }
}

/// 根据扩展名推断 image data URL 中的 MIME 子类型。
fn guess_image_ext(path: &Path) -> String {
    let ext = path
        .extension()
        .and_then(|s| s.to_str())
        .map(|s| s.to_lowercase())
        .unwrap_or_else(|| "png".to_string());
    match ext.as_str() {
        "jpg" => "jpeg".to_string(),
        _ => ext,
    }
}
