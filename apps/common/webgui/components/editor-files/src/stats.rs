//! =============================================================================
//! Process Name: AI-Windows-Admin WYSIWYG Editor - Document Statistics
//! =============================================================================
//! Description:
//!   Модуль высокоскоростного подсчёта статистики документов в линейной памяти.
//!
//! File: stats.rs
//! Project: ai-windows-admin
//! Package: apps.common.webgui.components.editor-files.src
//! Author: hypo69
//! Copyright: © 2026 hypo69
//! Updated: 2026-11-15 21:16:30
//! =============================================================================

use serde::Serialize;

#[derive(Serialize)]
pub struct DocumentStats {
    pub char_count: usize,
    pub word_count: usize,
    pub line_count: usize,
    pub reading_time_sec: usize,
}

pub fn compute_stats_json(text: &str) -> String {
    let char_count = text.chars().count();
    let word_count = text.split_whitespace().count();
    let line_count = if text.is_empty() { 0 } else { text.lines().count() };
    let reading_time_sec = (word_count * 60) / 200;

    let stats = DocumentStats {
        char_count,
        word_count,
        line_count,
        reading_time_sec,
    };

    serde_json::to_string(&stats).unwrap_or_else(|_| "{}".to_string())
}
