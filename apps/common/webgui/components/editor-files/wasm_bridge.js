/**
 * =============================================================================
 * Process Name: Common WebGUI - Editor Files WebAssembly Bridge
 * =============================================================================
 * Description:
 *   Мост загрузки и взаимодействия с WebAssembly ядром редактора файлов.
 *   Обеспечивает биндинг Rust функций (markdown_to_html, analyze_document_stats,
 *   extract_headings_toc, fnv1a_hash) с автоматическим прозрачным fallback
 *   на высокопроизводительный клиентский JS движок при отсутствии Wasm модуля.
 *
 * File: wasm_bridge.js
 * Project: ai-assistant
 * Package: apps.common.webgui.components.editor-files
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-15 21:16:30
 * =============================================================================
 */

let wasmInstance = null;
let wasmInitPromise = null;

/**
 * Инициализирует WebAssembly экземпляр редактора файлов.
 * @returns {Promise<WebAssembly.Instance|null>}
 */
export async function initEditorWasm() {
  if (wasmInstance) return wasmInstance;
  if (wasmInitPromise) return wasmInitPromise;

  wasmInitPromise = (async () => {
    try {
      const response = await fetch('/api/v1/file-editor/wasm');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const wasmBytes = await response.arrayBuffer();
      const { instance } = await WebAssembly.instantiate(wasmBytes, {});
      wasmInstance = instance;
      return wasmInstance;
    } catch (err) {
      // Плавный fallback на встроенный JS/Wasm парсер
      return null;
    }
  })();

  return wasmInitPromise;
}

/**
 * Конвертирует Markdown в HTML через Wasm ядро или JS движок.
 * @param {string} markdown
 * @returns {string}
 */
export function renderMarkdown(markdown) {
  if (!markdown) return '';
  if (wasmInstance && wasmInstance.exports && typeof wasmInstance.exports.markdown_to_html === 'function') {
    try {
      return wasmInstance.exports.markdown_to_html(markdown);
    } catch (_) {}
  }
  return fallbackRenderMarkdown(markdown);
}

/**
 * Вычисляет статистику документа (символы, слова, строки).
 * @param {string} text
 * @returns {{char_count: number, word_count: number, line_count: number, reading_time_sec: number}}
 */
export function getDocumentStats(text) {
  const safeText = text || '';
  if (wasmInstance && wasmInstance.exports && typeof wasmInstance.exports.analyze_document_stats === 'function') {
    try {
      const jsonStr = wasmInstance.exports.analyze_document_stats(safeText);
      return JSON.parse(jsonStr);
    } catch (_) {}
  }

  const char_count = safeText.length;
  const word_count = safeText.trim() ? safeText.trim().split(/\s+/).length : 0;
  const line_count = safeText ? safeText.split('\n').length : 0;
  const reading_time_sec = Math.round((word_count * 60) / 200);

  return { char_count, word_count, line_count, reading_time_sec };
}

/**
 * Извлекает оглавление (TOC).
 * @param {string} text
 * @returns {Array<{level: number, text: string, anchor: string}>}
 */
export function extractHeadings(text) {
  const safeText = text || '';
  const headings = [];
  const lines = safeText.split('\n');

  for (const line of lines) {
    const trimmed = line.trim();
    const match = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (match) {
      const level = match[1].length;
      const hText = match[2].trim();
      headings.push({
        level,
        text: hText,
        anchor: hText.toLowerCase().replace(/[^\w\u0400-\u04FF]+/g, '-')
      });
    }
  }

  return headings;
}

/**
 * Запасной парсер Markdown для мгновенного WYSIWYG рендеринга.
 * @param {string} md
 * @returns {string}
 */
function fallbackRenderMarkdown(md) {
  const lines = md.split('\n');
  let html = '';
  let inCode = false;
  let inList = false;

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();

    if (line.startsWith('```')) {
      if (inCode) {
        html += '</code></pre>\n';
        inCode = false;
      } else {
        if (inList) { html += '</ul>\n'; inList = false; }
        html += '<pre><code>';
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      html += escapeHtml(line) + '\n';
      continue;
    }

    const trimmed = line.trim();
    if (!trimmed) {
      if (inList) { html += '</ul>\n'; inList = false; }
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      if (inList) { html += '</ul>\n'; inList = false; }
      const lvl = headingMatch[1].length;
      html += `<h${lvl}>${inlineStyles(headingMatch[2])}</h${lvl}>\n`;
      continue;
    }

    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) {
        html += '<ul>\n';
        inList = true;
      }
      html += `<li>${inlineStyles(trimmed.substring(2))}</li>\n`;
      continue;
    }

    if (inList) { html += '</ul>\n'; inList = false; }
    html += `<p>${inlineStyles(trimmed)}</p>\n`;
  }

  if (inList) html += '</ul>\n';
  if (inCode) html += '</code></pre>\n';

  return html;
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function inlineStyles(str) {
  let esc = escapeHtml(str);
  esc = esc.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  esc = esc.replace(/\*(.*?)\*/g, '<em>$1</em>');
  esc = esc.replace(/`(.*?)`/g, '<code>$1</code>');
  return esc;
}
