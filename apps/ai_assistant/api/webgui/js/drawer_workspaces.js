/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Left Drawer Workspaces Navigator
 * =============================================================================
 * Description:
 *   Модуль динамического управления списком рабочих областей в боковом меню (Offcanvas).
 *   Обеспечивает:
 *   - Загрузку и отрисовку списка рабочих областей из REST API /api/v1/workspaces.
 *   - Каноническую навигацию по клику: переход на #tab-workspace#panel-files#workspace=<id>.
 *   - Мгновенное переключение активного рабочего пространства и закрытие выдвижного меню.
 *   - Подсветку активного пространства и синхронизацию с верхним меню и вкладками.
 *   - Надежный поиск рабочих областей с поддержкой Unicode (NFC), иврита и URL encoding.
 *
 * File: drawer_workspaces.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-20 02:16:00
 * =============================================================================
 */

let cachedWorkspaces = [];
let currentDrawerActiveId = '';

/**
 * Находит рабочую область в списке по ID, имени или закодированному URI.
 * Поддерживает нормализацию Unicode (NFC), нечувствительность к регистру и замену пробелов.
 * @param {Array} list - Список объектов рабочих областей
 * @param {string} target - Идентификатор или имя для поиска
 * @returns {Object|null}
 */
export function findWorkspaceMatch(list, target) {
  if (!target || !Array.isArray(list) || list.length === 0) return null;

  let decoded = target;
  try {
    decoded = decodeURIComponent(target);
  } catch (_) {}

  const cleanTarget = String(decoded).trim().normalize('NFC');
  const cleanTargetLower = cleanTarget.toLowerCase();

  // 1. Точное совпадение по workspace_id (с NFC нормализацией)
  let found = list.find((w) => (w.workspace_id || '').normalize('NFC') === cleanTarget);
  if (found) return found;

  // 2. Без учета регистра
  found = list.find(
    (w) => (w.workspace_id || '').normalize('NFC').toLowerCase() === cleanTargetLower
  );
  if (found) return found;

  // 3. По отображаемому имени name
  found = list.find(
    (w) => (w.name || '').normalize('NFC').toLowerCase() === cleanTargetLower
  );
  if (found) return found;

  // 4. По замене подчеркиваний на пробелы и наоборот
  const targetWithSpaces = cleanTargetLower.replace(/_/g, ' ');
  const targetWithUnderscores = cleanTargetLower.replace(/\s+/g, '_');

  found = list.find((w) => {
    const idLower = (w.workspace_id || '').normalize('NFC').toLowerCase();
    const nameLower = (w.name || '').normalize('NFC').toLowerCase();
    return (
      idLower === targetWithUnderscores ||
      nameLower === targetWithSpaces ||
      idLower.replace(/_/g, ' ') === targetWithSpaces ||
      nameLower.replace(/\s+/g, '_') === targetWithUnderscores
    );
  });

  return found || null;
}

/**
 * Экранирует спецсимволы для безопасной вставки в HTML.
 * @param {string} str 
 * @returns {string}
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Закрывает открытый верхний выпадающий список рабочих областей.
 */
export function closeTopWorkspaceDropdown() {
  const btn = document.getElementById('top-workspace-dropdown-btn');
  if (btn && window.bootstrap && window.bootstrap.Dropdown) {
    try {
      const dd = window.bootstrap.Dropdown.getInstance(btn);
      if (dd) dd.hide();
    } catch (_) {}
  }
}

/**
 * Закрывает открытые боковые меню Offcanvas и снимает оверлеи.
 */
export function closeOffcanvasDrawer() {
  const ocEl = document.getElementById('leftSideNavOffcanvas');
  if (ocEl && window.bootstrap && window.bootstrap.Offcanvas) {
    try {
      const oc = window.bootstrap.Offcanvas.getInstance(ocEl);
      if (oc) oc.hide();
    } catch (_) {}
  }
  setTimeout(() => {
    document.querySelectorAll('.offcanvas-backdrop, .modal-backdrop').forEach((b) => b.remove());
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.pointerEvents = '';
  }, 50);
}

/**
 * Подсвечивает активное рабочее пространство в выпадающем списке и меню.
 * @param {string} wsId 
 */
export function highlightActiveDrawerWorkspace(wsId) {
  currentDrawerActiveId = wsId || '';
  const containers = [
    document.getElementById('top-workspaces-dynamic-items'),
    document.getElementById('drawer-workspaces-dynamic-items'),
  ].filter(Boolean);
  if (containers.length === 0) return;

  const matched = findWorkspaceMatch(cachedWorkspaces, wsId);
  const matchedId = matched ? matched.workspace_id : wsId;
  const matchedTitle = matched ? (matched.name || matched.workspace_id) : wsId;

  // Обновляем текст на кнопке верхней навигационной панели
  const titleEl = document.getElementById('app-title');
  if (titleEl) {
    if (matched && matchedTitle) {
      titleEl.textContent = String(matchedTitle).replace(/^Workspace:\s*/i, '');
      titleEl.removeAttribute('data-i18n');
    } else if (!cachedWorkspaces || cachedWorkspaces.length === 0) {
      titleEl.textContent = 'Нет рабочих пространств';
      titleEl.setAttribute('data-i18n', 'workspace.noWorkspaces');
    }
  }

  containers.forEach((container) => {
    container.querySelectorAll('.drawer-ws-item, .top-ws-item').forEach((btn) => {
      const btnWsId = btn.getAttribute('data-ws-id');
      const isTarget = btnWsId === matchedId;
      btn.classList.toggle('active', isTarget);

      const icon = btn.querySelector('.drawer-ws-icon');
      if (icon) {
        if (isTarget) {
          icon.className = 'bi bi-folder-check text-success fs-6 flex-shrink-0 drawer-ws-icon';
        } else {
          icon.className = 'bi bi-folder text-muted fs-6 flex-shrink-0 drawer-ws-icon';
        }
      }

      const badge = btn.querySelector('.drawer-ws-status-badge');
      if (badge && isTarget) {
        badge.className = 'badge bg-success-subtle text-success border font-size-75 drawer-ws-status-badge';
        badge.textContent = 'активно';
      }
    });
  });
}

/**
 * Отрисовывает динамический список рабочих пространств в выпадающем списке и боковом меню.
 * @param {Array} workspaces - Список рабочих пространств
 * @param {string} [activeWsId] - Идентификатор текущей активной области
 */
export function renderDrawerWorkspaces(workspaces, activeWsId = '') {
  const containers = [
    document.getElementById('top-workspaces-dynamic-items'),
    document.getElementById('drawer-workspaces-dynamic-items'),
  ].filter(Boolean);
  const countBadges = [
    document.getElementById('top-ws-count-badge'),
    document.getElementById('drawer-ws-count-badge'),
  ].filter(Boolean);

  const list = Array.isArray(workspaces) ? workspaces : [];
  cachedWorkspaces = list;

  countBadges.forEach((b) => {
    b.textContent = String(list.length);
  });

  const effectiveActive = activeWsId || currentDrawerActiveId || (list[0]?.workspace_id || '');
  const matchedActive = findWorkspaceMatch(list, effectiveActive);
  const activeId = matchedActive ? matchedActive.workspace_id : effectiveActive;
  currentDrawerActiveId = activeId;

  // Обновляем текст на кнопке верхней навигационной панели
  const titleEl = document.getElementById('app-title');
  if (titleEl && matchedActive) {
    const cleanTitle = (matchedActive.name || matchedActive.workspace_id).replace(/^Workspace:\s*/i, '');
    titleEl.textContent = cleanTitle;
    titleEl.removeAttribute('data-i18n');
  }

  if (containers.length === 0) return;

  if (list.length === 0) {
    currentDrawerActiveId = '';
    const titleEl = document.getElementById('app-title');
    if (titleEl) {
      let fallback = 'Нет рабочих пространств';
      if (window.i18n && typeof window.i18n.t === 'function') {
        const trans = window.i18n.t('workspace.noWorkspaces');
        if (trans && trans !== 'workspace.noWorkspaces') {
          fallback = trans;
        }
      }
      titleEl.textContent = fallback;
      titleEl.setAttribute('data-i18n', 'workspace.noWorkspaces');
    }
    const emptyHtml = `
      <div class="p-3 text-center text-muted small">
        <i class="bi bi-folder2-open d-block mb-1 fs-5"></i>
        <span data-i18n="workspace.noWorkspaces">Нет рабочих областей</span>
      </div>
    `;
    containers.forEach((c) => {
      c.innerHTML = emptyHtml;
    });
    return;
  }

  const itemsHtml = list
    .map((ws) => {
      const isTarget = ws.workspace_id === activeId;
      const docsCount = ws.documents_count || 0;
      const factsCount = ws.active_facts_count || 0;
      const title = escapeHtml(ws.name || ws.workspace_id);

      return `
        <button class="list-group-item list-group-item-action d-flex align-items-center justify-content-between py-2 px-3 top-ws-item drawer-ws-item ${
          isTarget ? 'active' : ''
        }" data-ws-id="${escapeHtml(ws.workspace_id)}" type="button" title="Рабочее пространство: ${title}">
          <div class="d-flex align-items-center gap-2.5 overflow-hidden text-truncate">
            <i class="bi ${
              isTarget ? 'bi-folder-check text-success' : 'bi-folder text-muted'
            } fs-5 flex-shrink-0 drawer-ws-icon"></i>
            <div class="text-truncate text-start">
              <div class="fw-semibold text-truncate fs-6">${title}</div>
              <div class="small text-muted text-truncate font-size-75 d-flex align-items-center gap-1.5 mt-0.5" dir="ltr">
                <span class="badge bg-body-secondary text-body border px-1.5 py-0.5 drawer-ws-quick-link" data-panel="panel-documents" title="Открыть панель документов: ${docsCount}">📄 ${docsCount} док.</span>
                <span class="badge bg-body-secondary text-body border px-1.5 py-0.5 drawer-ws-quick-link" data-panel="panel-facts" title="Открыть панель фактов: ${factsCount}">💡 ${factsCount} факт.</span>
              </div>
            </div>
          </div>
          <span class="badge ${
            isTarget
              ? 'bg-success-subtle text-success border'
              : 'bg-secondary-subtle text-secondary border'
          } font-size-75 flex-shrink-0 ms-3 drawer-ws-status-badge">
            ${isTarget ? 'активно' : `${docsCount} док.`}
          </span>
        </button>
      `;
    })
    .join('');

  containers.forEach((c) => {
    c.innerHTML = itemsHtml;
  });
}

/**
 * Переключает на указанную рабочую область по каноническому стандарту URL.
 * Формат: #tab-workspace#panel-files#workspace=<id>
 * @param {string} workspaceId - Идентификатор рабочей области
 * @param {string} [panelId='panel-files'] - Идентификатор целевой панели
 */
export async function switchToWorkspace(workspaceId, panelId = 'panel-files') {
  if (!workspaceId) return;

  const matched = findWorkspaceMatch(cachedWorkspaces, workspaceId);
  const finalWsId = matched ? matched.workspace_id : workspaceId;

  if (typeof window.setActiveWorkspaceId === 'function') {
    window.setActiveWorkspaceId(finalWsId);
  }

  // 1. Формирование канонического URL стандарта workspace-url-routing
  const targetHash = `#tab-workspace#${panelId}#workspace=${encodeURIComponent(finalWsId)}`;
  try {
    if (typeof location !== 'undefined' && location.hash !== targetHash) {
      history.pushState(null, null, targetHash);
    }
  } catch (_) {}

  // 2. Активация вкладки tab-workspace (с lazyLoad при необходимости)
  if (typeof window.switchTab === 'function') {
    await window.switchTab('tab-workspace');
  }

  // 3. Выбор рабочей области на вкладке Workspace
  if (typeof window.selectWorkspaceInTab === 'function') {
    await window.selectWorkspaceInTab(finalWsId, true);
  }

  // 4. Переключение на суб-панель файлов/документов
  if (typeof window.switchWorkspaceSubTab === 'function') {
    window.switchWorkspaceSubTab(panelId, false);
  }

  // 5. Синхронизация верхнего выпадающего селектора репозитория
  if (typeof window.updateTopWorkspaceDropdown === 'function') {
    await window.updateTopWorkspaceDropdown(finalWsId);
  }

  // 6. Подсветка в выпадающем списке и меню
  highlightActiveDrawerWorkspace(finalWsId);

  // 7. Синхронизируем файловый менеджер и оповещаем систему
  if (typeof window.refreshFileTree === 'function') {
    await window.refreshFileTree(finalWsId);
  }
  document.dispatchEvent(new CustomEvent('workspace:changed', {
    detail: { workspaceId: finalWsId }
  }));

  // 8. Закрытие оффканвас панели и верхнего выпадающего списка
  closeTopWorkspaceDropdown();
  closeOffcanvasDrawer();
}

/**
 * Запрашивает актуальный список рабочих пространств с сервера и отрисовывает их в меню.
 * @param {string} [activeWsId] - Опциональный идентификатор активной области
 * @param {number} [retries=2] - Количество повторных попыток при сбое
 * @returns {Promise<Array>}
 */
export async function fetchAndRenderDrawerWorkspaces(activeWsId = '', retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch('/api/v1/workspaces');
      if (res.ok) {
        const data = await res.json();
        const list = data.workspaces || [];
        cachedWorkspaces = list;
        renderDrawerWorkspaces(list, activeWsId);
        return list;
      }
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 600));
      }
    } catch (err) {
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 600));
      } else {
        console.warn('[DrawerWorkspaces] Ошибка загрузки списка рабочих пространств:', err);
      }
    }
  }
  return cachedWorkspaces || [];
}

/**
 * Инициализирует модуль навигации по рабочим областям верхнего выпадающего списка.
 */
export async function initDrawerWorkspaces() {
  // 1. Делегированный слушатель кликов по элементам рабочих пространств в верхнем меню
  const topWrapper = document.getElementById('top-workspace-dropdown-wrapper');
  if (topWrapper) {
    topWrapper.addEventListener('click', (e) => {
      const createBtn = e.target.closest('#top-btn-nav-create-workspace, #menu-btn-nav-create-workspace');
      if (createBtn) {
        e.preventDefault();
        closeTopWorkspaceDropdown();
        // Если у кнопки нет data-tab (который уже обрабатывается в setupTabClicks), переключаем вкладку здесь
        if (!createBtn.dataset.tab && typeof window.switchTab === 'function') {
          window.switchTab('tab-create-workspace');
        }
        return;
      }
      const quickLink = e.target.closest('.drawer-ws-quick-link, [data-panel]');
      const wsBtn = e.target.closest('.drawer-ws-item, .top-ws-item, [data-ws-id]');
      if (wsBtn) {
        const wsId = wsBtn.getAttribute('data-ws-id');
        if (wsId) {
          e.preventDefault();
          const targetPanel = quickLink ? quickLink.getAttribute('data-panel') : 'panel-files';
          switchToWorkspace(wsId, targetPanel || 'panel-files');
          closeTopWorkspaceDropdown();
        }
      }
    });
  }

  // 1.1 Делегированный слушатель для бокового меню (если присутствует)
  const group = document.getElementById('drawer-workspaces-group');
  if (group) {
    group.addEventListener('click', (e) => {
      const quickLink = e.target.closest('.drawer-ws-quick-link, [data-panel]');
      const wsBtn = e.target.closest('.drawer-ws-item, [data-ws-id]');
      if (wsBtn) {
        const wsId = wsBtn.getAttribute('data-ws-id');
        if (wsId) {
          e.preventDefault();
          const targetPanel = quickLink ? quickLink.getAttribute('data-panel') : 'panel-files';
          switchToWorkspace(wsId, targetPanel || 'panel-files');
        }
      }
    });
  }

  // 2. Загружаем и отрисовываем текущие пространства
  const currentWs = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : '';
  await fetchAndRenderDrawerWorkspaces(currentWs);

  // 3. Слушаем единое событие context:changed
  document.addEventListener('context:changed', (e) => {
    const wsId = e.detail?.workspaceId;
    if (wsId) {
      highlightActiveDrawerWorkspace(wsId);
    }
  });
}

// Экспорт в глобальный контекст для взаимодействия между модулями
if (typeof window !== 'undefined') {
  window.switchToWorkspace = switchToWorkspace;
  window.renderDrawerWorkspaces = renderDrawerWorkspaces;
  window.fetchAndRenderDrawerWorkspaces = fetchAndRenderDrawerWorkspaces;
  window.highlightActiveDrawerWorkspace = highlightActiveDrawerWorkspace;
  window.findWorkspaceMatch = findWorkspaceMatch;
  window.initDrawerWorkspaces = initDrawerWorkspaces;
  window.closeTopWorkspaceDropdown = closeTopWorkspaceDropdown;
}
