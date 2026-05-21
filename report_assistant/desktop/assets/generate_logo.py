"""生成应用 Logo（多尺寸 PNG + Windows .ico）。

用法（开发期）：
    python -m report_assistant.desktop.assets.generate_logo

设计：
- 圆角方块底（iOS/Win11 风格），三段对角主色渐变（亮绿 -> 主绿 -> 深绿）
- 右上一道弧形高光、底部一抹暗角，营造立体质感
- 主体：三条白色清单条，首条左侧带 ring 形高亮点（"正在记录"）
- 小尺寸（≤32）自动简化：去掉高光/暗角/圆点，加粗横条以保证可读性

关键技术：
- 所有图形先在 4x 画布上绘制，再 LANCZOS 缩放，得到丝滑反走样
- ICO 用 **最大尺寸（256）** 作为 base image，自大到小 append，确保
  PIL 真正嵌入所有分辨率（之前以 16 为 base 会导致 ICO 内只有 16x16）
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ASSETS_DIR = Path(__file__).resolve().parent

# 主色（与 theme.py 一致），三段渐变让大尺寸更立体
PRIMARY_LIGHT = (52, 211, 153, 255)    # #34d399
PRIMARY = (16, 185, 129, 255)          # #10b981
PRIMARY_DARK = (5, 150, 105, 255)      # #059669
PRIMARY_DEEP = (4, 120, 87, 255)       # #047857
WHITE = (255, 255, 255, 255)
DOT_HIGHLIGHT = (167, 243, 208, 255)   # #a7f3d0，ring 内圈点缀色

# 输出尺寸
SIZES = [16, 24, 32, 48, 64, 128, 256, 512]
# 超采样倍数：先在 4x 大画布画，再缩放到目标尺寸
SUPERSAMPLE = 4


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(len(a)))


def _gradient_square(size: int) -> Image.Image:
    """对角三段主色渐变：左上 LIGHT -> 中 PRIMARY -> 右下 DEEP。"""
    base = Image.new("RGBA", (size, size))
    px = base.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))  # 0..1
            if t < 0.5:
                c = _lerp(PRIMARY_LIGHT, PRIMARY, t * 2)
            else:
                c = _lerp(PRIMARY, PRIMARY_DEEP, (t - 0.5) * 2)
            px[x, y] = (c[0], c[1], c[2], 255)
    return base


def _rounded_mask(size: int, radius_ratio: float = 0.235) -> Image.Image:
    """圆角方形 alpha 蒙版（含 1px anti-alias）。"""
    radius = max(2, int(size * radius_ratio))
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def _add_top_highlight(canvas: Image.Image) -> None:
    """右上角弧形高光，营造光泽感。"""
    s = canvas.size[0]
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    bbox = (-s * 0.15, -s * 0.55, s * 1.25, s * 0.45)
    draw.ellipse(bbox, fill=(255, 255, 255, 56))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=s * 0.05))
    canvas.alpha_composite(layer)


def _add_bottom_shade(canvas: Image.Image) -> None:
    """底部一抹深色暗角，进一步增强立体感。"""
    s = canvas.size[0]
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    bbox = (-s * 0.2, s * 0.55, s * 1.2, s * 1.6)
    draw.ellipse(bbox, fill=(0, 50, 35, 60))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=s * 0.06))
    canvas.alpha_composite(layer)


def _draw_list_glyph(canvas: Image.Image, *, full: bool) -> None:
    """在 canvas 中央画三条白色清单条 + 首条左侧的 ring 圆点。

    full=True 画完整版（含圆点 + 第三条短线）；False 简化版（仅三条等长横线）。
    """
    s = canvas.size[0]
    draw = ImageDraw.Draw(canvas)

    pad_x = int(s * 0.21)
    bar_h = max(2, int(s * (0.105 if full else 0.135)))
    gap = max(2, int(s * (0.085 if full else 0.075)))
    total_h = bar_h * 3 + gap * 2
    top_y = (s - total_h) // 2

    r = bar_h / 2

    if full:
        dot_r = bar_h * 0.92
        dot_cx = pad_x + dot_r
        line1_left = int(dot_cx + dot_r + s * 0.045)
    else:
        dot_r = 0
        line1_left = pad_x

    line_right = s - pad_x

    # 先画清单条
    for i in range(3):
        y0 = top_y + i * (bar_h + gap)
        y1 = y0 + bar_h
        x0 = line1_left if i == 0 else pad_x
        # 第二条略短一点（88%）、第三条更短（68%），让节奏更自然
        if not full:
            x1 = line_right
        elif i == 0:
            x1 = line_right
        elif i == 1:
            x1 = int(pad_x + (line_right - pad_x) * 0.88)
        else:
            x1 = int(pad_x + (line_right - pad_x) * 0.68)
        draw.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=WHITE)

    # 再画 ring 圆点（外白圈 + 内浅绿点 + 中心高光）
    if full:
        cy = top_y + bar_h / 2
        # 外圆（白）
        draw.ellipse(
            (dot_cx - dot_r, cy - dot_r, dot_cx + dot_r, cy + dot_r),
            fill=WHITE,
        )
        # 内空心填浅绿，做出 ring 视觉
        inner_r = dot_r * 0.58
        draw.ellipse(
            (dot_cx - inner_r, cy - inner_r, dot_cx + inner_r, cy + inner_r),
            fill=DOT_HIGHLIGHT,
        )
        # 中心实心点（白）
        core_r = dot_r * 0.28
        draw.ellipse(
            (dot_cx - core_r, cy - core_r, dot_cx + core_r, cy + core_r),
            fill=WHITE,
        )


def build_icon(size: int) -> Image.Image:
    """构造单一尺寸的 logo（4x 超采样 + LANCZOS 缩放）。"""
    big = size * SUPERSAMPLE
    full_detail = size >= 48  # 48 及以上画完整版

    if size >= 48:
        base = _gradient_square(big)
    else:
        # 小尺寸用纯色，避免渐变在低像素下变成脏色块
        base = Image.new("RGBA", (big, big), PRIMARY)

    # 小尺寸用更小圆角，保持视觉重量；大尺寸用更圆润的角
    radius_ratio = 0.22 if size <= 32 else 0.235
    mask = _rounded_mask(big, radius_ratio=radius_ratio)
    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    canvas.paste(base, (0, 0), mask)

    if size >= 64:
        _add_top_highlight(canvas)
    if size >= 128:
        _add_bottom_shade(canvas)

    _draw_list_glyph(canvas, full=full_detail)

    # 重新 mask 一次，确保所有阴影/高光仍在圆角内
    final = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    final.paste(canvas, (0, 0), mask)

    return final.resize((size, size), Image.Resampling.LANCZOS)


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

    # Windows ICO：每个尺寸独立构图（已写入 PNG），自大到小写入 ICO。
    # 注意：必须用最大尺寸作为 base，PIL 才会真正嵌入所有 append 进来的尺寸。
    ico_sizes = [256, 128, 64, 48, 32, 24, 16]
    ico_imgs = [Image.open(pngs[s]).convert("RGBA") for s in ico_sizes]
    ico_path = target / "logo.ico"
    ico_imgs[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
        append_images=ico_imgs[1:],
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
