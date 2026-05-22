// 一次性图标生成工具：生成 report-assistant 的应用图标
// 设计：圆角紫色方块 + 中间白色 "T" 字
// 输出位置：src-tauri/icons/

use anyhow::{Context, Result};
use std::fs::File;
use std::path::{Path, PathBuf};

use tiny_skia::{Color, FillRule, Paint, PathBuilder, Pixmap, Transform};

/// 紫色背景 #8B5CF6
const BG_R: u8 = 0x8B;
const BG_G: u8 = 0x5C;
const BG_B: u8 = 0xF6;

/// 在指定边长上渲染图标，返回 RGBA pixmap
fn render(size: u32) -> Result<Pixmap> {
    let s = size as f32;

    // 创建透明画布
    let mut pixmap = Pixmap::new(size, size).context("创建 pixmap 失败")?;

    // ---------- 1. 圆角紫色背景 ----------
    let radius = s * 0.22; // iOS 风格圆角半径：边长的 22%
    let bg_path = rounded_rect_path(0.0, 0.0, s, s, radius)
        .context("构造圆角矩形路径失败")?;

    let mut bg_paint = Paint::default();
    bg_paint.set_color(Color::from_rgba8(BG_R, BG_G, BG_B, 255));
    bg_paint.anti_alias = true;
    pixmap.fill_path(
        &bg_path,
        &bg_paint,
        FillRule::Winding,
        Transform::identity(),
        None,
    );

    // ---------- 2. 白色 "T" 字（用矩形拼出） ----------
    let mut fg_paint = Paint::default();
    fg_paint.set_color(Color::from_rgba8(255, 255, 255, 255));
    fg_paint.anti_alias = true;

    // 横线：宽 = 边长 × 0.62，高 = 边长 × 0.13，置于顶部约 25% 位置居中
    let h_w = s * 0.62;
    let h_h = s * 0.13;
    let h_x = (s - h_w) / 2.0;
    let h_y = s * 0.25;
    // 横线本身也加点小圆角，看起来更精致
    let h_radius = h_h * 0.25;
    let h_path = rounded_rect_path(h_x, h_y, h_w, h_h, h_radius)
        .context("构造横线路径失败")?;
    pixmap.fill_path(
        &h_path,
        &fg_paint,
        FillRule::Winding,
        Transform::identity(),
        None,
    );

    // 竖线：宽 = 边长 × 0.13，高 = 边长 × 0.5，与横线居中对齐（顶部对齐到横线下沿）
    let v_w = s * 0.13;
    let v_h = s * 0.5;
    let v_x = (s - v_w) / 2.0;
    let v_y = h_y; // 与横线顶端对齐，向下延伸
    let v_radius = v_w * 0.25;
    let v_path = rounded_rect_path(v_x, v_y, v_w, v_h, v_radius)
        .context("构造竖线路径失败")?;
    pixmap.fill_path(
        &v_path,
        &fg_paint,
        FillRule::Winding,
        Transform::identity(),
        None,
    );

    Ok(pixmap)
}

/// 构造一个圆角矩形路径
fn rounded_rect_path(
    x: f32,
    y: f32,
    w: f32,
    h: f32,
    r: f32,
) -> Option<tiny_skia::Path> {
    // 限制半径不超过短边一半
    let r = r.min(w / 2.0).min(h / 2.0).max(0.0);

    let mut pb = PathBuilder::new();
    // 顺时针绘制，使用三次贝塞尔近似圆弧（系数 0.5523 ≈ 4*(sqrt(2)-1)/3）
    let k = 0.5522847498_f32;
    let cx = r * k;

    // 左上起点
    pb.move_to(x + r, y);
    // 顶边 → 右上角
    pb.line_to(x + w - r, y);
    pb.cubic_to(x + w - r + cx, y, x + w, y + r - cx, x + w, y + r);
    // 右边 → 右下角
    pb.line_to(x + w, y + h - r);
    pb.cubic_to(x + w, y + h - r + cx, x + w - r + cx, y + h, x + w - r, y + h);
    // 底边 → 左下角
    pb.line_to(x + r, y + h);
    pb.cubic_to(x + r - cx, y + h, x, y + h - r + cx, x, y + h - r);
    // 左边 → 左上角
    pb.line_to(x, y + r);
    pb.cubic_to(x, y + r - cx, x + r - cx, y, x + r, y);
    pb.close();

    pb.finish()
}

/// 渲染为 RGBA 字节数据（连续 RGBA8888，行优先）
fn render_rgba_bytes(size: u32) -> Result<Vec<u8>> {
    let pixmap = render(size)?;
    // tiny-skia 的 Pixmap.data() 已经是 RGBA8888 顺序
    Ok(pixmap.data().to_vec())
}

/// 把 pixmap 保存为 PNG（通过 image crate）
fn save_png(size: u32, path: &Path) -> Result<u64> {
    let bytes = render_rgba_bytes(size)?;
    let img = image::RgbaImage::from_raw(size, size, bytes)
        .context("从 raw RGBA 构造 RgbaImage 失败")?;
    img.save(path)
        .with_context(|| format!("保存 PNG 失败: {}", path.display()))?;
    Ok(std::fs::metadata(path)?.len())
}

fn main() -> Result<()> {
    // 输出目录：相对于 workspace 根的 src-tauri/icons/
    // 用 CARGO_MANIFEST_DIR 推导，确保不论从哪里运行 cargo run 都能定位
    let manifest_dir =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")); // crates/icon-gen
    let workspace_root = manifest_dir
        .parent()
        .and_then(|p| p.parent())
        .context("定位 workspace 根目录失败")?
        .to_path_buf();
    let out_dir = workspace_root.join("src-tauri").join("icons");
    std::fs::create_dir_all(&out_dir)?;

    println!("输出目录: {}", out_dir.display());
    println!();

    // ---------- PNG 系列 ----------
    let png_targets: &[(&str, u32)] = &[
        ("32x32.png", 32),
        ("128x128.png", 128),
        ("128x128@2x.png", 256), // @2x 即 128 的两倍 256
        ("icon.png", 512),
    ];

    println!("== PNG 文件 ==");
    for (name, size) in png_targets {
        let path = out_dir.join(name);
        let bytes = save_png(*size, &path)?;
        println!(
            "  {:<18} {:>4}x{:<4}  {:>8} bytes",
            name, size, size, bytes
        );
    }

    // ---------- ICO（多尺寸） ----------
    println!();
    println!("== ICO ==");
    let ico_path = out_dir.join("icon.ico");
    {
        let mut icon_dir = ico::IconDir::new(ico::ResourceType::Icon);
        for &size in &[16u32, 32, 48, 64, 128, 256] {
            let rgba = render_rgba_bytes(size)?;
            let img = ico::IconImage::from_rgba_data(size, size, rgba);
            icon_dir.add_entry(ico::IconDirEntry::encode(&img)?);
        }
        let f = File::create(&ico_path)
            .with_context(|| format!("创建 {} 失败", ico_path.display()))?;
        icon_dir.write(f)?;
    }
    let ico_size = std::fs::metadata(&ico_path)?.len();
    println!(
        "  icon.ico (16/32/48/64/128/256)  {:>8} bytes",
        ico_size
    );

    // ---------- ICNS（macOS） ----------
    println!();
    println!("== ICNS ==");
    let icns_path = out_dir.join("icon.icns");
    {
        let mut family = icns::IconFamily::new();
        let entries: &[(icns::IconType, u32)] = &[
            (icns::IconType::RGBA32_16x16, 16),
            (icns::IconType::RGBA32_32x32, 32),
            (icns::IconType::RGBA32_64x64, 64),
            (icns::IconType::RGBA32_128x128, 128),
            (icns::IconType::RGBA32_256x256, 256),
            (icns::IconType::RGBA32_512x512, 512),
        ];
        for &(t, size) in entries {
            let rgba = render_rgba_bytes(size)?;
            let img = icns::Image::from_data(icns::PixelFormat::RGBA, size, size, rgba)?;
            family.add_icon_with_type(&img, t)?;
        }
        let mut f = File::create(&icns_path)
            .with_context(|| format!("创建 {} 失败", icns_path.display()))?;
        family.write(&mut f)?;
    }
    let icns_size = std::fs::metadata(&icns_path)?.len();
    println!(
        "  icon.icns (16/32/64/128/256/512)  {:>8} bytes",
        icns_size
    );

    println!();
    println!("全部图标已生成完毕。");
    Ok(())
}
