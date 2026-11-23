/**
 * =============================================================================
 * Process Name: Microsoft 365 Web Interface - Outlook Tab Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер вкладки управления Outlook (Microsoft 365).
 *   Обеспечивает загрузку входящих сообщений, отправку писем и двухуровневую URL маршрутизацию.
 *
 * File: main.js
 * Package: apps/microsoft/webgui/tab_outlook
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-15 21:05:00
 * =============================================================================
 */

let outlookMessages = [];

export async function initOutlookTab() {
  const reloadBtn = document.getElementById('btn-reload-outlook');
  if (reloadBtn) {
    reloadBtn.addEventListener('click', () => {
      loadOutlookMessages();
      loadOutlookStatus();
    });
  }

  const composeForm = document.getElementById('form-outlook-compose');
  if (composeForm) {
    composeForm.addEventListener('submit', handleSendOutlookMessage);
  }

  initTabUrlHashRouting();
  await Promise.all([
    loadOutlookStatus(),
    loadOutlookMessages()
  ]);
}

window.initOutlookTab = initOutlookTab;

async function loadOutlookStatus() {
  const badge = document.getElementById('outlook-status-badge');
  if (!badge) return;

  try {
    const res = await fetch('/api/v1/microsoft/outlook/status');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.configured) {
      badge.className = 'badge bg-success-subtle text-success border border-success-subtle';
      badge.textContent = data.account || 'Outlook Подключен';
    } else {
      badge.className = 'badge bg-warning-subtle text-warning border border-warning-subtle';
      badge.textContent = 'Требуется настройка';
    }
  } catch (err) {
    badge.className = 'badge bg-danger-subtle text-danger border border-danger-subtle';
    badge.textContent = 'Ошибка сервиса';
  }
}

async function loadOutlookMessages() {
  const tbody = document.getElementById('outlook-messages-tbody');
  if (!tbody) return;

  tbody.innerHTML = `
    <tr>
      <td colspan="3" class="text-center py-4 text-secondary">
        <div class="spinner-border spinner-border-sm text-primary mb-2" role="status"></div>
        <div class="small">Загрузка писем Outlook...</div>
      </td>
    </tr>
  `;

  try {
    const res = await fetch('/api/v1/microsoft/outlook/messages?limit=20');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    outlookMessages = await res.json();

    if (!outlookMessages || outlookMessages.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="3" class="text-center py-5 text-secondary">
            <i class="bi bi-inbox fs-3 mb-2 d-block"></i>
            <div class="small">Входящие сообщения не найдены или ящик не сконфигурирован</div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = outlookMessages.map(msg => `
      <tr>
        <td class="text-truncate fw-semibold" style="max-width: 220px;">
          ${escapeHtml(msg.from || 'Неизвестный')}
        </td>
        <td>
          <div class="text-truncate fw-bold text-dark" style="max-width: 480px;">
            ${escapeHtml(msg.subject || '(Без темы)')}
          </div>
        </td>
        <td class="text-secondary font-size-85 text-nowrap">
          ${escapeHtml(msg.date || '')}
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('[OutlookTab] Ошибка выборки писем:', err);
    tbody.innerHTML = `
      <tr>
        <td colspan="3" class="text-center py-4 text-danger">
          <i class="bi bi-exclamation-triangle fs-4 mb-2 d-block"></i>
          <div class="small">Не удалось загрузить сообщения Outlook: ${escapeHtml(err.message)}</div>
        </td>
      </tr>
    `;
  }
}

async function handleSendOutlookMessage(e) {
  e.preventDefault();
  const alertContainer = document.getElementById('outlook-compose-alert');
  const sendBtn = document.getElementById('btn-outlook-send');
  const to = document.getElementById('outlook-compose-to')?.value?.trim();
  const subject = document.getElementById('outlook-compose-subject')?.value?.trim();
  const body = document.getElementById('outlook-compose-body')?.value?.trim();

  if (!to || !subject || !body) return;

  if (sendBtn) {
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Отправка...';
  }

  try {
    const res = await fetch('/api/v1/microsoft/outlook/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to, subject, body, is_html: false })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    if (alertContainer) {
      alertContainer.innerHTML = `
        <div class="alert alert-success py-2 px-3 small d-flex align-items-center gap-2 mb-3">
          <i class="bi bi-check-circle-fill"></i>
          <span>Письмо успешно отправлено через Outlook!</span>
        </div>
      `;
    }
    document.getElementById('form-outlook-compose')?.reset();
  } catch (err) {
    if (alertContainer) {
      alertContainer.innerHTML = `
        <div class="alert alert-danger py-2 px-3 small d-flex align-items-center gap-2 mb-3">
          <i class="bi bi-exclamation-triangle-fill"></i>
          <span>Ошибка отправки: ${escapeHtml(err.message)}</span>
        </div>
      `;
    }
  } finally {
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.innerHTML = '<i class="bi bi-send"></i><span>Отправить</span>';
    }
  }
}

export function initTabUrlHashRouting() {
  const canonicalTabId = 'tab-outlook';
  const syncFromHash = () => {
    const raw = window.location.hash || '';
    if (!raw.includes(canonicalTabId)) return;
    const parts = raw.replace(/^#/, '').split('#');
    let panelPart = parts.find((p) => p.startsWith('panel-'));
    if (!panelPart) {
      const fallback = parts.find((p) => ['inbox', 'compose'].includes(p.toLowerCase()));
      if (fallback) panelPart = `panel-outlook-${fallback.toLowerCase()}`;
    }

    if (panelPart) {
      const btn = document.querySelector(`button[data-panel-id="${panelPart}"]`) ||
                  document.querySelector(`button[data-bs-target="#tab-pane-${panelPart.replace('panel-', '')}"]`);
      if (btn && window.bootstrap && window.bootstrap.Tab) {
        (window.bootstrap.Tab.getInstance?.(btn) || window.bootstrap.Tab.getOrCreateInstance?.(btn) || new window.bootstrap.Tab(btn)).show();
      }
    }
  };

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('#outlookTabNav button[data-panel-id], #outlookTabNav button[data-bs-toggle="pill"]');
    if (btn) {
      let rawPanel = btn.getAttribute('data-panel-id') || btn.getAttribute('data-bs-target')?.replace('#tab-pane-', '')?.replace('#', '');
      const panelId = rawPanel.startsWith('panel-') ? rawPanel : `panel-${rawPanel}`;
      history.replaceState(null, null, `#${canonicalTabId}#${panelId}`);
    }
  });

  window.addEventListener('hashchange', syncFromHash);
  syncFromHash();
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
