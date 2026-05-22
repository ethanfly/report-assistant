//! 日志初始化（轮转文件 + stderr）。

use tracing_subscriber::{EnvFilter, fmt, prelude::*};

use crate::{Result, paths};

/// 初始化全局 tracing subscriber。幂等，重复调用安全。
pub fn init() -> Result<tracing_appender::non_blocking::WorkerGuard> {
    let dir = paths::log_dir()?;
    let appender = tracing_appender::rolling::daily(&dir, "app.log");
    let (non_blocking, guard) = tracing_appender::non_blocking(appender);

    let env_filter = EnvFilter::try_from_env("REPORT_ASSISTANT_LOG")
        .unwrap_or_else(|_| EnvFilter::new("info,hyper=warn,reqwest=warn,h2=warn,sqlx=warn"));

    let file_layer = fmt::layer()
        .with_ansi(false)
        .with_writer(non_blocking)
        .with_target(true);

    let stderr_layer = fmt::layer()
        .with_ansi(true)
        .with_writer(std::io::stderr)
        .with_target(true);

    let _ = tracing_subscriber::registry()
        .with(env_filter)
        .with(file_layer)
        .with(stderr_layer)
        .try_init();

    Ok(guard)
}
