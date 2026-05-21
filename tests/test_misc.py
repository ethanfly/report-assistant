"""模板与截图 JSON 解析的纯函数测试。"""
from report_assistant.screenshot import _parse_vision_json
from report_assistant.templates import TEMPLATES, get_template


def test_get_template_known():
    t = get_template("standard")
    assert t.name == "standard"
    assert "{kind_title}" in t.instruction


def test_get_template_unknown():
    import pytest
    with pytest.raises(ValueError):
        get_template("nope")


def test_all_templates_render():
    for name, tpl in TEMPLATES.items():
        rendered = tpl.instruction.format(kind_title="日报", period="2024-06-12")
        assert "2024-06-12" in rendered


def test_parse_vision_json_plain():
    raw = '{"category":"开发","title":"修改 CLI","summary":"在改 cli.py","keywords":["cli"]}'
    out = _parse_vision_json(raw)
    assert out["category"] == "开发"
    assert out["title"] == "修改 CLI"
    assert out["keywords"] == ["cli"]


def test_parse_vision_json_with_codefence():
    raw = '```json\n{"category":"会议","title":"周会","summary":"项目同步"}\n```'
    out = _parse_vision_json(raw)
    assert out["category"] == "会议"
    assert out["title"] == "周会"


def test_parse_vision_json_with_prefix_text():
    raw = '好的，以下是分析：\n{"category":"文档","title":"写需求","summary":"PRD 起草"}\n谢谢'
    out = _parse_vision_json(raw)
    assert out["category"] == "文档"


def test_parse_vision_json_invalid_falls_back():
    out = _parse_vision_json("不是 JSON 的纯文本描述")
    assert out["category"] == "其他"
    assert "不是 JSON" in out["title"] or out["summary"]
