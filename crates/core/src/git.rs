//! Git 提交收集：基于 libgit2 提取本地仓库属于"我"的提交。
//!
//! 行为对齐旧版 Python 实现：
//! - 按时间区间 [since, until] 过滤
//! - 可选按作者邮箱 / 姓名过滤（任一命中即视为本人）
//! - 可选过滤 merge commit
//! - 输出按时间倒序

use std::path::Path;

use chrono::{DateTime, Local, TimeZone};
use serde::{Deserialize, Serialize};

use crate::{Error, Result, config::GitConfig};

/// 一条 git 提交记录。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Commit {
    /// 仓库本地路径（绝对路径或调用方传入的原始路径）
    pub repo: String,
    /// 路径最后一段，作为仓库简称
    pub repo_name: String,
    /// 完整 SHA
    pub hash: String,
    /// 前 7 位短 SHA
    pub short_hash: String,
    pub author_name: String,
    pub author_email: String,
    /// 提交时间（本地时区）
    pub time: DateTime<Local>,
    /// 完整 message：subject + 空行 + body
    pub message: String,
    /// 第一行
    pub subject: String,
    /// subject 之后的内容（已 trim）
    pub body: String,
    /// 是否为 merge commit
    pub is_merge: bool,
}

/// 判断给定路径是否是 git 仓库（支持普通仓库 / bare 仓库）。
pub fn is_git_repo(path: impl AsRef<Path>) -> bool {
    git2::Repository::open(path.as_ref()).is_ok()
}

/// 收集单个仓库在 [since, until] 时间范围内的所有提交。
///
/// 不做作者过滤，调用方按需要再过滤。返回顺序：提交时间倒序。
/// `display_name` 为空时回退到路径末段。
pub fn collect_commits(
    repo_path: impl AsRef<Path>,
    display_name: Option<&str>,
    since: DateTime<Local>,
    until: DateTime<Local>,
) -> Result<Vec<Commit>> {
    let path = repo_path.as_ref();
    let repo = git2::Repository::open(path)?;

    let repo_str = path.to_string_lossy().to_string();
    let repo_name = display_name
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string())
        .unwrap_or_else(|| {
            path.file_name()
                .map(|s| s.to_string_lossy().to_string())
                .unwrap_or_else(|| repo_str.clone())
        });

    let mut walk = repo.revwalk()?;
    // HEAD 起步；若仓库尚无任何提交，直接返回空
    if walk.push_head().is_err() {
        return Ok(Vec::new());
    }
    walk.set_sorting(git2::Sort::TIME)?;

    let since_ts = since.timestamp();
    let until_ts = until.timestamp();

    let mut out = Vec::new();
    for oid in walk {
        let oid = oid?;
        let commit = repo.find_commit(oid)?;
        let secs = commit.time().seconds();

        // TIME 排序为时间倒序，超过 since 之前的全部可以提前 break
        if secs < since_ts {
            break;
        }
        if secs > until_ts {
            continue;
        }

        let dt = Local
            .timestamp_opt(secs, 0)
            .single()
            .ok_or_else(|| Error::internal("无法解析 git 提交时间戳"))?;

        let author = commit.author();
        let author_name = author.name().unwrap_or("").to_string();
        let author_email = author.email().unwrap_or("").to_string();

        let raw_msg = commit.message().unwrap_or("");
        let (subject, body) = split_subject_body(raw_msg);

        let hash = commit.id().to_string();
        let short_hash = if hash.len() >= 7 {
            hash[..7].to_string()
        } else {
            hash.clone()
        };

        out.push(Commit {
            repo: repo_str.clone(),
            repo_name: repo_name.clone(),
            hash,
            short_hash,
            author_name,
            author_email,
            time: dt,
            message: raw_msg.trim_end().to_string(),
            subject,
            body,
            is_merge: commit.parent_count() > 1,
        });
    }

    Ok(out)
}

/// 按配置批量收集多个仓库的提交。
///
/// 行为：
/// - 自动按 `author_emails` / `author_names` 过滤；都为空时不过滤；任一命中即视为本人
/// - `include_merges = false` 时跳过 merge commit
/// - 单仓库失败仅记录 warn 日志，不中断整体流程
/// - 整体按时间倒序排列
pub fn collect_for_user(
    cfg: &GitConfig,
    since: DateTime<Local>,
    until: DateTime<Local>,
) -> Result<Vec<Commit>> {
    let emails: Vec<String> = cfg
        .author_emails
        .iter()
        .map(|s| s.trim().to_lowercase())
        .filter(|s| !s.is_empty())
        .collect();
    let names: Vec<String> = cfg
        .author_names
        .iter()
        .map(|s| s.trim().to_lowercase())
        .filter(|s| !s.is_empty())
        .collect();
    let no_author_filter = emails.is_empty() && names.is_empty();

    let mut all: Vec<Commit> = Vec::new();
    for repo in &cfg.repos {
        let trimmed = repo.path.trim();
        if trimmed.is_empty() {
            continue;
        }
        if !is_git_repo(trimmed) {
            tracing::warn!(repo = %trimmed, "跳过非 git 仓库");
            continue;
        }
        let alias = repo.alias.trim();
        let display = if alias.is_empty() { None } else { Some(alias) };
        match collect_commits(trimmed, display, since, until) {
            Ok(list) => {
                for c in list {
                    if !cfg.include_merges && c.is_merge {
                        continue;
                    }
                    if !no_author_filter && !is_self(&c, &emails, &names) {
                        continue;
                    }
                    all.push(c);
                }
            }
            Err(e) => {
                tracing::warn!(repo = %trimmed, error = %e, "收集仓库提交失败");
            }
        }
    }

    all.sort_by(|a, b| b.time.cmp(&a.time));
    Ok(all)
}

/// 把 raw message 切成 subject / body。
fn split_subject_body(raw: &str) -> (String, String) {
    let trimmed = raw.trim_end_matches('\n');
    let mut lines = trimmed.splitn(2, '\n');
    let subject = lines.next().unwrap_or("").trim().to_string();
    let body = lines.next().unwrap_or("").trim().to_string();
    (subject, body)
}

/// 判断该 commit 是否归属"我"。邮箱与姓名均做小写匹配。
fn is_self(c: &Commit, emails: &[String], names: &[String]) -> bool {
    let email_lc = c.author_email.to_lowercase();
    let name_lc = c.author_name.to_lowercase();
    if !emails.is_empty() && emails.iter().any(|e| e == &email_lc) {
        return true;
    }
    if !names.is_empty() && names.iter().any(|n| n == &name_lc) {
        return true;
    }
    false
}
