/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - IDE Activity Bar & Electron Navigation
 * =============================================================================
 * Description:
 *   Модуль вертикальной панели навигации в стиле стандартных IDE (Activity Bar)
 *   (VS Code / JetBrains / Cursor / Obsidian).
 *   Обеспечивает:
 *   - Вертикальную панель быстрого переключения рабочих разделов IDE слева
 *   - Индикацию и прямое взаимодействие с десктопной оболочкой Electron Shell
 *     (Node.js runtime + IPC мост `window.aiEngineBridge`)
 *   - Показ модального окна статуса Electron и Obsidian Vault
 *   - Поддержку IDE горячих клавиш (Alt+1..9, Ctrl+B, Ctrl+,)
 *   - Изолированное переключение вкладок без выезда левого меню при выборе элементов
 *
 * File: ide_navigation.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 02:16:00
 * =============================================================================
 */

import { switchSidebarView, initExtensionsSidebar } from './ide_extensions_sidebar.js';
import { toggleFileExplorerSidebar } from './ide_file_explorer.js';

/**
 * Безопасный вызов переключения главной вкладки без циклического импорта main.js.
 * @param {string} tabId
 * @returns {Promise<void>|void}
 */
function navigateToMainTab(tabId) {
  if (typeof window.switchMainTab === 'function') {
    return window.switchMainTab(tabId);
  }
  if (typeof window.switchTab === 'function') {
    return window.switchTab(tabId);
  }
}

/**
 * Проверяет, запущено ли приложение внутри десктопной оболочки Electron.
 * @returns {boolean}
 */
export function isElectronRuntime() {
  if (typeof window !== 'undefined' && window.aiEngineBridge && window.aiEngineBridge.isElectron) {
    return true;
  }
  if (typeof navigator !== 'undefined' && /Electron/i.test(navigator.userAgent)) {
    return true;
  }
  return false;
}

/**
 * Закрывает левую выдвижную панель (Side Bar Offcanvas), если она открыта.
 */
export function closeSideBar() {
  const offcanvasEl = document.getElementById('leftSideNavOffcanvas');
  if (!offcanvasEl || !window.bootstrap) return;
  try {
    const oc = bootstrap.Offcanvas.getInstance(offcanvasEl);
    if (oc) {
      oc.hide();
    }
  } catch (_) {}
}

/**
 * Открывает или закрывает левую выдвижную панель (Side Bar Offcanvas).
 */
export function toggleSideBar() {
  const offcanvasEl = document.getElementById('leftSideNavOffcanvas');
  if (!offcanvasEl || !window.bootstrap) return;
  const oc = bootstrap.Offcanvas.getOrCreateInstance(offcanvasEl);
  if (offcanvasEl.classList.contains('show')) {
    oc.hide();
  } else {
    oc.show();
  }
}

/**
 * Открывает общее модальное окно настроек пользователя и активирует вкладку статуса рантайма Electron Shell.
 */
export async function showElectronStatusModal() {
  const modalEl = document.getElementById('userSettingsModal');
  if (modalEl && window.bootstrap) {
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
    const tabBtn = document.getElementById('user-settings-tab-btn-electron');
    if (tabBtn && window.bootstrap.Tab) {
      bootstrap.Tab.getOrCreateInstance(tabBtn).show();
    }
  }
  await loadElectronStatus();
}

/**
 * Безопасная функция локализации строк через window.i18next с fallback-значением.
 * @param {string} key
 * @param {string} fallback
 * @returns {string}
 */
function t(key, fallback) {
  if (typeof window !== 'undefined' && window.i18next && typeof window.i18next.t === 'function') {
    const val = window.i18next.t(key);
    if (val && val !== key) return val;
  }
  return fallback;
}

/**
 * Загружает и отображает паспорт статуса оболочки Electron и Obsidian Vault в контейнере общего модального окна настроек.
 * @param {HTMLElement|null} container
 */
export async function loadElectronStatus(container = null) {
  if (!container) {
    container = document.getElementById('electron-status-content');
  }
  if (!container) return;

  const isElectron = isElectronRuntime();

  // Обновляем бейдж статуса в шапке модального окна настроек
  const badgeVal = document.getElementById('modal-header-electron-status-name');
  if (badgeVal) {
    badgeVal.textContent = isElectron ? t('userSettings.electronActive', 'Active') : t('userSettings.electronModeWeb', 'Web GUI');
  }
  const topBadge = document.getElementById('user-settings-electron-badge-top');
  if (topBadge) {
    topBadge.className = `badge ${isElectron ? 'bg-success-subtle text-success border-success-subtle' : 'bg-secondary-subtle text-body border-secondary-subtle'} border d-inline-flex align-items-center gap-1.5 ms-1 cursor-pointer user-settings-electron-badge`;
    const titleText = isElectron
      ? t('userSettings.electronBadgeActiveTitle', 'Electron Shell Active (Node.js + Chromium + Obsidian IPC)')
      : t('userSettings.electronBadgeWebTitle', 'Web GUI Mode (Electron Shell Ready)');
    topBadge.setAttribute('title', titleText);
  }

  let info = null;

  // 1. Попытка получить информацию напрямую через Electron IPC
  if (isElectron && window.aiEngineBridge?.getInfo) {
    try {
      info = await window.aiEngineBridge.getInfo();
    } catch (e) {
      console.warn('[IDE Nav] IPC getInfo error:', e);
    }
  }

  // 2. Получение паспорта сервера через REST API
  let serverStatus = null;
  try {
    const res = await fetch('/api/v1/engine/status');
    if (res.ok) {
      serverStatus = await res.json();
    }
  } catch (e) {
    console.warn('[IDE Nav] Server status error:', e);
  }

  const nodeVer = info?.versions?.node || processVerSafe('node') || t('userSettings.electronExternalNode', 'Внешний Node.js');
  const chromeVer = info?.versions?.chrome || processVerSafe('chrome') || 'Chromium';
  const electronVer = info?.versions?.electron || processVerSafe('electron') || (isElectron ? t('userSettings.electronActive', 'Active') : t('userSettings.electronInactive', 'Не активен'));

  // Проверяем наличие декларативных элементов DOM
  const banner = document.getElementById('electron-mode-banner');
  const iconBox = document.getElementById('electron-mode-icon-box');
  const icon = document.getElementById('electron-mode-icon');
  const title = document.getElementById('electron-mode-title');
  const desc = document.getElementById('electron-mode-desc');
  const cliHint = document.getElementById('electron-cli-hint');

  if (banner) {
    banner.className = `d-flex align-items-center gap-3 p-3 mb-3 rounded border ${isElectron ? 'bg-success-subtle border-success-subtle' : 'bg-body-secondary border-secondary-subtle'}`;
  }
  if (iconBox) {
    iconBox.className = `rounded-circle p-2 d-flex align-items-center justify-content-center ${isElectron ? 'bg-success text-white' : 'bg-primary text-white'} icon-box-44`;
  }
  if (icon) {
    icon.className = `bi ${isElectron ? 'bi-lightning-charge-fill' : 'bi-browser-edge'} fs-4`;
  }
  if (title) {
    title.textContent = isElectron
      ? t('userSettings.electronModeDesktop', 'Electron Desktop (Chromium + Node.js)')
      : t('userSettings.electronModeWeb', 'Web Browser GUI');
  }
  if (desc) {
    desc.textContent = isElectron
      ? t('userSettings.electronModeDesktopDesc', 'Полноценный нативный десктопный режим с поддержкой IPC и прямого доступа к Obsidian Vault')
      : t('userSettings.electronModeWebDesc', 'Интерфейс запущен в веб-браузере. Доступен запуск в десктопной оболочке Electron');
  }
  if (cliHint) {
    cliHint.classList.toggle('d-none', isElectron);
  }

  const elVer = document.getElementById('electron-val-ver');
  if (elVer) {
    elVer.textContent = electronVer;
    elVer.className = `ms-1 ${isElectron ? 'text-success' : 'text-secondary'}`;
  }
  const elNode = document.getElementById('electron-node-ver');
  if (elNode) elNode.textContent = nodeVer;

  const elChrome = document.getElementById('electron-chrome-ver');
  if (elChrome) elChrome.textContent = chromeVer;

  const elPriority = document.getElementById('electron-engine-priority-val');
  if (elPriority) elPriority.textContent = serverStatus?.preferred_engine || 'electron';

  // Привязка обработчиков открытия Obsidian
  const openObsBtn = document.getElementById('btn-ide-open-obsidian');
  if (openObsBtn && !openObsBtn._bound) {
    openObsBtn._bound = true;
    openObsBtn.addEventListener('click', async () => {
      const activeWs = (typeof window.getActiveWorkspaceId === 'function')
        ? window.getActiveWorkspaceId()
        : 'default';
      try {
        const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(activeWs)}/obsidian/open`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'ok') {
          if (window.showToast) window.showToast(t('userSettings.obsidianLaunched', 'Запущен протокол Obsidian Vault'), 'success');
        } else {
          if (window.showToast) window.showToast(data.message || t('userSettings.obsidianLaunchError', 'Ошибка запуска Obsidian'), 'warning');
        }
      } catch (err) {
        if (window.showToast) window.showToast(t('userSettings.obsidianLaunchError', 'Ошибка запуска Obsidian') + ': ' + err.message, 'danger');
      }
    });
  }

  const openFolderBtn = document.getElementById('btn-ide-open-folder');
  if (openFolderBtn && !openFolderBtn._bound) {
    openFolderBtn._bound = true;
    openFolderBtn.addEventListener('click', async () => {
      const activeWs = (typeof window.getActiveWorkspaceId === 'function')
        ? window.getActiveWorkspaceId()
        : 'default';
      try {
        const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(activeWs)}/open-folder`, { credentials: 'same-origin' });
        const data = await res.json();
        if (data.status === 'success') {
          if (window.showToast) window.showToast(t('userSettings.obsidianFolderOpened', 'Папка открыта в проводнике'), 'info');
        }
      } catch (_) {}
    });
  }
}

/**
 * Безопасное чтение версий из process.versions, если доступно.
 * @param {string} key 
 * @returns {string|null}
 */
function processVerSafe(key) {
  try {
    return window.process?.versions?.[key] || null;
  } catch (_) {
    return null;
  }
}

/**
 * Регистрация глобальных горячих клавиш в стиле стандартных IDE.
 */
function setupIdeKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Не перехватываем ввод в текстовых полях
    const targetTag = (e.target.tagName || '').toLowerCase();
    if (targetTag === 'input' || targetTag === 'textarea' || e.target.isContentEditable) {
      return;
    }

    // Ctrl+B или Alt+B: Свернуть/развернуть боковое меню (Side Bar)
    if ((e.ctrlKey && e.key.toLowerCase() === 'b') || (e.altKey && e.key.toLowerCase() === 'b')) {
      e.preventDefault();
      toggleFileExplorerSidebar();
      return;
    }

    // Ctrl+,: Открыть параметры / настройки
    if (e.ctrlKey && e.key === ',') {
      e.preventDefault();
      const settingsModalEl = document.getElementById('userSettingsModal');
      if (settingsModalEl && window.bootstrap) {
        bootstrap.Modal.getOrCreateInstance(settingsModalEl).show();
      }
      return;
    }

    // Alt+1 .. Alt+9: Быстрый переход по вкладкам инструментов IDE (меню не открывается)
    if (e.altKey && !e.ctrlKey && !e.metaKey) {
      const shortcutMap = {
        '1': 'tab-workspace',
        '2': 'tab-commits',
        '3': 'tab-diff',
        '4': 'tab-timeline',
        '5': 'tab-chat',
        '6': 'tab-graph',
        '7': 'tab-models',
        '8': 'tab-rag',
        '9': 'tab-verification',
      };
      const targetTab = shortcutMap[e.key];
      if (targetTab) {
        e.preventDefault();
        closeSideBar();
        navigateToMainTab(targetTab);
      }
    }
  });
}

/**
 * Инициализирует вертикальную панель навигации в стиле стандартных IDE (Activity Bar).
 */
export function initIdeNavigation() {
  const activityBar = document.getElementById('ide-activity-bar');
  if (!activityBar) return;

  const isElectron = isElectronRuntime();
  if (isElectron) {
    document.documentElement.classList.add('is-electron');
    document.body.classList.add('is-electron');
  }

  // 1. Инициализация статуса среды Electron и Obsidian Vault в общем модальном окне настроек
  const electronTabBtn = document.getElementById('user-settings-tab-btn-electron');
  if (electronTabBtn) {
    electronTabBtn.addEventListener('shown.bs.tab', () => {
      loadElectronStatus();
    });
  }
  const userSettingsModalEl = document.getElementById('userSettingsModal');
  if (userSettingsModalEl) {
    userSettingsModalEl.addEventListener('show.bs.modal', () => {
      loadElectronStatus();
    });
  }
  loadElectronStatus();

  // Резервная поддержка кнопки Activity Bar (если присутствует)
  const electronBtn = document.getElementById('ide-nav-electron-btn');
  if (electronBtn) {
    const dot = electronBtn.querySelector('.ide-status-dot');
    if (isElectron) {
      electronBtn.classList.add('text-success');
      electronBtn.setAttribute('title', 'Electron Shell Active (Node.js + Chromium + Obsidian IPC) — Нажмите для подробностей');
      if (dot) dot.classList.add('bg-success');
    } else {
      electronBtn.classList.add('text-muted');
      electronBtn.setAttribute('title', 'Web GUI Mode (Electron Shell Ready) — Нажмите для справки о запуске');
      if (dot) dot.classList.add('bg-secondary');
    }
    electronBtn.addEventListener('click', (e) => {
      e.preventDefault();
      showElectronStatusModal();
    });
  }

  // 2. Обработка и синхронизация состояния кнопки открытия меню разделов (#leftSideNavOffcanvas) в Activity Bar
  const toggleBtn = document.getElementById('ide-nav-toggle-sidebar');
  const drawerEl = document.getElementById('leftSideNavOffcanvas');
  if (toggleBtn) {
    // Резервный обработчик, если кнопка не управляется атрибутом data-bs-toggle="offcanvas"
    if (!toggleBtn.hasAttribute('data-bs-toggle')) {
      toggleBtn.addEventListener('click', (e) => {
        e.preventDefault();
        toggleSideBar();
      });
    }
    if (drawerEl) {
      drawerEl.addEventListener('shown.bs.offcanvas', () => {
        toggleBtn.classList.add('active');
      });
      drawerEl.addEventListener('hidden.bs.offcanvas', () => {
        toggleBtn.classList.remove('active');
      });
    }
  }

  // 3. Обработка кликов по элементам инструментов Activity Bar:
  // При клике на инструмент меню НЕ выезжает, а наоборот гарантированно скрывается!
  activityBar.querySelectorAll('.ide-activity-item[data-tab]').forEach((item) => {
    item.addEventListener('click', async (e) => {
      e.preventDefault();
      const tabId = item.dataset.tab;
      if (!tabId) return;

      // Гарантированно закрываем боковое выезжающее offcanvas-меню при выборе инструмента
      closeSideBar();

      const isCurrentActive = item.classList.contains('active');

      // Переключение представления боковой панели в зависимости от инструмента (VS Code Side Bar Views)
      if (tabId === 'tab-plugins') {
        switchSidebarView('extensions');
        if (isCurrentActive) {
          toggleFileExplorerSidebar();
        } else {
          toggleFileExplorerSidebar(true);
        }
      } else if (tabId === 'tab-workspace') {
        switchSidebarView('explorer');
        if (isCurrentActive) {
          toggleFileExplorerSidebar();
        } else {
          toggleFileExplorerSidebar(true);
        }
      }

      await navigateToMainTab(tabId);
      if (item.dataset.panel && typeof window.switchWorkspaceSubTab === 'function') {
        window.switchWorkspaceSubTab(item.dataset.panel, true);
      }
    });
  });

  // 4. Служебные кнопки в нижней части Activity Bar
  const settingsBtn = document.getElementById('ide-nav-settings');
  if (settingsBtn) {
    settingsBtn.addEventListener('click', (e) => {
      e.preventDefault();
      closeSideBar();
      const settingsModalEl = document.getElementById('userSettingsModal');
      if (settingsModalEl && window.bootstrap) {
        bootstrap.Modal.getOrCreateInstance(settingsModalEl).show();
      }
    });
  }

  // 5. Инициализация боковой панели расширений
  initExtensionsSidebar();

  // 6. Инициализация IDE клавиатурных комбинаций
  setupIdeKeyboardShortcuts();
}
