"""生成应用 Logo（多尺寸 PNG + Windows .ico）。

用法（开发期）：
    python -m report_assistant.desktop.assets.generate_logo

设计：
- 圆角方块底，填充主色渐变（emerald-500 → emerald-600）
- 中央白色"日"字（极简风），代表"日报"
- 右下角小绿点，呼应"实时记录"
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS_DIR = Path(__file__).resolve().parent

# 主色（与 theme.py 保持一致）
PRIMARY = (16, 185, 129, 255)         # #10b981
PRIMARY_DARK = (5, 150, 105, 255)      # #059669
PRIMARY_DEEP = (4, 120, 87, 255)       # #047857
WHITE = (255, 255, 255, 255)

# 输出尺寸
SIZES = [16, 24, 32, 48, 64, 128, 256, 512]


def _gradient(size: int) -> Image.Image:
    """生成对角线主色渐变图层。"""
    base = Image.new("RGBA", (size, size))
    px = base.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)
            r = int(PRIMARY[0] * (1 - t) + PRIMARY_DARK[0] * t)
            g = int(PRIMARY[1] * (1 - t) + PRIMARY_DARK[1] * t)
            b = int(PRIMARY[2] * (1 - t) + PRIMARY_DARK[2] * t)
            px[x, y] = (r, g, b, 255)
    return base


def _rounded_mask(size: int, radius_ratio: float = 0.22) -> Image.Image:
    """圆角方形 alpha 蒙版。"""
    radius = max(2, int(size * radius_ratio))
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def _draw_glyph(canvas: Image.Image) -> None:
    """在 canvas 中央画一个简化的"日"形：白色圆角矩形外框 + 中间横线。"""
    s = canvas.size[0]
    draw = ImageDraw.Draw(canvas)

    pad = int(s * 0.28)
    box = (pad, pad, s - pad, s - pad)
    stroke = max(2, int(s * 0.06))

    draw.rounded_rectangle(
        box, radius=int(s * 0.06),
        outline=WHITE, width=stroke,
    )
    cx0, cy0, cx1, cy1 = box
    mid_y = (cy0 + cy1) // 2
    half_stroke = stroke // 2
    draw.rectangle(
        (cx0 + stroke - 1, mid_y - half_stroke,
         cx1 - stroke + 1, mid_y + half_stroke + (stroke % 2)),
        fill=WHITE,
    )

    if s >= 48:
        dot_r = max(2, int(s * 0.08))
        margin = int(s * 0.10)
        cx = s - margin
        cy = s - margin
        draw.ellipse(
            (cx - dot_r - 2, cy - dot_r - 2, cx + dot_r + 2, cy + dot_r + 2),
            fill=WHITE,
        )
        draw.ellipse(
            (cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r),
            fill=PRIMARY_DEEP,
        )


def build_icon(size: int) -> Image.Image:
    if size >= 64:
        base = _gradient(size)
    else:
        base = Image.new("RGBA", (size, size), PRIMARY)

    mask = _rounded_mask(size)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(base, (0, 0), mask)
    _draw_glyph(canvas)
    return canvas


def generate(out_dir: Path | None = None) -> dict:
    target = out_dir or ASSETS_DIR
    target.mkdir(parents=True, exist_ok=True)

    pngs: dict[int, Path] = {}
    for s in SIZES:
        img = build_icon(s)
        path = target / f"logo_{s}.png"
        img.save(path, format="PNG", optimize=True)
        pngs[s] = path

    main_png = target / "logo.png"
    build_icon(512).save(main_png, format="PNG", optimize=True)

    ico_path = target / "logo.ico"
    ico_sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    base_img = Image.open(pngs[16])
    base_img.save(
        ico_path,
        format="ICO",
        sizes=ico_sizes,
        append_images=[Image.open(pngs[s]) for s in (24, 32, 48, 64, 128, 256)],
    )

    return {
        "main_png": main_png,
        "ico": ico_path,
        "pngs": pngs,
    }


if __name__ == "__main__":
    out = generate()
    print(f"主图: {out['main_png']}")
    print(f"ICO:  {out['ico']}")
    for s, p in sorted(out["pngs"].items()):
        print(f"  {s:>3}x{s:<3} -> {p.name}")
