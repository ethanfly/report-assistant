"""Storage 单元测试：确认入库、去重、按时间窗查询正常。"""
from datetime import datetime, timedelta

import pytest

from report_assistant.storage import Storage


@pytest.fixture()
def storage(tmp_path):
    return Storage(tmp_path / "test.sqlite")


def test_add_and_list_work_log(storage):
    now = datetime.now()
    storage.add_work_log(
        ts=now, source="git", title="feat: x", content="body",
        category="开发", meta={"hash": "abc123"}, dedupe_key="abc123",
    )
    rows = storage.list_work_logs(now - timedelta(hours=1), now + timedelta(hours=1))
    assert len(rows) == 1
    assert rows[0]["title"] == "feat: x"
    assert rows[0]["meta"]["hash"] == "abc123"


def test_dedupe_by_key(storage):
    now = datetime.now()
    id1 = storage.add_work_log(
        ts=now, source="git", title="t1", dedupe_key="same",
    )
    id2 = storage.add_work_log(
        ts=now, source="git", title="t1-changed", dedupe_key="same",
    )
    assert id1 == id2
    rows = storage.list_work_logs(now - timedelta(hours=1), now + timedelta(hours=1))
    assert len(rows) == 1


def test_list_filter_by_source(storage):
    now = datetime.now()
    storage.add_work_log(ts=now, source="git", title="g")
    storage.add_work_log(ts=now, source="screenshot", title="s")
    git_rows = storage.list_work_logs(now - timedelta(hours=1), now + timedelta(hours=1), source="git")
    shot_rows = storage.list_work_logs(now - timedelta(hours=1), now + timedelta(hours=1), source="screenshot")
    assert len(git_rows) == 1 and git_rows[0]["title"] == "g"
    assert len(shot_rows) == 1 and shot_rows[0]["title"] == "s"


def test_report_crud(storage):
    now = datetime.now()
    rid = storage.add_report(
        kind="daily", period_start=now, period_end=now,
        content="# hi", template="standard",
    )
    r = storage.get_report(rid)
    assert r is not None and r["content"] == "# hi"
    rows = storage.list_reports(kind="daily")
    assert len(rows) == 1
