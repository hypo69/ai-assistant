/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Version Comparison Tab Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки tab_diff («Сравнение версий»).
 *   Координирует жизненный цикл и панель panel_diff_stats.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_diff
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-19 18:35:00
 * =============================================================================
 */

import { initDiffStatsPanel, activateDiffPanel } from './panel_diff_stats/panel.js';

export function init() {
  initDiffStatsPanel();
}

export function activate() {
  activateDiffPanel();
}

window.initDiffTab = init;
window.activateDiffTab = activate;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
