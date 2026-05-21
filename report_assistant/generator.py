"""日报/周报/月报生成器：合并 git 提交 + 截图记录 → LLM → Markdown。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta
from typing import Optional

from .config import Config
from .git_collector import Commit, collect_from_many
from .llm import LLMClient
from .storage import Storage
from .templates import KIND_TITLE, ReportKind, get_template


@dataclass
class GenerateInput:
    kind: ReportKind
    period_start: datetime
    period_end: datetime
    template: str
    commits: list[Commit]
    screenshot_logs: list[dict]
    extra_notes: str = ""  # 用户手动补充的事项


# ── 时间范围工具 ─────────────────────────────────────────

def day_range(d: datetime) -> tuple[datetime, datetime]:
    start = datetime.combine(d.date(), dtime.min)
    end = datetime.combine(d.date(), dtime.max)
    return start, end


def week_range(d: datetime) -> tuple[datetime, datetime]:
    """ISO 周：周一 00:00 → 周日 23:59:59。"""
    monday = d - timedelta(days=d.weekday())
    start = datetime.combine(monday.date(), dtime.min)
    end = datetime.combine((monday + timedelta(days=6)).date(), dtime.max)
    return start, end


def month_range(d: datetime) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, 1)
    if d.month == 12:
        nxt = datetime(d.year + 1, 1, 1)
    else:
        nxt = datetime(d.year, d.month + 1, 1)
    end = nxt - timedelta(microseconds=1)
    return start, end


def resolve_period(kind: ReportKind, anchor: Optional[datetime] = None) -> tuple[datetime, datetime]:
    a = anchor or datetime.now()
    if kind == "daily":
        return day_range(a)
    if kind == "weekly":
        return week_range(a)
    if kind == "monthly":
        return month_range(a)
    raise ValueError(f"未知报告类型: {kind}")


# ── 数据收集 ─────────────────────────────────────────────

def collect_data(
    cfg: Config,
    storage: Storage,
    kind: ReportKind,
    anchor: Optional[datetime] = None,
    include_screenshots: bool = True,
) -> tuple[datetime, datetime, list[Commit], list[dict]]:
    start, end = resolve_period(kind, anchor)
    commits: list[Commit] = []
    if cfg.git.repos:
        commits = collect_from_many(
            cfg.git.repos,
            since=start,
            until=end,
            author_emails=cfg.git.author_emails,
            author_names=cfg.git.author_names,
            include_merges=cfg.git.include_merges,
        )
        # 同步入库（幂等）
        for c in commits:
            storage.add_work_log(
                ts=c.date,
                source="git",
                category="开发",
                title=c.subject,
                content=c.body,
                meta={
                    "repo": c.repo_name,
                    "hash": c.short_hash,
                    "files": c.files_changed[:20],
                    "insertions": c.insertions,
                    "deletions": c.deletions,
                    "author": c.author_name,
                },
                dedupe_key=c.hash,
            )

    screenshot_logs: list[dict] = []
    if include_screenshots:
        screenshot_logs = storage.list_work_logs(start, end, source="screenshot")

    return start, end, commits, screenshot_logs


# ── 提示词构建 ───────────────────────────────────────────

def _format_commits_block(commits: list[Commit]) -> str:
    if not commits:
        return "（本期无 git 提交记录）"
    by_repo: dict[str, list[Commit]] = {}
    for c in commits:
        by_repo.setdefault(c.repo_name, []).append(c)
    lines: list[str] = []
    for repo, items in by_repo.items():
        lines.append(f"### 仓库 {repo}（{len(items)} 个提交）")
        for c in items:
            files_summary = ""
            if c.files_changed:
                shown = c.files_changed[:5]
                files_summary = f"  文件: {', '.join(shown)}"
                if len(c.files_changed) > 5:
                    files_summary += f" 等 {len(c.files_changed)} 个"
            stat = f"+{c.insertions}/-{c.deletions}"
            line = (
                f"- [{c.date.strftime('%Y-%m-%d %H:%M')}] "
                f"{c.subject} ({c.short_hash}, {stat})"
            )
            if c.body:
                first_body_line = c.body.splitlines()[0].strip()
                if first_body_line:
                    line += f"\n  说明: {first_body_line}"
            if files_summary:
                line += f"\n{files_summary}"
            lines.append(line)
    return "\n".join(lines)


def _format_screenshot_block(logs: list[dict]) -> str:
    if not logs:
        return "（本期无截图记录）"
    lines: list[str] = []
    for log in logs:
        ts = log.get("ts", "")[:16].replace("T", " ")
        cat = log.get("category") or "其他"
        title = log.get("title") or ""
        summary = (log.get("content") or "").strip()
        line = f"- [{ts}] [{cat}] {title}"
        if summary:
            line += f"\n  {summary}"
        lines.append(line)
    return "\n".join(lines)


def build_prompt(inp: GenerateInput, cfg: Config) -> list[dict]:
    tpl = get_template(inp.template)
    kind_title = KIND_TITLE[inp.kind]
    if inp.kind == "daily":
        period = inp.period_start.strftime("%Y-%m-%d")
    elif inp.kind == "weekly":
        period = f"{inp.period_start.strftime('%Y-%m-%d')} ~ {inp.period_end.strftime('%Y-%m-%d')}"
    else:
        period = inp.period_start.strftime("%Y-%m")

    instruction = tpl.instruction.format(kind_title=kind_title, period=period)

    commits_block = _format_commits_block(inp.commits)
    shots_block = _format_screenshot_block(inp.screenshot_logs)

    user_info = ""
    if cfg.report.user_name:
        user_info += f"汇报人: {cfg.report.user_name}\n"
    if cfg.report.team:
        user_info += f"团队: {cfg.report.team}\n"

    extra = f"\n## 用户补充\n{inp.extra_notes}\n" if inp.extra_notes.strip() else ""

    system = (
        "你是一名资深的工作汇报助手。基于用户提供的 git 提交记录和屏幕活动记录，"
        "输出一份真实、凝练、有结构的工作报告。"
        "原则：1) 只基于事实，不要编造未发生的内容；2) 合并相似事项，避免流水账；"
        "3) 用动作 + 对象 + 结果的句式；4) 用中文输出（除非另有说明）。"
    )

    user = f"""{user_info}
请生成一份{kind_title}，覆盖时间范围：{period}。

{instruction}

## 数据：Git 提交记录
{commits_block}

## 数据：屏幕活动记录（来自截图分析，已去图）
{shots_block}
{extra}
开始生成报告（直接输出 Markdown，不要附加解释）：
"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ── 报告生成 ─────────────────────────────────────────────

def generate_report(
    cfg: Config,
    storage: Storage,
    llm: LLMClient,
    kind: ReportKind,
    anchor: Optional[datetime] = None,
    template: Optional[str] = None,
    extra_notes: str = "",
    save: bool = True,
) -> dict:
    """生成报告并（可选）入库。返回 {content, period_start, period_end, kind, template}。"""
    template = template or cfg.report.default_template
    start, end, commits, shots = collect_data(cfg, storage, kind, anchor)

    if not commits and not shots and not extra_notes.strip():
        # 没有任何数据时给出明确提示而非调用 LLM
        content = (
            f"# {KIND_TITLE[kind]}\n\n"
            f"时间范围: {start.isoformat()} ~ {end.isoformat()}\n\n"
            "本期没有采集到任何 git 提交、截图分析或手动备注。\n"
            "请检查：\n"
            "- 是否在配置中加入了 git 仓库路径与作者信息\n"
            "- 是否在该时间范围内执行过截图分析（capture / watch）\n"
        )
    else:
        inp = GenerateInput(
            kind=kind,
            period_start=start,
            period_end=end,
            template=template,
            commits=commits,
            screenshot_logs=shots,
            extra_notes=extra_notes,
        )
        messages = build_prompt(inp, cfg)
        content = llm.chat(messages)

    result = {
        "kind": kind,
        "period_start": start,
        "period_end": end,
        "template": template,
        "content": content,
        "stats": {
            "commits": len(commits),
            "screenshots": len(shots),
        },
    }
    if save:
        rid = storage.add_report(
            kind=kind,
            period_start=start,
            period_end=end,
            content=content,
            template=template,
        )
        result["id"] = rid
    return result
