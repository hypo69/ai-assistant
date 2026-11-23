/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Tab Workspace Version History Panel
 * =============================================================================
 * Description:
 *   Панель журнала версий (panel-commits) внутри вкладки tab_workspace.
 *   Переиспользует дружелюбный рендер событий, классификацию и локализацию
 *   из модуля tab_commits/panel_commits/panel.js.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/panel_commits
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-19 18:35:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';
import {
  getActiveLang,
  formatCommitMessage,
  formatFriendlyDate,
  classifyEvent,
  renderCommitsTable
} from '../../tab_commits/panel_commits/panel.js';

export { getActiveLang, formatCommitMessage, formatFriendlyDate, classifyEvent, renderCommitsTable };

let allCommits = [];
let isInitialized = false;

/**
 * Функция-обработчик результата ответа REST API роутера panel-commits.
 * @param {Object} result - Ответ от /v1/panel/panel-commits.
 * @param {HTMLElement} [panelEl=null] - Элемент карточки панели.
 */
export function renderCommitsPanel(result, panelEl = null) {
  allCommits = result?.data || [];
  renderCommitsTable(allCommits, panelEl);
}

/**
 * Загружает данные журнала версий для указанного рабочего пространства.
 * @param {string|null} [workspaceId=null] - Идентификатор рабочей области.
 * @param {boolean} [force=false] - Флаг принудительного обновления.
 */
export async function loadWorkspaceCommitsPanel(workspaceId = null, force = false) {
  return await loadPanelData('panel-commits', { force, workspace_id: workspaceId });
}

/**
 * Инициализирует обработчики событий и регистрацию рендерера панели panel-commits.
 */
export function initCommitsPanel() {
  registerPanelRenderer('panel-commits', renderCommitsPanel);

  if (!isInitialized) {
    isInitialized = true;

    const wsRoot = document.getElementById('subpane-ws-commits');
    wsRoot?.querySelector('#commits-refresh-btn')?.addEventListener('click', () => {
      const wsId = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : null;
      loadWorkspaceCommitsPanel(wsId, true);
    });

    wsRoot?.querySelector('#commits-search-input')?.addEventListener('input', (e) => {
      const q = (e.target.value || '').toLowerCase().trim();
      if (!q) {
        renderCommitsTable(allCommits, wsRoot);
        return;
      }
      const filtered = allCommits.filter((c) => {
        const friendly = formatCommitMessage(c.message || '').toLowerCase();
        return (
          friendly.includes(q) ||
          (c.message && c.message.toLowerCase().includes(q)) ||
          (c.author && c.author.toLowerCase().includes(q))
        );
      });
      renderCommitsTable(filtered, wsRoot);
    });

    const handleLanguageChanged = () => {
      renderCommitsTable(allCommits, wsRoot);
    };

    window.addEventListener('languageChanged', handleLanguageChanged);
    window.addEventListener('localeChanged', handleLanguageChanged);
    window.addEventListener('i18n:languageChanged', handleLanguageChanged);
  }
}
