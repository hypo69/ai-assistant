/**
 * =============================================================================
 * Process Name: Common WebGUI - Universal Editor Files Component Script
 * =============================================================================
 * Description:
 *   Контроллер универсального компонента editor-files.
 *   Управляет режимами WYSIWYG, Split и Raw Code, синхронизацией буферов,
 *   вызовом Wasm Bridge для Markdown/HTML рендеринга и TOC, статистикой
 *   и событиями сохранения/изменения файлов.
 *
 * File: editor_files.js
 * Project: ai-windows-admin
 * Package: apps.common.webgui.components.editor-files
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-15 21:16:30
 * =============================================================================
 */

import { initEditorWasm, renderMarkdown, getDocumentStats, extractHeadings } from './wasm_bridge.js';

export class EditorFilesComponent {
  /**
   * @param {HTMLElement} rootElement
   * @param {Object} options
   */
  constructor(rootElement, options = {}) {
    this.root = rootElement;
    this.options = Object.assign({
      initialContent: '',
      mode: 'wysiwyg', // 'wysiwyg' | 'split' | 'raw'
      onSave: null,
      onChange: null
    }, options);

    this.currentMode = this.options.mode;
    this.content = this.options.initialContent;
    this.isSyncing = false;

    this.dom = {};
  }

  /**
   * Инициализация компонента и привязка событий.
   */
  async init() {
    this.cacheDom();
    this.bindEvents();
    await initEditorWasm();
    this.setMode(this.currentMode);
    this.setContent(this.content);
  }

  cacheDom() {
    this.dom.wrapper = this.root.querySelector('#editor-files-container') || this.root;
    this.dom.textarea = this.root.querySelector('#editor-files-textarea');
    this.dom.visual = this.root.querySelector('#editor-files-visual');
    this.dom.tocList = this.root.querySelector('#editor-files-toc-list');
    this.dom.statLines = this.root.querySelector('#editor-stat-lines');
    this.dom.statWords = this.root.querySelector('#editor-stat-words');
    this.dom.statChars = this.root.querySelector('#editor-stat-chars');
    this.dom.statReading = this.root.querySelector('#editor-stat-reading');
    this.dom.btnSave = this.root.querySelector('#btn-editor-save');
    this.dom.modeBtns = this.root.querySelectorAll('.editor-mode-btn');
    this.dom.formatBtns = this.root.querySelectorAll('.editor-files-toolbar button[data-cmd]');
  }

  bindEvents() {
    // Ввод в текстовой области (Raw)
    if (this.dom.textarea) {
      this.dom.textarea.addEventListener('input', () => {
        if (this.isSyncing) return;
        this.content = this.dom.textarea.value;
        this.syncFromRaw();
      });
    }

    // Ввод в визуальной области (WYSIWYG)
    if (this.dom.visual) {
      this.dom.visual.addEventListener('input', () => {
        if (this.isSyncing) return;
        this.syncFromVisual();
      });
    }

    // Переключение режимов
    this.dom.modeBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const mode = e.currentTarget.getAttribute('data-mode');
        if (mode) this.setMode(mode);
      });
    });

    // Кнопка сохранения
    if (this.dom.btnSave) {
      this.dom.btnSave.addEventListener('click', () => {
        if (typeof this.options.onSave === 'function') {
          this.options.onSave(this.getContent());
        }
      });
    }

    // Команды форматирования WYSIWYG
    this.dom.formatBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const cmd = e.currentTarget.getAttribute('data-cmd');
        this.applyFormat(cmd);
      });
    });
  }

  setMode(mode) {
    this.currentMode = mode;
    this.dom.wrapper.setAttribute('data-active-mode', mode);

    this.dom.modeBtns.forEach(btn => {
      if (btn.getAttribute('data-mode') === mode) {
        btn.classList.add('is-active');
      } else {
        btn.classList.remove('is-active');
      }
    });

    if (mode === 'wysiwyg' || mode === 'split') {
      this.renderVisualContent();
    }
  }

  setContent(text) {
    this.content = text || '';
    if (this.dom.textarea) this.dom.textarea.value = this.content;
    this.renderVisualContent();
    this.updateStats();
    this.updateToc();
  }

  getContent() {
    return this.content;
  }

  syncFromRaw() {
    this.isSyncing = true;
    if (this.currentMode !== 'raw') {
      this.renderVisualContent();
    }
    this.updateStats();
    this.updateToc();
    this.notifyChange();
    this.isSyncing = false;
  }

  syncFromVisual() {
    this.isSyncing = true;
    // Базовая синхронизация текста из WYSIWYG innerText
    this.content = this.dom.visual.innerText;
    if (this.dom.textarea) {
      this.dom.textarea.value = this.content;
    }
    this.updateStats();
    this.updateToc();
    this.notifyChange();
    this.isSyncing = false;
  }

  renderVisualContent() {
    if (!this.dom.visual) return;
    const html = renderMarkdown(this.content);
    this.dom.visual.innerHTML = html;
  }

  updateStats() {
    const stats = getDocumentStats(this.content);
    if (this.dom.statLines) this.dom.statLines.textContent = stats.line_count;
    if (this.dom.statWords) this.dom.statWords.textContent = stats.word_count;
    if (this.dom.statChars) this.dom.statChars.textContent = stats.char_count;
    if (this.dom.statReading) this.dom.statReading.textContent = `${stats.reading_time_sec}s`;
  }

  updateToc() {
    if (!this.dom.tocList) return;
    const headings = extractHeadings(this.content);
    this.dom.tocList.innerHTML = '';

    headings.forEach(h => {
      const link = document.createElement('a');
      link.className = `editor-toc-link editor-toc-lvl-${h.level}`;
      link.textContent = h.text;
      link.addEventListener('click', () => {
        // Прокрутка к заголовку в визуальной области
        const hElements = this.dom.visual.querySelectorAll(`h${h.level}`);
        for (const el of hElements) {
          if (el.textContent.trim() === h.text.trim()) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            break;
          }
        }
      });
      this.dom.tocList.appendChild(link);
    });
  }

  applyFormat(cmd) {
    if (this.currentMode === 'raw') {
      this.applyFormatRaw(cmd);
      return;
    }
    document.execCommand(cmd === 'heading' ? 'formatBlock' : (cmd === 'ul' ? 'insertUnorderedList' : (cmd === 'ol' ? 'insertOrderedList' : cmd)), false, cmd === 'heading' ? 'h2' : null);
    this.syncFromVisual();
  }

  applyFormatRaw(cmd) {
    const el = this.dom.textarea;
    if (!el) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const selected = el.value.substring(start, end);
    let replacement = selected;

    switch (cmd) {
      case 'bold': replacement = `**${selected}**`; break;
      case 'italic': replacement = `*${selected}*`; break;
      case 'code': replacement = `\`${selected}\``; break;
      case 'heading': replacement = `## ${selected}`; break;
      case 'ul': replacement = `- ${selected}`; break;
      case 'ol': replacement = `1. ${selected}`; break;
      case 'quote': replacement = `> ${selected}`; break;
      case 'table': replacement = `\n| Column 1 | Column 2 |\n|---|---|\n| Item 1 | Item 2 |\n`; break;
      default: return;
    }

    el.setRangeText(replacement, start, end, 'end');
    this.content = el.value;
    this.syncFromRaw();
  }

  notifyChange() {
    if (typeof this.options.onChange === 'function') {
      this.options.onChange(this.content);
    }
  }
}
