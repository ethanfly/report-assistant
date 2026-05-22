//! report-assistant 核心业务库（纯 Rust，不依赖 GUI）。
//!
//! 模块边界：
//! - [`config`] 应用配置 + 读写
//! - [`storage`] SQLite 持久化（连接池 + WAL）
//! - [`screenshot`] 跨平台截图 + 空闲检测
//! - [`git`] 提交收集（基于 libgit2）
//! - [`llm`] OpenAI 兼容协议客户端
//! - [`generator`] 报告生成（聚合数据 + 调 LLM）
//! - [`templates`] 报告模板
//! - [`exporters`] 报告导出（md/html/pdf...）
//! - [`watch`] 后台监听服务（截图分析循环）
//! - [`paths`] 用户数据目录解析
//! - [`logging`] 日志初始化
//!
//! 所有耗时 / IO 操作均为 ``async``，调用方负责放在合适的 runtime 上。
//! 业务错误统一走 [`Error`] / [`Result`]。

pub mod config;
pub mod error;
pub mod exporters;
pub mod generator;
pub mod git;
pub mod llm;
pub mod logging;
pub mod paths;
pub mod screenshot;
pub mod storage;
pub mod templates;
pub mod watch;

pub use error::{Error, Result};
