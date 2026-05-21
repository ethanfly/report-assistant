"""命令行入口。

用法：
    report init                        # 初始化配置文件
    report config show                 # 查看当前配置位置与内容摘要
    report git --since 2024-01-01      # 仅看 git 提交
    report capture                     # 截图 + 视觉分析（一次）
    report watch                       # 长驻：定时截图分析
    report daily [--date YYYY-MM-DD] [--template standard|concise|technical|okr]
    report weekly [--date YYYY-MM-DD] [--template ...]
    report monthly [--month YYYY-MM] [--template ...]
    report list [--kind daily|weekly|monthly]
    report show <id>
    report export <id> --to file.md
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from dateutil import parser as dtparser
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from .config import Config, init_default_config, load_config, find_config_path
from .generator import collect_data, generate_report
from .git_collector import collect_from_many
from .llm import LLMError, build_client
from .screenshot import analyze_and_record, watch as watch_loop
from .storage import Storage
from .templates import KIND_TITLE, TEMPLATES


console = Console()


def _load() -> tuple[Config, Storage]:
    cfg = load_config()
    storage = Storage(Path(cfg.db_path).expanduser())
    return cfg, storage


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return dtparser.parse(s)
    except (ValueError, TypeError) as e:
        raise click.BadParameter(f"无法解析日期: {s} ({e})")


@click.group()
@click.version_option(package_name="report-assistant")
def main() -> None:
    """report-assistant: AI 日报/周报/月报生成助手。"""


# ── init / config ─────────────────────────────────────────

@main.command()
@click.option("--force", is_flag=True, help="强制覆盖已有配置")
def init(force: bool) -> None:
    """在 ~/.report-assistant/ 创建初始配置文件。"""
    path = init_default_config(force=force)
    console.print(f"[green]OK[/green] 配置文件: {path}")
    console.print("请编辑该文件，填写 LLM api_key、git 仓库路径与作者信息。")


@main.group()
def config() -> None:
    """配置管理。"""


@config.command("show")
def config_show() -> None:
    cfg = load_config()
    path = find_config_path()
    console.print(f"[bold]配置文件[/bold]: {path or '(未找到，使用默认值)'}")
    console.print(f"[bold]数据库[/bold]: {cfg.db_path}")
    console.print(f"[bold]LLM[/bold]: {cfg.llm.provider} | {cfg.llm.base_url} | model={cfg.llm.model}")
    console.print(f"[bold]API key[/bold]: {'已配置' if cfg.llm.api_key else '[red]未配置[/red]'}")
    console.print(f"[bold]Git 仓库[/bold]: {len(cfg.git.repos)} 个")
    for r in cfg.git.repos:
        console.print(f"  - {r}")
    console.print(
        f"[bold]作者过滤[/bold]: emails={cfg.git.author_emails}, names={cfg.git.author_names}"
    )


# ── git ──────────────────────────────────────────────────

@main.command()
@click.option("--since", default=None, help="起始时间，如 2024-01-01")
@click.option("--until", default=None, help="截止时间，如 2024-01-31")
@click.option("--days", default=None, type=int, help="过去 N 天（与 since/until 互斥）")
@click.option("--all-authors", is_flag=True, help="忽略作者过滤")
def git(since: Optional[str], until: Optional[str], days: Optional[int], all_authors: bool) -> None:
    """查看本地仓库的 git 提交记录。"""
    cfg, _ = _load()
    if days is not None:
        from datetime import timedelta
        end = datetime.now()
        start = end - timedelta(days=days)
    else:
        start = _parse_date(since) or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = _parse_date(until) or datetime.now()

    if not cfg.git.repos:
        console.print("[yellow]未配置 git 仓库。请先在配置文件中填写 git.repos。[/yellow]")
        sys.exit(1)

    commits = collect_from_many(
        cfg.git.repos,
        since=start,
        until=end,
        author_emails=None if all_authors else cfg.git.author_emails,
        author_names=None if all_authors else cfg.git.author_names,
        include_merges=cfg.git.include_merges,
    )
    if not commits:
        console.print("[yellow]该时间范围内无匹配的提交。[/yellow]")
        return

    table = Table(title=f"提交记录 {start:%Y-%m-%d} -> {end:%Y-%m-%d}（共 {len(commits)} 条）")
    table.add_column("时间", style="cyan", no_wrap=True)
    table.add_column("仓库", style="magenta")
    table.add_column("Hash", style="dim")
    table.add_column("作者")
    table.add_column("Subject")
    table.add_column("+/-", justify="right")
    for c in commits:
        table.add_row(
            c.date.strftime("%m-%d %H:%M"),
            c.repo_name,
            c.short_hash,
            c.author_name,
            c.subject[:60],
            f"+{c.insertions}/-{c.deletions}",
        )
    console.print(table)


# ── capture / watch ──────────────────────────────────────

@main.command()
@click.option("--image", type=click.Path(exists=True, dir_okay=False), default=None,
              help="使用指定图片而非新截图（用于测试或外部截图）")
def capture(image: Optional[str]) -> None:
    """截屏一次并用视觉模型分析，结果写入工作记录。"""
    cfg, storage = _load()
    try:
        with build_client(cfg.llm) as llm:
            shot = analyze_and_record(
                cfg, storage, llm,
                image_path=Path(image) if image else None,
            )
    except (LLMError, RuntimeError) as e:
        console.print(f"[red]X[/red] {e}")
        sys.exit(1)
    console.print(f"[green]OK[/green] [{shot.category}] {shot.title}")
    console.print(f"  {shot.summary}")
    if shot.keywords:
        console.print(f"  关键词: {', '.join(shot.keywords)}")


@main.command()
@click.option("--interval", type=int, default=None, help="截图间隔秒数，默认读取配置")
def watch(interval: Optional[int]) -> None:
    """长驻模式：按间隔持续截图分析。Ctrl+C 退出。"""
    cfg, storage = _load()
    iv = interval or cfg.screenshot.interval_seconds
    console.print(f"[green]开始监听[/green]，间隔 {iv}s。Ctrl+C 退出。")

    def on_capture(shot):
        console.print(
            f"[{shot.ts:%H:%M:%S}] [bold]{shot.category}[/bold] {shot.title}"
        )

    try:
        with build_client(cfg.llm) as llm:
            watch_loop(cfg, storage, llm, interval=iv, on_capture=on_capture)
    except KeyboardInterrupt:
        console.print("\n[dim]已停止[/dim]")
    except LLMError as e:
        console.print(f"[red]X[/red] {e}")
        sys.exit(1)


# ── 报告生成 ─────────────────────────────────────────────

_TEMPLATE_OPT = click.option(
    "--template", "-t",
    type=click.Choice(list(TEMPLATES.keys())),
    default=None,
    help="报告模板，默认使用配置中的 default_template",
)
_NOTES_OPT = click.option("--notes", "-n", default="", help="附加备注/补充内容")
_DRY_RUN_OPT = click.option("--dry-run", is_flag=True, help="仅展示数据，不调用 LLM 也不入库")
_OUTPUT_OPT = click.option("--output", "-o", type=click.Path(dir_okay=False), help="导出到 Markdown 文件")


def _generate_and_render(
    kind: str,
    anchor: Optional[datetime],
    template: Optional[str],
    notes: str,
    dry_run: bool,
    output: Optional[str],
) -> None:
    cfg, storage = _load()
    if dry_run:
        start, end, commits, shots = collect_data(cfg, storage, kind, anchor)
        console.print(f"[bold]时间范围[/bold]: {start} -> {end}")
        console.print(f"[bold]Commits[/bold]: {len(commits)}; [bold]Screenshots[/bold]: {len(shots)}")
        for c in commits[:20]:
            console.print(f"  - [{c.date:%m-%d %H:%M}] {c.repo_name}: {c.subject}")
        for s in shots[:20]:
            console.print(f"  - [{s['ts'][:16]}] {s.get('category')}: {s.get('title')}")
        return

    try:
        with build_client(cfg.llm) as llm:
            result = generate_report(
                cfg, storage, llm,
                kind=kind,
                anchor=anchor,
                template=template,
                extra_notes=notes,
            )
    except LLMError as e:
        console.print(f"[red]X[/red] {e}")
        sys.exit(1)

    stats = result["stats"]
    console.print(
        f"[green]OK[/green] 已生成 [bold]{KIND_TITLE[kind]}[/bold] "
        f"(id={result.get('id')}, commits={stats['commits']}, screenshots={stats['screenshots']})\n"
    )
    console.print(Markdown(result["content"]))

    if output:
        Path(output).write_text(result["content"], encoding="utf-8")
        console.print(f"\n[green]OK[/green] 已导出: {output}")


@main.command()
@click.option("--date", "-d", default=None, help="指定日期，默认今天")
@_TEMPLATE_OPT
@_NOTES_OPT
@_DRY_RUN_OPT
@_OUTPUT_OPT
def daily(date: Optional[str], template: Optional[str], notes: str,
          dry_run: bool, output: Optional[str]) -> None:
    """生成日报。"""
    _generate_and_render("daily", _parse_date(date), template, notes, dry_run, output)


@main.command()
@click.option("--date", "-d", default=None, help="周内任意日期，默认本周")
@_TEMPLATE_OPT
@_NOTES_OPT
@_DRY_RUN_OPT
@_OUTPUT_OPT
def weekly(date: Optional[str], template: Optional[str], notes: str,
           dry_run: bool, output: Optional[str]) -> None:
    """生成周报。"""
    _generate_and_render("weekly", _parse_date(date), template, notes, dry_run, output)


@main.command()
@click.option("--month", "-m", default=None, help="指定月份，如 2024-01；默认本月")
@_TEMPLATE_OPT
@_NOTES_OPT
@_DRY_RUN_OPT
@_OUTPUT_OPT
def monthly(month: Optional[str], template: Optional[str], notes: str,
            dry_run: bool, output: Optional[str]) -> None:
    """生成月报。"""
    anchor = _parse_date(month) if month else None
    _generate_and_render("monthly", anchor, template, notes, dry_run, output)


# ── 历史报告 ─────────────────────────────────────────────

@main.command("list")
@click.option("--kind", type=click.Choice(["daily", "weekly", "monthly"]), default=None)
@click.option("--limit", default=20, type=int)
def list_cmd(kind: Optional[str], limit: int) -> None:
    """列出历史报告。"""
    _, storage = _load()
    rows = storage.list_reports(kind=kind, limit=limit)
    if not rows:
        console.print("[dim]暂无报告。[/dim]")
        return
    table = Table(title="历史报告")
    table.add_column("ID", justify="right")
    table.add_column("类型")
    table.add_column("周期")
    table.add_column("模板")
    table.add_column("生成时间", style="dim")
    for r in rows:
        table.add_row(
            str(r["id"]),
            r["kind"],
            f"{r['period_start'][:10]} ~ {r['period_end'][:10]}",
            r.get("template") or "-",
            r.get("created_at") or "-",
        )
    console.print(table)


@main.command()
@click.argument("report_id", type=int)
def show(report_id: int) -> None:
    """查看指定报告。"""
    _, storage = _load()
    r = storage.get_report(report_id)
    if not r:
        console.print(f"[red]未找到报告 id={report_id}[/red]")
        sys.exit(1)
    console.print(Markdown(r["content"]))


@main.command()
@click.argument("report_id", type=int)
@click.option("--to", "target", required=True, type=click.Path(dir_okay=False))
def export(report_id: int, target: str) -> None:
    """将报告导出为 Markdown 文件。"""
    _, storage = _load()
    r = storage.get_report(report_id)
    if not r:
        console.print(f"[red]未找到报告 id={report_id}[/red]")
        sys.exit(1)
    Path(target).write_text(r["content"], encoding="utf-8")
    console.print(f"[green]OK[/green] 已导出: {target}")


if __name__ == "__main__":
    main()
