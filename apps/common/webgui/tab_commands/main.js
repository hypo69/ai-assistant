/**
 * =============================================================================
 * Process Name: Common WebGUI - User Commands Tab Controller
 * =============================================================================
 * Description:
 *   Контроллер вкладки пользовательской базы знаний команд и сниппетов.
 *   Обеспечивает интерактивный поиск, запуск, модальный редактор, копирование в буфер,
 *   переключение избранного и экспорт в Markdown.
 *
 * File: main.js
 * Package: apps/common/webgui/tab_commands
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-16 01:32:00
 * =============================================================================
 */

let commandsCache = new Map();
let currentExecutingCmd = null;
let searchDebounceTimer = null;

/**
 * Инициализация вкладки команд пользователя.
 */
export async function initCommandsTab() {
  bindEvents();
  await loadCategories();
  await loadCommandsList();

  // Восстановление активной субвкладки из URL хэша
  const hash = window.location.hash || '';
  if (hash.includes('#tab-commands#')) {
    const parts = hash.split('#').filter(Boolean);
    const targetPanel = parts[1];
    if (targetPanel) {
      const btn = document.querySelector(`#commands-subtabs-nav button[data-panel-id="${targetPanel}"]`);
      if (btn && window.bootstrap) {
        bootstrap.Tab.getOrCreateInstance(btn).show();
      }
    }
  }
}

// Экспорт для оркестратора tab-core
window.initCommandsTab = initCommandsTab;

/**
 * Привязка событий элементов вкладки.
 */
function bindEvents() {
  const searchInput = document.getElementById('cmd-filter-search');
  if (searchInput && !searchInput.dataset.bound) {
    searchInput.dataset.bound = 'true';
    searchInput.addEventListener('input', () => {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(loadCommandsList, 250);
    });
  }

  const catFilter = document.getElementById('cmd-filter-category');
  if (catFilter && !catFilter.dataset.bound) {
    catFilter.dataset.bound = 'true';
    catFilter.addEventListener('change', loadCommandsList);
  }

  const shellFilter = document.getElementById('cmd-filter-shell');
  if (shellFilter && !shellFilter.dataset.bound) {
    shellFilter.dataset.bound = 'true';
    shellFilter.addEventListener('change', loadCommandsList);
  }

  const favFilter = document.getElementById('cmd-filter-favorite');
  if (favFilter && !favFilter.dataset.bound) {
    favFilter.dataset.bound = 'true';
    favFilter.addEventListener('change', loadCommandsList);
  }

  const btnRefresh = document.getElementById('btn-commands-refresh');
  if (btnRefresh && !btnRefresh.dataset.bound) {
    btnRefresh.dataset.bound = 'true';
    btnRefresh.addEventListener('click', async () => {
      await loadCategories();
      await loadCommandsList();
    });
  }

  const btnCreate = document.getElementById('btn-commands-create');
  if (btnCreate && !btnCreate.dataset.bound) {
    btnCreate.dataset.bound = 'true';
    btnCreate.addEventListener('click', () => openEditorModal(null));
  }

  const btnExportMd = document.getElementById('btn-commands-export-md');
  if (btnExportMd && !btnExportMd.dataset.bound) {
    btnExportMd.dataset.bound = 'true';
    btnExportMd.addEventListener('click', openMarkdownTab);
  }

  const btnSave = document.getElementById('editor-cmd-btn-save');
  if (btnSave && !btnSave.dataset.bound) {
    btnSave.dataset.bound = 'true';
    btnSave.addEventListener('click', handleSaveCommand);
  }

  const btnDelete = document.getElementById('editor-cmd-btn-delete');
  if (btnDelete && !btnDelete.dataset.bound) {
    btnDelete.dataset.bound = 'true';
    btnDelete.addEventListener('click', handleDeleteCommand);
  }

  const btnExecute = document.getElementById('runner-cmd-btn-execute');
  if (btnExecute && !btnExecute.dataset.bound) {
    btnExecute.dataset.bound = 'true';
    btnExecute.addEventListener('click', handleExecuteCommand);
  }

  const btnCopyAllMd = document.getElementById('btn-cmd-copy-all-md');
  if (btnCopyAllMd && !btnCopyAllMd.dataset.bound) {
    btnCopyAllMd.dataset.bound = 'true';
    btnCopyAllMd.addEventListener('click', () => {
      const text = document.getElementById('commands-markdown-content')?.textContent || '';
      copyTextToClipboard(text);
    });
  }

  // Переключение субвкладки Markdown и синхронизация URL
  const subtabButtons = document.querySelectorAll('#commands-subtabs-nav button[data-bs-toggle="pill"]');
  subtabButtons.forEach(btn => {
    if (!btn.dataset.boundUrl) {
      btn.dataset.boundUrl = 'true';
      btn.addEventListener('shown.bs.tab', () => {
        const panelId = btn.dataset.panelId || btn.dataset.bsTarget?.replace('#pill-cmd-', 'panel-cmd-') || 'panel-cmd-cheatsheet';
        updateUrlWithPanel(panelId);
        if (btn.id === 'pill-cmd-markdown-tab') {
          loadMarkdownContent();
        }
      });
    }
  });
}

/**
 * Синхронизирует активную панель с хэшем URL (#tab-commands#<panel_id>).
 */
export function updateUrlWithPanel(panelId) {
  if (!panelId) return;
  const baseTab = 'tab-commands';
  const cleanPanel = panelId.startsWith('#') ? panelId.slice(1) : panelId;
  const newHash = `#${baseTab}#${cleanPanel}`;
  if (window.location.hash !== newHash) {
    window.history.replaceState(null, '', newHash);
  }
}

/**
 * Загрузка категорий в фильтр и datalist.
 */
async function loadCategories() {
  try {
    const res = await fetch('/api/v1/user-commands/categories');
    if (!res.ok) return;
    const data = await res.json();
    const cats = data.categories || [];

    const selectEl = document.getElementById('cmd-filter-category');
    const datalist = document.getElementById('editor-categories-datalist');
    if (!selectEl) return;

    const currentVal = selectEl.value;
    selectEl.innerHTML = `<option value="all">Все категории</option>`;
    if (datalist) datalist.innerHTML = '';

    cats.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat;
      opt.textContent = cat;
      selectEl.appendChild(opt);

      if (datalist) {
        const dOpt = document.createElement('option');
        dOpt.value = cat;
        datalist.appendChild(dOpt);
      }
    });

    if (cats.includes(currentVal)) {
      selectEl.value = currentVal;
    }
  } catch (err) {
    console.debug('[UserCommands] Ошибка загрузки категорий:', err);
  }
}

/**
 * Загрузка списка команд с учетом фильтрации.
 */
async function loadCommandsList() {
  const q = document.getElementById('cmd-filter-search')?.value.trim() || '';
  const category = document.getElementById('cmd-filter-category')?.value || 'all';
  const shell = document.getElementById('cmd-filter-shell')?.value || 'all';
  const fav = document.getElementById('cmd-filter-favorite')?.checked || false;

  let url = `/api/v1/user-commands/list?limit=250`;
  if (q) url += `&query=${encodeURIComponent(q)}`;
  if (category && category !== 'all') url += `&category=${encodeURIComponent(category)}`;
  if (shell && shell !== 'all') url += `&shell=${encodeURIComponent(shell)}`;
  if (fav) url += `&favorite=true`;

  const grid = document.getElementById('commands-cards-grid');
  const emptyBox = document.getElementById('commands-empty-state');
  const countBadge = document.getElementById('commands-badge-count');

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = data.items || [];

    commandsCache.clear();
    items.forEach(it => commandsCache.set(it.command_id, it));

    if (countBadge) countBadge.textContent = String(items.length);

    if (!grid) return;
    grid.innerHTML = '';

    if (items.length === 0) {
      if (emptyBox) emptyBox.classList.remove('d-none');
      return;
    }
    if (emptyBox) emptyBox.classList.add('d-none');

    items.forEach(it => {
      grid.appendChild(createCommandCard(it));
    });
  } catch (err) {
    console.error('[UserCommands] Ошибка загрузки списка:', err);
  }
}

/**
 * Рендеринг карточки команды.
 */
function createCommandCard(cmd) {
  const col = document.createElement('div');
  col.className = 'col-lg-6 col-md-12';

  const riskBadgeClass = cmd.risk_level === 'danger' ? 'bg-danger' : (cmd.risk_level === 'warn' ? 'bg-warning text-dark' : 'bg-success');
  const shellBadgeClass = cmd.shell === 'powershell' ? 'bg-primary' : (cmd.shell === 'python' ? 'bg-info text-dark' : 'bg-dark');

  col.innerHTML = `
    <div class="cmd-card p-3 h-100 d-flex flex-column" data-command-id="${cmd.command_id}">
      <div class="d-flex justify-content-between align-items-start mb-2 gap-2">
        <div class="d-flex align-items-center gap-2 flex-wrap">
          <i class="bi bi-star-fill cmd-star-btn ${cmd.favorite ? 'active' : ''}" title="Избранное" data-id="${cmd.command_id}"></i>
          <h6 class="mb-0 fw-bold">${escapeHtml(cmd.title)}</h6>
          <span class="badge ${shellBadgeClass} small">${cmd.shell}</span>
          <span class="badge bg-secondary small">${escapeHtml(cmd.category)}</span>
          <span class="badge ${riskBadgeClass} small">${cmd.risk_level}</span>
        </div>
        <div class="d-flex align-items-center gap-1 ms-auto">
          <button class="btn btn-sm btn-outline-secondary py-0 px-2 btn-cmd-edit" title="Редактировать" data-id="${cmd.command_id}">
            <i class="bi bi-pencil"></i>
          </button>
          <button class="btn btn-sm btn-outline-success py-0 px-2 btn-cmd-run" title="Запустить" data-id="${cmd.command_id}">
            <i class="bi bi-play-fill"></i>
          </button>
        </div>
      </div>

      ${cmd.description ? `<p class="small text-secondary mb-2">${escapeHtml(cmd.description)}</p>` : ''}

      <div class="cmd-code-box flex-grow-1 mb-2">
        <button class="btn btn-sm btn-outline-secondary position-absolute top-0 end-0 m-1 py-0 px-1 cmd-btn-copy" title="Копировать команду" data-code="${encodeURIComponent(cmd.command)}">
          <i class="bi bi-clipboard"></i>
        </button>
        <code>${escapeHtml(cmd.command)}</code>
      </div>

      <div class="d-flex justify-content-between align-items-center mt-auto pt-1">
        <div class="d-flex gap-1 flex-wrap">
          ${(cmd.tags || []).map(t => `<span class="badge bg-body-secondary text-secondary small cmd-tag-badge">${escapeHtml(t)}</span>`).join('')}
        </div>
        <small class="text-secondary font-monospace" style="font-size: 0.75rem;">Запусков: ${cmd.execution_count}</small>
      </div>
    </div>
  `;

  // Обработчики кнопок карточки
  col.querySelector('.cmd-star-btn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    handleToggleFavorite(cmd.command_id);
  });

  col.querySelector('.btn-cmd-edit')?.addEventListener('click', () => openEditorModal(cmd.command_id));
  col.querySelector('.btn-cmd-run')?.addEventListener('click', () => openRunnerModal(cmd.command_id));

  col.querySelector('.cmd-btn-copy')?.addEventListener('click', (e) => {
    e.stopPropagation();
    copyTextToClipboard(cmd.command);
  });

  return col;
}

/**
 * Переключение статуса 'избранное'.
 */
async function handleToggleFavorite(cmdId) {
  try {
    const res = await fetch(`/api/v1/user-commands/toggle-favorite/${cmdId}`, { method: 'POST' });
    if (!res.ok) return;
    const data = await res.json();
    const item = commandsCache.get(cmdId);
    if (item) {
      item.favorite = data.favorite;
      const star = document.querySelector(`.cmd-card[data-command-id="${cmdId}"] .cmd-star-btn`);
      if (star) {
        star.classList.toggle('active', data.favorite);
      }
    }
  } catch (err) {
    console.error('[UserCommands] Ошибка toggle-favorite:', err);
  }
}

/**
 * Открытие модального окна редактора.
 */
function openEditorModal(cmdId) {
  const modalEl = document.getElementById('modal-command-editor');
  if (!modalEl || !window.bootstrap) return;

  const form = document.getElementById('command-editor-form');
  if (form) form.reset();

  const btnDel = document.getElementById('editor-cmd-btn-delete');
  const titleEl = document.getElementById('modal-command-editor-title');

  if (cmdId && commandsCache.has(cmdId)) {
    const cmd = commandsCache.get(cmdId);
    document.getElementById('editor-cmd-id').value = cmd.command_id;
    document.getElementById('editor-cmd-title').value = cmd.title;
    document.getElementById('editor-cmd-category').value = cmd.category;
    document.getElementById('editor-cmd-shell').value = cmd.shell;
    document.getElementById('editor-cmd-tags').value = (cmd.tags || []).join(', ');
    document.getElementById('editor-cmd-risk').value = cmd.risk_level;
    document.getElementById('editor-cmd-favorite').checked = Boolean(cmd.favorite);
    document.getElementById('editor-cmd-desc').value = cmd.description || '';
    document.getElementById('editor-cmd-code').value = cmd.command;

    if (btnDel) btnDel.style.display = 'inline-block';
    if (titleEl) titleEl.querySelector('span').textContent = 'Редактирование команды';
  } else {
    document.getElementById('editor-cmd-id').value = '';
    document.getElementById('editor-cmd-shell').value = 'powershell';
    document.getElementById('editor-cmd-risk').value = 'safe';
    document.getElementById('editor-cmd-category').value = 'Общее';

    if (btnDel) btnDel.style.display = 'none';
    if (titleEl) titleEl.querySelector('span').textContent = 'Новая команда';
  }

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

/**
 * Сохранение команды из редактора.
 */
async function handleSaveCommand() {
  const title = document.getElementById('editor-cmd-title')?.value.trim();
  const command = document.getElementById('editor-cmd-code')?.value.trim();
  if (!title || !command) {
    alert('Пожалуйста, заполните название и текст команды.');
    return;
  }

  const cmdId = document.getElementById('editor-cmd-id')?.value.trim() || null;
  const category = document.getElementById('editor-cmd-category')?.value.trim() || 'Общее';
  const shell = document.getElementById('editor-cmd-shell')?.value || 'powershell';
  const tagsStr = document.getElementById('editor-cmd-tags')?.value.trim() || '';
  const risk = document.getElementById('editor-cmd-risk')?.value || 'safe';
  const favorite = document.getElementById('editor-cmd-favorite')?.checked || false;
  const description = document.getElementById('editor-cmd-desc')?.value.trim() || '';

  const tags = tagsStr.split(/[,;\s]+/).filter(Boolean).map(t => t.startsWith('#') ? t : `#${t}`);

  // Извлечение плейсхолдеров вида <PARAM>
  const placeholders = {};
  const matches = command.match(/<[A-Za-z0-9_-]+>/g) || [];
  matches.forEach(m => { placeholders[m] = `Параметр ${m}`; });

  const payload = {
    command_id: cmdId,
    title,
    command,
    shell,
    category,
    description,
    tags,
    placeholders,
    risk_level: risk,
    favorite,
  };

  try {
    const res = await fetch('/api/v1/user-commands/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const modalEl = document.getElementById('modal-command-editor');
    if (modalEl && window.bootstrap) {
      bootstrap.Modal.getInstance(modalEl)?.hide();
    }

    await loadCategories();
    await loadCommandsList();
  } catch (err) {
    alert(`Ошибка сохранения команды: ${err.message}`);
  }
}

/**
 * Удаление команды.
 */
async function handleDeleteCommand() {
  const cmdId = document.getElementById('editor-cmd-id')?.value.trim();
  if (!cmdId) return;
  if (!confirm('Вы действительно хотите удалить эту команду?')) return;

  try {
    const res = await fetch(`/api/v1/user-commands/item/${cmdId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const modalEl = document.getElementById('modal-command-editor');
    if (modalEl && window.bootstrap) {
      bootstrap.Modal.getInstance(modalEl)?.hide();
    }

    await loadCategories();
    await loadCommandsList();
  } catch (err) {
    alert(`Ошибка удаления команды: ${err.message}`);
  }
}

/**
 * Открытие модального окна запуска команды.
 */
function openRunnerModal(cmdId) {
  const cmd = commandsCache.get(cmdId);
  if (!cmd) return;
  currentExecutingCmd = cmd;

  const modalEl = document.getElementById('modal-command-runner');
  if (!modalEl || !window.bootstrap) return;

  const preview = document.getElementById('runner-cmd-preview');
  if (preview) preview.textContent = cmd.command;

  const paramsBox = document.getElementById('runner-cmd-params-box');
  const paramsFields = document.getElementById('runner-cmd-params-fields');
  const placeholders = Object.keys(cmd.placeholders || {});

  if (placeholders.length > 0 && paramsBox && paramsFields) {
    paramsBox.classList.remove('d-none');
    paramsFields.innerHTML = '';
    placeholders.forEach(ph => {
      const col = document.createElement('div');
      col.className = 'col-md-6';
      col.innerHTML = `
        <label class="form-label small fw-semibold font-monospace mb-1">${escapeHtml(ph)}</label>
        <input type="text" class="form-control form-control-sm font-monospace runner-param-input" data-placeholder="${escapeHtml(ph)}" placeholder="Значение для ${escapeHtml(ph)}">
      `;
      paramsFields.appendChild(col);
    });
  } else if (paramsBox) {
    paramsBox.classList.add('d-none');
  }

  const outBox = document.getElementById('runner-cmd-output-box');
  if (outBox) outBox.classList.add('d-none');

  bootstrap.Modal.getOrCreateInstance(modalEl).show();
}

/**
 * Запуск команды на исполнение.
 */
async function handleExecuteCommand() {
  if (!currentExecutingCmd) return;

  const btn = document.getElementById('runner-cmd-btn-execute');
  const outBox = document.getElementById('runner-cmd-output-box');
  const consoleEl = document.getElementById('runner-cmd-console-output');
  const badge = document.getElementById('runner-cmd-status-badge');
  const asAdmin = document.getElementById('runner-cmd-as-admin')?.checked || false;

  const params = {};
  document.querySelectorAll('.runner-param-input').forEach(input => {
    const ph = input.dataset.placeholder;
    if (ph && input.value.trim()) {
      params[ph] = input.value.trim();
    }
  });

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Выполняется...`;
  }
  if (outBox) outBox.classList.remove('d-none');
  if (consoleEl) consoleEl.textContent = 'Инициализация подпроцесса...';

  try {
    const res = await fetch('/api/v1/user-commands/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        command_id: currentExecutingCmd.command_id,
        parameters: params,
        as_admin: asAdmin,
        timeout_sec: 30,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (badge) {
      badge.textContent = `Код: ${data.exit_code} (${data.duration_ms} мс)`;
      badge.className = data.exit_code === 0 ? 'badge bg-success' : 'badge bg-danger';
    }

    let output = '';
    if (data.stdout) output += data.stdout;
    if (data.stderr) output += (output ? '\n[STDERR]\n' : '') + data.stderr;
    if (!output) output = '(Команда выполнена без вывода)';

    if (consoleEl) consoleEl.textContent = output;
  } catch (err) {
    if (consoleEl) consoleEl.textContent = `Сбой выполнения: ${err.message}`;
    if (badge) {
      badge.textContent = 'Ошибка';
      badge.className = 'badge bg-danger';
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="bi bi-play-fill"></i> Выполнить`;
    }
  }
}

/**
 * Загрузка Markdown-представления шпаргалки.
 */
async function loadMarkdownContent() {
  const container = document.getElementById('commands-markdown-content');
  if (!container) return;
  container.textContent = 'Загрузка Markdown шпаргалки...';

  try {
    const res = await fetch('/api/v1/user-commands/export-markdown');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    container.textContent = text || '(Шпаргалка пуста)';
  } catch (err) {
    container.textContent = `Ошибка загрузки шпаргалки: ${err.message}`;
  }
}

function openMarkdownTab() {
  const tabTrigger = document.getElementById('pill-cmd-markdown-tab');
  if (tabTrigger && window.bootstrap) {
    bootstrap.Tab.getOrCreateInstance(tabTrigger).show();
  }
}

/**
 * Копирование текста в буфер обмена с уведомлением.
 */
async function copyTextToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    showMiniToast('Команда скопирована в буфер обмена!');
  } catch (e) {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showMiniToast('Команда скопирована!');
  }
}

function showMiniToast(msg) {
  let toast = document.getElementById('cmd-mini-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'cmd-mini-toast';
    toast.className = 'position-fixed bottom-0 end-0 m-3 p-2 px-3 bg-dark text-white rounded shadow-lg small';
    toast.style.zIndex = '9999';
    toast.style.transition = 'opacity 0.3s ease';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = '1';
  toast.style.display = 'block';
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => { toast.style.display = 'none'; }, 300);
  }, 2000);
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
