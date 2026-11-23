/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Chat Panel
 * =============================================================================
 * Description:
 *   Клиентский модуль панели диалога с ИИ (Чат) в рамках вкладки
 *   tab-workspace (#tab-workspace#panel-chat). Ответы формируются строго по
 *   документам выбранной рабочей области через контур /api/v1/ask
 *   (без подмешивания общих знаний модели).
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/panel_chat
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-19 22:11:01
 * =============================================================================
 */

import { fetchJson, t } from '../common/ui_utils.js';
import { getCurrentWorkspaceId } from '../panel_workspace_select/panel.js';

let isSending = false;
let getWorkspaceIdCallback = null;
let activePurchaseScenario = null;
let lastIntroRunId = null;

/**
 * Возвращает текущий код языка интерфейса (ru, en, he, uk).
 * @returns {string}
 */
function getCurrentLanguage() {
  const lang =
    (typeof window !== 'undefined' && window.i18n && window.i18n.lang) ||
    (typeof document !== 'undefined' && document.documentElement.lang) ||
    'ru';
  return String(lang).toLowerCase().slice(0, 2);
}

/**
 * Возвращает локализованное поле условия или сценария по текущему языку интерфейса (ru, en, he, uk).
 * @param {Object} obj - Объект сценария или условия.
 * @param {string} field - Базовое имя поля ('title', 'summary', 'details', 'action_prompt').
 * @returns {string}
 */
function getLocalizedField(obj, field) {
  if (!obj || typeof obj !== 'object') return '';
  if (obj[`${field}_i18nKey`]) {
    const byKey = t(obj[`${field}_i18nKey`], '');
    if (byKey) return byKey;
  }
  const cleanLang = getCurrentLanguage();
  const i18nMap = obj[`${field}_i18n`];
  if (i18nMap && typeof i18nMap === 'object') {
    if (i18nMap[cleanLang]) return String(i18nMap[cleanLang]);
    if (i18nMap.he) return String(i18nMap.he);
    if (i18nMap.en) return String(i18nMap.en);
    if (i18nMap.ru) return String(i18nMap.ru);
  }
  if (obj[`${field}_${cleanLang}`]) {
    return String(obj[`${field}_${cleanLang}`]);
  }
  return String(obj[field] || '');
}

/**
 * Обновляет статус условия сценария покупки на сервере и перерисовывает трекер.
 * @param {string} conditionId - Идентификатор условия.
 * @param {'completed'|'planned'|'in_progress'} newStatus - Новый статус.
 */
async function updateScenarioCondition(conditionId, newStatus) {
  try {
    const res = await fetchJson('/api/v1/workspaces/telegram-scenario/condition', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ condition_id: conditionId, status: newStatus }),
    });
    if (res && res.scenario && res.scenario.chat_scenario) {
      renderPurchaseScenarioTracker(res.scenario.chat_scenario, { postIntro: false });
      return;
    }
  } catch (err) {
    console.warn('[ChatPanel] Ошибка обновления условия сценария:', err);
  }
  if (activePurchaseScenario && Array.isArray(activePurchaseScenario.conditions)) {
    for (const c of activePurchaseScenario.conditions) {
      if (c.id === conditionId) {
        c.status = newStatus;
      }
    }
    renderPurchaseScenarioTracker(activePurchaseScenario, { postIntro: false });
  }
}

/**
 * Заносит осмотр коровы Зины (20.11 в 06:00) в календарь ветеринара и страхового агента с напоминаниями.
 * @param {Object} item - Описание условия сценария.
 */
async function executeScheduleInspectionInChat(item) {
  if (isSending) return;
  const wsId = resolveCurrentWorkspaceId() || '';
  const curLang =
    (typeof window !== 'undefined' && window.i18n && window.i18n.lang) ||
    (typeof document !== 'undefined' && document.documentElement.lang) ||
    'ru';
  isSending = true;

  const itemTitle = getLocalizedField(item, 'title') || t('workspace.chatScheduleDefaultBtn', 'בדיקת הפרה ביומן (20.11 06:00)');
  appendMessage('user', `📅 ${itemTitle}`);
  const pendingBubble = appendMessage('assistant', '', true);

  try {
    const res = await fetchJson('/api/v1/workspaces/telegram-scenario/schedule-inspection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: wsId, language: curLang }),
    });

    if (res && res.scenario && res.scenario.chat_scenario) {
      renderPurchaseScenarioTracker(res.scenario.chat_scenario, { postIntro: false });
    }

    const gcal = (res && res.google_calendar) || {};
    const attendeesStr = ((res && res.attendees) || ['veterinarian@davidka.net', 'attorney@davidka.net'])
      .map((a) => `\`${a}\``)
      .join(', ');
    const lblDateTime = t('workspace.chatScheduleDateTime', 'Дата и время');
    const lblAddress = t('workspace.chatScheduleAddress', 'Адрес');
    const lblAttendees = t('workspace.chatScheduleAttendees', 'Участники (календарь + напоминания)');
    const lblReminders = t('workspace.chatScheduleReminders', 'Напоминания');
    const valReminders = t('workspace.chatScheduleRemindersValue', 'за 12 часов (email) и за 60 минут (popup / VALARM)');
    const lblIcsFile = t('workspace.chatScheduleIcsFile', 'Файл приглашения (.ics с VALARM в Git)');
    const lblOpenGcal = t('ui.calendar.open_in_gcal', 'Открыть в Google Calendar');
    const lblGcalCreated = t('workspace.chatScheduleGcalCreated', 'Событие создано, приглашения отправлены участникам');

    const lines = [
      `### 📅 ${res.summary || 'בדיקת הפרה זינה במשק שמוליק — דוד משה'}`,
      `- **🕒 ${lblDateTime}:** \`20.11.2026, 06:00–07:00\` (\`${res.start_time || '2026-11-20T06:00:00+02:00'}\`)`,
      `- **📍 ${lblAddress}:** \`${res.location || "מושב נהלל, משק מס' 42"}\``,
      `- **👥 ${lblAttendees}:** ${attendeesStr}`,
      `- **🔔 ${lblReminders}:** ${valReminders}`,
      `- **📎 ${lblIcsFile}:** \`${res.ics_rel || 'עסקת קניית פרה/zina_inspection_20261120_0600.ics'}\``,
    ];
    if (gcal.status === 'success') {
      lines.push(`- **✅ Google Calendar API:** ${lblGcalCreated} (\`ID: ${gcal.id}\`)${gcal.html_link ? ` — [${lblOpenGcal}](${gcal.html_link})` : ''}.`);
    } else if (gcal.error) {
      lines.push(`- **ℹ️ Google Calendar API:** \`${gcal.error}\``);
    }

    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      pendingBubble.innerHTML = renderMessageContent(lines.join('\n'));
    }
    document.dispatchEvent(new CustomEvent('workspace:changed', { detail: { workspaceId: wsId } }));
  } catch (err) {
    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      pendingBubble.innerHTML = `<div class="text-danger small">${escapeHtml(err.message || String(err))}</div>`;
    }
  } finally {
    isSending = false;
    scrollToBottom();
  }
}
/**
 * Рендерит панель выполненных и намеченных условий сценария покупки в окне чата.
 * @param {Object|null} chatScenario - Данные сценария покупки.
 * @param {Object} [options] - Опции рендера.
 * @param {boolean} [options.postIntro=false] - Добавить ли стартовое сообщение в ленту чата.
 * @param {string|null} [options.runId=null] - Идентификатор запуска сценария.
 */
export function renderPurchaseScenarioTracker(chatScenario, { postIntro = false, runId = null } = {}) {
  const tracker = getWorkspaceChatElement('#ws-chat-scenario-tracker');
  if (!tracker) return;

  if (!chatScenario || !Array.isArray(chatScenario.conditions) || chatScenario.conditions.length === 0) {
    activePurchaseScenario = null;
    tracker.classList.add('d-none');
    return;
  }

  activePurchaseScenario = chatScenario;
  tracker.classList.remove('d-none');

  const titleEl = getWorkspaceChatElement('#ws-chat-scenario-title');
  const progressBadge = getWorkspaceChatElement('#ws-chat-scenario-progress-badge');
  const doneCountEl = getWorkspaceChatElement('#ws-chat-scenario-done-count');
  const plannedCountEl = getWorkspaceChatElement('#ws-chat-scenario-planned-count');
  const doneList = getWorkspaceChatElement('#ws-chat-scenario-done-list');
  const plannedList = getWorkspaceChatElement('#ws-chat-scenario-planned-list');

  const scenTitle = getLocalizedField(chatScenario, 'title');
  if (titleEl && scenTitle) {
    titleEl.textContent = scenTitle;
  }

  const conditions = chatScenario.conditions;
  const completed = conditions.filter((c) => c.status === 'completed');
  const planned = conditions.filter((c) => c.status !== 'completed');

  if (progressBadge) {
    progressBadge.textContent = `${completed.length} / ${conditions.length}`;
  }
  if (doneCountEl) {
    doneCountEl.textContent = String(completed.length);
  }
  if (plannedCountEl) {
    plannedCountEl.textContent = String(planned.length);
  }

  const runActionLabel = t('workspace.chatScenarioRunActionBtn', 'Выполнить в чате');
  const markDoneTitle = t('workspace.chatScenarioMarkDoneTitle', 'Отметить как выполненное');
  const markPlannedTitle = t('workspace.chatScenarioMarkPlannedTitle', 'Вернуть в намеченные');

  if (doneList) {
    doneList.innerHTML = '';
    if (completed.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'text-muted fst-italic py-1';
      empty.textContent = t('workspace.chatScenarioEmptyCompleted', 'Пока нет выполненных условий');
      doneList.appendChild(empty);
    } else {
      for (const item of completed) {
        const itemTitle = getLocalizedField(item, 'title');
        const itemDetails = getLocalizedField(item, 'details');
        const row = document.createElement('div');
        row.className = 'd-flex align-items-start gap-2 p-1.5 rounded bg-success-subtle border border-success-subtle';
        row.innerHTML = `
          <button class="btn btn-sm btn-link p-0 text-success flex-shrink-0" type="button" title="${escapeHtml(markPlannedTitle)}">
            <i class="bi bi-check-square-fill"></i>
          </button>
          <div class="flex-grow-1 lh-sm">
            <div class="fw-semibold text-body">${escapeHtml(itemTitle)}</div>
            ${itemDetails ? `<div class="text-secondary small">${escapeHtml(itemDetails)}</div>` : ''}
          </div>
        `;
        const toggleBtn = row.querySelector('button');
        if (toggleBtn) {
          toggleBtn.onclick = () => updateScenarioCondition(item.id, 'planned');
        }
        doneList.appendChild(row);
      }
    }
  }

  if (plannedList) {
    plannedList.innerHTML = '';
    if (planned.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'text-success fw-semibold py-1';
      empty.textContent = t('workspace.chatScenarioEmptyPlanned', 'Все условия выполнены!');
      plannedList.appendChild(empty);
    } else {
      for (const item of planned) {
        const itemTitle = getLocalizedField(item, 'title');
        const itemDetails = getLocalizedField(item, 'details');
        const itemPrompt = getLocalizedField(item, 'action_prompt');
        const row = document.createElement('div');
        row.className = 'd-flex flex-column gap-1.5 p-1.5 rounded bg-warning-subtle border border-warning-subtle';
        row.innerHTML = `
          <div class="d-flex align-items-start gap-2">
            <button class="btn btn-sm btn-link p-0 text-warning-emphasis flex-shrink-0 ws-cond-check-btn" type="button" title="${escapeHtml(markDoneTitle)}">
              <i class="bi bi-square"></i>
            </button>
            <div class="flex-grow-1 lh-sm">
              <div class="fw-semibold text-body">${escapeHtml(itemTitle)}</div>
              ${itemDetails ? `<div class="text-secondary small">${escapeHtml(itemDetails)}</div>` : ''}
            </div>
          </div>
        `;
        const checkBtn = row.querySelector('.ws-cond-check-btn');
        if (checkBtn) {
          checkBtn.onclick = () => updateScenarioCondition(item.id, 'completed');
        }
        if (itemPrompt || item.action_type) {
          const actionBtn = document.createElement('button');
          actionBtn.type = 'button';
          actionBtn.className = 'btn btn-sm btn-outline-primary align-self-start py-0 px-2 small';
          actionBtn.innerHTML = `<i class="bi bi-play-fill me-1"></i>${escapeHtml(runActionLabel)}`;
          actionBtn.onclick = () => {
            if (item.action_type === 'schedule_inspection') {
              executeScheduleInspectionInChat(item);
            } else {
              sendChatMessage(itemPrompt, item.id);
            }
          };
          row.appendChild(actionBtn);
        }
        plannedList.appendChild(row);
      }
    }
  }

  if (postIntro && (!runId || runId !== lastIntroRunId)) {
    lastIntroRunId = runId || `intro_${Date.now()}`;
    const doneMd = completed
      .map((c) => {
        const ct = getLocalizedField(c, 'title');
        const cd = getLocalizedField(c, 'details');
        return `- [x] **${ct}**${cd ? ` — \`${cd}\`` : ''}`;
      })
      .join('\n');
    const plannedMd = planned
      .map((c) => {
        const ct = getLocalizedField(c, 'title');
        const cd = getLocalizedField(c, 'details');
        return `- [ ] **${ct}**${cd ? ` — ${cd}` : ''}`;
      })
      .join('\n');
    const introMd = [
      `### 🐄 ${scenTitle || 'עסקת קניית פרה'}`,
      getLocalizedField(chatScenario, 'summary') || '',
      '',
      `**✅ ${t('workspace.chatScenarioCompletedTitle', 'Выполненные условия')}:**`,
      doneMd,
      '',
      `**🎯 ${t('workspace.chatScenarioPlannedTitle', 'Намеченные условия')}:**`,
      plannedMd,
    ].filter((line) => line !== undefined).join('\n');
    appendMessage('assistant', introMd);
  }
}

/**
 * Подгружает активный сценарий покупки с сервера при открытии панели чата.
 */
export async function loadActivePurchaseScenario({ postIntroIfEmpty = false } = {}) {
  try {
    const wsId = resolveCurrentWorkspaceId() || '';
    const res = await fetchJson('/api/v1/workspaces/telegram-scenario/status');
    const scen = res && res.scenario ? res.scenario : null;
    if (!scen || !scen.chat_scenario) {
      renderPurchaseScenarioTracker(null);
      return;
    }
    const scenWs = String(scen.workspace_id || '').normalize('NFC');
    if (wsId && scenWs && wsId !== scenWs) {
      renderPurchaseScenarioTracker(null);
      return;
    }
    const msgsEl = getWorkspaceChatElement('#ws-chat-messages');
    const isEmpty = !msgsEl || msgsEl.children.length === 0;
    renderPurchaseScenarioTracker(scen.chat_scenario, {
      postIntro: postIntroIfEmpty && isEmpty,
      runId: scen.run_id || null,
    });
  } catch (_) {
    // Тихо игнорируем при недоступности эндпоинта
  }
}

/**
 * Возвращает корневой DOM-контейнер панели чата рабочего пространства.
 * @returns {HTMLElement|null}
 */
export function getWorkspaceChatContainer() {
  return document.getElementById('subpane-ws-chat') || document.getElementById('panel-chat') || document.getElementById('tab-workspace') || document;
}

/**
 * Ищет элемент внутри контейнера панели чата с fallback на глобальный document.
 * Предотвращает коллизии идентификаторов с выделенной вкладкой #tab-chat.
 * @param {string} selector - CSS селектор элемента
 * @returns {HTMLElement|null}
 */
export function getWorkspaceChatElement(selector) {
  const container = getWorkspaceChatContainer();
  if (container && container !== document) {
    const el = container.querySelector(selector);
    if (el) return el;
  }
  return document.querySelector(selector);
}



/**
 * Экранирует HTML-спецсимволы для безопасного отображения пользовательского ввода.
 * @param {string} str - Исходный текст.
 * @returns {string} Экранированный текст.
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Рендерит текст сообщения в безопасный HTML (с поддержкой Markdown при наличии marked).
 * @param {string} text - Исходный текст ответа.
 * @returns {string} HTML-разметка.
 */
function renderMessageContent(text) {
  if (typeof window !== 'undefined' && window.marked && typeof window.marked.parse === 'function') {
    try {
      return window.marked.parse(text);
    } catch (_) {}
  }
  return escapeHtml(text).replace(/\n/g, '<br/>');
}

/**
 * Прокручивает окно диалога к последнему сообщению.
 */
function scrollToBottom() {
  const windowEl = getWorkspaceChatElement('#ws-chat-response-window');
  if (windowEl) {
    windowEl.scrollTop = windowEl.scrollHeight;
  }
}

/**
 * Добавляет сообщение в окно диалога.
 * @param {'user' | 'assistant'} sender - Отправитель сообщения.
 * @param {string} text - Текст сообщения.
 * @param {boolean} [isPending=false] - Флаг ожидания ответа (с индикатором загрузки).
 * @returns {HTMLElement} Созданный DOM-элемент сообщения.
 */
function appendMessage(sender, text, isPending = false) {
  const container = getWorkspaceChatElement('#ws-chat-messages');
  const emptyState = getWorkspaceChatElement('#ws-chat-empty-state');
  if (emptyState) {
    emptyState.classList.add('d-none');
  }
  if (!container) return null;

  const msgDiv = document.createElement('div');
  const isUser = sender === 'user';

  msgDiv.className = isUser
    ? 'align-self-start chat-msg-user shadow-xs'
    : 'align-self-start chat-msg-bot shadow-xs';

  const isHebrew =
    document.documentElement.getAttribute('dir') === 'rtl' ||
    (document.documentElement.lang || '').startsWith('he') ||
    /[\u0590-\u05FF]/.test(text || '');
  if (isHebrew) {
    container.setAttribute('dir', 'rtl');
    msgDiv.setAttribute('dir', 'rtl');
  }

  if (isPending) {
    msgDiv.setAttribute('data-pending', 'true');
    msgDiv.innerHTML = `
      <div class="d-flex align-items-center gap-2 text-secondary small py-1">
        <span class="spinner-border spinner-border-sm text-primary" role="status"></span>
        <span>${t('workspace.chatAiThinking', 'ИИ формирует ответ...')}</span>
      </div>
    `;
  } else {
    msgDiv.innerHTML = renderMessageContent(text);
  }

  container.appendChild(msgDiv);
  scrollToBottom();
  return msgDiv;
}

/**
 * Очищает историю сообщений чата и возвращает стартовое состояние.
 */
export function clearChatHistory() {
  const container = getWorkspaceChatElement('#ws-chat-messages');
  const emptyState = getWorkspaceChatElement('#ws-chat-empty-state');
  const statusEl = getWorkspaceChatElement('#ws-chat-status');

  if (container) {
    container.innerHTML = '';
  }
  if (emptyState) {
    emptyState.classList.remove('d-none');
  }
  if (statusEl) {
    statusEl.textContent = t('workspace.chatReadyStatus', 'Готов к диалогу');
  }
}

/**
 * Извлекает активный идентификатор рабочего пространства с многоуровневым fallback.
 * @returns {string|null}
 */
export function resolveCurrentWorkspaceId() {
  // 1. Коллбек, переданный при инициализации (из main.js)
  let wsId = typeof getWorkspaceIdCallback === 'function' ? getWorkspaceIdCallback() : null;
  if (wsId) return String(wsId).trim().normalize('NFC');

  // 2. Модуль панели выбора рабочей области
  wsId = getCurrentWorkspaceId();
  if (wsId) return String(wsId).trim().normalize('NFC');

  // 3. Глобальная переменная на объекте window
  if (typeof window !== 'undefined' && window.currentWorkspaceId) {
    return String(window.currentWorkspaceId).trim().normalize('NFC');
  }

  // 4. Верхний селектор рабочего пространства
  if (typeof window !== 'undefined' && typeof window.getActiveWorkspaceId === 'function') {
    const act = window.getActiveWorkspaceId();
    if (act) return String(act).trim().normalize('NFC');
  }

  // 5. Разбор URL hash (#tab-workspace#panel-chat#workspace=<wsId>)
  if (typeof location !== 'undefined' && location.hash) {
    const match = location.hash.match(/workspace=([^&/#]+)/i);
    if (match && match[1]) {
      try {
        return decodeURIComponent(match[1]).trim().normalize('NFC');
      } catch (_) {
        return match[1].trim().normalize('NFC');
      }
    }
  }

  // 6. DOM-селектор рабочих областей #ws-selector
  if (typeof document !== 'undefined') {
    const selector = document.getElementById('ws-selector');
    if (selector && selector.value) {
      return String(selector.value).trim().normalize('NFC');
    }
  }

  // 7. Сохраненное значение в localStorage
  if (typeof localStorage !== 'undefined') {
    try {
      const stored = localStorage.getItem('ai_assistant_active_workspace');
      if (stored) return String(stored).trim().normalize('NFC');
    } catch (_) {}
  }

  return null;
}

export function extractFactCommandText(rawText) {
  const trimmed = (rawText || '').trim();
  const match = trimmed.match(/^(?:\/fact|\/факт|fact:|факт:|עובדה:)\s+(.+)$/i);
  return match ? match[1].trim() : null;
}

export function extractTaskCommandText(rawText) {
  const trimmed = (rawText || '').trim();
  const match = trimmed.match(/^(?:\/task|\/задача|\/завдання|task:|задача:|завдання:|משימה:)\s+(.+)$/i);
  return match ? match[1].trim() : null;
}

/**
 * Ставит новую задачу из панели чата рабочей области с привязкой к базе знаний и календарю.
 * @param {string|null} [taskOverride=null] - Явный текст задачи (если не передан, берётся из поля ввода).
 */
export async function addTaskFromChat(taskOverride = null) {
  if (isSending) return;

  const inputEl = getWorkspaceChatElement('#ws-chat-input');
  const sendBtn = getWorkspaceChatElement('#ws-chat-send-btn');
  const addFactBtn = getWorkspaceChatElement('#ws-chat-add-fact-btn');
  const addTaskBtn = getWorkspaceChatElement('#ws-chat-add-task-btn');
  const statusEl = getWorkspaceChatElement('#ws-chat-status');

  const rawText = taskOverride !== null ? String(taskOverride).trim() : (inputEl ? inputEl.value.trim() : '');
  if (!rawText) {
    if (inputEl) {
      inputEl.value = t(
        'workspace.chatTaskDefaultPrompt',
        'Связаться с ветеринаром и страховым агентом, согласовать с ними дату и время осмотра',
      );
      inputEl.focus();
    }
    return;
  }

  isSending = true;
  if (taskOverride === null && inputEl) inputEl.value = '';
  if (sendBtn) sendBtn.disabled = true;
  if (addFactBtn) addFactBtn.disabled = true;
  if (addTaskBtn) addTaskBtn.disabled = true;
  if (statusEl) statusEl.textContent = t('workspace.chatAddingTaskStatus', 'Постановка задачи...');

  appendMessage('user', `🎯 ${rawText}`);
  const pendingBubble = appendMessage('assistant', '', true);
  const wsId = resolveCurrentWorkspaceId();
  const curLang =
    (typeof window !== 'undefined' && window.i18n && window.i18n.lang) ||
    (typeof document !== 'undefined' && document.documentElement.lang) ||
    'ru';

  try {
    if (!wsId) {
      throw new Error(t('workspace.chatErrorNoWorkspace', 'Не выбрана рабочая область'));
    }

    const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(wsId)}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_text: rawText,
        language: curLang,
      }),
    });

    if (res && res.scenario && res.scenario.chat_scenario) {
      renderPurchaseScenarioTracker(res.scenario.chat_scenario, { postIntro: false });
    }

    const confirmText =
      res.summary_markdown ||
      `✅ **${t('workspace.chatTaskSavedMsg', 'Задача поставлена и сохранена')}:** \`${res.document_id || 'chat_tasks.md'}\`\n\n> ${escapeHtml(res.task_text || rawText)}`;

    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      pendingBubble.innerHTML = renderMessageContent(confirmText);
    }
    if (statusEl) {
      statusEl.textContent = t('workspace.chatTaskSavedStatus', 'Задача поставлена');
    }
    document.dispatchEvent(new CustomEvent('workspace:tasksUpdated', { detail: { workspaceId: wsId, result: res } }));
    document.dispatchEvent(new CustomEvent('workspace:changed', { detail: { workspaceId: wsId } }));
  } catch (err) {
    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      const errPrefix = t('workspace.chatTaskAddError', 'Ошибка постановки задачи:');
      pendingBubble.innerHTML = `
        <div class="text-danger small d-flex align-items-center gap-1.5">
          <i class="bi bi-exclamation-triangle-fill"></i>
          <span>${errPrefix} ${escapeHtml(err.message || String(err))}</span>
        </div>
      `;
    }
    if (statusEl) {
      statusEl.textContent = t('workspace.chatErrorStatus', 'Ошибка генерации');
    }
  } finally {
    isSending = false;
    if (sendBtn) sendBtn.disabled = false;
    if (addFactBtn) addFactBtn.disabled = false;
    if (addTaskBtn) addTaskBtn.disabled = false;
    if (inputEl) inputEl.focus();
    scrollToBottom();
  }
}

/**
 * Сохраняет введённое утверждение как новый факт во внутренние файлы рабочей области и базу знаний.
 * @param {string|null} [factOverride=null] - Явный текст факта (если не передан, берётся из поля ввода).
 */
export async function addFactFromChat(factOverride = null) {
  if (isSending) return;

  const inputEl = getWorkspaceChatElement('#ws-chat-input');
  const sendBtn = getWorkspaceChatElement('#ws-chat-send-btn');
  const addFactBtn = getWorkspaceChatElement('#ws-chat-add-fact-btn');
  const statusEl = getWorkspaceChatElement('#ws-chat-status');

  const rawText = factOverride !== null ? String(factOverride).trim() : (inputEl ? inputEl.value.trim() : '');
  if (!rawText) return;

  isSending = true;
  if (factOverride === null && inputEl) inputEl.value = '';
  if (sendBtn) sendBtn.disabled = true;
  if (addFactBtn) addFactBtn.disabled = true;
  if (statusEl) statusEl.textContent = t('workspace.chatAddingFactStatus', 'Сохранение факта...');

  appendMessage('user', `📌 ${rawText}`);
  const pendingBubble = appendMessage('assistant', '', true);
  const wsId = resolveCurrentWorkspaceId();

  try {
    if (!wsId) {
      throw new Error(t('workspace.chatErrorNoWorkspace', 'Не выбрана рабочая область'));
    }

    const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(wsId)}/facts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fact_text: rawText }),
    });

    const docName = res.document_id || 'chat_facts.md';
    const commitShort = (res.commit_hash || 'HEAD').slice(0, 8);
    const savedPrefix = t('workspace.chatFactSavedMsg', 'Факт сохранён во внутренний файл и базу знаний');
    const factsInFileLabel = t('workspace.chatFactsInFile', 'фактов в файле');
    const confirmText = `✅ **${savedPrefix}:** \`${docName}\` (Git: \`${commitShort}\`, ${factsInFileLabel}: **${res.facts_count || 1}**)\n\n> ${escapeHtml(res.fact_text || rawText)}`;

    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      pendingBubble.innerHTML = renderMessageContent(confirmText);
    }
    if (statusEl) {
      statusEl.textContent = t('workspace.chatFactSavedStatus', 'Факт добавлен');
    }
    document.dispatchEvent(new CustomEvent('workspace:factsUpdated', { detail: { workspaceId: wsId, result: res } }));
  } catch (err) {
    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      const errPrefix = t('workspace.chatFactAddError', 'Ошибка добавления факта:');
      pendingBubble.innerHTML = `
        <div class="text-danger small d-flex align-items-center gap-1.5">
          <i class="bi bi-exclamation-triangle-fill"></i>
          <span>${errPrefix} ${escapeHtml(err.message || String(err))}</span>
        </div>
      `;
    }
    if (statusEl) {
      statusEl.textContent = t('workspace.chatErrorStatus', 'Ошибка генерации');
    }
  } finally {
    isSending = false;
    if (sendBtn) sendBtn.disabled = false;
    if (addFactBtn) addFactBtn.disabled = false;
    if (inputEl) inputEl.focus();
    scrollToBottom();
  }
}

/**
 * Отправляет пользовательское сообщение в ИИ и отображает ответ в окне диалога.
 * @param {string|null} [promptOverride=null] - Явный текст запроса (например, из трекера сценария).
 * @param {string|null} [conditionIdToComplete=null] - ID условия сценария, которое отметить выполненным после ответа.
 */
export async function sendChatMessage(promptOverride = null, conditionIdToComplete = null) {
  if (isSending) return;

  const inputEl = getWorkspaceChatElement('#ws-chat-input');
  const sendBtn = getWorkspaceChatElement('#ws-chat-send-btn');
  const statusEl = getWorkspaceChatElement('#ws-chat-status');

  const text = promptOverride !== null ? String(promptOverride).trim() : (inputEl ? inputEl.value.trim() : '');
  if (!text) return;

  const cmdTask = promptOverride === null ? extractTaskCommandText(text) : null;
  if (cmdTask) {
    if (inputEl) inputEl.value = '';
    await addTaskFromChat(cmdTask);
    return;
  }

  const cmdFact = promptOverride === null ? extractFactCommandText(text) : null;
  if (cmdFact) {
    if (inputEl) inputEl.value = '';
    await addFactFromChat(cmdFact);
    return;
  }

  isSending = true;
  if (promptOverride === null && inputEl) inputEl.value = '';
  if (sendBtn) sendBtn.disabled = true;
  if (statusEl) statusEl.textContent = t('workspace.chatSendingStatus', 'Отправка запроса...');

  // 1. Отображаем сообщение пользователя
  appendMessage('user', text);

  // 2. Отображаем временный блок ожидания ответа
  const pendingBubble = appendMessage('assistant', '', true);

  const wsId = resolveCurrentWorkspaceId();
  let responseText = '';
  let durationMs = 0;

  try {
    // Fail-Fast: чат работает строго в контексте выбранной рабочей области
    if (!wsId) {
      throw new Error(t('workspace.chatErrorNoWorkspace', 'Не выбрана рабочая область'));
    }

    // Ответ формируется ТОЛЬКО по документам рабочей области (контур /api/v1/ask).
    // Прямой вызов модели (/api/v1/chat/test-model) запрещён: он подмешивал общие знания из интернета.
    const askRes = await fetchJson('/api/v1/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: text,
        workspace_id: wsId,
        language: getCurrentLanguage(),
        mode: 'local_first',
      }),
    });

    responseText = askRes && askRes.answer ? askRes.answer : t('workspace.chatNoAnswer', 'Ответ не получен.');
    durationMs = (askRes && askRes.processing && askRes.processing.latency_ms) || 0;

    // Цитаты источников из документов рабочей области
    const docFallback = t('workspace.chatDocumentFallback', 'документ');
    const quotes = ((askRes && askRes.sources) || [])
      .filter((s) => s && s.quote)
      .map((s) => `> ${s.quote}\n>\n> — *${s.document_id || docFallback}*`);
    if (quotes.length) {
      responseText += `\n\n${quotes.join('\n\n')}`;
    }

    // Заменяем блок ожидания готовым ответом
    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      pendingBubble.innerHTML = renderMessageContent(responseText);
    }
    if (statusEl) {
      const succText = t('workspace.chatSuccessStatus', 'Ответ получен');
      const msLabel = t('common.ms', 'мс');
      statusEl.textContent = durationMs > 0 ? `${succText} (${durationMs} ${msLabel})` : succText;
    }
    if (conditionIdToComplete) {
      await updateScenarioCondition(conditionIdToComplete, 'completed');
    }
  } catch (err) {
    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      const errPrefix = t('workspace.chatErrorGeneration', 'Ошибка генерации ответа:');
      pendingBubble.innerHTML = `
        <div class="text-danger small d-flex align-items-center gap-1.5">
          <i class="bi bi-exclamation-triangle-fill"></i>
          <span>${errPrefix} ${escapeHtml(err.message || String(err))}</span>
        </div>
      `;
    }
    if (statusEl) {
      statusEl.textContent = t('workspace.chatErrorStatus', 'Ошибка генерации');
    }
  } finally {
    isSending = false;
    if (sendBtn) sendBtn.disabled = false;
    if (inputEl) inputEl.focus();
    scrollToBottom();
  }
}

/**
 * Загружает выбранные пользователем файлы прямо из окна чата в рабочую область.
 * При загрузке триггерного аудио (דוד משה - שמוליק שיחת טלפון.mp3) автоматически
 * запускает полный сценарий: assets/ -> עסקת קניית פרה -> транскрипт -> PDF в MD -> база знаний -> трекер задач.
 * @param {FileList|File[]} files - Список файлов для загрузки.
 */
export async function uploadFilesFromChat(files) {
  if (isSending || !files || files.length === 0) return;

  const fileArr = Array.from(files);
  const sendBtn = getWorkspaceChatElement('#ws-chat-send-btn');
  const addFactBtn = getWorkspaceChatElement('#ws-chat-add-fact-btn');
  const uploadBtn = getWorkspaceChatElement('#ws-chat-upload-btn');
  const statusEl = getWorkspaceChatElement('#ws-chat-status');

  const wsId = resolveCurrentWorkspaceId();
  if (!wsId) {
    appendMessage('assistant', `⚠️ ${t('workspace.chatErrorNoWorkspace', 'Не выбрана рабочая область')}`);
    return;
  }

  isSending = true;
  if (sendBtn) sendBtn.disabled = true;
  if (addFactBtn) addFactBtn.disabled = true;
  if (uploadBtn) uploadBtn.disabled = true;
  if (statusEl) statusEl.textContent = t('workspace.chatUploadingStatus', 'Загрузка и индексация файла...');

  const namesList = fileArr.map((f) => `\`${f.name}\``).join(', ');
  appendMessage('user', `📎 ${namesList}`);
  const pendingBubble = appendMessage('assistant', '', true);
  if (pendingBubble) {
    const hintText = t(
      'workspace.chatUploadProcessingHint',
      'Загружаю файл в assets/, копирую транскрипт, конвертирую PDF в MD и добавляю всё в базу знаний...',
    );
    pendingBubble.innerHTML = `
      <div class="d-flex align-items-center gap-2 text-secondary small py-1">
        <span class="spinner-border spinner-border-sm text-primary" role="status"></span>
        <span>${escapeHtml(hintText)}</span>
      </div>
    `;
  }

  try {
    const formData = new FormData();
    for (const f of fileArr) {
      formData.append('files', f, f.name);
    }
    formData.append('pdf_mode', 'local');
    formData.append('ocr_mode', 'model');
    formData.append('audio_mode', 'model');
    formData.append('commit_message', `Chat upload: ${fileArr.map((f) => f.name).join(', ')}`);

    const resp = await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/files/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(errText || `HTTP ${resp.status}`);
    }
    const uploadRes = await resp.json();

    // Подгружаем актуальное состояние сценария (выполненные + намеченные задачи)
    let chatScen = null;
    let scenRunId = null;
    try {
      const scenRes = await fetchJson('/api/v1/workspaces/telegram-scenario/status');
      if (scenRes && scenRes.scenario && scenRes.scenario.chat_scenario) {
        chatScen = scenRes.scenario.chat_scenario;
        scenRunId = scenRes.scenario.run_id || null;
      }
    } catch (_) {}

    if (chatScen) {
      renderPurchaseScenarioTracker(chatScen, { postIntro: false, runId: scenRunId });
      const completed = (chatScen.conditions || []).filter((c) => c.status === 'completed');
      const planned = (chatScen.conditions || []).filter((c) => c.status !== 'completed');
      const doneMd = completed
        .map((c) => {
          const ct = getLocalizedField(c, 'title');
          const cd = getLocalizedField(c, 'details');
          return `- [x] **${ct}**${cd ? ` — \`${cd}\`` : ''}`;
        })
        .join('\n');
      const plannedMd = planned
        .map((c) => {
          const ct = getLocalizedField(c, 'title');
          const cd = getLocalizedField(c, 'details');
          return `- [ ] **${ct}**${cd ? ` — ${cd}` : ''}`;
        })
        .join('\n');
      const reportMd = [
        `### ✅ ${getLocalizedField(chatScen, 'title') || 'עסקת קניית פרה'}`,
        getLocalizedField(chatScen, 'summary') || '',
        '',
        `**✅ ${t('workspace.chatScenarioCompletedTitle', 'Выполненные условия')} (${completed.length}):**`,
        doneMd,
        '',
        `**🎯 ${t('workspace.chatScenarioPlannedTitle', 'Намеченные условия')} (${planned.length}):**`,
        plannedMd,
      ].join('\n');
      if (pendingBubble) {
        pendingBubble.removeAttribute('data-pending');
        pendingBubble.innerHTML = renderMessageContent(reportMd);
      }
    } else {
      const addedCount = uploadRes.files_added || fileArr.length;
      const okMsg = `✅ **${t('workspace.chatUploadSuccessStatus', 'Файл загружен в базу знаний')}** (${addedCount}): ${namesList}`;
      if (pendingBubble) {
        pendingBubble.removeAttribute('data-pending');
        pendingBubble.innerHTML = renderMessageContent(okMsg);
      }
    }

    if (statusEl) {
      statusEl.textContent = t('workspace.chatUploadSuccessStatus', 'Файл загружен в базу знаний');
    }
    document.dispatchEvent(new CustomEvent('workspace:changed', { detail: { workspaceId: wsId } }));
  } catch (err) {
    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      const errPrefix = t('workspace.chatUploadError', 'Ошибка загрузки файла:');
      pendingBubble.innerHTML = `
        <div class="text-danger small d-flex align-items-center gap-1.5">
          <i class="bi bi-exclamation-triangle-fill"></i>
          <span>${escapeHtml(errPrefix)} ${escapeHtml(err.message || String(err))}</span>
        </div>
      `;
    }
    if (statusEl) {
      statusEl.textContent = t('workspace.chatErrorStatus', 'Ошибка генерации');
    }
  } finally {
    isSending = false;
    if (sendBtn) sendBtn.disabled = false;
    if (addFactBtn) addFactBtn.disabled = false;
    if (uploadBtn) uploadBtn.disabled = false;
    scrollToBottom();
  }
}

/**
 * Инициализирует обработчики событий панели чата.
 * @param {Function|null} [getWorkspaceIdFn=null] - Функция получения ID активного рабочего пространства.
 */
export function initChatPanel(getWorkspaceIdFn = null) {
  if (typeof getWorkspaceIdFn === 'function') {
    getWorkspaceIdCallback = getWorkspaceIdFn;
  }

  const sendBtn = getWorkspaceChatElement('#ws-chat-send-btn');
  const addFactBtn = getWorkspaceChatElement('#ws-chat-add-fact-btn');
  const addTaskBtn = getWorkspaceChatElement('#ws-chat-add-task-btn');
  const inputEl = getWorkspaceChatElement('#ws-chat-input');
  const clearBtn = getWorkspaceChatElement('#ws-chat-clear-btn');

  if (sendBtn) {
    sendBtn.onclick = () => sendChatMessage();
  }
  if (addFactBtn) {
    addFactBtn.onclick = () => addFactFromChat();
  }
  if (addTaskBtn) {
    addTaskBtn.onclick = () => addTaskFromChat();
  }

  if (inputEl && !inputEl.dataset.wsChatBound) {
    inputEl.dataset.wsChatBound = 'true';
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }

  if (clearBtn) {
    clearBtn.onclick = () => clearChatHistory();
  }

  const uploadBtn = getWorkspaceChatElement('#ws-chat-upload-btn');
  const fileInput = getWorkspaceChatElement('#ws-chat-file-input');
  if (uploadBtn && fileInput && !uploadBtn.dataset.bound) {
    uploadBtn.dataset.bound = 'true';
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async () => {
      if (fileInput.files && fileInput.files.length > 0) {
        const selected = Array.from(fileInput.files);
        fileInput.value = '';
        await uploadFilesFromChat(selected);
      }
    });
  }

  const dropZone = getWorkspaceChatElement('#ws-chat-response-window');
  if (dropZone && !dropZone.dataset.dropBound) {
    dropZone.dataset.dropBound = 'true';
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('border-primary');
    });
    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('border-primary');
    });
    dropZone.addEventListener('drop', async (e) => {
      e.preventDefault();
      dropZone.classList.remove('border-primary');
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        await uploadFilesFromChat(e.dataTransfer.files);
      }
    });
  }

  const toggleBtn = getWorkspaceChatElement('#ws-chat-scenario-toggle-btn');
  const scenarioBody = getWorkspaceChatElement('#ws-chat-scenario-body');
  const toggleIcon = getWorkspaceChatElement('#ws-chat-scenario-toggle-icon');
  if (toggleBtn && scenarioBody && !toggleBtn.dataset.bound) {
    toggleBtn.dataset.bound = 'true';
    toggleBtn.addEventListener('click', () => {
      const collapsed = scenarioBody.classList.toggle('d-none');
      if (toggleIcon) {
        toggleIcon.className = collapsed ? 'bi bi-chevron-down' : 'bi bi-chevron-up';
      }
    });
  }

  if (typeof document !== 'undefined' && !document.body.dataset.wsChatScenarioListenerBound) {
    document.body.dataset.wsChatScenarioListenerBound = 'true';
    document.addEventListener('workspace:scenarioChatStart', (ev) => {
      const scen = ev && ev.detail ? ev.detail.scenario : null;
      if (scen && scen.chat_scenario) {
        renderPurchaseScenarioTracker(scen.chat_scenario, {
          postIntro: true,
          runId: scen.run_id || null,
        });
      }
    });
    document.addEventListener('workspace:changed', () => {
      loadActivePurchaseScenario({ postIntroIfEmpty: false });
    });
    window.addEventListener('i18n:languageChanged', () => {
      if (activePurchaseScenario) {
        renderPurchaseScenarioTracker(activePurchaseScenario, { postIntro: false });
      }
    });
  }
}
