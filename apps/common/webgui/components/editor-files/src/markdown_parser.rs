//! =============================================================================
//! Process Name: AI-Windows-Admin WYSIWYG Editor - Markdown Parser & TOC
//! =============================================================================
//! Description:
//!   Высокопроизводительный парсер диалекта Markdown в HTML и экстрактор TOC
//!   для интерактивного WYSIWYG предпросмотра и синхронизации блоков.
//!
//! File: markdown_parser.rs
//! Project: ai-windows-admin
//! Package: apps.common.webgui.components.editor-files.src
//! Author: hypo69
//! Copyright: © 2026 hypo69
//! Updated: 2026-11-15 21:16:30
//! =============================================================================

use serde::Serialize;

#[derive(Serialize)]
pub struct HeadingItem {
    pub level: usize,
    pub text: String,
    pub anchor: String,
}

pub fn extract_toc_json(markdown: &str) -> String {
    let mut headings = Vec::new();

    for line in markdown.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('#') {
            let mut level = 0;
            for ch in trimmed.chars() {
                if ch == '#' {
                    level += 1;
                } else {
                    break;
                }
            }
            if level > 0 && level <= 6 && trimmed.as_bytes().get(level) == Some(&b' ') {
                let text = trimmed[level..].trim().to_string();
                let anchor = text.to_lowercase().replace(' ', "-");
                headings.push(HeadingItem { level, text, anchor });
            }
        }
    }

    serde_json::to_string(&headings).unwrap_or_else(|_| "[]".to_string())
}

pub fn render_markdown(markdown: &str) -> String {
    let mut out = String::with_capacity(markdown.len() * 2);
    let mut in_code_block = false;
    let mut in_list = false;

    for raw_line in markdown.lines() {
        let line = raw_line.trim_end();

        if line.starts_with("```") {
            if in_code_block {
                out.push_str("</code></pre>\n");
                in_code_block = false;
            } else {
                if in_list {
                    out.push_str("</ul>\n");
                    in_list = false;
                }
                out.push_str("<pre><code>");
                in_code_block = true;
            }
            continue;
        }

        if in_code_block {
            out.push_str(&html_escape(line));
            out.push('\n');
            continue;
        }

        let trimmed = line.trim();
        if trimmed.is_empty() {
            if in_list {
                out.push_str("</ul>\n");
                in_list = false;
            }
            continue;
        }

        if trimmed.starts_with('#') {
            if in_list {
                out.push_str("</ul>\n");
                in_list = false;
            }
            let mut level = 0;
            for ch in trimmed.chars() {
                if ch == '#' {
                    level += 1;
                } else {
                    break;
                }
            }
            if level > 0 && level <= 6 && trimmed.as_bytes().get(level) == Some(&b' ') {
                let title = trimmed[level..].trim();
                out.push_str(&format!("<h{}>{}</h{}>\n", level, inline_markdown(title), level));
                continue;
            }
        }

        if trimmed.starts_with("- ") || trimmed.starts_with("* ") {
            if !in_list {
                out.push_str("<ul>\n");
                in_list = true;
            }
            let item_text = &trimmed[2..];
            out.push_str(&format!("<li>{}</li>\n", inline_markdown(item_text)));
            continue;
        }

        if in_list {
            out.push_str("</ul>\n");
            in_list = false;
        }

        out.push_str(&format!("<p>{}</p>\n", inline_markdown(trimmed)));
    }

    if in_list {
        out.push_str("</ul>\n");
    }
    if in_code_block {
        out.push_str("</code></pre>\n");
    }

    out
}

fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn inline_markdown(s: &str) -> String {
    let escaped = html_escape(s);
    let strong = parse_double_delimiters(&escaped, "**", "<strong>", "</strong>");
    let em = parse_double_delimiters(&strong, "*", "<em>", "</em>");
    let code = parse_double_delimiters(&em, "`", "<code>", "</code>");
    code
}

fn parse_double_delimiters(s: &str, delimiter: &str, open_tag: &str, close_tag: &str) -> String {
    let mut result = String::with_capacity(s.len());
    let mut rest = s;
    let mut is_open = false;

    while let Some(pos) = rest.find(delimiter) {
        result.push_str(&rest[..pos]);
        if is_open {
            result.push_str(close_tag);
            is_open = false;
        } else {
            result.push_str(open_tag);
            is_open = true;
        }
        rest = &rest[pos + delimiter.len()..];
    }
    result.push_str(rest);
    if is_open {
        result.push_str(close_tag);
    }
    result
}
