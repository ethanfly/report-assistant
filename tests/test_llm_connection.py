"""check_connection 行为测试（不发真实网络请求）。"""
from unittest.mock import patch

from report_assistant.config import LLMConfig
from report_assistant.llm import LLMError, check_connection


def test_check_connection_no_api_key():
    cfg = LLMConfig(api_key="")
    ok, msg = check_connection(cfg)
    assert ok is False
    assert "API Key" in msg


def test_check_connection_success_with_mocked_chat():
    cfg = LLMConfig(api_key="sk-test", model="gpt-4o-mini")
    with patch("report_assistant.llm.LLMClient.chat", return_value="pong"):
        ok, msg = check_connection(cfg)
    assert ok is True
    assert "gpt-4o-mini" in msg
    assert "pong" in msg


def test_check_connection_llm_error_returns_false():
    cfg = LLMConfig(api_key="sk-test")
    with patch(
        "report_assistant.llm.LLMClient.chat",
        side_effect=LLMError("HTTP 401: invalid api key"),
    ):
        ok, msg = check_connection(cfg)
    assert ok is False
    assert "401" in msg


def test_check_connection_unknown_exception():
    cfg = LLMConfig(api_key="sk-test")
    with patch(
        "report_assistant.llm.LLMClient.chat",
        side_effect=ValueError("boom"),
    ):
        ok, msg = check_connection(cfg)
    assert ok is False
    assert "未知错误" in msg
