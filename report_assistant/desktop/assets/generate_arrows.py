"""生成 UI 控件用的小箭头/加减号图标。

这些图标供 QSS 通过 image: url() 引用，避免依赖平台原生样式。

用法：
    python -m report_assistant.desktop.assets.generate_arrows
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS_DIR = Path(__file__).resolve().parent

# 颜色（与 theme.py 对齐）
MUTED = (148, 163, 184, 255)        # #94a3b8
PRIMARY = (16, 185, 129, 255)       # #10b981
PRIMARY_DARK = (5, 150, 105, 255)   # #059669


def _chevron(direction: str, size: int = 16, color=MUTED, weight: int = 2) -> Image.Image:
    """绘制 V 形箭头（chevron）。direction: up | down"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size
    pad = max(3, s // 4)
    mid = s / 2
    if direction == "down":
        p1 = (pad, mid - 1)
        p2 = (mid - 0.5, s - pad - 1)
        p3 = (s - pad - 1, mid - 1)
    elif direction == "up":
        p1 = (pad, mid)
        p2 = (mid - 0.5, pad)
        p3 = (s - pad - 1, mid)
    else:
        raise ValueError(direction)
    draw.line([p1, p2], fill=color, width=weight, joint="curve")
    draw.line([p2, p3], fill=color, width=weight, joint="curve")
    return img


def _plus(size: int = 14, color=MUTED, weight: int = 2) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = max(3, size // 4)
    mid = size / 2
    half_w = weight / 2
    draw.rectangle((pad, mid - half_w, size - pad, mid + half_w), fill=color)
    draw.rectangle((mid - half_w, pad, mid + half_w, size - pad), fill=color)
    return img


def _minus(size: int = 14, color=MUTED, weight: int = 2) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = max(3, size // 4)
    mid = size / 2
    half_w = weight / 2
    draw.rectangle((pad, mid - half_w, size - pad, mid + half_w), fill=color)
    return img


def generate(out_dir: Path | None = None) -> dict:
    target = out_dir or ASSETS_DIR
    target.mkdir(parents=True, exist_ok=True)

    pairs = {
        "chevron_down": _chevron("down", 16, MUTED),
        "chevron_down_active": _chevron("down", 16, PRIMARY_DARK),
        "chevron_up": _chevron("up", 16, MUTED),
        "chevron_up_active": _chevron("up", 16, PRIMARY_DARK),
        "plus": _plus(14, MUTED),
        "plus_active": _plus(14, PRIMARY_DARK),
        "minus": _minus(14, MUTED),
        "minus_active": _minus(14, PRIMARY_DARK),
    }
    out: dict[str, Path] = {}
    for name, img in pairs.items():
        path = target / f"{name}.png"
        img.save(path, format="PNG", optimize=True)
        out[name] = path
    return out


if __name__ == "__main__":
    out = generate()
    for k, v in out.items():
        print(f"{k:>22} -> {v.name}")
