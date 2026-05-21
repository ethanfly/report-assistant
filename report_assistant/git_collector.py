"""Git 提交记录收集器。

从一个或多个本地仓库读取指定时间窗口、指定作者的 commit 历史。
依赖系统 git 命令，不需要额外 Python 库。
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from dateutil import parser as dtparser


@dataclass
class Commit:
    repo: str
    repo_name: str
    hash: str
    short_hash: str
    author_name: str
    author_email: str
    date: datetime
    subject: str
    body: str
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "repo_name": self.repo_name,
            "hash": self.hash,
            "short_hash": self.short_hash,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "date": self.date.isoformat(),
            "subject": self.subject,
            "body": self.body,
            "files_changed": self.files_changed,
            "insertions": self.insertions,
            "deletions": self.deletions,
        }


# 单元分隔符使用罕见字符，避免与 commit message 内容冲突
# RECORD_SEP 放在 format 开头：split 后每段保证以 commit head 起始，
# 上一个 commit 的 numstat 行会被自然归入它自己的段尾。
_FIELD_SEP = "\x1e"
_RECORD_SEP = "\x1f"

_PRETTY_FORMAT = _RECORD_SEP + _FIELD_SEP.join(
    ["%H", "%h", "%an", "%ae", "%aI", "%s", "%b"]
)


def _run_git(repo: Path, args: list[str]) -> str:
    """在指定仓库运行 git 命令并返回 stdout。失败时抛 RuntimeError。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as e:
        raise RuntimeError("未找到 git 命令，请先安装 git。") from e
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} 在 {repo} 失败: {result.stderr.strip()}"
        )
    return result.stdout


def is_git_repo(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        _run_git(path, ["rev-parse", "--is-inside-work-tree"])
        return True
    except RuntimeError:
        return False


def collect_commits(
    repo_path: str | Path,
    since: datetime,
    until: datetime,
    author_emails: Optional[list[str]] = None,
    author_names: Optional[list[str]] = None,
    include_merges: bool = False,
) -> list[Commit]:
    """从单个仓库收集指定时间窗口、指定作者的提交。

    作者过滤逻辑：邮箱与姓名任一匹配即视为本人提交。
    若两者都为空，返回所有作者的提交。
    """
    repo = Path(str(repo_path)).expanduser().resolve()
    if not is_git_repo(repo):
        raise RuntimeError(f"{repo} 不是一个有效的 git 仓库")

    args = [
        "log",
        f"--since={since.isoformat()}",
        f"--until={until.isoformat()}",
        f"--pretty=format:{_PRETTY_FORMAT}",
        "--numstat",
    ]
    if not include_merges:
        args.append("--no-merges")

    output = _run_git(repo, args)
    if not output.strip():
        return []

    repo_name = repo.name
    commits: list[Commit] = []
    # 用 _RECORD_SEP 切分 commit
    for raw in output.split(_RECORD_SEP):
        raw = raw.strip("\n")
        if not raw.strip():
            continue
        # 头部固定 7 个字段，剩余为 numstat 行
        head, _, tail = raw.partition("\n")
        parts = head.split(_FIELD_SEP)
        if len(parts) < 7:
            continue
        h, sh, an, ae, ad, subject, body = parts[:7]
        # %b 可能跨多行，但 numstat 紧接其后；用空行作为分隔不可靠，
        # 改为：从 tail 中识别符合 numstat 格式的尾部行
        body_lines: list[str] = [body] if body else []
        numstat_lines: list[str] = []
        for line in tail.splitlines():
            if _is_numstat_line(line):
                numstat_lines.append(line)
            else:
                body_lines.append(line)
        full_body = "\n".join(body_lines).strip()

        files: list[str] = []
        ins = dels = 0
        for nl in numstat_lines:
            cols = nl.split("\t")
            if len(cols) >= 3:
                a, d, fname = cols[0], cols[1], cols[2]
                files.append(fname)
                if a.isdigit():
                    ins += int(a)
                if d.isdigit():
                    dels += int(d)

        try:
            dt = dtparser.isoparse(ad)
        except (ValueError, TypeError):
            continue

        # 作者过滤
        if author_emails or author_names:
            email_match = any(
                e and e.lower() in ae.lower() for e in (author_emails or [])
            )
            name_match = any(
                n and n.lower() in an.lower() for n in (author_names or [])
            )
            if not (email_match or name_match):
                continue

        commits.append(
            Commit(
                repo=str(repo),
                repo_name=repo_name,
                hash=h,
                short_hash=sh,
                author_name=an,
                author_email=ae,
                date=dt,
                subject=subject,
                body=full_body,
                files_changed=files,
                insertions=ins,
                deletions=dels,
            )
        )
    # git log 默认倒序，这里按时间正序输出方便阅读
    commits.sort(key=lambda c: c.date)
    return commits


def _is_numstat_line(line: str) -> bool:
    """numstat 行格式: '<insertions>\\t<deletions>\\t<file>'，二进制文件可能是 '-\\t-\\t<file>'。"""
    if "\t" not in line:
        return False
    cols = line.split("\t")
    if len(cols) < 3:
        return False
    a, d = cols[0], cols[1]
    return (a.isdigit() or a == "-") and (d.isdigit() or d == "-")


def collect_from_many(
    repos: list[str],
    since: datetime,
    until: datetime,
    author_emails: Optional[list[str]] = None,
    author_names: Optional[list[str]] = None,
    include_merges: bool = False,
) -> list[Commit]:
    """从多个仓库聚合提交，按时间排序。"""
    all_commits: list[Commit] = []
    for r in repos:
        try:
            all_commits.extend(
                collect_commits(
                    r, since, until, author_emails, author_names, include_merges
                )
            )
        except RuntimeError as e:
            # 单个仓库失败不影响其他
            print(f"[warn] 跳过仓库 {r}: {e}")
    all_commits.sort(key=lambda c: c.date)
    return all_commits
