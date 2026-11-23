/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Version History Panel (panel_commits)
 * =============================================================================
 * Description:
 *   Изолированная панель журнала версий и событий хранилища (panel-commits).
 *   Отображает хронологию изменений документов на понятном пользователю языке
 *   (без Git-терминологии), с фильтрацией по категориям, поиском и переходом
 *   к наглядному сравнению версий (#tab-diff).
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_commits/panel_commits
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-19 18:45:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';
import { openCommitCompareModal } from './version_compare_modal.js';

let allCommits = [];
let activeFilter = 'all';
let searchQuery = '';
let isInitialized = false;

/**
 * Безопасное экранирование HTML-спецсимволов.
 * @param {string} str - Исходная строка
 * @returns {string}
 */
export function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Локализация по ключу с fallback.
 * @param {string} key - Ключ локализации
 * @param {string} [fallback=''] - Значение по умолчанию
 * @returns {string}
 */
export function t(key, fallback = '') {
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
 * Определяет текущий активный язык интерфейса.
 * @returns {string}
 */
export function getActiveLang() {
  if (typeof window !== 'undefined') {
    return (
      window.i18n?.lang ||
      (typeof window.getCurrentLang === 'function' && window.getCurrentLang()) ||
      localStorage.getItem('app_language') ||
      'ru'
    );
  }
  return 'ru';
}

/**
 * Классифицирует системное сообщение коммита в понятную категорию и бейдж.
 * @param {string} rawMsg - Исходное сообщение коммита
 * @returns {{ category: string, badgeKey: string, icon: string, badgeClass: string }}
 */
export function classifyEvent(rawMsg) {
  const m = (rawMsg || '').toLowerCase();

  if (m.includes('добавлен факт из чата') || m.includes('obsidian sync') || m.includes('chat fact') || m.includes('עובדה מהצ')) {
    return {
      category: 'notes',
      badgeKey: 'ui.commits.typeNote',
      icon: 'bi-chat-left-text',
      badgeClass: 'bg-info-subtle text-info-emphasis border border-info-subtle'
    };
  }
  if (m.startsWith('удален') || m.includes('watchdog: удаление') || m.startsWith('deleted') || m.startsWith('видалено') || m.includes('נמחק')) {
    return {
      category: 'docs',
      badgeKey: 'ui.commits.typeDeleted',
      icon: 'bi-trash3',
      badgeClass: 'bg-danger-subtle text-danger-emphasis border border-danger-subtle'
    };
  }
  if (m.startsWith('создан') || m.startsWith('created') || m.startsWith('створено') || m.includes('נוצר')) {
    return {
      category: 'docs',
      badgeKey: 'ui.commits.typeCreated',
      icon: 'bi-file-earmark-plus',
      badgeClass: 'bg-success-subtle text-success-emphasis border border-success-subtle'
    };
  }
  if (m.startsWith('переименован') || m.startsWith('перемещение') || m.startsWith('renamed') || m.startsWith('перейменовано') || m.includes('שונה שם')) {
    return {
      category: 'docs',
      badgeKey: 'ui.commits.typeMoved',
      icon: 'bi-arrow-left-right',
      badgeClass: 'bg-warning-subtle text-warning-emphasis border border-warning-subtle'
    };
  }
  if (
    m.startsWith('watchdog:') ||
    m.startsWith('авто-сканирование') ||
    m.startsWith('индексация') ||
    m.startsWith('синхронизация') ||
    m.startsWith('auto-scan') ||
    m.startsWith('index linked') ||
    m.startsWith('sync source')
  ) {
    return {
      category: 'auto',
      badgeKey: 'ui.commits.typeAuto',
      icon: 'bi-cpu',
      badgeClass: 'bg-primary-subtle text-primary-emphasis border border-primary-subtle'
    };
  }
  if (m.startsWith('git:') || m.includes('.gitignore')) {
    return {
      category: 'auto',
      badgeKey: 'ui.commits.typeSystem',
      icon: 'bi-gear',
      badgeClass: 'bg-secondary-subtle text-secondary-emphasis border border-secondary-subtle'
    };
  }
  return {
    category: 'docs',
    badgeKey: 'ui.commits.typeUpdated',
    icon: 'bi-pencil-square',
    badgeClass: 'bg-primary-subtle text-primary-emphasis border border-primary-subtle'
  };
}

/**
 * Преобразует технические сообщения Git в дружелюбный текст на активном языке.
 * @param {string} msg - Исходный текст сообщения коммита
 * @returns {string}
 */
export function formatCommitMessage(msg) {
  if (!msg) return '';
  const lang = getActiveLang();

  const translations = {
    ru: [
      [/^Git: начальная конфигурация \.gitignore и README\.md$/i, 'Начальная настройка хранилища'],
      [/^Git: исключение (директории|каталога) assets из репозитория$/i, 'Настройка исключений хранилища (папка вложений)'],
      [/^Git: добавление README\.md рабочего пространства$/i, 'Добавлено описание рабочего пространства'],
      [/^Watchdog: удаление (.+)$/i, 'Автосохранение — удалён документ: $1'],
      [/^Watchdog: изменение (.+)$/i, 'Автосохранение — изменён документ: $1'],
      [/^Watchdog: транскрибация и обновление (.+)$/i, 'Авторасшифровка аудио/видео и обновление: $1'],
      [/^Watchdog: транскрибация внешнего медиа (.+)$/i, 'Авторасшифровка медиафайла: $1'],
      [/^Watchdog: изменения в (.+)$/i, 'Автосохранение изменений: $1'],
      [/^Obsidian sync факта из чата: (.+)$/i, 'Сохранена заметка из чата: $1'],
      [/^Добавлен факт из чата: (.+)$/i, 'Заметка из чата: $1'],
      [/^Индексация связанного файла (.+)$/i, 'Индексация документа для поиска: $1'],
      [/^Синхронизация источника \((.+?)\): (.+)$/i, 'Синхронизация документа ($1): $2'],
      [/^Перемещение источника без изменений \((.+?)\): (.+) -> (.+)$/i, 'Перемещение документа ($1): $2 → $3'],
      [/^Авто-сканирование (.+)$/i, 'Автоматическая проверка папки: $1'],
    ],
    he: [
      [/^Git: начальная конфигурация \.gitignore и README\.md$/i, 'הגדרה ראשונית של מאגר המסמכים'],
      [/^Git: исключение (директории|каталога) assets из репозитория$/i, 'הגדרת החרגת תיקיית קבצים מצורפים'],
      [/^Git: добавление README\.md рабочего пространства$/i, 'הוספת תיאור סביבת העבודה'],
      [/^Индексация связанного файла (.+)$/i, 'הוספת מסמך לחיפוש החכם: $1'],
      [/^Обновление документа (.+)$/i, 'עדכון מסמך: $1'],
      [/^Синхронизация источника \((.+?)\): (.+)$/i, 'סנכרון מסמך ($1): $2'],
      [/^Перемещение источника без изменений \((.+?)\): (.+) -> (.+)$/i, 'העברת מסמך ($1): $2 ← $3'],
      [/^Авто-сканирование (.+)$/i, 'סריקה אוטומטית: $1'],
      [/^Создан файл: (.+)$/i, 'נוצר מסמך: $1'],
      [/^Создана папка: (.+)$/i, 'נוצרה תיקייה: $1'],
      [/^Удален файл: (.+)$/i, 'נמחק מסמך: $1'],
      [/^Удален каталог: (.+)$/i, 'נמחקה תיקייה: $1'],
      [/^Обновлен: (.+)$/i, 'עודכן: $1'],
      [/^Переименован: (.+) -> (.+)$/i, 'שונה שם: $1 ← $2'],
      [/^Скопирован: (.+) -> (.+)$/i, 'הועתק: $1 ← $2'],
      [/^Watchdog: удаление (.+)$/i, 'שמירה אוטומטית — נמחק: $1'],
      [/^Watchdog: изменение (.+)$/i, 'שמירה אוטומטית — עודכן: $1'],
      [/^Watchdog: транскрибация и обновление (.+)$/i, 'תמלול ועדכון אוטומטי: $1'],
      [/^Watchdog: транскрибация внешнего медиа (.+)$/i, 'תמלול קובץ מדיה: $1'],
      [/^Watchdog: изменения в (.+)$/i, 'שמירה אוטומטית של שינויים: $1'],
      [/^Добавлен факт из чата: (.+)$/i, "הערה מהצ'אט: $1"],
      [/^Obsidian sync факта из чата: (.+)$/i, "נשמרה הערה מהצ'אט: $1"],
    ],
    en: [
      [/^Git: начальная конфигурация \.gitignore и README\.md$/i, 'Initial vault setup'],
      [/^Git: исключение (директории|каталога) assets из репозитория$/i, 'Vault settings: exclude attachments folder'],
      [/^Git: добавление README\.md рабочего пространства$/i, 'Added workspace description'],
      [/^Индексация связанного файла (.+)$/i, 'Indexed document for search: $1'],
      [/^Обновление документа (.+)$/i, 'Updated document: $1'],
      [/^Синхронизация источника \((.+?)\): (.+)$/i, 'Synced document ($1): $2'],
      [/^Перемещение источника без изменений \((.+?)\): (.+) -> (.+)$/i, 'Moved document ($1): $2 → $3'],
      [/^Авто-сканирование (.+)$/i, 'Automatic folder scan: $1'],
      [/^Создан файл: (.+)$/i, 'Created document: $1'],
      [/^Создана папка: (.+)$/i, 'Created folder: $1'],
      [/^Удален файл: (.+)$/i, 'Deleted document: $1'],
      [/^Удален каталог: (.+)$/i, 'Deleted folder: $1'],
      [/^Обновлен: (.+)$/i, 'Updated: $1'],
      [/^Переименован: (.+) -> (.+)$/i, 'Renamed: $1 → $2'],
      [/^Скопирован: (.+) -> (.+)$/i, 'Copied: $1 → $2'],
      [/^Watchdog: удаление (.+)$/i, 'Auto-save — deleted: $1'],
      [/^Watchdog: изменение (.+)$/i, 'Auto-save — updated: $1'],
      [/^Watchdog: транскрибация и обновление (.+)$/i, 'Auto-transcribed & updated: $1'],
      [/^Watchdog: транскрибация внешнего медиа (.+)$/i, 'Auto-transcribed media: $1'],
      [/^Watchdog: изменения в (.+)$/i, 'Auto-saved changes: $1'],
      [/^Добавлен факт из чата: (.+)$/i, 'Note from chat: $1'],
      [/^Obsidian sync факта из чата: (.+)$/i, 'Saved note from chat: $1'],
    ],
    uk: [
      [/^Git: начальная конфигурация \.gitignore и README\.md$/i, 'Початкове налаштування сховища'],
      [/^Git: исключение (директории|каталога) assets из репозитория$/i, 'Налаштування виключень сховища (папка вкладень)'],
      [/^Git: добавление README\.md рабочего пространства$/i, 'Додано опис робочого простору'],
      [/^Индексация связанного файла (.+)$/i, 'Індексація документа для пошуку: $1'],
      [/^Обновление документа (.+)$/i, 'Оновлення документа: $1'],
      [/^Синхронизация источника \((.+?)\): (.+)$/i, 'Синхронізація документа ($1): $2'],
      [/^Перемещение источника без изменений \((.+?)\): (.+) -> (.+)$/i, 'Переміщення документа ($1): $2 → $3'],
      [/^Авто-сканирование (.+)$/i, 'Автоматична перевірка папки: $1'],
      [/^Создан файл: (.+)$/i, 'Створено документ: $1'],
      [/^Создана папка: (.+)$/i, 'Створено папку: $1'],
      [/^Удален файл: (.+)$/i, 'Видалено документ: $1'],
      [/^Удален каталог: (.+)$/i, 'Видалено папку: $1'],
      [/^Обновлен: (.+)$/i, 'Оновлено: $1'],
      [/^Переименован: (.+) -> (.+)$/i, 'Перейменовано: $1 → $2'],
      [/^Скопирован: (.+) -> (.+)$/i, 'Скопійовано: $1 → $2'],
      [/^Watchdog: удаление (.+)$/i, 'Автозбереження — видалено: $1'],
      [/^Watchdog: изменение (.+)$/i, 'Автозбереження — змінено: $1'],
      [/^Watchdog: транскрибация и обновление (.+)$/i, 'Авторозшифрування та оновлення: $1'],
      [/^Watchdog: транскрибация внешнего медиа (.+)$/i, 'Авторозшифрування медіафайлу: $1'],
      [/^Watchdog: изменения в (.+)$/i, 'Автозбереження змін: $1'],
      [/^Добавлен факт из чата: (.+)$/i, 'Нотатка з чату: $1'],
      [/^Obsidian sync факта из чата: (.+)$/i, 'Збережено нотатку з чату: $1'],
    ]
  };

  const rules = translations[lang] || translations.ru;
  for (const [pattern, replacement] of rules) {
    if (pattern.test(msg)) {
      return msg.replace(pattern, replacement);
    }
  }
  return msg;
}

/**
 * Форматирует ISO-дату в понятный человеку вид («Сегодня, 14:25», «Вчера, 18:10», «12.11.2026, 09:40»).
 * @param {string} isoStr - Строка даты ISO 8601
 * @returns {{ display: string, full: string }}
 */
export function formatFriendlyDate(isoStr) {
  if (!isoStr) return { display: '—', full: '' };
  const parsed = new Date(isoStr);
  if (Number.isNaN(parsed.getTime())) {
    const clean = isoStr.replace('T', ' ').slice(0, 16);
    return { display: clean, full: isoStr };
  }

  const lang = getActiveLang();
  const localeMap = { ru: 'ru-RU', en: 'en-US', he: 'he-IL', uk: 'uk-UA' };
  const locale = localeMap[lang] || 'ru-RU';

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart.getTime() - 86400000);
  const itemDayStart = new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());

  const timeStr = parsed.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
  const fullStr = parsed.toLocaleString(locale, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });

  if (itemDayStart.getTime() === todayStart.getTime()) {
    return { display: `${t('ui.commits.today', 'Сегодня')}, ${timeStr}`, full: fullStr };
  }
  if (itemDayStart.getTime() === yesterdayStart.getTime()) {
    return { display: `${t('ui.commits.yesterday', 'Вчера')}, ${timeStr}`, full: fullStr };
  }
  const datePart = parsed.toLocaleDateString(locale, { day: '2-digit', month: 'short', year: 'numeric' });
  return { display: `${datePart}, ${timeStr}`, full: fullStr };
}

/**
 * Применяет текущие фильтры (категория + текстовый поиск) к списку событий.
 * @param {Array<Object>} commits - Полный список событий
 * @returns {Array<Object>}
 */
function applyFilters(commits) {
  return (commits || []).filter((c) => {
    if (activeFilter !== 'all') {
      const info = classifyEvent(c.message);
      if (info.category !== activeFilter) return false;
    }
    if (searchQuery) {
      const q = searchQuery;
      const friendlyMsg = formatCommitMessage(c.message || '').toLowerCase();
      const rawMsg = (c.message || '').toLowerCase();
      const author = (c.author || '').toLowerCase();
      const hash = (c.commit_hash || '').toLowerCase();
      if (!friendlyMsg.includes(q) && !rawMsg.includes(q) && !author.includes(q) && !hash.includes(q)) {
        return false;
      }
    }
    return true;
  });
}

/**
 * Отрисовывает дружелюбную таблицу журнала версий в #tab-commits и #subpane-ws-commits.
 * @param {Array<Object>} commits - Список событий сохранения
 * @param {HTMLElement} [targetRoot=null] - Опциональный родительский контейнер
 */
export function renderCommitsTable(commits, targetRoot = null) {
  const roots = targetRoot
    ? [targetRoot]
    : Array.from(document.querySelectorAll('#tab-commits, #subpane-ws-commits'));
  if (roots.length === 0) {
    roots.push(document);
  }

  const count = commits ? commits.length : 0;
  const suffix = t('ui.commits.commitsCountSuffix', t('workspace.commitsCountSuffix', 'событий'));
  const emptyText = t('ui.commits.notFound', t('workspace.commitsNotFound', 'Записей в журнале пока нет'));
  const unknownAuthor = t('ui.commits.authorUnknown', t('workspace.authorUnknown', 'Система'));
  const diffLabel = t('ui.commits.diffBtn', 'Что изменилось');

  roots.forEach((root) => {
    const tbody = root.querySelector('#commits-table-body');
    const countBadge = root.querySelector('#commits-count-badge');
    if (!tbody) return;

    if (countBadge) {
      countBadge.textContent = `${count} ${suffix}`;
    }

    if (!commits || commits.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-muted">${escapeHtml(emptyText)}</td></tr>`;
      return;
    }

    tbody.innerHTML = commits.map((c) => {
      const fullHash = c.commit_hash || '';
      const shortHash = c.short_hash || (fullHash ? fullHash.slice(0, 7) : '');
      const dateObj = formatFriendlyDate(c.timestamp);
      const author = c.author || unknownAuthor;
      const rawMsg = c.message || '';
      const friendlyMsg = formatCommitMessage(rawMsg);
      const ev = classifyEvent(rawMsg);
      const evLabel = t(ev.badgeKey, 'Обновление');
      const tooltipMeta = shortHash ? `${dateObj.full} (${shortHash})` : dateObj.full;

      return `
        <tr class="commit-row-clickable"
            data-hash="${escapeHtml(fullHash)}"
            data-msg="${escapeHtml(friendlyMsg)}"
            data-author="${escapeHtml(author)}"
            data-time="${escapeHtml(dateObj.display)}">
          <td>
            <span class="badge ${ev.badgeClass} d-inline-flex align-items-center gap-1" title="${escapeHtml(tooltipMeta)}">
              <i class="bi ${ev.icon}"></i>
              <span>${escapeHtml(evLabel)}</span>
            </span>
          </td>
          <td class="text-muted small text-nowrap" title="${escapeHtml(tooltipMeta)}">${escapeHtml(dateObj.display)}</td>
          <td><span class="fw-medium">${escapeHtml(author)}</span></td>
          <td class="text-truncate commits-msg-cell" title="${escapeHtml(friendlyMsg)}">${escapeHtml(friendlyMsg)}</td>
          <td class="text-end">
            <button class="btn btn-outline-primary btn-sm py-0 px-2 d-inline-flex align-items-center gap-1 commit-diff-btn"
              data-hash="${escapeHtml(fullHash)}"
              data-msg="${escapeHtml(friendlyMsg)}"
              data-author="${escapeHtml(author)}"
              data-time="${escapeHtml(dateObj.display)}"
              type="button">
              <i class="bi bi-layout-split"></i>
              <span>${escapeHtml(diffLabel)}</span>
            </button>
          </td>
        </tr>
      `;
    }).join('');

    const handleOpenCompare = (el) => {
      const h = el.getAttribute('data-hash');
      if (!h) return;
      openCommitCompareModal(h, {
        message: el.getAttribute('data-msg') || '',
        author: el.getAttribute('data-author') || '',
        time: el.getAttribute('data-time') || ''
      });
    };

    tbody.querySelectorAll('tr.commit-row-clickable').forEach((row) => {
      row.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        handleOpenCompare(row);
      });
    });

    tbody.querySelectorAll('.commit-diff-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        handleOpenCompare(e.currentTarget);
      });
    });
  });
}

/**
 * Обработчик рендера панели panel-commits.
 * @param {Object} result - Ответ REST API
 * @param {HTMLElement} [panelEl=null] - Элемент карточки панели
 */
export function renderCommitsPanel(result, panelEl = null) {
  allCommits = result?.data || [];
  renderCommitsTable(applyFilters(allCommits), panelEl);
}

/**
 * Активация панели: загрузка свежих данных журнала версий.
 */
export function activateCommitsPanel() {
  const wsId = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : null;
  loadPanelData('panel-commits', { force: true, workspace_id: wsId });
}

/**
 * Инициализирует панель журнала версий и привязывает обработчики событий.
 */
export function initCommitsPanel() {
  registerPanelRenderer('panel-commits', renderCommitsPanel);

  if (!isInitialized) {
    isInitialized = true;

    document.getElementById('commits-refresh-btn')?.addEventListener('click', () => {
      const wsId = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : null;
      loadPanelData('panel-commits', { force: true, workspace_id: wsId });
    });

    document.getElementById('commits-search-input')?.addEventListener('input', (e) => {
      searchQuery = (e.target.value || '').toLowerCase().trim();
      renderCommitsTable(applyFilters(allCommits));
    });

    document.getElementById('commits-filter-bar')?.addEventListener('click', (e) => {
      const btn = e.target.closest('.commits-filter-pill');
      if (!btn) return;
      activeFilter = btn.getAttribute('data-filter') || 'all';
      document.querySelectorAll('#commits-filter-bar .commits-filter-pill').forEach((b) => {
        b.classList.toggle('active', b === btn);
      });
      renderCommitsTable(applyFilters(allCommits));
    });

    const handleContextOrRepoChange = (e) => {
      const pane = document.getElementById('tab-commits') || document.getElementById('commits');
      const isActive = pane && (pane.classList.contains('active') || pane.classList.contains('show'));
      if (!isActive) return;
      loadPanelData('panel-commits', {
        force: true,
        repo_path: e.detail?.repoPath,
        workspace_id: e.detail?.workspaceId
      });
    };

    const handleLanguageChanged = () => {
      renderCommitsTable(applyFilters(allCommits));
    };

    document.addEventListener('context:changed', handleContextOrRepoChange);
    document.addEventListener('repo:changed', handleContextOrRepoChange);
    document.addEventListener('workspace:changed', handleContextOrRepoChange);
    window.addEventListener('languageChanged', handleLanguageChanged);
    window.addEventListener('localeChanged', handleLanguageChanged);
    window.addEventListener('i18n:languageChanged', handleLanguageChanged);
  }

  const wsId = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : null;
  loadPanelData('panel-commits', { force: true, workspace_id: wsId });
}
