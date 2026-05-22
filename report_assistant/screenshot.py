"""屏幕截图与视觉分析。

通过 mss 跨平台截屏；分析后可选删除以保护隐私（默认删除）。
截图分析输出包含分类、要点和文本描述，写入 work_logs。
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import Config
from .llm import LLMClient, LLMError
from .storage import Storage


logger = logging.getLogger("screenshot")


VISION_PROMPT = """你是工作内容识别助手。请分析这张屏幕截图，识别用户当前正在做什么工作。

请用 JSON 格式返回，且仅返回 JSON，不要添加 markdown 代码块标记：
{
  "category": "开发|会议|沟通|文档|学习|设计|测试|其他",
  "title": "一句话概括（10-20 字）",
  "summary": "2-3 句话描述具体在做什么、用到的工具/项目/页面",
  "keywords": ["关键词1", "关键词2"]
}

注意：
- 如果截图中有明显的代码、IDE、终端，归类为"开发"。
- 如果是会议软件（Zoom/Teams/腾讯会议等），归类为"会议"。
- 不要编造看不到的内容；信息不足就如实写"屏幕内容不明确"。
- 不要包含个人隐私信息（如完整邮箱、密码、token）。
"""


@dataclass
class AnalyzedShot:
    ts: datetime
    category: str
    title: str
    summary: str
    keywords: list[str]
    raw_path: Optional[str]  # 若 keep_after_analysis=False，则为 None


def list_monitors() -> list[dict]:
    """枚举可用监视器。

    返回 [{"index": int, "label": str, "width": int, "height": int}, ...]
    其中 index=0 是所有屏幕合并，与 mss.monitors[0] 对齐。
    """
    try:
        import mss
    except ImportError:
        return []
    out = []
    with mss.mss() as sct:
        for i, m in enumerate(sct.monitors):
            if i == 0:
                label = f"全部屏幕（{len(sct.monitors) - 1} 个）"
            else:
                label = f"屏幕 {i} · {m['width']}×{m['height']}"
            out.append({
                "index": i,
                "label": label,
                "width": m["width"],
                "height": m["height"],
            })
    return out


def get_idle_seconds() -> int:
    """获取系统空闲时间（自上次输入起的秒数）。

    Windows: 调用 GetLastInputInfo（user32.dll）
    macOS / Linux: 暂不可靠（缺统一 API），返回 0 表示"未空闲"
    """
    import sys
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT),
                    ("dwTime", wintypes.DWORD),
                ]

            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(lii)
            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                return 0
            tick_count = ctypes.windll.kernel32.GetTickCount()
            return max(0, (tick_count - lii.dwTime) // 1000)
        except Exception:
            return 0
    return 0


# 视觉模型用 1280px 宽就够了；过大反而拖慢 UI 线程（PIL/base64 持 GIL）
_MAX_DIMENSION = 1600


def capture_screen(
    output_dir: str | Path,
    monitor_index: int = 1,
) -> Path:
    """全屏截图并保存为 PNG，返回文件路径。

    monitor_index：0=所有屏幕合并；1+=指定屏幕。

    注意：本函数会被 WatchWorker 在后台线程调用，但 PIL/PNG 编码持有 GIL，
    因此过大或 optimize=True 都会让 UI 卡顿。这里：
    1) 长边超过 1600px 时按比例缩小（视觉模型完全够用）
    2) 关闭 PIL 的 optimize（PNG 优化压缩可能持 GIL 几秒）
    3) compress_level=1（最快压缩）
    """
    try:
        import mss
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("请先安装依赖: pip install mss Pillow") from e

    out_dir = Path(str(output_dir)).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"shot_{ts}.png"

    with mss.mss() as sct:
        if monitor_index < 0 or monitor_index >= len(sct.monitors):
            monitor_index = 1 if len(sct.monitors) > 1 else 0
        monitor = sct.monitors[monitor_index]
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        # 等比例缩到长边 _MAX_DIMENSION 内
        w, h = img.size
        m = max(w, h)
        if m > _MAX_DIMENSION:
            ratio = _MAX_DIMENSION / m
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        img.save(out_path, format="PNG", optimize=False, compress_level=1)
    return out_path


def analyze_and_record(
    cfg: Config,
    storage: Storage,
    llm: LLMClient,
    image_path: Optional[Path] = None,
) -> AnalyzedShot:
    """截屏 → 视觉分析 → 写入 work_logs；按配置决定是否保留图片。"""
    path = image_path or capture_screen(
        cfg.screenshot.output_dir,
        monitor_index=cfg.screenshot.monitor_index,
    )
    try:
        raw = llm.analyze_image(path, VISION_PROMPT)
    except LLMError:
        # 分析失败时不保留图片（避免泄露），重新抛出
        if not cfg.screenshot.keep_after_analysis:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    parsed = _parse_vision_json(raw)
    ts = datetime.now()

    storage.add_work_log(
        ts=ts,
        source="screenshot",
        title=parsed["title"],
        content=parsed["summary"],
        category=parsed["category"],
        meta={
            "keywords": parsed.get("keywords", []),
            "image_path": str(path) if cfg.screenshot.keep_after_analysis else "",
        },
    )

    kept_path: Optional[str] = str(path)
    if not cfg.screenshot.keep_after_analysis:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        kept_path = None

    return AnalyzedShot(
        ts=ts,
        category=parsed["category"],
        title=parsed["title"],
        summary=parsed["summary"],
        keywords=parsed.get("keywords", []),
        raw_path=kept_path,
    )


def _parse_vision_json(text: str) -> dict:
    """容错解析视觉模型返回的 JSON：剥离 markdown code fence、找首个 { }。"""
    s = text.strip()
    if s.startswith("```"):
        # 去掉 ```json ... ``` 包裹
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()

    # 兜底：截取第一个 { 到最后一个 }
    if not s.startswith("{"):
        i, j = s.find("{"), s.rfind("}")
        if i >= 0 and j > i:
            s = s[i : j + 1]

    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        # 解析失败时退化为纯文本摘要
        return {
            "category": "其他",
            "title": (text or "屏幕内容").strip()[:30],
            "summary": (text or "").strip()[:300],
            "keywords": [],
        }

    return {
        "category": str(data.get("category") or "其他"),
        "title": str(data.get("title") or "屏幕内容")[:60],
        "summary": str(data.get("summary") or "")[:500],
        "keywords": [str(k) for k in (data.get("keywords") or [])][:10],
    }


def watch(
    cfg: Config,
    storage: Storage,
    llm: LLMClient,
    interval: Optional[int] = None,
    on_capture=None,
    on_idle_skip=None,
) -> None:
    """长驻模式：按 interval 间隔不断截屏并分析，直到收到 KeyboardInterrupt。

    若 cfg.screenshot.idle_skip_seconds > 0 且系统空闲时间超过该阈值，
    本轮将跳过截图（节省成本，避免无效记录）。
    """
    interval = interval or cfg.screenshot.interval_seconds
    while True:
        idle_threshold = int(getattr(cfg.screenshot, "idle_skip_seconds", 0) or 0)
        if idle_threshold > 0:
            idle = get_idle_seconds()
            if idle >= idle_threshold:
                if on_idle_skip:
                    on_idle_skip(idle)
                time.sleep(min(interval, 60))
                continue
        try:
            shot = analyze_and_record(cfg, storage, llm)
            if on_capture:
                on_capture(shot)
        except (LLMError, RuntimeError) as e:
            logger.warning("截图分析失败: %s", e)
        except Exception:
            # CLI 长驻同样需要兜底，避免一次异常打断整个 watch 循环
            logger.exception("截图分析未预期异常")
        time.sleep(interval)
