/**
 * =============================================================================
 * Название: Панель настройки браузерного BERT (WebGPU / WASM)
 * =============================================================================
 * Описание:
 *   Управляет выбором мультиязычных или по-языковых (ru/en/he/uk) моделей,
 *   параметрами квантования, семантического кэша и живым тестом в браузере.
 *
 * Файл: apps/ai_assistant/api/webgui/tab_models/panel_local_bert/panel.js
 * Пакет: apps/ai_assistant/api/webgui/tab_models/panel_local_bert
 * Автор: hypo69
 * Updated: 2026-11-16 04:26:00
 * =============================================================================
 */

import { showModelsNotification } from '../common/ui_utils.js';

let _catalogModels = [];

function _t(key, fallback) {
  return typeof window.t === 'function' ? window.t(key, fallback) : fallback;
}

function _togglePerLanguageBlock(mode) {
  const block = document.getElementById('local-bert-per-lang-block');
  if (block) {
    block.style.display = mode === 'per_language' ? '' : 'none';
  }
}

function _populateModelSelect(selectEl, models, selectedValue) {
  if (!selectEl) return;
  selectEl.innerHTML = '';
  models.forEach((m) => {
    const opt = document.createElement('option');
    opt.value = m.model_id;
    opt.textContent = `${m.title} (~${m.size_int8_mb} MB INT8)`;
    selectEl.appendChild(opt);
  });
  if (selectedValue && models.some((m) => m.model_id === selectedValue)) {
    selectEl.value = selectedValue;
  }
}

/**
 * Загружает каталог моделей и текущую конфигурацию браузерного BERT.
 */
export async function loadLocalBertConfig() {
  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const [catRes, cfgRes] = await Promise.all([
      fetchFn('/api/v1/local-bert/catalog'),
      fetchFn('/api/v1/local-bert/config'),
    ]);
    const catData = typeof catRes.json === 'function' ? await catRes.json() : catRes;
    const cfg = typeof cfgRes.json === 'function' ? await cfgRes.json() : cfgRes;

    _catalogModels = Array.isArray(catData.models) ? catData.models : [];

    const enabledEl = document.getElementById('local-bert-enabled');
    const modeEl = document.getElementById('local-bert-mode');
    const defaultModelEl = document.getElementById('local-bert-default-model');
    const backendEl = document.getElementById('local-bert-backend');
    const quantEl = document.getElementById('local-bert-quantization');
    const routingEl = document.getElementById('local-bert-intent-routing');
    const cacheEl = document.getElementById('local-bert-semantic-cache');
    const thresholdEl = document.getElementById('local-bert-cache-threshold');

    const multiModels = _catalogModels.filter((m) => m.is_multilingual);
    _populateModelSelect(defaultModelEl, multiModels.length ? multiModels : _catalogModels, cfg.default_model);

    const perLang = cfg.per_language_models || {};
    ['ru', 'en', 'he', 'uk'].forEach((lang) => {
      const sel = document.getElementById(`local-bert-lang-${lang}`);
      const filtered = _catalogModels.filter((m) => Array.isArray(m.languages) && m.languages.includes(lang));
      _populateModelSelect(sel, filtered.length ? filtered : _catalogModels, perLang[lang]);
    });

    if (enabledEl) enabledEl.checked = cfg.enabled ?? true;
    if (modeEl) {
      modeEl.value = cfg.mode || 'multilingual';
      _togglePerLanguageBlock(modeEl.value);
    }
    if (backendEl) backendEl.value = cfg.execution_backend || 'auto';
    if (quantEl) quantEl.value = cfg.quantization || 'q8';
    if (routingEl) routingEl.checked = cfg.enable_intent_routing ?? true;
    if (cacheEl) cacheEl.checked = cfg.enable_semantic_cache ?? true;
    if (thresholdEl) thresholdEl.value = String(cfg.semantic_cache_threshold ?? 0.92);
  } catch (err) {
    console.error('Ошибка загрузки настроек Local BERT:', err);
  }
}

/**
 * Сохраняет настройки браузерного BERT на сервер.
 */
export async function saveLocalBertConfig() {
  const payload = {
    enabled: document.getElementById('local-bert-enabled')?.checked ?? true,
    mode: document.getElementById('local-bert-mode')?.value || 'multilingual',
    default_model: document.getElementById('local-bert-default-model')?.value || 'Xenova/multilingual-e5-small',
    per_language_models: {
      ru: document.getElementById('local-bert-lang-ru')?.value || 'TrendHD/rubert-tiny2-int8',
      en: document.getElementById('local-bert-lang-en')?.value || 'Xenova/all-MiniLM-L6-v2',
      he: document.getElementById('local-bert-lang-he')?.value || 'codewithkyrian/heBERT',
      uk: document.getElementById('local-bert-lang-uk')?.value || 'Xenova/multilingual-e5-small',
    },
    execution_backend: document.getElementById('local-bert-backend')?.value || 'auto',
    quantization: document.getElementById('local-bert-quantization')?.value || 'q8',
    enable_intent_routing: document.getElementById('local-bert-intent-routing')?.checked ?? true,
    enable_semantic_cache: document.getElementById('local-bert-semantic-cache')?.checked ?? true,
    semantic_cache_threshold: parseFloat(document.getElementById('local-bert-cache-threshold')?.value || '0.92'),
  };

  try {
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const res = await fetchFn('/api/v1/local-bert/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = typeof res.json === 'function' ? await res.json() : res;
    if (data.status === 'success') {
      if (window.LocalBertEngine) {
        window.LocalBertEngine._config = data.config;
      }
      showModelsNotification(_t('ui.mdl.local_bert_saved', 'Настройки браузерного BERT сохранены!'), 'success');
    } else {
      showModelsNotification(data.detail || data.message || 'Ошибка сохранения', 'error');
    }
  } catch (err) {
    showModelsNotification(`Ошибка: ${err.message}`, 'error');
  }
}

/**
 * Запускает живой тест модели прямо в браузере через Web Worker (WebGPU/WASM).
 */
export async function runLocalBertBrowserTest() {
  const statusEl = document.getElementById('local-bert-test-status');
  const resultEl = document.getElementById('local-bert-test-result');
  const textA = document.getElementById('local-bert-test-text-a')?.value?.trim() || '';
  const textB = document.getElementById('local-bert-test-text-b')?.value?.trim() || '';
  const btn = document.getElementById('btn-test-local-bert');

  if (!textA || !textB) {
    showModelsNotification(_t('ui.mdl.local_bert_need_texts', 'Введите обе фразы для сравнения'), 'warning');
    return;
  }

  try {
    if (btn) btn.disabled = true;
    if (resultEl) resultEl.textContent = '';
    if (statusEl) statusEl.textContent = _t('ui.mdl.local_bert_loading_worker', 'Инициализация WebGPU/WASM...');

    if (!window.LocalBertEngine) {
      await import('/html/js/local-bert-client.js?v=20261116_v1');
    }

    const unsubscribe = window.LocalBertEngine.onProgress((info) => {
      if (!statusEl || !info) return;
      if (info.status === 'progress' && typeof info.progress === 'number') {
        statusEl.textContent = `${info.file || 'ONNX'}: ${Math.round(info.progress)}%`;
      } else if (info.status) {
        statusEl.textContent = `${info.status}${info.file ? `: ${info.file}` : ''}`;
      }
    });

    const modelId = document.getElementById('local-bert-default-model')?.value || 'Xenova/multilingual-e5-small';
    const backend = document.getElementById('local-bert-backend')?.value || 'auto';
    const quantization = document.getElementById('local-bert-quantization')?.value || 'q8';

    const res = await window.LocalBertEngine.compareSimilarity(textA, textB, {
      modelId,
      backend,
      quantization,
    });
    unsubscribe();

    if (statusEl) {
      statusEl.textContent = `${res.device.toUpperCase()} • ${res.elapsedMs} ms • dim=${res.dimensions}`;
    }
    if (resultEl) {
      resultEl.textContent = `Cosine similarity: ${res.similarity}`;
    }
  } catch (err) {
    if (statusEl) statusEl.textContent = `Error: ${err.message}`;
    showModelsNotification(`Local BERT error: ${err.message}`, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Привязывает обработчики событий панели Local BERT.
 */
export function bindLocalBertEvents() {
  const modeEl = document.getElementById('local-bert-mode');
  if (modeEl && !modeEl.dataset.bound) {
    modeEl.dataset.bound = '1';
    modeEl.addEventListener('change', () => _togglePerLanguageBlock(modeEl.value));
  }

  const saveBtn = document.getElementById('btn-save-local-bert');
  if (saveBtn && !saveBtn.dataset.bound) {
    saveBtn.dataset.bound = '1';
    saveBtn.addEventListener('click', saveLocalBertConfig);
  }

  const testBtn = document.getElementById('btn-test-local-bert');
  if (testBtn && !testBtn.dataset.bound) {
    testBtn.dataset.bound = '1';
    testBtn.addEventListener('click', runLocalBertBrowserTest);
  }
}
