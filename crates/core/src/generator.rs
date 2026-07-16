//! 报告生成：聚合工作日志 + Git 提交 → 调 LLM → 入库。
//!
//! 提供两个入口：
//! - [`collect_data`]：仅做数据汇总（同步），可用于前端预览或单独 git 同步；
//! - [`generate_report`]：完整流水线，最终落库返回报告 ID。
//!
//! 时间区间按 [`Kind`] 自动计算：
//! - Daily：anchor 当天 00:00 → 次日 00:00
//! - Weekly：anchor 所在周一 00:00 → 下周一 00:00
//! - Monthly：anchor 所在月 1 号 00:00 → 下月 1 号 00:00

use std::fmt::Write as _;

use chrono::{DateTime, Datelike, Duration, Local, NaiveDate, TimeZone};
use serde::{Deserialize, Serialize};

use crate::{
    Error, Result,
    config::Config,
    git, llm, storage,
    templates::{self, Kind, ReportTemplate},
};

/// 生成报告的请求参数。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerateRequest {
    /// 周期种类。
    pub kind: Kind,
    /// 锚点时间，默认 now。
    pub anchor: DateTime<Local>,
    /// 模板 key，不填则使用 `cfg.report.default_template`。
    pub template: Option<String>,
    /// 用户额外补充 / 备注。
    pub extra_notes: String,
    /// 是否包含截图分析摘要（默认 true）。
    pub include_screenshots: bool,
    /// 是否包含 Git 提交（默认 true）。
    pub include_git: bool,
}

impl Default for GenerateRequest {
    fn default() -> Self {
        Self {
            kind: Kind::Daily,
            anchor: Local::now(),
            template: None,
            extra_notes: String::new(),
            include_screenshots: true,
            include_git: true,
        }
    }
}

/// 生成结果。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerateResult {
    pub kind: String,
    pub period_start: DateTime<Local>,
    pub period_end: DateTime<Local>,
    pub template: String,
    pub content: String,
    pub commit_count: usize,
    pub screenshot_count: usize,
    #[serde(default)]
    pub todo_count: usize,
    pub report_id: i64,
}

/// 仅汇总后的中间数据（不含 LLM 输出）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PreparedData {
    pub kind: String,
    pub period_start: DateTime<Local>,
    pub period_end: DateTime<Local>,
    pub work_logs: Vec<storage::WorkLog>,
    pub commits: Vec<git::Commit>,
    /// 本周期内已完成的待办（按 completed_at）。
    #[serde(default)]
    pub completed_todos: Vec<storage::Todo>,
}

/// 计算 [`Kind`] 对应的时间区间 `[start, end)`。
pub fn period_range(
    kind: &Kind,
    anchor: DateTime<Local>,
) -> Result<(DateTime<Local>, DateTime<Local>)> {
    let date = anchor.date_naive();
    let (start_date, end_date) = match kind {
        Kind::Daily => (date, date + Duration::days(1)),
        Kind::Weekly => {
            // chrono::Weekday::num_days_from_monday: 周一=0..周日=6
            let offset = anchor.weekday().num_days_from_monday() as i64;
            let monday = date - Duration::days(offset);
            (monday, monday + Duration::days(7))
        }
        Kind::Monthly => {
            let first = NaiveDate::from_ymd_opt(date.year(), date.month(), 1)
                .ok_or_else(|| Error::internal("无效月份起点"))?;
            let next = if date.month() == 12 {
                NaiveDate::from_ymd_opt(date.year() + 1, 1, 1)
            } else {
                NaiveDate::from_ymd_opt(date.year(), date.month() + 1, 1)
            }
            .ok_or_else(|| Error::internal("无效月份终点"))?;
            (first, next)
        }
    };
    Ok((to_local_midnight(start_date)?, to_local_midnight(end_date)?))
}

fn to_local_midnight(d: NaiveDate) -> Result<DateTime<Local>> {
    let naive = d
        .and_hms_opt(0, 0, 0)
        .ok_or_else(|| Error::internal("00:00:00 时间构造失败"))?;
    Local
        .from_local_datetime(&naive)
        .single()
        .ok_or_else(|| Error::internal("本地时区映射歧义或缺失"))
}

/// 仅汇总数据（同步）。
///
/// 流程：
/// 1. 计算 `[period_start, period_end)`；
/// 2. 拉取该区间内的 Git 提交并写入 `work_logs`（source = "git"，dedupe_key = commit hash）；
/// 3. 从数据库读出 work_logs（include_screenshots=false 时排除 screenshot）。
pub fn collect_data(
    cfg: &Config,
    storage: &storage::Storage,
    kind: Kind,
    anchor: DateTime<Local>,
    include_screenshots: bool,
) -> Result<PreparedData> {
    let (period_start, period_end) = period_range(&kind, anchor)?;

    // ① 拉取 Git 提交并入库（去重交给 storage 层）
    let commits = git::collect_for_user(&cfg.git, period_start, period_end)?;
    for c in &commits {
        let title = if c.subject.is_empty() {
            first_line(&c.message)
        } else {
            c.subject.clone()
        };
        let meta = serde_json::json!({
            "dedupe_key": c.hash,
            "hash": c.hash,
            "short_hash": c.short_hash,
            "author_name": c.author_name,
            "author_email": c.author_email,
            "repo": c.repo,
            "repo_name": c.repo_name,
            "is_merge": c.is_merge,
        });
        // dedupe 命中时 storage 内部会静默跳过。
        let _ = storage.add_work_log(
            c.time,
            "git",
            &title,
            &c.message,
            Some("commit"),
            meta,
            Some(&c.hash),
        );
    }

    // ② 再 list_work_logs，让生成的报告与数据库一致。
    let work_logs = if include_screenshots {
        storage.list_work_logs(period_start, period_end, None)?
    } else {
        // 排除截图时直接在内存里过滤，避免给 storage 增加负向过滤接口。
        let all = storage.list_work_logs(period_start, period_end, None)?;
        all.into_iter()
            .filter(|l| l.source != "screenshot")
            .collect()
    };

    // ③ 本周期已完成的待办（主证据来源）
    let completed_todos = storage.list_completed_todos(period_start, period_end)?;

    Ok(PreparedData {
        kind: kind.as_str().to_string(),
        period_start,
        period_end,
        work_logs,
        commits,
        completed_todos,
    })
}

/// 完整生成（异步）：聚合 → LLM → 入库。
pub async fn generate_report(
    cfg: &Config,
    storage: &storage::Storage,
    llm_client: &llm::LlmClient,
    req: GenerateRequest,
) -> Result<GenerateResult> {
    // 1) 数据准备
    let prepared = collect_data(
        cfg,
        storage,
        req.kind.clone(),
        req.anchor,
        req.include_screenshots,
    )?;

    // 2) 选模板：req → cfg.report.default_template → standard
    let tpl = pick_template(req.template.as_deref(), &cfg.report.default_template);

    // 3) 构造 LLM 消息
    let user_msg = build_user_prompt(cfg, &req, &prepared, &tpl);
    let messages = vec![
        llm::ChatMessage::text("system", &tpl.system_prompt),
        llm::ChatMessage::text("user", &user_msg),
    ];

    // 4) 调 LLM（model / temperature 走客户端默认）
    let content = llm_client.chat(messages, None, None).await?;
    if content.trim().is_empty() {
        return Err(Error::llm("LLM 返回内容为空"));
    }

    // 5) 入库
    let report_id = storage.add_report(
        &prepared.kind,
        prepared.period_start,
        prepared.period_end,
        Some(&tpl.key),
        &content,
    )?;

    // 6) 统计计数
    let commit_count = prepared.commits.len();
    let screenshot_count = prepared
        .work_logs
        .iter()
        .filter(|l| l.source == "screenshot")
        .count();
    let todo_count = prepared.completed_todos.len();

    Ok(GenerateResult {
        kind: prepared.kind,
        period_start: prepared.period_start,
        period_end: prepared.period_end,
        template: tpl.key,
        content,
        commit_count,
        screenshot_count,
        todo_count,
        report_id,
    })
}

/// 模板选择优先级：显式参数 > 配置默认 > standard。
fn pick_template(req_key: Option<&str>, cfg_default: &str) -> ReportTemplate {
    if let Some(k) = req_key {
        if let Some(t) = templates::get(k) {
            return t;
        }
    }
    if let Some(t) = templates::get(cfg_default) {
        return t;
    }
    templates::default_template()
}

/// 拼接给 LLM 的 user 消息。
///
/// 证据优先级：**已完成待办（主）** > Git 提交 > 截图摘要 > 其他记录 > 用户补充。
fn build_user_prompt(
    cfg: &Config,
    req: &GenerateRequest,
    prepared: &PreparedData,
    tpl: &ReportTemplate,
) -> String {
    let mut out = String::with_capacity(1024);

    let _ = writeln!(out, "报告类型：{}", req.kind.label_zh());
    if !cfg.report.user_name.trim().is_empty() {
        let _ = writeln!(out, "撰写人：{}", cfg.report.user_name);
    }
    if !cfg.report.team.trim().is_empty() {
        let _ = writeln!(out, "团队：{}", cfg.report.team);
    }
    let _ = writeln!(
        out,
        "时间范围：{} ~ {}",
        prepared.period_start.format("%Y-%m-%d %H:%M"),
        prepared.period_end.format("%Y-%m-%d %H:%M"),
    );
    out.push_str(
        "\n【重要】本报告请以「已完成待办」为主要事实来源撰写「完成事项」；\
         Git 提交与截图仅作补充佐证，不要用截图臆造完成项。\n\n",
    );

    // —— 已完成待办（主证据） ——
    out.push_str("## 已完成待办（优先依据）\n");
    if prepared.completed_todos.is_empty() {
        out.push_str("（本周期内无已完成待办）\n");
    } else {
        for t in &prepared.completed_todos {
            let when = t
                .completed_at
                .map(|dt| dt.format("%m-%d %H:%M").to_string())
                .unwrap_or_else(|| "??".to_string());
            let _ = writeln!(out, "- [{}] {}", when, t.content);
        }
    }
    out.push('\n');

    // —— Git 提交清单 ——
    if req.include_git {
        out.push_str("## Git 提交清单（补充）\n");
        if prepared.commits.is_empty() {
            out.push_str("（本周期内无提交）\n");
        } else {
            for c in &prepared.commits {
                let title = if c.subject.is_empty() {
                    first_line(&c.message)
                } else {
                    c.subject.clone()
                };
                let _ = writeln!(
                    out,
                    "- [{}] {} <{}> {} — {}",
                    c.time.format("%m-%d %H:%M"),
                    c.repo_name,
                    c.short_hash,
                    c.author_name,
                    title,
                );
            }
        }
        out.push('\n');
    }

    // —— 截图分析摘要 ——
    if req.include_screenshots {
        out.push_str("## 截图分析摘要（补充）\n");
        let shots: Vec<&storage::WorkLog> = prepared
            .work_logs
            .iter()
            .filter(|l| l.source == "screenshot")
            .collect();
        if shots.is_empty() {
            out.push_str("（本周期内无截图记录）\n");
        } else {
            for s in shots {
                let summary = if s.content.chars().count() > 240 {
                    let truncated: String = s.content.chars().take(240).collect();
                    format!("{}…", truncated)
                } else {
                    s.content.clone()
                };
                let _ = writeln!(
                    out,
                    "- [{}] {} — {}",
                    s.ts.format("%m-%d %H:%M"),
                    s.title,
                    summary,
                );
            }
        }
        out.push('\n');
    }

    // —— 其他来源（手动录入等；todo 已在上方专节出现，这里排除） ——
    let others: Vec<&storage::WorkLog> = prepared
        .work_logs
        .iter()
        .filter(|l| l.source != "screenshot" && l.source != "git" && l.source != "todo")
        .collect();
    if !others.is_empty() {
        out.push_str("## 其他工作记录\n");
        for o in others {
            let _ = writeln!(
                out,
                "- [{}] ({}) {} — {}",
                o.ts.format("%m-%d %H:%M"),
                o.source,
                o.title,
                o.content,
            );
        }
        out.push('\n');
    }

    // —— 用户额外笔记 ——
    if !req.extra_notes.trim().is_empty() {
        out.push_str("## 用户补充\n");
        out.push_str(req.extra_notes.trim());
        out.push_str("\n\n");
    }

    // —— 模板提示 ——
    out.push_str("## 输出要求\n");
    out.push_str(&tpl.user_prompt_hint);

    out
}

fn first_line(s: &str) -> String {
    s.lines().next().unwrap_or("").trim().to_string()
}
