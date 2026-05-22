// 一次性图标生成工具：生成 report-assistant 的应用图标
// 设计：32×32 像素艺术 — 清新绿系二次元少女头像
// 渲染：nearest-neighbor 整数放大（不做抗锯齿，保留像素硬边）
// 输出位置：src-tauri/icons/

use anyhow::{Context, Result};
use std::fs::File;
use std::path::{Path, PathBuf};

use tiny_skia::Pixmap;

/// 32×32 像素艺术位图，每行严格 32 个字符。
///
/// 字符 → 颜色（详见 [`color_for_char`]）：
/// - `.` 浅绿背景    `#` 深绿像素描边
/// - `H` 头发（清新绿）  `S` 皮肤
/// - `E` 眼瞳（黑）  `W` 眼睛高光（白）
/// - `R` 红晕（粉）  `M` 嘴巴（深粉）
#[rustfmt::skip]
const PIXEL_ART_32: &[&str] = &[
    "################################", //  0  上边框
    "#..............................#", //  1  顶部留白
    "#..............................#", //  2  顶部留白
    "#.............HHHH.............#", //  3  头顶（4 像素）
    "#...........HHHHHHHH...........#", //  4  （8）
    "#.........HHHHHHHHHHHH.........#", //  5  （12）
    "#.......HHHHHHHHHHHHHHHH.......#", //  6  （16）
    "#.....HHHHHHHHHHHHHHHHHHHH.....#", //  7  （20）
    "#....HHHHHHHHHHHHHHHHHHHHHH....#", //  8  （22）
    "#...HHHHHHHHHHHHHHHHHHHHHHHH...#", //  9  （24）
    "#..HHHHHHHHHHHHHHHHHHHHHHHHHH..#", // 10  （26）
    "#..HHHHHHHHHHHHHHHHHHHHHHHHHH..#", // 11  刘海
    "#..HHHHHHHHHHHHHHHHHHHHHHHHHH..#", // 12  刘海
    "#.HHHHHHSSSSSSSSSSSSSSSSHHHHHH.#", // 13  额头开始
    "#.HHHHHHSSSSSSSSSSSSSSSSHHHHHH.#", // 14  额头
    "#.HHHHHHSSSWESSSSSSWESSSHHHHHH.#", // 15  眼上半
    "#.HHHHHHSSSEESSSSSSEESSSHHHHHH.#", // 16  眼下半
    "#.HHHHHHSSSSSSSSSSSSSSSSHHHHHH.#", // 17  鼻梁区
    "#.HHHHHHSSRSSSSSSSSSSRSSHHHHHH.#", // 18  红晕
    "#.HHHHHHSSSSSSSMMSSSSSSSHHHHHH.#", // 19  嘴巴
    "#.HHHHHHSSSSSSSSSSSSSSSSHHHHHH.#", // 20  脸颊
    "#.HHHHHHHSSSSSSSSSSSSSSHHHHHHH.#", // 21  下巴开始收窄
    "#..HHHHHHHSSSSSSSSSSSSHHHHHHH..#", // 22
    "#...HHHHHHHSSSSSSSSSSHHHHHHH...#", // 23
    "#....HHHHHHHHSSSSSSHHHHHHHH....#", // 24
    "#......HHHHHHHHHHHHHHHHHH......#", // 25  下方头发
    "#........HHHHHHHHHHHHHH........#", // 26
    "#...........HHHHHHHH...........#", // 27
    "#..............HH..............#", // 28  尾尖
    "#..............................#", // 29  底部留白
    "#..............................#", // 30  底部留白
    "################################", // 31  下边框
];

/// 字符 → RGBA 颜色（清新绿系，alpha 全为 255）。
fn color_for_char(c: char) -> [u8; 4] {
    match c {
        '.' => [0xE8, 0xF5, 0xE9, 0xFF], // 浅绿背景
        '#' => [0x2E, 0x7D, 0x32, 0xFF], // 深绿像素描边
        'H' => [0x7B, 0xC4, 0x7F, 0xFF], // 头发：清新绿
        'S' => [0xFF, 0xE0, 0xBD, 0xFF], // 皮肤
        'E' => [0x22, 0x22, 0x22, 0xFF], // 眼瞳（黑）
        'W' => [0xFF, 0xFF, 0xFF, 0xFF], // 眼睛高光（白）
        'R' => [0xFF, 0xB3, 0xB3, 0xFF], // 红晕（粉）
        'M' => [0xE5, 0x73, 0x73, 0xFF], // 嘴巴（深粉）
        _ => [0, 0, 0, 0],               // 未知字符 → 透明（理论上不会触发）
    }
}

/// 把 32×32 像素艺术烤成一张 RGBA 调色板表，
/// 同时校验行数=32 且每行长度严格为 32（否则 panic 提前报错）。
fn build_palette() -> [[u8; 4]; 32 * 32] {
    let mut palette = [[0u8; 4]; 32 * 32];
    assert_eq!(PIXEL_ART_32.len(), 32, "PIXEL_ART_32 必须正好 32 行");
    for (row_idx, row) in PIXEL_ART_32.iter().enumerate() {
        let chars: Vec<char> = row.chars().collect();
        assert_eq!(
            chars.len(),
            32,
            "第 {} 行长度不是 32（实际 {}）：{}",
            row_idx,
            chars.len(),
            row
        );
        for (col_idx, &ch) in chars.iter().enumerate() {
            palette[row_idx * 32 + col_idx] = color_for_char(ch);
        }
    }
    palette
}

/// 在指定边长上渲染图标（nearest-neighbor 整数放大），返回 RGBA pixmap。
///
/// 不做任何抗锯齿，保留像素艺术的硬边。
/// tiny-skia 的 `Pixmap` 内部为预乘 RGBA；本工具所有颜色 alpha=255，
/// 预乘值等于未预乘值，故可直接写入字节缓冲。
fn render(size: u32) -> Result<Pixmap> {
    let palette = build_palette();
    let mut pixmap = Pixmap::new(size, size).context("创建 pixmap 失败")?;

    let data = pixmap.data_mut();
    for y in 0..size {
        // nearest-neighbor 采样：源 y = floor(y * 32 / size)
        let sy = ((y as u64 * 32) / size as u64).min(31) as usize;
        let row_offset = sy * 32;
        for x in 0..size {
            let sx = ((x as u64 * 32) / size as u64).min(31) as usize;
            let rgba = palette[row_offset + sx];
            let i = ((y * size + x) * 4) as usize;
            data[i..i + 4].copy_from_slice(&rgba);
        }
    }

    Ok(pixmap)
}

/// 渲染为 RGBA 字节数据（连续 RGBA8888，行优先）
fn render_rgba_bytes(size: u32) -> Result<Vec<u8>> {
    let pixmap = render(size)?;
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
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")); // crates/icon-gen
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
