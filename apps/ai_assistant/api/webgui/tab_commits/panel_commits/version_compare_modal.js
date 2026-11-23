/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Side-by-Side Version Compare Modal
 * =============================================================================
 * Description:
 *   Контроллер модального окна двухпанельного сравнения файлов (#versionCompareModal).
 *   При нажатии на строку сохранения в журнале версий (#tab-workspace#panel-commits
 *   или #tab-commits) открывает изменённые файлы с двумя областями рядом:
 *   «Закоммиченная версия» и «Нынешняя (оригинальная) версия».
 *   Если найдено несколько сохранённых версий, спрашивает пользователя,
 *   открыть ли их тоже (не более 10 файлов/версий), либо оставить только
 *   выбранную/последнюю версию рядом с оригинальным файлом.
 *
 * File: version_compare_modal.js
 * Package: apps/ai_assistant/api/webgui/tab_commits/panel_commits
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-19 20:22:30
 * =============================================================================
 */

const MAX_OPEN_FILES = 10;

let modalState = {
  commitHash: '',
  meta: null,
  comparisons: [],
  activeIndex: 0,
  totalChangedFiles: 0,
  includeOtherCommits: false,
  handlersBound: false
};

/**
 * Локализация по ключу с fallback.
 * @param {string} key - Ключ локализации
 * @param {string} [fallback=''] - Значение по умолчанию
 * @returns {string}
 */
function t(key, fallback = '') {
  if (typeof window !== 'undefined') {
    if (window.i18n && typeof window.i18n.t === 'function') {
      const val = window.i18n.t(key, fallback);
      if (val && val !== key) return val;
    }
    if (window.i18next && typeof window.i18next.t === 'function') {
      const val = window.i18next.t(key);
      if (val && val !== key) return val;
    }
  }
  return fallback || key;
}

/**
 * Экранирование HTML-спецсимволов.
 * @param {string} str - Входная строка
 * @returns {string}
 */
function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Извлекает имя файла из относительного пути.
 * @param {string} filePath - Относительный путь файла
 * @returns {string}
 */
function getFileName(filePath) {
  if (!filePath) return '';
  const norm = String(filePath).replace(/\\/g, '/');
  const idx = norm.lastIndexOf('/');
  return idx === -1 ? norm : norm.slice(idx + 1);
}

const HEBREW_CHAR_RE = /[\u0590-\u05FF]/;

function resolveComparisonDirection(item) {
  if (item?.direction === 'rtl') return 'rtl';
  const combined = `${item?.current_content || ''}\n${item?.committed_content || ''}`;
  if (typeof window !== 'undefined' && typeof window.detectDocumentDirection === 'function') {
    return window.detectDocumentDirection(combined, item?.file_path || '');
  }
  if (HEBREW_CHAR_RE.test(combined) || (!combined.trim() && HEBREW_CHAR_RE.test(String(item?.file_path || '')))) {
    return 'rtl';
  }
  return 'ltr';
}

/**
 * Форматирует две текстовые версии для наглядного построчного сравнения рядом.
 * @param {string} leftText - Текст сохранённой (закоммиченной) версии
 * @param {string} rightText - Текст нынешней (оригинальной) версии
 * @returns {{ leftHtml: string, rightHtml: string, diffLinesCount: number }}
 */
function buildSideBySideHtml(leftText, rightText) {
  const leftLines = (leftText || '').split('\n');
  const rightLines = (rightText || '').split('\n');
  const maxLen = Math.max(leftLines.length, rightLines.length);

  let diffLinesCount = 0;
  const leftParts = [];
  const rightParts = [];

  for (let i = 0; i < maxLen; i += 1) {
    const hasLeft = i < leftLines.length;
    const hasRight = i < rightLines.length;
    const lVal = hasLeft ? leftLines[i] : '';
    const rVal = hasRight ? rightLines[i] : '';

    let leftCls = '';
    let rightCls = '';

    if (hasLeft && !hasRight) {
      leftCls = 'is-removed';
      diffLinesCount += 1;
    } else if (!hasLeft && hasRight) {
      rightCls = 'is-added';
      diffLinesCount += 1;
    } else if (lVal !== rVal) {
      leftCls = 'is-removed';
      rightCls = 'is-added';
      diffLinesCount += 1;
    }

    leftParts.push(`
      <div class="vc-line ${leftCls}">
        <span class="vc-line-num">${hasLeft ? i + 1 : ''}</span>
        <span class="vc-line-text" dir="auto">${esc(lVal || ' ')}</span>
      </div>
    `);
    rightParts.push(`
      <div class="vc-line ${rightCls}">
        <span class="vc-line-num">${hasRight ? i + 1 : ''}</span>
        <span class="vc-line-text" dir="auto">${esc(rVal || ' ')}</span>
      </div>
    `);
  }

  return {
    leftHtml: leftParts.join(''),
    rightHtml: rightParts.join(''),
    diffLinesCount
  };
}

/**
 * Отрисовывает активную пару сравнения (две области рядом: Закоммиченная ↔ Нынешняя).
 */
function renderActiveComparison() {
  const container = document.getElementById('vc-compare-panes-container');
  const tabsEl = document.getElementById('vc-files-tabs');
  const tabsBar = document.getElementById('vc-files-tabs-bar');
  const limitBadge = document.getElementById('vc-files-limit-badge');
  if (!container) return;

  const list = modalState.comparisons || [];
  if (list.length === 0) {
    if (tabsBar) tabsBar.classList.add('d-none');
    container.innerHTML = `<div class="text-center py-5 text-muted">${esc(t('ui.commits.compareNoFiles', 'В этом сохранении нет изменённых файлов для просмотра.'))}</div>`;
    return;
  }

  if (tabsBar && tabsEl) {
    tabsBar.classList.remove('d-none');
    tabsEl.innerHTML = list.map((item, idx) => {
      const name = getFileName(item.file_path);
      const isSelected = idx === modalState.activeIndex;
      const versionTag = item.is_selected_commit
        ? ''
        : ` (${(item.committed_timestamp || '').replace('T', ' ').slice(5, 16)})`;
      return `
        <button class="btn btn-sm btn-outline-secondary vc-file-tab-btn d-inline-flex align-items-center gap-1 ${isSelected ? 'active' : ''}"
                data-idx="${idx}" title="${esc(item.file_path)}" type="button">
          <i class="bi bi-file-earmark-text"></i>
          <span>${esc(name + versionTag)}</span>
        </button>
      `;
    }).join('');

    tabsEl.querySelectorAll('.vc-file-tab-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        modalState.activeIndex = Number(btn.getAttribute('data-idx') || 0);
        renderActiveComparison();
      });
    });

    if (limitBadge) {
      const shownLabel = t('ui.commits.compareShownCount', 'Показано');
      const maxNote = t('ui.commits.compareMaxTen', 'макс. 10');
      limitBadge.textContent = `${shownLabel}: ${list.length} (${maxNote})`;
    }
  }

  const currentItem = list[modalState.activeIndex] || list[0];
  const committedTitle = t('ui.commits.paneCommittedTitle', 'Сохранённая версия');
  const currentTitle = t('ui.commits.paneCurrentTitle', 'Нынешняя версия (оригинал)');
  const binaryMsg = t('ui.diff.binaryNotice', 'Документ обновлён (вложения, PDF и изображения не отображаются построчно).');
  const identicalMsg = t('ui.commits.compareIdentical', 'Текст в сохранённой и нынешней версиях совпадает');
  const diffLinesLabel = t('ui.commits.compareDiffLines', 'Различающихся строк');

  const committedDate = currentItem.committed_timestamp
    ? currentItem.committed_timestamp.replace('T', ' ').slice(0, 16)
    : '';

  if (currentItem.is_binary) {
    container.innerHTML = `
      <div class="alert alert-secondary d-flex align-items-center gap-2 mb-0">
        <i class="bi bi-file-earmark-binary fs-4"></i>
        <div>
          <div class="fw-semibold">${esc(currentItem.file_path)}</div>
          <div class="small">${esc(binaryMsg)}</div>
        </div>
      </div>
    `;
    return;
  }

  const { leftHtml, rightHtml, diffLinesCount } = buildSideBySideHtml(
    currentItem.committed_content,
    currentItem.current_content
  );
  const paneDir = resolveComparisonDirection(currentItem);
  const paneAlign = paneDir === 'rtl' ? 'right' : 'left';

  const statusHtml = diffLinesCount === 0
    ? `<span class="badge bg-success-subtle text-success-emphasis border border-success-subtle">${esc(identicalMsg)}</span>`
    : `<span class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle">${esc(diffLinesLabel)}: ${diffLinesCount}</span>`;

  container.innerHTML = `
    <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-2">
      <div class="small text-muted text-truncate" title="${esc(currentItem.file_path)}">
        <i class="bi bi-folder2-open me-1"></i>
        <strong dir="auto">${esc(currentItem.file_path)}</strong>
      </div>
      ${statusHtml}
    </div>
    <div class="row g-3">
      <div class="col-12 col-lg-6">
        <div class="vc-pane-box">
          <div class="vc-pane-header">
            <span class="d-flex align-items-center gap-1">
              <i class="bi bi-clock-history text-warning"></i>
              <span>${esc(committedTitle)}</span>
            </span>
            <span class="small text-muted fw-normal">${esc(committedDate)}</span>
          </div>
          <div class="vc-pane-body" dir="${paneDir}" style="direction: ${paneDir}; text-align: ${paneAlign};" id="vc-pane-left">${leftHtml}</div>
        </div>
      </div>
      <div class="col-12 col-lg-6">
        <div class="vc-pane-box">
          <div class="vc-pane-header">
            <span class="d-flex align-items-center gap-1">
              <i class="bi bi-file-earmark-check text-success"></i>
              <span>${esc(currentTitle)}</span>
            </span>
            <span class="badge bg-success-subtle text-success-emphasis border border-success-subtle">${esc(t('ui.commits.paneCurrentBadge', 'Сейчас'))}</span>
          </div>
          <div class="vc-pane-body" dir="${paneDir}" style="direction: ${paneDir}; text-align: ${paneAlign};" id="vc-pane-right">${rightHtml}</div>
        </div>
      </div>
    </div>
  `;

  // Синхронизированная прокрутка двух областей
  const leftPane = document.getElementById('vc-pane-left');
  const rightPane = document.getElementById('vc-pane-right');
  if (leftPane && rightPane) {
    let syncing = false;
    leftPane.addEventListener('scroll', () => {
      if (syncing) return;
      syncing = true;
      rightPane.scrollTop = leftPane.scrollTop;
      syncing = false;
    });
    rightPane.addEventListener('scroll', () => {
      if (syncing) return;
      syncing = true;
      leftPane.scrollTop = rightPane.scrollTop;
      syncing = false;
    });
  }
}

/**
 * Загружает данные сравнения с бэкенда (/api/v1/commit-compare).
 * @param {string} commitHash - Хэш выбранной версии
 * @param {boolean} [includeOtherCommits=false] - Включать ли другие сохранённые версии (до 10)
 */
async function fetchCompareData(commitHash, includeOtherCommits = false) {
  const container = document.getElementById('vc-compare-panes-container');
  const banner = document.getElementById('vc-multi-commits-banner');
  const bannerText = document.getElementById('vc-multi-commits-text');

  if (container) {
    container.innerHTML = `
      <div class="text-center py-5 text-muted">
        <div class="spinner-border spinner-border-sm text-primary mb-2" role="status"></div>
        <div class="small">${esc(t('ui.diff.loadingDiff', 'Загрузка изменений...'))}</div>
      </div>
    `;
  }

  try {
    const wsId = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : '';
    let url = `/api/v1/commit-compare?commit_hash=${encodeURIComponent(commitHash)}&max_files=${MAX_OPEN_FILES}&include_other_commits=${includeOtherCommits ? 'true' : 'false'}`;
    if (wsId) url += `&workspace_id=${encodeURIComponent(wsId)}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    modalState.comparisons = data.comparisons || [];
    modalState.activeIndex = 0;
    modalState.totalChangedFiles = data.total_changed_files || 0;
    modalState.includeOtherCommits = includeOtherCommits;

    if (banner && bannerText) {
      if (!includeOtherCommits && data.has_multiple_commits && data.other_commits_count > 0) {
        const tmpl = t(
          'ui.commits.multiCommitsQuestion',
          'Найдено ещё {count} сохранённых версий для этих документов. Открыть их тоже для сравнения (не более 10)?'
        );
        bannerText.textContent = tmpl.replace('{count}', String(data.other_commits_count));
        banner.classList.remove('d-none');
      } else {
        banner.classList.add('d-none');
      }
    }

    renderActiveComparison();
  } catch (err) {
    if (container) {
      container.innerHTML = `<div class="alert alert-danger mb-0">${esc(t('ui.diff.loadError', 'Не удалось загрузить изменения'))}: ${esc(err.message)}</div>`;
    }
  }
}

/**
 * Привязывает обработчики кнопок модального окна один раз.
 */
function bindModalHandlers() {
  if (modalState.handlersBound) return;
  modalState.handlersBound = true;

  document.getElementById('vc-btn-open-all-commits')?.addEventListener('click', () => {
    if (modalState.commitHash) {
      fetchCompareData(modalState.commitHash, true);
    }
  });

  document.getElementById('vc-btn-keep-latest-only')?.addEventListener('click', () => {
    document.getElementById('vc-multi-commits-banner')?.classList.add('d-none');
  });

  document.getElementById('vc-btn-open-full-diff')?.addEventListener('click', () => {
    const modalEl = document.getElementById('versionCompareModal');
    if (modalEl && window.bootstrap?.Modal) {
      window.bootstrap.Modal.getOrCreateInstance(modalEl).hide();
    }
    if (modalState.commitHash && typeof window.switchTab === 'function') {
      window._selectedCommitHash = modalState.commitHash;
      window._selectedCommitMeta = modalState.meta;
      window.switchTab('tab-diff');
      if (typeof window.activateDiffTab === 'function') {
        window.activateDiffTab();
      }
    }
  });
}

/**
 * Открывает модальное окно двухпанельного сравнения для выбранной строки коммита.
 * @param {string} commitHash - Хэш выбранного сохранения
 * @param {Object} [meta={}] - Метаданные события ({ message, author, time })
 */
export function openCommitCompareModal(commitHash, meta = {}) {
  const modalEl = document.getElementById('versionCompareModal');
  if (!modalEl || !commitHash) return;

  bindModalHandlers();
  modalState.commitHash = commitHash;
  modalState.meta = { hash: commitHash, ...meta };

  const subtitleEl = document.getElementById('vc-modal-subtitle');
  if (subtitleEl) {
    const parts = [meta.time, meta.author, meta.message].filter(Boolean);
    subtitleEl.textContent = parts.join(' • ');
  }

  document.getElementById('vc-multi-commits-banner')?.classList.add('d-none');

  if (window.bootstrap?.Modal) {
    window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
  }

  fetchCompareData(commitHash, false);
}
