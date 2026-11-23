/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Main Orchestrator Script
 * =============================================================================
 * Description:
 *   Главный клиентский скрипт-оркестратор веб-интерфейса AI Assistant
 *   (Умное версионирование и верификация).
 *   Обеспечивает переключение вкладок, управление темами (светлая/тёмная/кирпичная/терминал),
 *   многоязычность i18n, кеширование и связь с 2-step верификацией.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Updated: 2026-11-20 02:16:00
 * =============================================================================
 */

import { initI18n, switchLang, applyTranslations } from './i18n.js';
import { initTheme } from './theme.js';
import { initUserSettings } from './userSettings.js?v=20261120_v1';
import { initCacheUI } from './cache-ui.js';
import { switchTab, loadTab, setupTabClicks } from './tab-core.js?v=20261120_v1';
import { initTopWorkspaceDropdown, updateTopWorkspaceDropdown, areWorkspacesEqual } from './top_workspace_dropdown.js?v=20261116_v2';
import { initCustomContextMenu } from './context-menu.js';
import {
  initDrawerWorkspaces,
  fetchAndRenderDrawerWorkspaces,
  highlightActiveDrawerWorkspace,
  switchToWorkspace,
  findWorkspaceMatch,
} from './drawer_workspaces.js?v=20261120_v1';
import { initIdeNavigation } from './ide_navigation.js?v=20261120_v1';
import { initIdeFileExplorer } from './ide_file_explorer.js?v=20261119_v3';
import { initModelTester, sendModelPing } from './model-tester.js';
import './api-cache.js';

// Глобальный экспорт для вызова из разметки и дочерних вкладок
window.switchTab = switchTab;
window.switchToTab = switchTab;
window.applyTranslations = applyTranslations;
window.switchLang = switchLang;
window.switchLocale = switchLang;
window.sendModelPing = sendModelPing;

// Карта соответствия вкладок: id -> [htmlUrl, jsUrl]
const TABS = {
  'workspace':        ['/html/tab_workspace/index.html?v=20261119_v2', '/html/tab_workspace/main.js?v=20261119_v10'],
  'create-workspace': ['/html/tab_create_workspace/index.html?v=20261120_v1', '/html/tab_create_workspace/main.js?v=20261120_v1'],
  'timeline':         ['/html/tab_timeline/index.html',         '/html/tab_timeline/main.js'],
  'commits':          ['/html/tab_commits/index.html?v=20261119_v2', '/html/tab_commits/main.js?v=20261119_v3'],
  'diff':             ['/html/tab_diff/index.html?v=20261119_v1',    '/html/tab_diff/main.js?v=20261119_v2'],
  'graph':            ['/html/tab_graph/index.html',            '/html/tab_graph/main.js'],
  'rag':              ['/html/tab_rag/index.html',              '/html/tab_rag/main.js'],
  'verification':     ['/html/tab_verification/index.html',     '/html/tab_verification/main.js'],
  'theme-editor':     ['/html/tab_theme_editor/index.html?v=20261119_v1',     '/html/tab_theme_editor/main.js?v=20261119_v1'],
  'models':           ['/html/tab_models/index.html?v=20261120_v1',           '/html/tab_models/main.js?v=20261120_v1'],
  'git-maintenance':  ['/html/tab_git_maintenance/index.html',  '/html/tab_git_maintenance/main.js'],
  'gmail':            ['/html/tab_gmail/index.html',            '/html/tab_gmail/main.js'],
  'outlook':          ['/html/tab_outlook/index.html',          '/html/tab_outlook/main.js'],
  'calendar':         ['/html/tab_calendar/index.html?v=20261119_v2', '/html/tab_calendar/main.js?v=20261119_v2'],
  'drive':            ['/html/tab_drive/index.html',            '/html/tab_drive/main.js'],
  'contacts':         ['/html/tab_contacts/index.html',         '/html/tab_contacts/main.js'],
  'plugins':          ['/html/tab_plugins/index.html',          '/html/tab_plugins/main.js'],
  'file-editor':      ['/html/tab_file_editor/index.html?v=20261119_v1',      '/html/tab_file_editor/main.js?v=20261119_v2'],
  'file-tree':        ['/html/tab_file_tree/index.html',        '/html/tab_file_tree/main.js'],
  'obsidian':         ['/html/tab_obsidian/index.html',         '/html/tab_obsidian/main.js'],
  'doc-categorizer':  ['/html/tab_doc_categorizer/index.html',  '/html/tab_doc_categorizer/main.js'],
  'chat':             ['/html/tab_chat/index.html?v=20261119_v5', '/html/tab_chat/main.js?v=20261119_v5'],
  'tasks':            ['/html/tab_tasks/index.html',            '/html/tab_tasks/main.js'],
  'instruments':      ['/html/tab_instruments/index.html?v=20261119_v1',      '/html/tab_instruments/main.js?v=20261119_v1'],
  'commands':         ['/html/tab_commands/index.html',         '/html/tab_commands/main.js'],
  'wikillm':          ['/html/tab_wikillm/index.html',          '/html/tab_wikillm/main.js'],
  'tooltips':         ['/html/tab_tooltips/index.html',         '/html/tab_tooltips/main.js'],
};

const loaded = new Set();

async function lazyLoad(tabName) {
  if (loaded.has(tabName) || !TABS[tabName]) return;
  loaded.add(tabName);
  const v = Date.now();
  const [html, js] = TABS[tabName];
  const withBust = (url) => `${url}${url.includes('?') ? '&' : '?'}t=${v}`;
  try {
    await loadTab(tabName, withBust(html), withBust(js));
    applyTranslations();
  } catch (err) {
    loaded.delete(tabName);
    throw err;
  }
}

let saveStateDebounceTimer = null;

/**
 * Сохраняет последнюю активную вкладку, URL и рабочее пространство в localStorage и config.json.
 * @param {string} tabId 
 * @param {string|null} [urlHash=null] 
 * @param {string|null} [workspaceId=null] 
 */
export function saveActiveState(tabId, urlHash = null, workspaceId = null) {
  if (!tabId) return;
  const cleanTab = tabId.startsWith('tab-') ? tabId : `tab-${tabId}`;
  const effectiveHash = urlHash !== null ? urlHash : (typeof location !== 'undefined' ? location.hash : '');
  const effectiveWs = workspaceId || (typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : null);

  try {
    localStorage.setItem('ai_assistant_last_tab', cleanTab);
    if (effectiveHash) {
      localStorage.setItem('ai_assistant_last_hash', effectiveHash);
    }
    if (effectiveWs) {
      localStorage.setItem('ai_assistant_active_workspace', effectiveWs);
    }
  } catch (_) {}

  clearTimeout(saveStateDebounceTimer);
  saveStateDebounceTimer = setTimeout(() => {
    try {
      fetch('/api/v1/workspaces/active-tab', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tab_id: cleanTab,
          url_hash: effectiveHash || `#${cleanTab}`,
          workspace_id: effectiveWs,
        }),
      }).catch(() => {});
    } catch (_) {}
  }, 300);
}
window.saveActiveState = saveActiveState;

export async function switchMainTab(tabId) {
  if (!tabId) return;

  const rawName = tabId.startsWith('tab-') ? tabId.slice(4) : tabId;
  const normId = tabId.startsWith('tab-') ? tabId : `tab-${tabId}`;

  // Мгновенное переключение активного класса
  switchTab(normId);

  // Lazy-load ресурсов вкладки при первом открытии
  if (!loaded.has(rawName) && TABS[rawName]) {
    await lazyLoad(rawName).catch(err => console.warn(`[Main] Ошибка lazyLoad для ${rawName}:`, err));
  }

  // Фиксируем последнюю открытую вкладку в конфигурации
  saveActiveState(normId);
}
window.switchTab = switchMainTab;
window.switchToTab = switchMainTab;
window.switchMainTab = switchMainTab;

// Обработка 2-Step аннотации факта
function setupAnnotationModal() {
  const submitBtn = document.getElementById('btn-submit-annotation');
  if (!submitBtn) return;

  submitBtn.addEventListener('click', async () => {
    const src = document.getElementById('modal-source-id')?.value.trim();
    const tgt = document.getElementById('modal-target-id')?.value.trim();
    const rel = document.getElementById('modal-relation-type')?.value;
    const desc = document.getElementById('modal-summary-desc')?.value.trim();
    const statusBox = document.getElementById('modal-validation-preview');

    if (!src || !tgt) {
      alert('Заполните Источник (Source ID) и Цель (Target ID)');
      return;
    }

    if (statusBox) {
      statusBox.innerHTML = '<div class="spinner-border spinner-border-sm text-primary me-2"></div> Валидация контуром безопасности...';
    }

    try {
      const res = await fetch('/api/v1/annotate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_id: src,
          target_id: tgt,
          relation_type: rel,
          summary: desc,
          confidence: 1.0,
          provenance: 'user_webgui'
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const result = await res.json();
      if (statusBox) {
        statusBox.innerHTML = `<span class="text-success fw-semibold">✅ Успешно верифицировано и сохранено в темпоральный граф!</span>`;
      }

      setTimeout(() => {
        const modalEl = document.getElementById('annotateModal');
        if (modalEl && window.bootstrap) {
          const m = bootstrap.Modal.getInstance(modalEl);
          if (m) m.hide();
        }
        if (typeof window.loadPanelData === 'function') {
          window.loadPanelData('panel-knowledge-links', { force: true });
        }
      }, 900);
    } catch (err) {
      if (statusBox) {
        statusBox.innerHTML = `<span class="text-danger fw-semibold">❌ Отклонено верификатором: ${err.message}</span>`;
      }
    }
  });
}

async function initTopGmailBadge() {
  try {
    const res = await fetch('/api/v1/gmail/labels');
    if (!res.ok) return;
    const data = await res.json();
    const inbox = (data.labels || []).find(l => l.id === 'INBOX');
    const topBadge = document.getElementById('top-nav-gmail-badge');
    if (topBadge && inbox) {
      const count = inbox.messages_unread || 0;
      topBadge.textContent = count;
      if (count > 0) topBadge.classList.remove('d-none');
    }
  } catch (_) {}
}

// Вспомогательный канонический парсер URL стандарта workspace-url-routing
export function parseWorkspaceUrlComponents(rawHash) {
  const clean = (rawHash || '').replace(/^#/, '');
  const parts = clean.split('#').filter(Boolean);
  const tabId = parts[0] || 'tab-workspace';
  let panelId = null;
  let blockId = null;
  let wsId = null;

  for (let i = 1; i < parts.length; i++) {
    const part = parts[i];
    if (part.startsWith('workspace=')) {
      try {
        wsId = decodeURIComponent(part.slice(10));
      } catch (_) {
        wsId = part.slice(10);
      }
    } else if (part.startsWith('panel-') || part.startsWith('step')) {
      panelId = part;
    } else if (part.startsWith('block-')) {
      blockId = part;
    } else if (!wsId && !part.includes('=')) {
      try {
        wsId = decodeURIComponent(part);
      } catch (_) {
        wsId = part;
      }
    }
  }

  return {
    tabId,
    panelId: panelId || (tabId === 'tab-workspace' ? 'panel-files' : null),
    blockId: blockId ? blockId.replace(/^block-/, '') : null,
    workspaceId: wsId ? wsId.trim().normalize('NFC') : null,
  };
}

async function init() {
  // Защита от повторного запуска оркестратора
  if (window.__aiAssistantMainInitStarted) return;
  window.__aiAssistantMainInitStarted = true;

  // 1. Инициализация темы (light, dark, brick, terminal, system) и мгновенная привязка навигации
  initTheme();
  setupTabClicks();
  initCacheUI();
  setupAnnotationModal();

  // 1.1 Мгновенное переключение на активную вкладку из URL для устранения задержки рендера (Fast First Paint)
  const initialHash = (typeof location !== 'undefined' ? location.hash : '') || '';
  const preParsed = parseWorkspaceUrlComponents(initialHash);
  if (preParsed.tabId && preParsed.tabId !== 'tab-chat') {
    switchTab(preParsed.tabId);
  }

  // 2. Инициализация i18n с авто-определением языка и URL параметров (?lang=ru, ?locale=ru-RU)
  await initI18n();

  // 3. Настройки пользователя (неблокирующий запуск, чтобы сетевые задержки /api/v1/auth/check не тормозили интерфейс)
  initUserSettings().catch((err) => {
    console.warn('[Main] Ошибка фоновой инициализации userSettings:', err);
  });

  // 5.1 Инициализация выпадающего списка рабочих пространств на верхней панели
  await initTopWorkspaceDropdown();

  // 5.2 Инициализация кастомного контекстного меню (ПКМ) и Git GC
  await initCustomContextMenu();

  // 5.3 Инициализация бокового меню рабочих областей
  await initDrawerWorkspaces();

  // 5.4 Синхронизация бейджа непрочитанных писем Gmail в верхней панели
  initTopGmailBadge();

  // 5.5 Инициализация вертикальной панели навигации в стиле стандартных IDE (Activity Bar)
  initIdeNavigation();
  // 5.6 Инициализация стандартного навигатора по файлам и Command Center
  initIdeFileExplorer();
  initModelTester();

  // 6. Определение активного пространства и вкладки из конфига и URL стандартов workspace-url-routing
  const currentHash = typeof location !== 'undefined' ? location.hash : '';
  const hasUserHash = Boolean(currentHash && currentHash !== '#' && currentHash.length > 1);

  // 6.1 Считываем сохраненное состояние из localStorage
  let localLastTab = null;
  let localLastHash = null;
  let localLastWs = null;
  try {
    localLastTab = localStorage.getItem('ai_assistant_last_tab');
    localLastHash = localStorage.getItem('ai_assistant_last_hash');
    localLastWs = localStorage.getItem('ai_assistant_active_workspace');
  } catch (_) {}

  // 6.2 Проверяем фактический список доступных рабочих пространств на сервере
  let availableWorkspaces = [];
  try {
    const wsRes = await fetch('/api/v1/workspaces');
    if (wsRes.ok) {
      const wsData = await wsRes.json();
      availableWorkspaces = wsData.workspaces || [];
    }
  } catch (err) {
    console.warn('[Main] Ошибка получения списка рабочих пространств:', err);
  }

  // 6.3 Запрашиваем последнее активное пространство и вкладку из конфига на сервере
  let serverActiveWs = null;
  let serverLastTab = null;
  let serverLastUrl = null;
  try {
    const activeRes = await fetch('/api/v1/workspaces/active');
    if (activeRes.ok) {
      const activeData = await activeRes.json();
      if (activeData) {
        serverActiveWs = activeData.workspace_id || null;
        serverLastTab = activeData.last_active_tab || null;
        serverLastUrl = activeData.last_active_url || null;
      }
    }
  } catch (err) {
    console.warn('[Main] Ошибка получения активного рабочего пространства из конфига:', err);
  }

  let effectiveHash = currentHash;
  if (!hasUserHash) {
    // Восстанавливаем последнюю открытую вкладку и пространство из конфига или localStorage
    if (serverLastUrl) {
      effectiveHash = serverLastUrl;
    } else if (localLastHash) {
      effectiveHash = localLastHash;
    } else if (serverLastTab || localLastTab) {
      const restoredTab = serverLastTab || localLastTab;
      const restoredWs = serverActiveWs || localLastWs;
      if ((restoredTab === 'tab-workspace' || restoredTab === 'workspace') && restoredWs) {
        effectiveHash = `#tab-workspace#panel-files#workspace=${encodeURIComponent(restoredWs)}`;
      } else {
        effectiveHash = restoredTab.startsWith('#') ? restoredTab : `#${restoredTab}`;
      }
    } else if (serverActiveWs || localLastWs) {
      const restoredWs = serverActiveWs || localLastWs;
      effectiveHash = `#tab-workspace#panel-files#workspace=${encodeURIComponent(restoredWs)}`;
    }
  }

  const parsedUrl = parseWorkspaceUrlComponents(effectiveHash || '#tab-workspace');
  let initialTabId = parsedUrl.tabId || 'tab-workspace';
  let targetWsId = parsedUrl.workspaceId || serverActiveWs || localLastWs;
  const targetPanelId = parsedUrl.panelId || 'panel-files';

  if (availableWorkspaces.length === 0) {
    initialTabId = 'tab-create-workspace';
    targetWsId = null;
    try {
      localStorage.removeItem('ai_assistant_active_workspace');
      localStorage.removeItem('ai_assistant_active_repo');
      localStorage.removeItem('ai_assistant_last_hash');
    } catch (_) {}
    if (typeof window.setActiveWorkspaceId === 'function') {
      window.setActiveWorkspaceId('');
    }
    if (typeof window.updateActiveWorkspaceHeaderTitle === 'function') {
      window.updateActiveWorkspaceHeaderTitle('');
    }
    if (typeof location !== 'undefined' && (location.hash.startsWith('#tab-workspace') || location.hash.includes('workspace='))) {
      location.hash = '#tab-create-workspace';
    }
  } else if (!targetWsId && availableWorkspaces[0]) {
    targetWsId = availableWorkspaces[0].workspace_id;
  }

  if (!hasUserHash && effectiveHash) {
    try {
      history.replaceState(null, '', `${location.pathname}${location.search || ''}${effectiveHash}`);
    } catch (_) {}
  }

  const rawTabName = initialTabId.startsWith('tab-') ? initialTabId.slice(4) : initialTabId;

  // 7. Загрузка исключительно целевой активной вкладки
  await switchMainTab(initialTabId);
  applyTranslations();

  // 8. Если рабочие пространства есть, синхронизируем суб-панели и выпадающий список
  if (availableWorkspaces.length > 0) {
    if (targetWsId) {
      await updateTopWorkspaceDropdown(targetWsId);
      highlightActiveDrawerWorkspace(targetWsId);
      if (typeof window.refreshFileTree === 'function') {
        window.refreshFileTree(targetWsId);
      }
    }
    if ((initialTabId === 'tab-workspace' || initialTabId === 'workspace') && typeof window.switchWorkspaceSubTab === 'function') {
      window.switchWorkspaceSubTab(targetPanelId, false, parsedUrl.blockId);
    }
  } else {
    await updateTopWorkspaceDropdown(null);
  }

  // 9. Реакция на изменение URL хэша пользователем или историей браузера
  window.addEventListener('hashchange', async () => {
    const parsed = parseWorkspaceUrlComponents(typeof location !== 'undefined' ? location.hash : '');
    const curTab = parsed.tabId;
    if (curTab) {
      await switchMainTab(curTab);
    }
    if (curTab === 'tab-workspace' || curTab === 'workspace') {
      if (parsed.workspaceId) {
        const curWs = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : '';
        if (!areWorkspacesEqual(parsed.workspaceId, curWs)) {
          if (typeof window.selectWorkspaceInTab === 'function') {
            await window.selectWorkspaceInTab(parsed.workspaceId);
          }
          await updateTopWorkspaceDropdown(parsed.workspaceId);
          highlightActiveDrawerWorkspace(parsed.workspaceId);
          if (typeof window.refreshFileTree === 'function') {
            window.refreshFileTree(parsed.workspaceId);
          }
        }
        if (typeof window.switchWorkspaceSubTab === 'function' && parsed.panelId) {
          window.switchWorkspaceSubTab(parsed.panelId, false, parsed.blockId);
        }
      }
    }
    saveActiveState(curTab, location.hash, parsed.workspaceId);
  });
  // 10. Навигация на главную страницу при клике по брендингу (#app-brand-link)
  const brandLink = document.getElementById('app-brand-link');
  if (brandLink) {
    brandLink.addEventListener('click', (e) => {
      if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
      e.preventDefault();
      if (typeof location !== 'undefined' && location.hash) {
        history.pushState(null, '', location.pathname);
      }
      switchMainTab('tab-workspace');
    });
  }
}

document.readyState === 'loading'
  ? document.addEventListener('DOMContentLoaded', init)
  : init();
