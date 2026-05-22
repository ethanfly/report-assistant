//! 统一错误类型。

use thiserror::Error;

#[derive(Debug, Error)]
pub enum Error {
    #[error("IO 错误: {0}")]
    Io(#[from] std::io::Error),

    #[error("配置错误: {0}")]
    Config(String),

    #[error("YAML 解析错误: {0}")]
    Yaml(#[from] serde_yaml::Error),

    #[error("JSON 解析错误: {0}")]
    Json(#[from] serde_json::Error),

    #[error("数据库错误: {0}")]
    Sqlite(#[from] rusqlite::Error),

    #[error("数据库连接池错误: {0}")]
    Pool(#[from] r2d2::Error),

    #[error("HTTP 错误: {0}")]
    Http(#[from] reqwest::Error),

    #[error("LLM 错误: {0}")]
    Llm(String),

    #[error("Git 错误: {0}")]
    Git(#[from] git2::Error),

    #[error("截图错误: {0}")]
    Screenshot(String),

    #[error("图像处理错误: {0}")]
    Image(#[from] image::ImageError),

    #[error("内部错误: {0}")]
    Internal(String),

    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

impl Error {
    pub fn config(msg: impl Into<String>) -> Self {
        Self::Config(msg.into())
    }
    pub fn llm(msg: impl Into<String>) -> Self {
        Self::Llm(msg.into())
    }
    pub fn screenshot(msg: impl Into<String>) -> Self {
        Self::Screenshot(msg.into())
    }
    pub fn internal(msg: impl Into<String>) -> Self {
        Self::Internal(msg.into())
    }
}

pub type Result<T> = std::result::Result<T, Error>;
