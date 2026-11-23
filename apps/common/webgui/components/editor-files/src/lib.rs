//! =============================================================================
//! Process Name: AI-Windows-Admin WYSIWYG Editor - Rust Core Entry
//! =============================================================================
//! Description:
//!   Модуль WebAssembly ядра WYSIWYG редактора файлов.
//!   Предоставляет функции быстрого парсинга Markdown в HTML, безопасной очистки,
//!   конвертации HTML в Markdown, вычисления FNV-1a хеша буфера, подсчета статистики
//!   (слова, символы, строки) и формирования структуры заголовков документа (TOC).
//!
//! File: lib.rs
//! Project: ai-windows-admin
//! Package: apps.common.webgui.components.editor-files.src
//! Author: hypo69
//! Copyright: © 2026 hypo69
//! Updated: 2026-11-15 21:16:30
//! =============================================================================

pub mod markdown_parser;
pub mod stats;

use wasm_bindgen::prelude::*;

/// Вычисляет 32-битный хеш FNV-1a для содержимого буфера редактора.
#[no_mangle]
#[wasm_bindgen]
pub fn fnv1a_hash(data: &[u8]) -> u32 {
    let mut hash: u32 = 2166136261;
    for &byte in data {
        hash ^= byte as u32;
        hash = hash.wrapping_mul(16777619);
    }
    hash
}

/// Выполняет высокоскоростной парсинг Markdown в HTML на стороне Rust WASM.
#[wasm_bindgen]
pub fn markdown_to_html(markdown_text: &str) -> String {
    markdown_parser::render_markdown(markdown_text)
}

/// Анализирует текст и возвращает JSON со статистикой (символы, слова, строки).
#[wasm_bindgen]
pub fn analyze_document_stats(text: &str) -> String {
    stats::compute_stats_json(text)
}

/// Извлекает оглавление документа (TOC / Headings) в формате JSON.
#[wasm_bindgen]
pub fn extract_headings_toc(markdown_text: &str) -> String {
    markdown_parser::extract_toc_json(markdown_text)
}
