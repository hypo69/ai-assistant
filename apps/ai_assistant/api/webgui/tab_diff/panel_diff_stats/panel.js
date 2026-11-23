/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Version Comparison Panel (panel_diff_stats)
 * =============================================================================
 * Description:
 *   Дружелюбная панель сравнения версий документов (panel-diff-stats).
 *   Загружает список сохранений в понятный выпадающий список, отображает
 *   затронутые документы, преобразует технические различия в наглядный
 *   человекочитаемый вид и запрашивает пояснение простыми словами у ИИ.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_diff/panel_diff_stats
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-19 20:23:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';
import {
  t,
  escapeHtml,
  formatCommitMessage,
  formatFriendlyDate
} from '../../tab_commits/panel_commits/panel.js';

let isInitialized = false;
let availableVersions = [];
let lastDiffRawText = '';
let lastDiffMeta = { commitHash: 'HEAD', filePath: null, label: '' };
let lastStatsData = [];
let viewMode = 'friendly'; // 'friendly' | 'raw'
let onlyChanges = true;

/**
 * Разделяет относительный путь файла на имя файла и каталог.
 * @param {string} fullPath - Относительный путь файла
 * @returns {{ name: string, dir: string }}
 */
function splitFilePath(fullPath) {
  if (!fullPath) return { name: '', dir: '' };
  const normalized = String(fullPath).replace(/\\/g, '/');
  const idx = normalized.lastIndexOf('/');
  if (idx === -1) return { name: normalized, dir: '' };
  return {
    name: normalized.slice(idx + 1),
    dir: normalized.slice(0, idx)
  };
}

/**
 * Разбирает сырой unified diff на структурированные карточки документов.
 * @param {string} rawText - Исходный текст diff
 * @returns {Array<Object>}
 */
export function parseUnifiedDiff(rawText) {
  if (!rawText || !rawText.trim()) return [];

  const files = [];
  let currentFile = null;
  let currentHunk = null;

  const lines = rawText.split('\n');
  for (const line of lines) {
    if (line.startsWith('diff --git ')) {
      if (currentFile) files.push(currentFile);
      const match = line.match(/^diff --git a\/(.+?) b\/(.+)$/);
      const fullPath = match ? match[2] : line.replace('diff --git ', '').trim();
      const { name, dir } = splitFilePath(fullPath);
      currentFile = {
        fullPath,
        name,
        dir,
        isBinary: false,
        addedCount: 0,
        removedCount: 0,
        hunks: []
      };
      currentHunk = null;
      continue;
    }

    if (!currentFile) {
      if (line.startsWith('+++ b/')) {
        const fullPath = line.slice(6).trim();
        const { name, dir } = splitFilePath(fullPath);
        currentFile = {
          fullPath,
          name,
          dir,
          isBinary: false,
          addedCount: 0,
          removedCount: 0,
          hunks: []
        };
      }
      continue;
    }

    if (
      line.startsWith('Binary files ') ||
      line.startsWith('GIT binary patch') ||
      line.includes('Binary file')
    ) {
      currentFile.isBinary = true;
      continue;
    }

    if (
      line.startsWith('index ') ||
      line.startsWith('--- ') ||
      line.startsWith('+++ ') ||
      line.startsWith('new file mode') ||
      line.startsWith('deleted file mode') ||
      line.startsWith('old mode') ||
      line.startsWith('new mode') ||
      line.startsWith('similarity index') ||
      line.startsWith('rename from') ||
      line.startsWith('rename to') ||
      line.startsWith('\\ No newline at end of file')
    ) {
      continue;
    }

    if (line.startsWith('@@')) {
      currentHunk = { lines: [] };
      currentFile.hunks.push(currentHunk);
      continue;
    }

    if (!currentHunk) {
      currentHunk = { lines: [] };
      currentFile.hunks.push(currentHunk);
    }

    if (line.startsWith('+')) {
      currentFile.addedCount += 1;
      currentHunk.lines.push({ type: 'add', text: line.slice(1) });
    } else if (line.startsWith('-')) {
      currentFile.removedCount += 1;
      currentHunk.lines.push({ type: 'del', text: line.slice(1) });
    } else if (line.startsWith(' ')) {
      currentHunk.lines.push({ type: 'ctx', text: line.slice(1) });
    } else if (line.trim()) {
      currentHunk.lines.push({ type: 'ctx', text: line });
    }
  }

  if (currentFile) files.push(currentFile);
  return files;
}

/**
 * Отрисовывает наглядный человекочитаемый просмотр изменений в #diff-friendly-view.
 * @param {string} rawText - Исходный текст различий
 */
function renderFriendlyDiffView(rawText) {
  const container = document.getElementById('diff-friendly-view');
  if (!container) return;

  if (!rawText || !rawText.trim()) {
    container.innerHTML = `<div class="text-center py-4 text-muted small">${escapeHtml(t('ui.diff.noChanges', 'В выбранной версии нет текстовых изменений.'))}</div>`;
    return;
  }

  const files = parseUnifiedDiff(rawText);
  if (files.length === 0) {
    container.innerHTML = `<div class="text-center py-4 text-muted small">${escapeHtml(t('ui.diff.noChanges', 'В выбранной версии нет текстовых изменений.'))}</div>`;
    return;
  }

  const addedWord = t('ui.diff.addedLabel', 'Добавлено');
  const removedWord = t('ui.diff.removedLabel', 'Удалено');
  const binaryNotice = t('ui.diff.binaryNotice', 'Файл обновлён (вложения, PDF и изображения не отображаются построчно).');
  const unchangedFragment = t('ui.diff.unchangedSeparator', '••• Неизменённая часть документа •••');

  container.innerHTML = files.map((file) => {
    let bodyHtml = '';
    if (file.isBinary) {
      bodyHtml = `
        <div class="p-3 text-muted small d-flex align-items-center gap-2">
          <i class="bi bi-file-earmark-binary fs-5 text-info"></i>
          <span>${escapeHtml(binaryNotice)}</span>
        </div>
      `;
    } else {
      const chunksHtml = [];
      file.hunks.forEach((hunk, hunkIdx) => {
        const filteredLines = onlyChanges
          ? hunk.lines.filter((l) => l.type === 'add' || l.type === 'del')
          : hunk.lines;

        if (filteredLines.length === 0) return;

        if (hunkIdx > 0 && chunksHtml.length > 0) {
          chunksHtml.push(`<div class="friendly-diff-row is-separator">${escapeHtml(unchangedFragment)}</div>`);
        }

        filteredLines.forEach((l) => {
          const rowClass = l.type === 'add' ? 'is-added' : (l.type === 'del' ? 'is-removed' : 'is-context');
          const sign = l.type === 'add' ? '+' : (l.type === 'del' ? '−' : '·');
          const displayLine = l.text === '' ? ' ' : l.text;
          chunksHtml.push(`
            <div class="friendly-diff-row ${rowClass}">
              <span class="friendly-diff-sign">${sign}</span>
              <span class="friendly-diff-text" dir="auto">${escapeHtml(displayLine)}</span>
            </div>
          `);
        });
      });

      if (chunksHtml.length === 0) {
        bodyHtml = `<div class="p-3 text-muted small">${escapeHtml(t('ui.diff.noTextLines', 'Содержимое документа не изменилось.'))}</div>`;
      } else {
        bodyHtml = `<div class="friendly-diff-lines">${chunksHtml.join('')}</div>`;
      }
    }

    return `
      <div class="friendly-diff-file">
        <div class="friendly-diff-file-header">
          <div class="d-flex align-items-center gap-2 min-w-0">
            <i class="bi bi-file-earmark-text text-primary"></i>
            <span class="text-truncate" title="${escapeHtml(file.fullPath)}">${escapeHtml(file.name)}</span>
            ${file.dir ? `<span class="small text-muted fw-normal text-truncate">${escapeHtml(file.dir)}</span>` : ''}
          </div>
          <div class="d-flex align-items-center gap-2">
            ${file.addedCount > 0 ? `<span class="badge bg-success-subtle text-success-emphasis border border-success-subtle">+${file.addedCount} ${escapeHtml(addedWord)}</span>` : ''}
            ${file.removedCount > 0 ? `<span class="badge bg-danger-subtle text-danger-emphasis border border-danger-subtle">−${file.removedCount} ${escapeHtml(removedWord)}</span>` : ''}
          </div>
        </div>
        ${bodyHtml}
      </div>
    `;
  }).join('');
}

/**
 * Переключает режим отображения между наглядным и техническим.
 */
function applyViewMode() {
  const friendlyEl = document.getElementById('diff-friendly-view');
  const rawEl = document.getElementById('diff-raw-wrapper');
  const btnFriendly = document.getElementById('diff-mode-friendly-btn');
  const btnRaw = document.getElementById('diff-mode-raw-btn');

  if (friendlyEl) friendlyEl.classList.toggle('d-none', viewMode !== 'friendly');
  if (rawEl) rawEl.classList.toggle('d-none', viewMode !== 'raw');
  if (btnFriendly) btnFriendly.classList.toggle('active', viewMode === 'friendly');
  if (btnRaw) btnRaw.classList.toggle('active', viewMode === 'raw');
}

/**
 * Отрисовывает панель недавно изменённых документов (panel-diff-stats).
 * @param {Object} result - Ответ API panel-diff-stats
 */
export function renderDiffStatsPanel(result) {
  lastStatsData = result?.data || [];
  const container = document.getElementById('diff-stats-body');
  const countBadge = document.getElementById('diff-stats-count-badge');
  if (!container) return;

  const filesWord = t('ui.diff.docsCountSuffix', 'документов');
  if (countBadge) countBadge.textContent = `${lastStatsData.length} ${filesWord}`;

  if (lastStatsData.length === 0) {
    container.innerHTML = `<div class="small text-muted text-center py-2">${escapeHtml(t('ui.diff.noRecentFiles', 'Недавних изменений документов пока нет.'))}</div>`;
    return;
  }

  const html = `
    <div class="d-flex flex-wrap gap-2">
      ${lastStatsData.map((item) => {
        const { name, dir } = splitFilePath(item.file_path);
        const isSelected = lastDiffMeta.commitHash === item.commit_hash && lastDiffMeta.filePath === item.file_path;
        const msgTip = item.message ? formatCommitMessage(item.message) : '';
        const dateTip = item.timestamp ? formatFriendlyDate(item.timestamp).display : '';
        const titleTip = [item.file_path, dateTip, msgTip].filter(Boolean).join(' • ');
        return `
          <div class="badge bg-body-tertiary text-body border p-2 d-flex align-items-center gap-2 file-diff-chip ${isSelected ? 'is-active' : ''}"
               data-hash="${escapeHtml(item.commit_hash)}"
               data-path="${escapeHtml(item.file_path)}"
               title="${escapeHtml(titleTip)}">
            <i class="bi bi-file-earmark-text text-primary"></i>
            <span class="text-truncate diff-chip-name">${escapeHtml(name)}</span>
            ${dir ? `<span class="text-muted small d-none d-md-inline">(${escapeHtml(dir)})</span>` : ''}
            <span class="text-success small">+${item.insertions || 0}</span>
            <span class="text-danger small">−${item.deletions || 0}</span>
          </div>
        `;
      }).join('')}
    </div>
  `;
  container.innerHTML = html;

  container.querySelectorAll('.file-diff-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const h = chip.getAttribute('data-hash');
      const p = chip.getAttribute('data-path');
      const selectEl = document.getElementById('diff-version-select');
      if (selectEl && h) {
        const optExists = Array.from(selectEl.options).some((o) => o.value === h);
        if (optExists) selectEl.value = h;
      }
      loadDiff(h, p);
      container.querySelectorAll('.file-diff-chip').forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
    });
  });
}

/**
 * Заполняет выпадающий список версий (#diff-version-select) понятными названиями сохранений.
 * @param {string|null} [preferredHash=null] - Хэш версии, которую нужно выбрать сразу
 */
export async function loadVersionSelector(preferredHash = null) {
  const selectEl = document.getElementById('diff-version-select');
  if (!selectEl) return null;

  try {
    const wsId = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : '';
    let url = '/api/v1/panel/panel-commits?limit=40';
    if (wsId) url += `&workspace_id=${encodeURIComponent(wsId)}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();
    availableVersions = payload?.data || [];

    if (availableVersions.length === 0) {
      selectEl.innerHTML = `<option value="">${escapeHtml(t('ui.diff.noVersions', 'Сохранённых версий пока нет'))}</option>`;
      return null;
    }

    selectEl.innerHTML = availableVersions.map((c, idx) => {
      const dateStr = formatFriendlyDate(c.timestamp).display;
      const friendlyMsg = formatCommitMessage(c.message || '');
      const shortMsg = friendlyMsg.length > 52 ? `${friendlyMsg.slice(0, 52)}…` : friendlyMsg;
      const prefix = idx === 0 ? `${t('ui.diff.latestTag', 'Последнее')}: ` : '';
      const label = `${prefix}${dateStr} — ${shortMsg}`;
      return `<option value="${escapeHtml(c.commit_hash)}">${escapeHtml(label)}</option>`;
    }).join('');

    let targetHash = preferredHash;
    if (targetHash && !availableVersions.some((v) => v.commit_hash === targetHash)) {
      const meta = window._selectedCommitMeta;
      const fallbackLabel = meta?.message
        ? `${meta.time || ''} — ${meta.message}`
        : t('ui.diff.selectedVersion', 'Выбранная версия');
      const opt = document.createElement('option');
      opt.value = targetHash;
      opt.textContent = fallbackLabel;
      selectEl.prepend(opt);
    }

    if (!targetHash) {
      targetHash = availableVersions[0].commit_hash;
    }
    selectEl.value = targetHash;
    return targetHash;
  } catch (err) {
    selectEl.innerHTML = `<option value="HEAD">${escapeHtml(t('ui.diff.latestVersion', 'Последнее сохранение'))}</option>`;
    return preferredHash || 'HEAD';
  }
}

/**
 * Возвращает понятный заголовок для выбранной версии.
 * @param {string} commitHash - Идентификатор версии
 * @param {string|null} filePath - Путь к документу
 * @returns {string}
 */
function buildFriendlyHeader(commitHash, filePath) {
  const versionObj = availableVersions.find((v) => v.commit_hash === commitHash);
  const allDocsLabel = t('ui.diff.allDocuments', 'Все документы в сохранении');
  const docPart = filePath ? splitFilePath(filePath).name : allDocsLabel;

  if (versionObj) {
    const dateStr = formatFriendlyDate(versionObj.timestamp).display;
    const msg = formatCommitMessage(versionObj.message || '');
    return `${dateStr} • ${docPart}${msg ? ` — ${msg}` : ''}`;
  }
  if (window._selectedCommitMeta && window._selectedCommitMeta.hash === commitHash) {
    return `${window._selectedCommitMeta.time || ''} • ${docPart} — ${window._selectedCommitMeta.message || ''}`;
  }
  return docPart;
}

/**
 * Загружает и отображает изменения для выбранной версии и документа.
 * @param {string} commitHash - Идентификатор версии
 * @param {string|null} [filePath=null] - Опциональный путь к документу
 */
export async function loadDiff(commitHash, filePath = null) {
  const pre = document.getElementById('diff-code-pre');
  const friendlyEl = document.getElementById('diff-friendly-view');
  const title = document.getElementById('diff-header-title');
  const indicator = document.getElementById('diff-status-indicator');

  if (!commitHash) return;

  lastDiffMeta = { commitHash, filePath, label: buildFriendlyHeader(commitHash, filePath) };

  const loadingText = t('ui.diff.loadingDiff', 'Загрузка изменений...');
  if (friendlyEl) friendlyEl.innerHTML = `<div class="text-center py-4 text-muted small">${escapeHtml(loadingText)}</div>`;
  if (pre) pre.textContent = loadingText;
  if (indicator) indicator.textContent = t('ui.diff.statusLoading', 'Загрузка...');

  try {
    let url = `/api/v1/diff?commit_hash=${encodeURIComponent(commitHash)}`;
    const wsId = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : '';
    if (wsId) url += `&workspace_id=${encodeURIComponent(wsId)}`;
    if (filePath) url += `&file_path=${encodeURIComponent(filePath)}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const diffText = data.diff_text || data.diff || '';
    lastDiffRawText = diffText;

    if (pre) {
      pre.textContent = diffText || t('ui.diff.noChanges', 'В выбранной версии нет текстовых изменений.');
      const rawDir = (typeof window !== 'undefined' && typeof window.detectDocumentDirection === 'function')
        ? window.detectDocumentDirection(diffText, filePath || '')
        : (/[\u0590-\u05FF]/.test(diffText) ? 'rtl' : 'ltr');
      pre.setAttribute('dir', rawDir);
      pre.style.direction = rawDir;
      pre.style.textAlign = rawDir === 'rtl' ? 'right' : 'left';
    }
    renderFriendlyDiffView(diffText);
    if (title) title.textContent = lastDiffMeta.label;
    if (indicator) indicator.textContent = t('ui.diff.statusLoaded', 'Готово');
  } catch (err) {
    const errMsg = `${t('ui.diff.loadError', 'Не удалось загрузить изменения')}: ${err.message}`;
    if (friendlyEl) friendlyEl.innerHTML = `<div class="text-center py-4 text-danger small">${escapeHtml(errMsg)}</div>`;
    if (pre) pre.textContent = errMsg;
    if (indicator) indicator.textContent = t('ui.diff.statusError', 'Ошибка');
  }
}

/**
 * Запрашивает у ИИ объяснение изменений простыми словами.
 * @param {string} commitHash - Идентификатор версии
 * @param {string|null} [filePath=null] - Опциональный путь к документу
 */
export async function loadAIInsights(commitHash, filePath = null) {
  const card = document.getElementById('diff-ai-card');
  const textEl = document.getElementById('diff-ai-summary-text');
  const entitiesBox = document.getElementById('diff-ai-entities-box');

  if (!card || !textEl || !commitHash) return;
  card.classList.remove('d-none');
  textEl.textContent = t('ui.diff.aiAnalyzing', 'ИИ изучает изменения и готовит краткое пояснение...');
  if (entitiesBox) entitiesBox.innerHTML = '';

  try {
    const wsId = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : null;
    const res = await fetch('/api/v1/insights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        commit_hash: commitHash,
        file_path: filePath,
        workspace_id: wsId || null
      })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    textEl.textContent = data.summary || data.explanation || t('ui.diff.aiDone', 'Пояснение сформировано.');
    const entities = data.entities_affected || data.matched_entities || [];
    if (entitiesBox && Array.isArray(entities) && entities.length > 0) {
      entitiesBox.innerHTML = entities.map((e) => {
        const label = typeof e === 'string' ? e : (e.title || e.name || e.id || '');
        return label ? `<span class="badge bg-secondary-subtle text-secondary border">${escapeHtml(label)}</span>` : '';
      }).join('');
    }
  } catch (err) {
    textEl.textContent = `${t('ui.diff.aiError', 'Не удалось получить пояснение ИИ')}: ${err.message}`;
  }
}

/**
 * Активация вкладки сравнения версий: подгружает список версий и выбранное сохранение.
 */
export async function activateDiffPanel() {
  const wsId = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : null;
  loadPanelData('panel-diff-stats', { force: true, workspace_id: wsId });

  const preferredHash = window._selectedCommitHash || null;
  window._selectedCommitHash = null;

  const targetHash = await loadVersionSelector(preferredHash);
  if (targetHash) {
    await loadDiff(targetHash, null);
  }
}

/**
 * Инициализирует панель сравнения версий и привязывает обработчики событий.
 */
export function initDiffStatsPanel() {
  registerPanelRenderer('panel-diff-stats', renderDiffStatsPanel);

  if (!isInitialized) {
    isInitialized = true;

    document.getElementById('diff-version-select')?.addEventListener('change', (e) => {
      const h = e.target.value;
      if (h) loadDiff(h, null);
    });

    document.getElementById('diff-load-btn')?.addEventListener('click', () => {
      const h = document.getElementById('diff-version-select')?.value || 'HEAD';
      loadDiff(h, lastDiffMeta.commitHash === h ? lastDiffMeta.filePath : null);
    });

    document.getElementById('diff-ai-insights-btn')?.addEventListener('click', () => {
      const h = document.getElementById('diff-version-select')?.value || 'HEAD';
      const fp = lastDiffMeta.commitHash === h ? lastDiffMeta.filePath : null;
      loadAIInsights(h, fp);
    });

    document.getElementById('diff-ai-close-btn')?.addEventListener('click', () => {
      document.getElementById('diff-ai-card')?.classList.add('d-none');
    });

    document.getElementById('diff-only-changes-toggle')?.addEventListener('change', (e) => {
      onlyChanges = Boolean(e.target.checked);
      if (lastDiffRawText) renderFriendlyDiffView(lastDiffRawText);
    });

    document.getElementById('diff-mode-friendly-btn')?.addEventListener('click', () => {
      viewMode = 'friendly';
      applyViewMode();
    });

    document.getElementById('diff-mode-raw-btn')?.addEventListener('click', () => {
      viewMode = 'raw';
      applyViewMode();
    });

    const handleContextOrRepoChange = (e) => {
      const pane = document.getElementById('tab-diff') || document.getElementById('diff');
      const isActive = pane && (pane.classList.contains('active') || pane.classList.contains('show'));
      if (!isActive) return;
      loadPanelData('panel-diff-stats', { force: true, repo_path: e.detail?.repoPath, workspace_id: e.detail?.workspaceId });
      loadVersionSelector(null).then((h) => {
        if (h) loadDiff(h, null);
      });
    };

    const handleLanguageChanged = () => {
      if (lastStatsData.length > 0) {
        renderDiffStatsPanel({ data: lastStatsData });
      }
      if (lastDiffRawText) {
        renderFriendlyDiffView(lastDiffRawText);
      }
      const title = document.getElementById('diff-header-title');
      if (title && lastDiffMeta.commitHash) {
        title.textContent = buildFriendlyHeader(lastDiffMeta.commitHash, lastDiffMeta.filePath);
      }
    };

    document.addEventListener('context:changed', handleContextOrRepoChange);
    document.addEventListener('repo:changed', handleContextOrRepoChange);
    document.addEventListener('workspace:changed', handleContextOrRepoChange);
    window.addEventListener('languageChanged', handleLanguageChanged);
    window.addEventListener('localeChanged', handleLanguageChanged);
    window.addEventListener('i18n:languageChanged', handleLanguageChanged);
  }

  applyViewMode();
  activateDiffPanel();
}
