"""Git 提交收集器测试：用真实临时仓库验证解析逻辑。"""
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from report_assistant.git_collector import collect_commits, is_git_repo


def _git(repo: Path, *args: str, env=None) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )


def _git_available() -> bool:
    """通过 PATH 检测 git；避免在某些受限环境下创建子进程。"""
    return shutil.which("git") is not None


pytestmark = pytest.mark.skipif(not _git_available(), reason="git not available on PATH")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Tester",
        "GIT_AUTHOR_EMAIL": "tester@example.com",
        "GIT_COMMITTER_NAME": "Tester",
        "GIT_COMMITTER_EMAIL": "tester@example.com",
    }
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "tester@example.com")
    _git(r, "config", "user.name", "Tester")

    (r / "a.txt").write_text("hello\n", encoding="utf-8")
    _git(r, "add", "a.txt", env=env)
    _git(r, "commit", "-q", "-m", "feat: add a", env=env)

    (r / "b.txt").write_text("world\n", encoding="utf-8")
    _git(r, "add", "b.txt", env=env)
    _git(r, "commit", "-q", "-m", "feat: add b\n\nbody line 1", env=env)
    return r


def test_is_git_repo(repo, tmp_path):
    assert is_git_repo(repo)
    assert not is_git_repo(tmp_path / "nope")


def test_collect_all_commits(repo):
    since = datetime.now() - timedelta(days=1)
    until = datetime.now() + timedelta(days=1)
    commits = collect_commits(repo, since, until)
    assert len(commits) == 2
    subjects = [c.subject for c in commits]
    assert "feat: add a" in subjects
    assert "feat: add b" in subjects
    # numstat 应能解析到文件
    files = {f for c in commits for f in c.files_changed}
    assert {"a.txt", "b.txt"}.issubset(files)


def test_filter_by_email(repo):
    since = datetime.now() - timedelta(days=1)
    until = datetime.now() + timedelta(days=1)
    matched = collect_commits(repo, since, until, author_emails=["tester@example.com"])
    none = collect_commits(repo, since, until, author_emails=["someone-else@example.com"])
    assert len(matched) == 2
    assert len(none) == 0


def test_body_parsed(repo):
    since = datetime.now() - timedelta(days=1)
    until = datetime.now() + timedelta(days=1)
    commits = collect_commits(repo, since, until)
    body_commit = next(c for c in commits if c.subject == "feat: add b")
    assert "body line 1" in body_commit.body
