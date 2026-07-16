//! report-assistant 命令行入口。
//!
//! 整体设计：
//! - 用 [`clap`] derive 定义命令树；二进制名 `report-assistant`（在 Cargo.toml 中声明）。
//! - 所有耗时 / 网络操作走 tokio 异步；`main` 用 `#[tokio::main]`。
//! - 核心业务全部委托给 `report-assistant-core` crate，CLI 仅做：
//!   1) 解析参数；2) 调用核心 API；3) 打印人类可读输出（或 `--json`）。
//! - 错误统一收敛到 [`anyhow::Error`]：`core::Error` 实现了 `std::error::Error`，
//!   通过 `?` 自动转换。

use std::path::PathBuf;

use anyhow::{Context, Result, anyhow, bail};
use chrono::{DateTime, Duration, Local, NaiveDate, TimeZone};
use clap::{Args, Parser, Subcommand, ValueEnum};
use serde::Serialize;
use serde_json::Value as JsonValue;

use report_assistant_core as core;
use report_assistant_core::{
    config::Config,
    exporters::ExportFormat,
    generator::{GenerateRequest, generate_report},
    llm::{ChatMessage, LlmClient, check_connection},
    paths,
    screenshot::{capture_screen, idle_seconds, list_monitors},
    storage::Storage,
    templates::Kind,
};

// ---------------------------------------------------------------------------
// 常量
// ---------------------------------------------------------------------------

/// 单次 capture 命令使用的视觉提示词。
/// 与 `core::watch::VISION_PROMPT` 保持一致；CLI 自己保留一份避免循环依赖。
const VISION_PROMPT: &str = "你是工作内容识别助手。请分析这张屏幕截图，识别用户当前正在做什么工作。

请用 JSON 格式返回，且仅返回 JSON，不要添加 markdown 代码块标记：
{
  \"category\": \"开发|会议|沟通|文档|学习|设计|测试|其他\",
  \"title\": \"一句话概括（10-20 字）\",
  \"summary\": \"2-3 句话描述具体在做什么、用到的工具/项目/页面\",
  \"keywords\": [\"关键词1\", \"关键词2\"]
}

注意：
- 如果截图中有明显的代码、IDE、终端，归类为\"开发\"。
- 如果是会议软件（Zoom/Teams/腾讯会议等），归类为\"会议\"。
- 不要编造看不到的内容；信息不足就如实写\"屏幕内容不明确\"。
- 不要包含个人隐私信息（如完整邮箱、密码、token）。
";

// ---------------------------------------------------------------------------
// 命令定义
// ---------------------------------------------------------------------------

#[derive(Parser, Debug)]
#[command(
    name = "report-assistant",
    version,
    about = "工作报告助手：自动采集 Git 提交 / 屏幕活动并生成日 / 周 / 月报"
)]
struct Cli {
    /// 以 JSON 格式输出结果（适合脚本调用）
    #[arg(long, global = true)]
    json: bool,

    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// 写入默认配置（已存在则保留原文件）
    Init,

    /// 配置管理
    Config {
        #[command(subcommand)]
        cmd: ConfigCmd,
    },

    /// 立即截图分析一次并入库
    Capture,

    /// 前台运行后台监听（Ctrl+C 退出）
    Watch(WatchArgs),

    /// Git 同步 / 浏览
    Git {
        #[command(subcommand)]
        cmd: GitCmd,
    },

    /// 报告生成与管理
    Report {
        #[command(subcommand)]
        cmd: ReportCmd,
    },

    /// 列出最近的工作日志
    Logs(LogsArgs),

    /// LLM 工具
    Llm {
        #[command(subcommand)]
        cmd: LlmCmd,
    },

    /// 清理旧数据
    Cleanup(CleanupArgs),

    /// 数据库统计
    Stats,

    /// 枚举显示器
    Monitors,
}

#[derive(Subcommand, Debug)]
enum ConfigCmd {
    /// 打印当前配置（YAML）
    Show,
    /// 打印配置文件路径
    Path,
    /// 修改某字段，path 形如 `llm.api_key` / `screenshot.interval_seconds`
    Set { path: String, value: String },
}

#[derive(Args, Debug)]
struct WatchArgs {
    /// 截图间隔（秒）；不传则使用配置文件中的值
    #[arg(long)]
    interval: Option<u64>,
}

#[derive(Subcommand, Debug)]
enum GitCmd {
    /// 把今日 / 本周提交拉到本地数据库（按配置中的仓库列表）
    Sync,
    /// 列出最近 N 天的提交（不入库）
    List {
        #[arg(long, default_value_t = 7)]
        days: i64,
    },
}

#[derive(Subcommand, Debug)]
enum ReportCmd {
    /// 生成日报
    Daily(GenArgs),
    /// 生成周报
    Weekly(GenArgs),
    /// 生成月报
    Monthly(GenArgs),
    /// 列出报告
    List {
        #[arg(long, default_value_t = 20)]
        limit: usize,
    },
    /// 展示报告内容
    Show { id: i64 },
    /// 导出报告
    Export {
        id: i64,
        /// 导出格式
        #[arg(long, value_enum)]
        format: ExportFmt,
        /// 输出目录
        #[arg(long)]
        out: PathBuf,
    },
}

#[derive(Args, Debug)]
struct GenArgs {
    /// 锚点日期，YYYY-MM-DD；默认今天
    #[arg(long)]
    date: Option<String>,
    /// 报告模板 key（standard / concise / technical / okr 等）
    #[arg(long)]
    template: Option<String>,
    /// 用户额外补充
    #[arg(long, default_value = "")]
    notes: String,
}

#[derive(Copy, Clone, Debug, ValueEnum)]
enum ExportFmt {
    Md,
    Html,
    Txt,
}

impl From<ExportFmt> for ExportFormat {
    fn from(f: ExportFmt) -> Self {
        match f {
            ExportFmt::Md => ExportFormat::Md,
            ExportFmt::Html => ExportFormat::Html,
            ExportFmt::Txt => ExportFormat::Txt,
        }
    }
}

#[derive(Args, Debug)]
struct LogsArgs {
    #[arg(long, default_value_t = 50)]
    limit: usize,
    /// 仅展示该来源（git / screenshot / manual / ...）
    #[arg(long)]
    source: Option<String>,
}

#[derive(Subcommand, Debug)]
enum LlmCmd {
    /// 测试 LLM 连接
    Test,
}

#[derive(Args, Debug)]
struct CleanupArgs {
    /// 保留最近多少天，超过的删除
    #[arg(long, default_value_t = 60)]
    days: i64,
    /// 清空全部数据
    #[arg(long)]
    all: bool,
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

#[tokio::main]
async fn main() -> Result<()> {
    // 初始化 tracing；失败也不致命，CLI 仍可正常工作。
    let _guard = core::logging::init().ok();

    let cli = Cli::parse();
    let json = cli.json;

    match cli.cmd {
        Cmd::Init => cmd_init(json).await,
        Cmd::Config { cmd } => cmd_config(cmd, json).await,
        Cmd::Capture => cmd_capture(json).await,
        Cmd::Watch(args) => cmd_watch(args, json).await,
        Cmd::Git { cmd } => cmd_git(cmd, json).await,
        Cmd::Report { cmd } => cmd_report(cmd, json).await,
        Cmd::Logs(args) => cmd_logs(args, json).await,
        Cmd::Llm { cmd } => cmd_llm(cmd, json).await,
        Cmd::Cleanup(args) => cmd_cleanup(args, json).await,
        Cmd::Stats => cmd_stats(json).await,
        Cmd::Monitors => cmd_monitors(json).await,
    }
}

// ---------------------------------------------------------------------------
// init
// ---------------------------------------------------------------------------

async fn cmd_init(json: bool) -> Result<()> {
    let path = core::config::init_default_if_absent()?;
    if json {
        print_json(&serde_json::json!({
            "config_path": path.display().to_string(),
        }))
    } else {
        println!("✓ 配置已就绪：{}", path.display());
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// config
// ---------------------------------------------------------------------------

async fn cmd_config(cmd: ConfigCmd, json: bool) -> Result<()> {
    match cmd {
        ConfigCmd::Show => {
            let cfg = core::config::load()?;
            if json {
                // 转一次 YAML→JSON，保证字段名一致
                let v = serde_json::to_value(&cfg)?;
                print_json(&v)
            } else {
                let yaml = serde_yaml_to_string(&cfg)?;
                print!("{}", yaml);
                Ok(())
            }
        }
        ConfigCmd::Path => {
            let p = paths::config_path()?;
            if json {
                print_json(&serde_json::json!({ "path": p.display().to_string() }))
            } else {
                println!("{}", p.display());
                Ok(())
            }
        }
        ConfigCmd::Set { path, value } => cmd_config_set(&path, &value, json).await,
    }
}

async fn cmd_config_set(path: &str, value: &str, json: bool) -> Result<()> {
    if path.trim().is_empty() {
        bail!("path 不能为空");
    }

    // 1) 读取当前配置（不存在则用默认）
    let cfg = core::config::load()?;
    let mut tree = serde_json::to_value(&cfg).context("配置无法序列化为 JSON")?;

    // 2) 在 JSON 树上设置目标字段
    let parsed_value = parse_scalar(value);
    set_at_path(&mut tree, path, parsed_value.clone())?;

    // 3) 反序列化回 Config，借此校验字段类型
    let new_cfg: Config = serde_json::from_value(tree)
        .with_context(|| format!("路径 '{}' 设置后的配置不合法", path))?;

    // 4) 落盘
    let saved_path = core::config::save(&new_cfg)?;

    if json {
        print_json(&serde_json::json!({
            "path": path,
            "value": parsed_value,
            "config_path": saved_path.display().to_string(),
        }))
    } else {
        // 含 api_key 等敏感字段时不回显完整值
        let display = display_scalar(path, &parsed_value);
        println!("✓ {} = {}", path, display);
        println!("  写入：{}", saved_path.display());
        Ok(())
    }
}

/// 把字符串转成最贴切的 JSON 标量：bool > i64 > f64 > string。
fn parse_scalar(s: &str) -> JsonValue {
    let trimmed = s.trim();
    match trimmed {
        "true" => return JsonValue::Bool(true),
        "false" => return JsonValue::Bool(false),
        _ => {}
    }
    if let Ok(n) = trimmed.parse::<i64>() {
        return serde_json::json!(n);
    }
    if let Ok(f) = trimmed.parse::<f64>() {
        // 仅当 f64 不能被 i64 表示时才走浮点
        return serde_json::json!(f);
    }
    JsonValue::String(s.to_string())
}

/// 给敏感字段（含 `api_key` / `token` / `secret`）打码后再展示。
fn display_scalar(path: &str, v: &JsonValue) -> String {
    let lower = path.to_lowercase();
    let sensitive = lower.contains("api_key")
        || lower.contains("token")
        || lower.contains("secret")
        || lower.contains("password");
    if sensitive {
        if let Some(s) = v.as_str() {
            if s.is_empty() {
                return "(empty)".to_string();
            }
            return format!("{}***", s.chars().take(4).collect::<String>());
        }
    }
    match v {
        JsonValue::String(s) => s.clone(),
        other => other.to_string(),
    }
}

/// 在嵌套 JSON 对象里按点路径设置值。中间缺失的层级会自动创建为对象。
fn set_at_path(root: &mut JsonValue, path: &str, value: JsonValue) -> Result<()> {
    let parts: Vec<&str> = path.split('.').filter(|s| !s.is_empty()).collect();
    if parts.is_empty() {
        bail!("非法路径: {}", path);
    }
    let mut cur: &mut JsonValue = root;
    for p in &parts[..parts.len() - 1] {
        if !cur.is_object() {
            bail!("路径 '{}' 中段 '{}' 不是对象", path, p);
        }
        let obj = cur.as_object_mut().unwrap();
        if !obj.contains_key(*p) {
            obj.insert(p.to_string(), JsonValue::Object(Default::default()));
        }
        cur = obj.get_mut(*p).unwrap();
    }
    let last = parts.last().unwrap();
    let obj = cur
        .as_object_mut()
        .ok_or_else(|| anyhow!("路径 '{}' 末段不是对象", path))?;
    obj.insert(last.to_string(), value);
    Ok(())
}

fn serde_yaml_to_string<T: Serialize>(v: &T) -> Result<String> {
    serde_yaml::to_string(v).context("序列化为 YAML 失败")
}

// ---------------------------------------------------------------------------
// capture（单次截图分析）
// ---------------------------------------------------------------------------

async fn cmd_capture(json: bool) -> Result<()> {
    let cfg = core::config::load()?;
    let storage = open_storage(&cfg)?;
    let vision = cfg
        .llm
        .resolve_vision()
        .ok_or_else(|| anyhow!("未配置默认视觉模型，请先在 config 中指定"))?
        .clone();
    let llm = LlmClient::new(vision).context("LLM 客户端构造失败")?;

    let dir = cfg.resolved_screenshot_dir()?;
    let monitor_index = cfg.screenshot.monitor_index;

    // 截图：放到 blocking thread 避免阻塞 reactor
    let dir_clone = dir.clone();
    let path = tokio::task::spawn_blocking(move || capture_screen(dir_clone, monitor_index))
        .await
        .map_err(|e| anyhow!("截图任务异常: {e}"))??;

    // 视觉分析
    let raw = match llm.analyze_image(&path, VISION_PROMPT).await {
        Ok(s) => s,
        Err(e) => {
            // 失败时清理文件
            let _ = std::fs::remove_file(&path);
            return Err(e.into());
        }
    };

    let parsed = parse_vision_json(&raw);
    let now = Local::now();
    let keep = cfg.screenshot.keep_after_analysis;

    let meta = serde_json::json!({
        "keywords": parsed.keywords,
        "image_path": if keep { path.to_string_lossy().to_string() } else { String::new() },
    });
    if !keep {
        let _ = std::fs::remove_file(&path);
    }

    let id = storage.add_work_log(
        now,
        "screenshot",
        &parsed.title,
        &parsed.summary,
        Some(&parsed.category),
        meta.clone(),
        None,
    )?;

    if json {
        print_json(&serde_json::json!({
            "id": id,
            "ts": now,
            "category": parsed.category,
            "title": parsed.title,
            "summary": parsed.summary,
            "keywords": parsed.keywords,
            "image_path": meta.get("image_path"),
        }))
    } else {
        println!("✓ 已入库 work_log #{} ({})", id, now.format("%Y-%m-%d %H:%M:%S"));
        println!("  分类：{}", parsed.category);
        println!("  标题：{}", parsed.title);
        println!("  摘要：{}", parsed.summary);
        if !parsed.keywords.is_empty() {
            println!("  关键词：{}", parsed.keywords.join(", "));
        }
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// watch（前台监听）
// ---------------------------------------------------------------------------

async fn cmd_watch(args: WatchArgs, json: bool) -> Result<()> {
    let mut cfg = core::config::load()?;
    if let Some(itv) = args.interval {
        cfg.screenshot.interval_seconds = itv;
    }
    let storage = open_storage(&cfg)?;

    let handle = core::watch::start(cfg, storage);
    let mut rx = handle.subscribe();

    if !json {
        println!("✓ watch 已启动，Ctrl+C 退出");
    }

    // 主循环：select(事件 / Ctrl+C)
    loop {
        tokio::select! {
            biased;
            _ = tokio::signal::ctrl_c() => {
                if !json {
                    eprintln!("\n收到 Ctrl+C，正在停止…");
                }
                handle.stop();
                break;
            }
            evt = rx.recv() => {
                match evt {
                    Ok(e) => print_watch_event(&e, json),
                    Err(tokio::sync::broadcast::error::RecvError::Lagged(n)) => {
                        eprintln!("(订阅滞后，丢失 {} 条事件)", n);
                    }
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                }
            }
        }
    }

    handle.join().await;
    if !json {
        println!("watch 已退出");
    }
    Ok(())
}

fn print_watch_event(evt: &core::watch::WatchEvent, json: bool) {
    if json {
        if let Ok(s) = serde_json::to_string(evt) {
            println!("{}", s);
        }
        return;
    }

    use core::watch::WatchEvent::*;
    match evt {
        Started { interval_seconds } => {
            println!("[watch] 已启动，间隔 {}s", interval_seconds);
        }
        Captured {
            ts,
            category,
            title,
            summary,
            keywords,
        } => {
            println!(
                "[{}] {} | {} — {}",
                ts.format("%H:%M:%S"),
                category,
                title,
                summary,
            );
            if !keywords.is_empty() {
                println!("           关键词: {}", keywords.join(", "));
            }
        }
        Failed { message } => {
            eprintln!("[watch] 失败: {}", message);
        }
        IdleSkipped { idle_seconds } => {
            println!("[watch] 空闲 {}s，跳过本轮", idle_seconds);
        }
        Stopped => {
            println!("[watch] 已停止");
        }
    }
}

// ---------------------------------------------------------------------------
// git
// ---------------------------------------------------------------------------

async fn cmd_git(cmd: GitCmd, json: bool) -> Result<()> {
    let cfg = core::config::load()?;

    match cmd {
        GitCmd::Sync => {
            let storage = open_storage(&cfg)?;
            // 默认拉本周（覆盖今日 + 整周）
            let prepared = core::generator::collect_data(
                &cfg,
                &storage,
                Kind::Weekly,
                Local::now(),
                /* include_screenshots */ false,
            )?;
            let count = prepared.commits.len();

            if json {
                print_json(&serde_json::json!({
                    "kind": "weekly",
                    "period_start": prepared.period_start,
                    "period_end": prepared.period_end,
                    "commit_count": count,
                    "commits": prepared.commits,
                }))
            } else {
                println!(
                    "✓ 已同步本周 {} ~ {}：{} 条提交",
                    prepared.period_start.format("%Y-%m-%d"),
                    prepared.period_end.format("%Y-%m-%d"),
                    count,
                );
                for c in &prepared.commits {
                    println!(
                        "  [{}] {} <{}> {} — {}",
                        c.time.format("%m-%d %H:%M"),
                        c.repo_name,
                        c.short_hash,
                        c.author_name,
                        first_line(&c.message),
                    );
                }
                Ok(())
            }
        }
        GitCmd::List { days } => {
            let days = days.max(1);
            let until = Local::now();
            let since = until - Duration::days(days);
            let commits = core::git::collect_for_user(&cfg.git, since, until)?;

            if json {
                print_json(&commits)
            } else {
                println!(
                    "最近 {} 天提交（{} ~ {}）：共 {} 条",
                    days,
                    since.format("%Y-%m-%d"),
                    until.format("%Y-%m-%d"),
                    commits.len(),
                );
                for c in &commits {
                    println!(
                        "  [{}] {} <{}> {} — {}",
                        c.time.format("%m-%d %H:%M"),
                        c.repo_name,
                        c.short_hash,
                        c.author_name,
                        first_line(&c.message),
                    );
                }
                Ok(())
            }
        }
    }
}

// ---------------------------------------------------------------------------
// report
// ---------------------------------------------------------------------------

async fn cmd_report(cmd: ReportCmd, json: bool) -> Result<()> {
    match cmd {
        ReportCmd::Daily(args) => cmd_report_generate(Kind::Daily, args, json).await,
        ReportCmd::Weekly(args) => cmd_report_generate(Kind::Weekly, args, json).await,
        ReportCmd::Monthly(args) => cmd_report_generate(Kind::Monthly, args, json).await,
        ReportCmd::List { limit } => cmd_report_list(limit, json).await,
        ReportCmd::Show { id } => cmd_report_show(id, json).await,
        ReportCmd::Export { id, format, out } => cmd_report_export(id, format, out, json).await,
    }
}

async fn cmd_report_generate(kind: Kind, args: GenArgs, json: bool) -> Result<()> {
    let cfg = core::config::load()?;
    let storage = open_storage(&cfg)?;
    let text_provider = cfg
        .llm
        .resolve_text()
        .ok_or_else(|| anyhow!("未配置默认文本模型，请先在 config 中指定"))?
        .clone();
    let llm = LlmClient::new(text_provider).context("LLM 客户端构造失败")?;

    let anchor = parse_anchor(args.date.as_deref())?;

    let req = GenerateRequest {
        kind: kind.clone(),
        anchor,
        template: args.template,
        extra_notes: args.notes,
        include_screenshots: true,
        include_git: true,
    };

    let result = generate_report(&cfg, &storage, &llm, req).await?;

    if json {
        print_json(&result)
    } else {
        println!(
            "✓ {} 报告 #{} 已生成（模板 {}，{} ~ {}）",
            zh_label(&kind),
            result.report_id,
            result.template,
            result.period_start.format("%Y-%m-%d %H:%M"),
            result.period_end.format("%Y-%m-%d %H:%M"),
        );
        println!(
            "  数据：{} 条已完成待办，{} 条提交，{} 条截图记录",
            result.todo_count, result.commit_count, result.screenshot_count
        );
        println!("---");
        println!("{}", result.content);
        Ok(())
    }
}

async fn cmd_report_list(limit: usize, json: bool) -> Result<()> {
    let cfg = core::config::load()?;
    let storage = open_storage(&cfg)?;
    let reports = storage.list_reports(limit)?;

    if json {
        print_json(&reports)
    } else {
        if reports.is_empty() {
            println!("（暂无报告）");
        }
        for r in &reports {
            println!(
                "#{:<4} [{}] {} ~ {}  template={}  ({})",
                r.id,
                r.kind,
                r.period_start.format("%Y-%m-%d"),
                r.period_end.format("%Y-%m-%d"),
                r.template.as_deref().unwrap_or("-"),
                r.created_at.format("%Y-%m-%d %H:%M"),
            );
        }
        Ok(())
    }
}

async fn cmd_report_show(id: i64, json: bool) -> Result<()> {
    let cfg = core::config::load()?;
    let storage = open_storage(&cfg)?;
    let report = storage
        .get_report(id)?
        .ok_or_else(|| anyhow!("未找到报告 #{}", id))?;

    if json {
        print_json(&report)
    } else {
        println!(
            "#{} [{}] {} ~ {}  template={}",
            report.id,
            report.kind,
            report.period_start.format("%Y-%m-%d"),
            report.period_end.format("%Y-%m-%d"),
            report.template.as_deref().unwrap_or("-"),
        );
        println!("生成时间：{}", report.created_at.format("%Y-%m-%d %H:%M:%S"));
        println!("---");
        println!("{}", report.content);
        Ok(())
    }
}

async fn cmd_report_export(id: i64, fmt: ExportFmt, out: PathBuf, json: bool) -> Result<()> {
    let cfg = core::config::load()?;
    let storage = open_storage(&cfg)?;
    let report = storage
        .get_report(id)?
        .ok_or_else(|| anyhow!("未找到报告 #{}", id))?;

    let path = core::exporters::export_report(&report, &out, fmt.into())?;

    if json {
        print_json(&serde_json::json!({
            "id": id,
            "path": path.display().to_string(),
            "format": format!("{:?}", fmt).to_lowercase(),
        }))
    } else {
        println!("✓ 已导出到 {}", path.display());
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// logs
// ---------------------------------------------------------------------------

async fn cmd_logs(args: LogsArgs, json: bool) -> Result<()> {
    let cfg = core::config::load()?;
    let storage = open_storage(&cfg)?;

    // 没有"按 ts 倒序 + limit"的现成 API；用 1 年区间近似覆盖日常用途。
    let until = Local::now() + Duration::days(1);
    let since = Local::now() - Duration::days(365);
    let mut all = storage.list_work_logs(since, until, args.source.as_deref())?;

    // list_work_logs 是 ASC，反转后取前 limit 条
    all.reverse();
    let limit = if args.limit == 0 { 50 } else { args.limit };
    all.truncate(limit);

    if json {
        print_json(&all)
    } else {
        if all.is_empty() {
            println!("（暂无日志）");
        }
        for log in &all {
            let cat = log.category.as_deref().unwrap_or("-");
            println!(
                "#{:<5} [{}] {:<10} {:<8} {}",
                log.id,
                log.ts.format("%Y-%m-%d %H:%M"),
                log.source,
                truncate(cat, 8),
                log.title,
            );
            if !log.content.is_empty() {
                let snippet: String = log.content.chars().take(120).collect();
                println!("       {}", snippet);
            }
        }
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// llm test
// ---------------------------------------------------------------------------

async fn cmd_llm(cmd: LlmCmd, json: bool) -> Result<()> {
    match cmd {
        LlmCmd::Test => {
            let cfg = core::config::load()?;
            let provider = match cfg.llm.resolve_text() {
                Some(p) => p.clone(),
                None => {
                    if json {
                        return print_json(&serde_json::json!({
                            "ok": false,
                            "message": "未配置默认文本模型，请先指定 default_text_id"
                        }));
                    } else {
                        eprintln!("✗ 未配置默认文本模型，请先指定 default_text_id");
                        std::process::exit(1);
                    }
                }
            };
            let (ok, msg) = check_connection(&provider).await;

            if json {
                print_json(&serde_json::json!({
                    "ok": ok,
                    "message": msg,
                    "model": provider.model,
                    "base_url": provider.base_url,
                }))
            } else {
                if ok {
                    println!("✓ {}", msg);
                } else {
                    eprintln!("✗ {}", msg);
                }
                if !ok {
                    std::process::exit(1);
                }
                Ok(())
            }
        }
    }
}

// 兼容性：保留同步签名也可以；这里返回未使用的 `()` 给 Rust 检查 happy
#[allow(dead_code)]
fn _placeholder_for_chat_message_use(_: ChatMessage) {}

// ---------------------------------------------------------------------------
// cleanup / stats / monitors
// ---------------------------------------------------------------------------

async fn cmd_cleanup(args: CleanupArgs, json: bool) -> Result<()> {
    let cfg = core::config::load()?;
    let storage = open_storage(&cfg)?;

    let stats = if args.all {
        storage.purge_all()?
    } else {
        let cutoff = Local::now() - Duration::days(args.days.max(0));
        storage.purge_before(cutoff)?
    };

    if json {
        print_json(&stats)
    } else {
        println!(
            "✓ 已清理：work_logs {} 条，reports {} 条",
            stats.work_logs, stats.reports
        );
        Ok(())
    }
}

async fn cmd_stats(json: bool) -> Result<()> {
    let cfg = core::config::load()?;
    let storage = open_storage(&cfg)?;
    let s = storage.stats()?;

    if json {
        print_json(&s)
    } else {
        println!("work_logs: {}", s.work_logs_total);
        println!("reports:   {}", s.reports_total);
        match (s.earliest_log, s.latest_log) {
            (Some(a), Some(b)) => println!(
                "区间:      {} ~ {}",
                a.format("%Y-%m-%d %H:%M"),
                b.format("%Y-%m-%d %H:%M"),
            ),
            _ => println!("区间:      （无数据）"),
        }
        Ok(())
    }
}

async fn cmd_monitors(json: bool) -> Result<()> {
    let monitors = list_monitors();
    if json {
        return print_json(&monitors);
    }
    if monitors.is_empty() {
        println!("（未检测到显示器）");
    }
    for m in &monitors {
        println!("#{:<2} {}  ({}×{})", m.index, m.label, m.width, m.height);
    }
    let idle = idle_seconds();
    println!("当前空闲秒数：{}", idle);
    Ok(())
}

// ---------------------------------------------------------------------------
// 辅助
// ---------------------------------------------------------------------------

fn open_storage(cfg: &Config) -> Result<Storage> {
    let path = cfg.resolved_db_path()?;
    Storage::open(&path).with_context(|| format!("打开数据库失败：{}", path.display()))
}

fn print_json<T: Serialize>(v: &T) -> Result<()> {
    let s = serde_json::to_string_pretty(v).context("JSON 序列化失败")?;
    println!("{}", s);
    Ok(())
}

fn first_line(s: &str) -> String {
    s.lines().next().unwrap_or("").trim().to_string()
}

fn truncate(s: &str, max_chars: usize) -> String {
    let mut out = String::new();
    for (i, c) in s.chars().enumerate() {
        if i >= max_chars {
            break;
        }
        out.push(c);
    }
    out
}

/// 把 YYYY-MM-DD 解析为本地中午 12:00（避开 DST 边界）。
fn parse_anchor(s: Option<&str>) -> Result<DateTime<Local>> {
    let Some(d) = s else {
        return Ok(Local::now());
    };
    let nd = NaiveDate::parse_from_str(d.trim(), "%Y-%m-%d")
        .with_context(|| format!("无效日期：{}（应为 YYYY-MM-DD）", d))?;
    let ndt = nd
        .and_hms_opt(12, 0, 0)
        .ok_or_else(|| anyhow!("时间构造失败"))?;
    Local
        .from_local_datetime(&ndt)
        .single()
        .ok_or_else(|| anyhow!("本地时区映射失败"))
}

fn zh_label(k: &Kind) -> &'static str {
    match k {
        Kind::Daily => "日报",
        Kind::Weekly => "周报",
        Kind::Monthly => "月报",
    }
}

// ---------------------------------------------------------------------------
// 视觉响应解析（capture 复用 watch 的逻辑，独立维护一份避免循环依赖）
// ---------------------------------------------------------------------------

struct ParsedVision {
    category: String,
    title: String,
    summary: String,
    keywords: Vec<String>,
}

fn parse_vision_json(text: &str) -> ParsedVision {
    let mut s = text.trim().to_string();
    if s.starts_with("```") {
        let lines: Vec<&str> = s.lines().collect();
        let body: Vec<&str> = lines
            .iter()
            .skip_while(|l| l.starts_with("```"))
            .take_while(|l| l.trim() != "```")
            .copied()
            .collect();
        s = body.join("\n").trim().to_string();
    }
    if !s.starts_with('{') {
        if let (Some(i), Some(j)) = (s.find('{'), s.rfind('}')) {
            if j > i {
                s = s[i..=j].to_string();
            }
        }
    }

    match serde_json::from_str::<JsonValue>(&s) {
        Ok(v) => {
            let category = v
                .get("category")
                .and_then(|x| x.as_str())
                .unwrap_or("其他")
                .to_string();
            let title = v
                .get("title")
                .and_then(|x| x.as_str())
                .unwrap_or("屏幕内容")
                .chars()
                .take(60)
                .collect();
            let summary = v
                .get("summary")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .chars()
                .take(500)
                .collect();
            let keywords = v
                .get("keywords")
                .and_then(|x| x.as_array())
                .map(|a| {
                    a.iter()
                        .filter_map(|x| x.as_str().map(|s| s.to_string()))
                        .take(10)
                        .collect()
                })
                .unwrap_or_default();
            ParsedVision {
                category,
                title,
                summary,
                keywords,
            }
        }
        Err(_) => ParsedVision {
            category: "其他".to_string(),
            title: text.trim().chars().take(30).collect(),
            summary: text.trim().chars().take(300).collect(),
            keywords: vec![],
        },
    }
}
