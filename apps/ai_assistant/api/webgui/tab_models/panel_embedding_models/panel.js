/**
 * =============================================================================
 * Название: Панель управления моделями эмбеддингов (WebAssembly/WebGPU, Gemini, Ollama, OpenAI, Hash)
 * =============================================================================
 * Описание:
 *   Управляет выбором активного провайдера и модели эмбеддингов по образцу
 *   панели каталога LLM-моделей, сохранением в config.json / user_settings
 *   и живым тестированием векторизации (для local_bert — прямо в браузере
 *   через Web Worker с Transformers.js + WebAssembly / WebGPU).
 *
 * Файл: apps/ai_assistant/api/webgui/tab_models/panel_embedding_models/panel.js
 * Пакет: apps/ai_assistant/api/webgui/tab_models/panel_embedding_models
 * Автор: hypo69
 * Updated: 2026-11-20 00:12:00
 * =============================================================================
 */

import { escapeHtml, showModelsNotification } from '../common/ui_utils.js';

let _embeddingCatalog = {};
let _embeddingMeta = {};

function _t(key, fallback) {
  return typeof window.t === 'function' ? window.t(key, fallback) : fallback;
}

function _formatProviderLabel(provider) {
  const labels = {
    local_bert: _t('ui.mdl.emb_prov_local_bert', '⚡ Browser BERT (WebAssembly / WebGPU)'),
    gemini: _t('ui.mdl.emb_prov_gemini', '✨ Google Gemini API'),
    ollama: _t('ui.mdl.emb_prov_ollama', '🦙 Ollama (Local Server)'),
    openai: _t('ui.mdl.emb_prov_openai', '🌐 OpenAI Compatible'),
    hash: _t('ui.mdl.emb_prov_hash', '🔢 Local Hash (Offline Fallback)'),
  };
  return labels[provider] || provider;
}

function _updateRuntimeBadge(provider, modelId) {
  const badge = document.getElementById('embedding-runtime-badge');
  if (!badge) return;

  if (provider === 'local_bert') {
    const meta = (_embeddingMeta.local_bert && _embeddingMeta.local_bert[modelId]) || null;
    const sizeInfo = meta ? ` • ~${meta.size_int8_mb} MB INT8 • dim=${meta.dimensions}` : '';
    badge.textContent = `${_t('ui.mdl.emb_runtime_browser', 'Браузер (WASM/WebGPU)')}${sizeInfo}`;
    badge.className = 'badge bg-info-subtle text-info-emphasis border font-monospace';
  } else if (provider === 'gemini' || provider === 'openai') {
    const dim = (_embeddingMeta.dimensions && _embeddingMeta.dimensions[modelId]) || '';
    badge.textContent = `${_t('ui.mdl.emb_runtime_cloud', 'Облачный API')}${dim ? ` • dim=${dim}` : ''}`;
    badge.className = 'badge bg-primary-subtle text-primary-emphasis border font-monospace';
  } else {
    const dim = (_embeddingMeta.dimensions && _embeddingMeta.dimensions[modelId]) || '';
    badge.textContent = `${_t('ui.mdl.emb_runtime_local', 'Локальный бэкенд')}${dim ? ` • dim=${dim}` : ''}`;
    badge.className = 'badge bg-secondary-subtle text-secondary-emphasis border font-monospace';
  }
}

function _populateEmbeddingModelSelect(provider, selectedModel = '') {
  const modelSelect = document.getElementById('embedding-model-select');
  if (!modelSelect) return;

  const list = _embeddingCatalog[provider] || [];
  modelSelect.innerHTML = '';

  if (list.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = _t('ui.mdl.emb_no_models', 'Нет доступных моделей');
    modelSelect.appendChild(opt);
    return;
  }

  list.forEach((modelId) => {
    const opt = document.createElement('option');
    opt.value = modelId;
    const lbMeta = provider === 'local_bert' && _embeddingMeta.local_bert ? _embeddingMeta.local_bert[modelId] : null;
    if (lbMeta) {
      opt.textContent = `${lbMeta.title} (~${lbMeta.size_int8_mb} MB, dim=${lbMeta.dimensions})`;
    } else {
      const dim = _embeddingMeta.dimensions && _embeddingMeta.dimensions[modelId];
      opt.textContent = dim ? `${modelId} (dim=${dim})` : modelId;
    }
    modelSelect.appendChild(opt);
  });

  if (selectedModel && list.includes(selectedModel)) {
    modelSelect.value = selectedModel;
  } else {
    modelSelect.selectedIndex = 0;
  }

  _updateRuntimeBadge(provider, modelSelect.value);
}

/**
 * Загружает каталог моделей эмбеддингов и текущую активную модель с сервера.
 * @param {boolean} [forceRefresh=false] - Принудительно обновить кэш каталога.
 */
export async function loadEmbeddingModels(forceRefresh = false) {
  const providerSelect = document.getElementById('embedding-provider-select');
  const modelSelect = document.getElementById('embedding-model-select');
  const badgeEl = document.getElementById('saved-default-embedding-badge');
  if (!providerSelect || !modelSelect) return;

  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const url = forceRefresh ? '/api/v1/embeddings/models?refresh=true' : '/api/v1/embeddings/models';
    const [catRes, activeRes] = await Promise.all([
      fetchFn(url),
      fetchFn('/api/v1/embeddings/active-model'),
    ]);

    const catData = typeof catRes.json === 'function' ? await catRes.json() : catRes;
    const activeData = typeof activeRes.json === 'function' ? await activeRes.json() : activeRes;

    _embeddingCatalog = catData.models || {};
    _embeddingMeta = catData.metadata || {};

    const providers = Object.keys(_embeddingCatalog).filter(
      (p) => Array.isArray(_embeddingCatalog[p]) && _embeddingCatalog[p].length > 0
    );

    providerSelect.innerHTML = '';
    providers.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p;
      opt.textContent = _formatProviderLabel(p);
      providerSelect.appendChild(opt);
    });

    const activeProv = providers.includes(activeData.provider) ? activeData.provider : (providers[0] || 'local_bert');
    const activeModel = activeData.model || '';

    providerSelect.value = activeProv;
    _populateEmbeddingModelSelect(activeProv, activeModel);

    if (badgeEl) {
      const displayModel = modelSelect.value || activeModel;
      badgeEl.textContent = displayModel ? `${activeProv}: ${displayModel}` : _t('ui.mdl.txt_43e40d49', 'Не задана');
      badgeEl.className = displayModel
        ? 'badge bg-success font-monospace px-2 py-1'
        : 'badge bg-secondary font-monospace px-2 py-1';
    }

    if (forceRefresh) {
      showModelsNotification(_t('ui.mdl.emb_refreshed', 'Список моделей эмбеддингов обновлён'), 'success');
    }
  } catch (err) {
    console.error('Ошибка загрузки моделей эмбеддингов:', err);
    showModelsNotification(`${_t('ui.mdl.emb_load_error', 'Ошибка загрузки моделей эмбеддингов')}: ${err.message}`, 'danger');
  }
}

/**
 * Сохраняет выбранную модель эмбеддингов как активную в конфигурации.
 */
export async function saveEmbeddingModel(showNotify = true) {
  const provider = document.getElementById('embedding-provider-select')?.value || '';
  const model = document.getElementById('embedding-model-select')?.value || '';
  if (!provider || !model) {
    if (showNotify) {
      showModelsNotification(_t('ui.mdl.emb_select_first', 'Сначала выберите модель эмбеддингов'), 'warning');
    }
    return;
  }

  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const res = await fetchFn('/api/v1/embeddings/model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, model, save_to_config: true }),
    });
    const data = typeof res.json === 'function' ? await res.json() : res;

    const badgeEl = document.getElementById('saved-default-embedding-badge');
    if (badgeEl) {
      badgeEl.textContent = `${provider}: ${model}`;
      badgeEl.className = 'badge bg-success font-monospace px-2 py-1';
    }

    if (showNotify) {
      showModelsNotification(
        data.message || `${_t('ui.mdl.emb_saved', 'Модель эмбеддингов сохранена')}: ${model}`,
        'success'
      );
    }
  } catch (err) {
    console.error('Ошибка сохранения модели эмбеддингов:', err);
    if (showNotify) {
      showModelsNotification(`${_t('ui.mdl.emb_save_error', 'Ошибка сохранения')}: ${err.message}`, 'danger');
    }
  }
}

/**
 * Выполняет живой тест генерации эмбеддинга (в браузере для local_bert или через API).
 */
export async function executeEmbeddingTest() {
  const provider = document.getElementById('embedding-provider-select')?.value || '';
  const model = document.getElementById('embedding-model-select')?.value || '';
  const inputEl = document.getElementById('embedding-test-input');
  const btn = document.getElementById('btn-embedding-test-send');
  const resultBox = document.getElementById('embedding-test-result');

  if (!model || !resultBox) return;
  const text = (inputEl?.value || '').trim() || 'Проверка семантического поиска и генерации векторов';

  resultBox.style.display = 'block';
  if (btn) btn.disabled = true;

  try {
    if (provider === 'local_bert') {
      resultBox.innerHTML = `<span class="text-info small">${escapeHtml(_t('ui.mdl.local_bert_loading_worker', 'Загрузка модели в WebAssembly / WebGPU...'))}</span>`;
      if (!window.LocalBertEngine) {
        await import('/html/js/local-bert-client.js?v=20261120_v1');
      }
      const unsub = window.LocalBertEngine.onProgress((info) => {
        if (!info) return;
        if (info.status === 'progress' && typeof info.progress === 'number') {
          resultBox.innerHTML = `<span class="text-info small">${escapeHtml(info.file || 'ONNX')}: ${Math.round(info.progress)}%</span>`;
        }
      });
      const res = await window.LocalBertEngine.embed(text, { modelId: model, force: true });
      unsub();
      const preview = (res.vector || []).slice(0, 6).map((v) => Number(v).toFixed(4)).join(', ');
      resultBox.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom">
          <div>
            <span class="badge bg-success me-2">Browser ${escapeHtml(String(res.device || 'wasm').toUpperCase())}</span>
            <span class="text-secondary small font-monospace">⚡ ${res.elapsedMs} ms • dim=${res.dimensions}</span>
          </div>
          <span class="badge bg-secondary-subtle text-secondary-emphasis border font-monospace">${escapeHtml(model)}</span>
        </div>
        <div class="small font-monospace text-body">[${escapeHtml(preview)}, ...]</div>
      `;
      return;
    }

    resultBox.innerHTML = `<span class="text-info small">${escapeHtml(_t('ui.mdl.emb_testing', 'Генерация вектора...'))}</span>`;
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const res = await fetchFn('/api/v1/embeddings/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, model, text }),
    });
    const data = typeof res.json === 'function' ? await res.json() : res;

    if (data.status === 'success') {
      const preview = (data.vector_preview || []).map((v) => Number(v).toFixed(4)).join(', ');
      resultBox.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1 pb-1 border-bottom">
          <div>
            <span class="badge bg-success me-2">200 OK</span>
            <span class="text-secondary small font-monospace">⚡ ${data.duration_ms || 0} ms • dim=${data.dimensions}</span>
          </div>
          <span class="badge bg-secondary-subtle text-secondary-emphasis border font-monospace">${escapeHtml(model)}</span>
        </div>
        <div class="small font-monospace text-body">[${escapeHtml(preview)}, ...]</div>
      `;
    } else {
      resultBox.innerHTML = `
        <div class="text-danger small font-monospace">${escapeHtml(data.message || 'Ошибка генерации эмбеддинга')}</div>
      `;
    }
  } catch (err) {
    resultBox.innerHTML = `<div class="text-danger small font-monospace">${escapeHtml(err.message || String(err))}</div>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Привязывает обработчики событий панели моделей эмбеддингов.
 */
export function bindEmbeddingEvents() {
  const providerSelect = document.getElementById('embedding-provider-select');
  const modelSelect = document.getElementById('embedding-model-select');
  const refreshBtn = document.getElementById('btn-refresh-embedding-models');
  const saveBtn = document.getElementById('btn-embedding-model-save');
  const testBtn = document.getElementById('btn-embedding-test-send');
  const testInput = document.getElementById('embedding-test-input');

  if (providerSelect && !providerSelect.dataset.bound) {
    providerSelect.dataset.bound = '1';
    providerSelect.addEventListener('change', () => {
      _populateEmbeddingModelSelect(providerSelect.value);
    });
  }

  if (modelSelect && !modelSelect.dataset.bound) {
    modelSelect.dataset.bound = '1';
    modelSelect.addEventListener('change', () => {
      _updateRuntimeBadge(providerSelect?.value || '', modelSelect.value);
    });
  }

  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = '1';
    refreshBtn.addEventListener('click', () => loadEmbeddingModels(true));
  }

  if (saveBtn && !saveBtn.dataset.bound) {
    saveBtn.dataset.bound = '1';
    saveBtn.addEventListener('click', () => saveEmbeddingModel(true));
  }

  if (testBtn && !testBtn.dataset.bound) {
    testBtn.dataset.bound = '1';
    testBtn.addEventListener('click', executeEmbeddingTest);
  }

  if (testInput && !testInput.dataset.bound) {
    testInput.dataset.bound = '1';
    testInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        executeEmbeddingTest();
      }
    });
  }
}
