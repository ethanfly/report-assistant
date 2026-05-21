"""LLM 客户端：兼容 OpenAI Chat Completions 协议。

支持文本生成与多模态（图片输入）。
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx

from .config import LLMConfig


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        if not cfg.api_key:
            raise LLMError(
                "未配置 LLM api_key。请编辑配置文件或设置环境变量 REPORT_ASSISTANT_API_KEY。"
            )
        self.cfg = cfg
        self._client = httpx.Client(
            base_url=cfg.base_url.rstrip("/"),
            timeout=cfg.timeout,
            headers={
                "Authorization": f"Bearer {cfg.api_key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ── 文本对话 ────────────────────────────────────────────────
    def chat(
        self,
        messages: list[dict[str, Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        payload = {
            "model": model or self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature if temperature is None else temperature,
        }
        try:
            resp = self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as e:
            raise LLMError(f"LLM 请求失败: {e}") from e
        if resp.status_code >= 400:
            raise LLMError(
                f"LLM HTTP {resp.status_code}: {resp.text[:500]}"
            )
        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise LLMError(f"LLM 响应解析失败: {resp.text[:500]}") from e

    # ── 视觉分析 ────────────────────────────────────────────────
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        model: Optional[str] = None,
    ) -> str:
        """对单张图片做视觉分析，返回文字描述。"""
        path = Path(str(image_path))
        if not path.exists():
            raise LLMError(f"图片不存在: {path}")
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        ext = path.suffix.lstrip(".").lower() or "png"
        if ext == "jpg":
            ext = "jpeg"
        data_url = f"data:image/{ext};base64,{b64}"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]
        return self.chat(messages, model=model or self.cfg.vision_model)


def build_client(cfg: LLMConfig) -> LLMClient:
    return LLMClient(cfg)


def check_connection(cfg: LLMConfig) -> tuple[bool, str]:
    """测试 LLM 连通性。返回 (ok, message)。

    用一个最小请求验证：base_url 可达 + api_key 有效 + model 存在。

    （注：函数名故意不以 test_ 开头，避免被 pytest 当成测试用例自动收集。）
    """
    if not cfg.api_key:
        return False, "未填写 API Key"
    # 测试用更短的超时，避免用户感觉"卡死"
    probe_cfg = LLMConfig(
        provider=cfg.provider,
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        model=cfg.model,
        vision_model=cfg.vision_model,
        temperature=cfg.temperature,
        timeout=min(cfg.timeout, 15),
    )
    try:
        with build_client(probe_cfg) as llm:
            reply = llm.chat(
                [{"role": "user", "content": "ping"}],
                temperature=0,
            )
        snippet = (reply or "").strip().replace("\n", " ")[:80]
        return True, f"连接成功（model={cfg.model}）: {snippet}"
    except LLMError as e:
        return False, str(e)[:300]
    except Exception as e:
        return False, f"未知错误: {e}"
