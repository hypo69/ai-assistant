/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - RAG Tab Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки tab_rag (User Space RAG).
 *   Координирует жизненный цикл, синхронизацию активной рабочей области,
 *   маршрутизацию URL (#tab-rag#workspace=<id>) и взаимодействие с панелью panel-rag-chunks.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_rag
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-16 04:32:00
 * =============================================================================
 */

import { initRagPanel, loadWorkspacesList, updateWorkspaceRagStatus, parseWorkspaceFromHash } from './panel_rag/panel.js?v=20261116_v1';
import { loadPanelData } from '../js/panel-loader.js?v=20261116_v1';

let initialized = false;

export function init() {
  if (initialized) return;
  initialized = true;

  initRagPanel();

  // Синхронизация при смене рабочей области через верхнее меню или события приложения
  document.addEventListener('context:changed', async (e) => {
    const wsId = e.detail?.workspace_id;
    if (wsId) {
      const select = document.getElementById('rag-workspace-select');
      if (select && select.value !== wsId) {
        select.value = wsId;
      }
      await updateWorkspaceRagStatus(wsId);
      loadPanelData('panel-rag-chunks', { workspace_id: wsId, force: true });
    }
  });

  // Синхронизация при изменении URL хэша (Back/Forward или прямая навигация)
  window.addEventListener('hashchange', async () => {
    const wsId = parseWorkspaceFromHash();
    if (wsId) {
      const select = document.getElementById('rag-workspace-select');
      if (select && select.value !== wsId) {
        select.value = wsId;
        await updateWorkspaceRagStatus(wsId);
        loadPanelData('panel-rag-chunks', { workspace_id: wsId, force: true });
      }
    }
  });
}

window.initRagTab = init;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
