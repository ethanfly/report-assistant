//! 报告导出：把报告内容（Markdown）保存为 .md / .html / .txt 文件。
//!
//! - .md：原样写入；
//! - .html：使用 pulldown-cmark 渲染为完整的 HTML 文档；
//! - .txt：原 Markdown 文本（不做转换，便于纯文本场景粘贴）。

use std::path::{Path, PathBuf};

use pulldown_cmark::{Options, Parser, html};

use crate::{Result, storage::Report};

/// 导出格式。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExportFormat {
    Md,
    Html,
    Txt,
}

impl ExportFormat {
    /// 文件扩展名（不含 `.`）。
    pub fn ext(self) -> &'static str {
        match self {
            ExportFormat::Md => "md",
            ExportFormat::Html => "html",
            ExportFormat::Txt => "txt",
        }
    }
}

/// 导出报告到指定目录。
///
/// 文件名规则：`{kind}_{period_start:YYYYMMDD}-{period_end:YYYYMMDD}.{ext}`
/// 文件名中所有不安全字符会被替换为 `_`。
pub fn export_report(
    report: &Report,
    dir: impl AsRef<Path>,
    fmt: ExportFormat,
) -> Result<PathBuf> {
    let dir = dir.as_ref();
    std::fs::create_dir_all(dir)?;

    let file_name = format!(
        "{}_{}-{}.{}",
        sanitize_segment(&report.kind),
        report.period_start.format("%Y%m%d"),
        report.period_end.format("%Y%m%d"),
        fmt.ext(),
    );
    let path = dir.join(file_name);

    let bytes: Vec<u8> = match fmt {
        ExportFormat::Md | ExportFormat::Txt => report.content.as_bytes().to_vec(),
        ExportFormat::Html => render_html(report).into_bytes(),
    };

    std::fs::write(&path, bytes)?;
    Ok(path)
}

/// 把 Markdown 渲染成一个最小可用的 HTML 文档（含 UTF-8 + 简单样式）。
fn render_html(report: &Report) -> String {
    let mut opts = Options::empty();
    opts.insert(Options::ENABLE_TABLES);
    opts.insert(Options::ENABLE_STRIKETHROUGH);
    opts.insert(Options::ENABLE_TASKLISTS);
    opts.insert(Options::ENABLE_FOOTNOTES);

    let parser = Parser::new_ext(&report.content, opts);
    let mut body = String::new();
    html::push_html(&mut body, parser);

    let title = format!(
        "{} {} ~ {}",
        report.kind,
        report.period_start.format("%Y-%m-%d"),
        report.period_end.format("%Y-%m-%d"),
    );

    format!(
        "<!DOCTYPE html>\n\
<html lang=\"zh-CN\">\n\
<head>\n\
<meta charset=\"utf-8\" />\n\
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n\
<title>{title}</title>\n\
<style>\n\
body {{ font-family: -apple-system, \"Segoe UI\", \"PingFang SC\", \"Microsoft YaHei\", sans-serif; \
max-width: 820px; margin: 2rem auto; padding: 0 1rem; line-height: 1.7; color: #222; }}\n\
h1, h2, h3 {{ line-height: 1.3; }}\n\
code {{ background: #f4f4f4; padding: 0 .25rem; border-radius: 3px; }}\n\
pre {{ background: #f4f4f4; padding: 1rem; border-radius: 6px; overflow-x: auto; }}\n\
blockquote {{ color: #555; border-left: 4px solid #ddd; margin: 0; padding: 0 1rem; }}\n\
table {{ border-collapse: collapse; }} th, td {{ border: 1px solid #ddd; padding: 4px 8px; }}\n\
</style>\n\
</head>\n\
<body>\n\
{body}\n\
</body>\n\
</html>\n",
        title = html_escape(&title),
        body = body,
    )
}

/// 文件名安全：把 ':' '/' '\\' 等替换为 '_'。
fn sanitize_segment(s: &str) -> String {
    s.chars()
        .map(|c| match c {
            '/' | '\\' | ':' | '*' | '?' | '"' | '<' | '>' | '|' | '\0' | '\n' | '\r' | '\t' => '_',
            _ => c,
        })
        .collect()
}

/// 极简 HTML 转义，仅用于 `<title>` 等纯文本场合。
fn html_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(c),
        }
    }
    out
}
