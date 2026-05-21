"""时间范围工具测试。"""
from datetime import datetime

from report_assistant.generator import day_range, week_range, month_range, resolve_period


def test_day_range():
    d = datetime(2024, 6, 15, 14, 30)
    s, e = day_range(d)
    assert s == datetime(2024, 6, 15, 0, 0, 0)
    assert e.year == 2024 and e.month == 6 and e.day == 15
    assert e.hour == 23 and e.minute == 59


def test_week_range_wednesday():
    # 2024-06-12 是周三
    d = datetime(2024, 6, 12, 10, 0)
    s, e = week_range(d)
    assert s.date() == datetime(2024, 6, 10).date()  # 周一
    assert e.date() == datetime(2024, 6, 16).date()  # 周日


def test_month_range_normal():
    d = datetime(2024, 6, 15)
    s, e = month_range(d)
    assert s == datetime(2024, 6, 1)
    assert e.year == 2024 and e.month == 6 and e.day == 30


def test_month_range_december():
    d = datetime(2024, 12, 25)
    s, e = month_range(d)
    assert s == datetime(2024, 12, 1)
    assert e.year == 2024 and e.month == 12 and e.day == 31


def test_resolve_period_dispatches():
    d = datetime(2024, 6, 12)
    assert resolve_period("daily", d) == day_range(d)
    assert resolve_period("weekly", d) == week_range(d)
    assert resolve_period("monthly", d) == month_range(d)
