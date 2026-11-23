# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Web Interface - Skills Manager Client Module
# =============================================================================
# Description:
#   Клиентский модуль управления автономными навыками (.agents/skills) в WebGUI.
#   Обеспечивает загрузку каталога навыков, фильтрацию, модальное редактирование
#   секретов и параметров (secrets.json) и тестирование подключений (например, SMTP).
#
# File: skills_manager.js
# Package: apps.ai_assistant.api.webgui.tab_plugins
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 20:33:00
# =============================================================================

let allSkills = [];
let activeSkillName = null;

/**
 * Инициализирует модуль менеджера навыков и обработчики событий.
 */
export function initSkillsManager() {
  const btnReload = document.getElementById('btn-reload-skills');
  if (btnReload) {
    btnReload.addEventListener('click', loadSkillsCatalog);
  }

  const searchInput = document.getElementById('skills-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      renderSkillsCards(filterSkills(searchInput.value));
    });
  }

  const saveBtn = document.getElementById('btn-save-skill-config');
  if (saveBtn) {
    saveBtn.addEventListener('click', saveActiveSkillConfig);
  }

  const testBtn = document.getElementById('btn-test-skill-connection');
  if (testBtn) {
    testBtn.addEventListener('click', testActiveSkillConnection);
  }

  // Первоначальная загрузка
  loadSkillsCatalog();
}

/**
 * Загружает каталог навыков с бэкенда.
 */
export async function loadSkillsCatalog() {
  const grid = document.getElementById('skills-cards-grid');
  if (!grid) return;

  grid.innerHTML = `
    <div class="col-12 text-center py-4 text-secondary">
      <div class="spinner-border spinner-border-sm text-primary mb-2" role="status"></div>
      <div class="small">Загрузка каталога навыков...</div>
    </div>
  `;

  try {
    const res = await fetch('/api/v1/skills');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    allSkills = await res.json();

    const countBadge = document.getElementById('skills-total-count-badge');
    if (countBadge) {
      countBadge.textContent = `${allSkills.length} навыков`;
    }

    renderSkillsCards(allSkills);
  } catch (err) {
    console.error('[skills_manager] Ошибка загрузки навыков:', err);
    grid.innerHTML = `
      <div class="col-12 text-center py-4 text-danger">
        <i class="bi bi-exclamation-triangle fs-4 mb-2"></i>
        <div class="small">Не удалось загрузить каталог навыков: ${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}

/**
 * Фильтрует навыки по поисковому запросу.
 * @param {string} query
 * @returns {Array}
 */
function filterSkills(query) {
  if (!query) return allSkills;
  const q = query.toLowerCase().trim();
  return allSkills.filter(s =>
    (s.id && s.id.toLowerCase().includes(q)) ||
    (s.name && s.name.toLowerCase().includes(q)) ||
    (s.description && s.description.toLowerCase().includes(q))
  );
}

/**
 * Отрисовывает карточки навыков в сетку.
 * @param {Array} skills
 */
function renderSkillsCards(skills) {
  const grid = document.getElementById('skills-cards-grid');
  if (!grid) return;

  if (!skills || skills.length === 0) {
    grid.innerHTML = `
      <div class="col-12 text-center py-5 text-secondary">
        <i class="bi bi-inbox fs-3 mb-2 d-block"></i>
        <div class="small">Навыки не найдены</div>
      </div>
    `;
    return;
  }

  grid.innerHTML = skills.map(skill => {
    const isConfigured = skill.is_configured;
    const hasConfig = skill.has_config;
    const badgeConfig = isConfigured
      ? `<span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-check-circle me-1"></i>Настроен</span>`
      : hasConfig
      ? `<span class="badge bg-warning-subtle text-warning border border-warning-subtle"><i class="bi bi-gear me-1"></i>Требует настройки</span>`
      : `<span class="badge bg-secondary-subtle text-secondary border">Без конфигурации</span>`;

    const configBtn = hasConfig
      ? `<button class="btn btn-sm btn-outline-primary d-flex align-items-center gap-1.5 btn-open-skill-config" data-skill-id="${escapeHtml(skill.id)}">
           <i class="bi bi-sliders"></i>
           <span>Настройки</span>
         </button>`
      : '';

    return `
      <div class="col-12 col-md-6 col-xl-4">
        <div class="card h-100 shadow-sm border hover-shadow transition">
          <div class="card-body d-flex flex-column justify-content-between p-3">
            <div>
              <div class="d-flex align-items-start justify-content-between gap-2 mb-2">
                <div class="d-flex align-items-center gap-2">
                  <span class="fs-4">⚡</span>
                  <div>
                    <h6 class="card-title fw-bold mb-0 text-truncate font-size-95">${escapeHtml(skill.name || skill.id)}</h6>
                    <small class="text-secondary font-size-80 font-monospace">${escapeHtml(skill.id)}</small>
                  </div>
                </div>
                <div>${badgeConfig}</div>
              </div>
              <p class="card-text text-secondary font-size-85 line-clamp-2 mb-3">
                ${escapeHtml(skill.description || 'Описание отсутствует')}
              </p>
            </div>
            <div class="d-flex align-items-center justify-content-between pt-2 border-top mt-auto">
              <span class="text-secondary font-size-75 font-monospace text-truncate" style="max-width: 160px;" title="${escapeHtml(skill.path)}">
                <i class="bi bi-folder2-open me-1"></i>${escapeHtml(skill.path)}
              </span>
              <div class="d-flex align-items-center gap-1.5">
                ${configBtn}
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');

  // Навешиваем слушатели на кнопки открытия конфигурации
  grid.querySelectorAll('.btn-open-skill-config').forEach(btn => {
    btn.addEventListener('click', () => {
      const skillId = btn.getAttribute('data-skill-id');
      if (skillId) openSkillConfigModal(skillId);
    });
  });
}

/**
 * Открывает модальное окно настроек навыка.
 * @param {string} skillId
 */
export async function openSkillConfigModal(skillId) {
  activeSkillName = skillId;
  const modalEl = document.getElementById('modal-skill-config');
  if (!modalEl || !window.bootstrap) return;

  const titleName = document.getElementById('modal-skill-name');
  if (titleName) titleName.textContent = skillId;

  const testBtn = document.getElementById('btn-test-skill-connection');
  if (testBtn) {
    testBtn.classList.toggle('d-none', skillId !== 'smtp-mail-agent');
  }

  const container = document.getElementById('modal-skill-fields-container');
  const alertContainer = document.getElementById('modal-skill-alert-container');
  if (alertContainer) alertContainer.innerHTML = '';

  if (container) {
    container.innerHTML = `
      <div class="text-center py-4 text-secondary">
        <div class="spinner-border spinner-border-sm text-primary mb-2"></div>
        <div class="small">Загрузка параметров...</div>
      </div>
    `;
  }

  const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();

  try {
    const res = await fetch(`/api/v1/skills/${encodeURIComponent(skillId)}/config`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderSkillConfigForm(skillId, data.config, data.is_template);
  } catch (err) {
    console.error('[skills_manager] Ошибка получения конфигурации:', err);
    if (container) {
      container.innerHTML = `
        <div class="alert alert-danger py-2 px-3 small">
          Не удалось загрузить параметры конфигурации: ${escapeHtml(err.message)}
        </div>
      `;
    }
  }
}

/**
 * Отрисовывает форму настроек навыка (специализированную для SMTP/Outlook или универсальную JSON).
 * @param {string} skillId
 * @param {Object} config
 * @param {boolean} isTemplate
 */
function renderSkillConfigForm(skillId, config, isTemplate) {
  const container = document.getElementById('modal-skill-fields-container');
  if (!container) return;

  const alertContainer = document.getElementById('modal-skill-alert-container');
  if (alertContainer && isTemplate) {
    alertContainer.innerHTML = `
      <div class="alert alert-info py-2 px-3 small d-flex align-items-center gap-2 mb-3">
        <i class="bi bi-info-circle-fill"></i>
        <span>Конфигурация еще не сохранена. Заполните поля ниже для создания secrets.json.</span>
      </div>
    `;
  }

  if (skillId === 'smtp-mail-agent') {
    const smtp = config?.smtp || config || {};
    container.innerHTML = `
      <div class="card p-3 border shadow-sm">
        <div class="d-flex align-items-center justify-content-between mb-3 border-bottom pb-2">
          <h6 class="fw-bold mb-0 text-primary d-flex align-items-center gap-2">
            <i class="bi bi-envelope-at"></i>
            <span>Параметры SMTP / Outlook</span>
          </h6>
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-secondary" type="button" id="btn-preset-outlook">
              <i class="bi bi-microsoft me-1"></i>Пресет: Outlook 365
            </button>
            <button class="btn btn-outline-secondary" type="button" id="btn-preset-gmail">
              <i class="bi bi-google me-1"></i>Пресет: Gmail
            </button>
          </div>
        </div>
        <div class="row g-3">
          <div class="col-12 col-md-8">
            <label class="form-label small fw-bold" for="smtp-cfg-host">SMTP Сервер (Host)</label>
            <input class="form-control form-control-sm font-monospace" id="smtp-cfg-host" value="${escapeHtml(smtp.host || 'smtp.office365.com')}" required />
          </div>
          <div class="col-12 col-md-4">
            <label class="form-label small fw-bold" for="smtp-cfg-port">Порт (Port)</label>
            <input class="form-control form-control-sm font-monospace" id="smtp-cfg-port" type="number" value="${escapeHtml(smtp.port || 587)}" required />
          </div>
          <div class="col-12 col-md-6">
            <label class="form-label small fw-bold" for="smtp-cfg-username">Логин / Email (Outlook / Microsoft 365)</label>
            <input class="form-control form-control-sm" id="smtp-cfg-username" type="email" placeholder="user@outlook.com" value="${escapeHtml(smtp.username || '')}" required />
          </div>
          <div class="col-12 col-md-6">
            <label class="form-label small fw-bold" for="smtp-cfg-password">Пароль приложения (App Password)</label>
            <div class="input-group input-group-sm">
              <input class="form-control" id="smtp-cfg-password" type="password" placeholder="Пароль приложения" value="${escapeHtml(smtp.password || '')}" required />
              <button class="btn btn-outline-secondary" type="button" id="btn-toggle-pwd-visibility">
                <i class="bi bi-eye"></i>
              </button>
            </div>
            <div class="form-text font-size-75">Для Outlook с 2FA используйте пароль приложения из аккаунта Microsoft.</div>
          </div>
          <div class="col-12 col-md-6">
            <label class="form-label small fw-bold" for="smtp-cfg-from-email">Email отправителя (From)</label>
            <input class="form-control form-control-sm" id="smtp-cfg-from-email" type="email" placeholder="user@outlook.com" value="${escapeHtml(smtp.from_email || '')}" />
          </div>
          <div class="col-12 col-md-6">
            <label class="form-label small fw-bold" for="smtp-cfg-from-name">Имя отправителя (Display Name)</label>
            <input class="form-control form-control-sm" id="smtp-cfg-from-name" type="text" placeholder="AI Assistant" value="${escapeHtml(smtp.from_name || 'AI Assistant')}" />
          </div>
          <div class="col-12 d-flex align-items-center gap-4 pt-2">
            <div class="form-check form-switch mb-0">
              <input class="form-check-input" type="checkbox" id="smtp-cfg-use-tls" ${smtp.use_tls !== false ? 'checked' : ''} />
              <label class="form-check-label small" for="smtp-cfg-use-tls">STARTTLS (Порт 587)</label>
            </div>
            <div class="form-check form-switch mb-0">
              <input class="form-check-input" type="checkbox" id="smtp-cfg-use-ssl" ${smtp.use_ssl ? 'checked' : ''} />
              <label class="form-check-label small" for="smtp-cfg-use-ssl">SSL (Порт 465)</label>
            </div>
          </div>
        </div>
      </div>
    `;

    // Слушатели для пресетов
    document.getElementById('btn-preset-outlook')?.addEventListener('click', () => {
      document.getElementById('smtp-cfg-host').value = 'smtp.office365.com';
      document.getElementById('smtp-cfg-port').value = '587';
      document.getElementById('smtp-cfg-use-tls').checked = true;
      document.getElementById('smtp-cfg-use-ssl').checked = false;
    });

    document.getElementById('btn-preset-gmail')?.addEventListener('click', () => {
      document.getElementById('smtp-cfg-host').value = 'smtp.gmail.com';
      document.getElementById('smtp-cfg-port').value = '587';
      document.getElementById('smtp-cfg-use-tls').checked = true;
      document.getElementById('smtp-cfg-use-ssl').checked = false;
    });

    // Переключение видимости пароля
    const btnTogglePwd = document.getElementById('btn-toggle-pwd-visibility');
    const pwdInput = document.getElementById('smtp-cfg-password');
    btnTogglePwd?.addEventListener('click', () => {
      const isPwd = pwdInput.type === 'password';
      pwdInput.type = isPwd ? 'text' : 'password';
      btnTogglePwd.innerHTML = isPwd ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
    });
  } else {
    // Универсальный JSON-редактор
    const formatted = JSON.stringify(config, null, 2);
    container.innerHTML = `
      <div>
        <label class="form-label small fw-bold" for="skill-cfg-json">Конфигурация JSON (secrets.json)</label>
        <textarea class="form-control form-control-sm font-monospace" id="skill-cfg-json" rows="12">${escapeHtml(formatted)}</textarea>
      </div>
    `;
  }
}

/**
 * Сохраняет настройки активного навыка.
 */
async function saveActiveSkillConfig() {
  if (!activeSkillName) return;
  const saveBtn = document.getElementById('btn-save-skill-config');
  const alertContainer = document.getElementById('modal-skill-alert-container');
  if (saveBtn) saveBtn.disabled = true;

  try {
    let payloadConfig = {};

    if (activeSkillName === 'smtp-mail-agent') {
      const host = document.getElementById('smtp-cfg-host')?.value?.trim() || '';
      const port = parseInt(document.getElementById('smtp-cfg-port')?.value, 10) || 587;
      const username = document.getElementById('smtp-cfg-username')?.value?.trim() || '';
      const password = document.getElementById('smtp-cfg-password')?.value || '';
      const fromEmail = document.getElementById('smtp-cfg-from-email')?.value?.trim() || username;
      const fromName = document.getElementById('smtp-cfg-from-name')?.value?.trim() || '';
      const useTls = document.getElementById('smtp-cfg-use-tls')?.checked ?? true;
      const useSsl = document.getElementById('smtp-cfg-use-ssl')?.checked ?? false;

      payloadConfig = {
        smtp: {
          host,
          port,
          use_tls: useTls,
          use_ssl: useSsl,
          username,
          password,
          from_email: fromEmail,
          from_name: fromName,
          timeout: 30
        }
      };
    } else {
      const rawJson = document.getElementById('skill-cfg-json')?.value || '{}';
      payloadConfig = JSON.parse(rawJson);
    }

    const res = await fetch(`/api/v1/skills/${encodeURIComponent(activeSkillName)}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config: payloadConfig })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${res.status}`);
    }

    if (alertContainer) {
      alertContainer.innerHTML = `
        <div class="alert alert-success py-2 px-3 small d-flex align-items-center gap-2 mb-3">
          <i class="bi bi-check-circle-fill"></i>
          <span>Настройки успешно сохранены в secrets.json</span>
        </div>
      `;
    }

    await loadSkillsCatalog();
  } catch (err) {
    console.error('[skills_manager] Ошибка сохранения:', err);
    if (alertContainer) {
      alertContainer.innerHTML = `
        <div class="alert alert-danger py-2 px-3 small d-flex align-items-center gap-2 mb-3">
          <i class="bi bi-exclamation-triangle-fill"></i>
          <span>Ошибка сохранения: ${escapeHtml(err.message)}</span>
        </div>
      `;
    }
  } finally {
    if (saveBtn) saveBtn.disabled = false;
  }
}

/**
 * Тестирует соединение для активного навыка (например, SMTP).
 */
async function testActiveSkillConnection() {
  if (!activeSkillName) return;
  const testBtn = document.getElementById('btn-test-skill-connection');
  const alertContainer = document.getElementById('modal-skill-alert-container');
  if (testBtn) {
    testBtn.disabled = true;
    testBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Проверка...';
  }

  try {
    const res = await fetch(`/api/v1/skills/${encodeURIComponent(activeSkillName)}/test-connection`, {
      method: 'POST'
    });

    const data = await res.json();
    const result = data.result || data;

    if (res.ok && result.status === 'success') {
      if (alertContainer) {
        alertContainer.innerHTML = `
          <div class="alert alert-success py-2 px-3 small d-flex align-items-center gap-2 mb-3">
            <i class="bi bi-check-circle-fill fs-5"></i>
            <div>
              <div class="fw-bold">Подключение успешно установлено!</div>
              <div class="font-size-85">${escapeHtml(result.message || 'SMTP сервер ответил успешно')} (${escapeHtml(result.host)}:${escapeHtml(result.port)})</div>
            </div>
          </div>
        `;
      }
    } else {
      if (alertContainer) {
        alertContainer.innerHTML = `
          <div class="alert alert-danger py-2 px-3 small d-flex align-items-center gap-2 mb-3">
            <i class="bi bi-x-circle-fill fs-5"></i>
            <div>
              <div class="fw-bold">Ошибка подключения к серверу:</div>
              <div class="font-size-85">${escapeHtml(result.message || data.detail || 'Не удалось авторизоваться')}</div>
            </div>
          </div>
        `;
      }
    }
  } catch (err) {
    if (alertContainer) {
      alertContainer.innerHTML = `
        <div class="alert alert-danger py-2 px-3 small d-flex align-items-center gap-2 mb-3">
          <i class="bi bi-exclamation-triangle-fill"></i>
          <span>Ошибка тестирования соединения: ${escapeHtml(err.message)}</span>
        </div>
      `;
    }
  } finally {
    if (testBtn) {
      testBtn.disabled = false;
      testBtn.innerHTML = '<i class="bi bi-lightning-charge"></i><span>Проверить соединение</span>';
    }
  }
}

/**
 * Экранирует HTML строку.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
