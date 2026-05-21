"""SingleInstance 单元测试。

用 QApplication offscreen 平台跑；不依赖图形界面。
"""
import os
import uuid

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from report_assistant.desktop.singleton import SingleInstance  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def test_first_acquire_succeeds(qapp):
    key = f"report-assistant.test.{uuid.uuid4().hex[:8]}"
    guard = SingleInstance(key=key)
    try:
        assert guard.try_acquire() is True
    finally:
        guard.release()


def test_second_acquire_fails(qapp):
    key = f"report-assistant.test.{uuid.uuid4().hex[:8]}"
    g1 = SingleInstance(key=key)
    g2 = SingleInstance(key=key)
    try:
        assert g1.try_acquire() is True
        assert g2.try_acquire() is False
    finally:
        g1.release()
        g2.release()


def test_release_then_acquire_again(qapp):
    key = f"report-assistant.test.{uuid.uuid4().hex[:8]}"
    g = SingleInstance(key=key)
    assert g.try_acquire() is True
    g.release()
    g2 = SingleInstance(key=key)
    try:
        assert g2.try_acquire() is True
    finally:
        g2.release()
