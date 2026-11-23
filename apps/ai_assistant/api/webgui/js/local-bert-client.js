/**
 * =============================================================================
 * Название: Клиентский сервис браузерного BERT (WebGPU / WASM)
 * =============================================================================
 * Описание:
 *   Управляет Web Worker для локального расчёта эмбеддингов, семантического
 *   сходства и кэширования конфигурации из /api/v1/local-bert/config.
 *
 * Файл: local-bert-client.js
 * Пакет: apps/ai_assistant/api/webgui/js
 * Автор: hypo69
 * Updated: 2026-11-16 04:26:00
 * =============================================================================
 */

class LocalBertClient {
  constructor() {
    this._worker = null;
    this._reqCounter = 0;
    this._pending = new Map();
    this._progressListeners = new Set();
    this._config = null;
  }

  /**
   * Возвращает или создаёт экземпляр Web Worker.
   */
  _ensureWorker() {
    if (this._worker) return this._worker;
    this._worker = new Worker('/html/js/local-bert-worker.js?v=20261116_v1', { type: 'module' });
    this._worker.addEventListener('message', (event) => {
      const msg = event.data || {};
      if (msg.type === 'progress') {
        this._progressListeners.forEach((cb) => {
          try { cb(msg.info); } catch (_) {}
        });
        return;
      }
      const pending = this._pending.get(msg.id);
      if (!pending) return;
      this._pending.delete(msg.id);
      if (msg.type === 'error') {
        pending.reject(new Error(msg.error || 'Ошибка локального BERT'));
      } else {
        pending.resolve(msg.result);
      }
    });
    return this._worker;
  }

  /**
   * Подписка на события загрузки весов модели.
   */
  onProgress(callback) {
    this._progressListeners.add(callback);
    return () => this._progressListeners.delete(callback);
  }

  /**
   * Загружает и кэширует конфигурацию локального BERT с бэкенда.
   */
  async getConfig(forceRefresh = false) {
    if (this._config && !forceRefresh) return this._config;
    const fetchFn = (window.api && window.api.fetch) || fetch;
    const res = await fetchFn('/api/v1/local-bert/config');
    this._config = typeof res.json === 'function' ? await res.json() : res;
    return this._config;
  }

  /**
   * Выполняет запрос к Web Worker.
   */
  _callWorker(action, payload) {
    const worker = this._ensureWorker();
    const id = ++this._reqCounter;
    return new Promise((resolve, reject) => {
      this._pending.set(id, { resolve, reject });
      worker.postMessage({ id, action, payload });
    });
  }

  /**
   * Вычисляет эмбеддинг текста в браузере.
   */
  async embed(text, options = {}) {
    const cfg = await this.getConfig();
    if (!cfg.enabled && !options.force) {
      throw new Error('Локальный браузерный BERT отключён в настройках');
    }
    const lang = options.language || document.documentElement.lang || 'ru';
    const modelId = options.modelId || (
      cfg.mode === 'per_language' && cfg.per_language_models && cfg.per_language_models[lang]
        ? cfg.per_language_models[lang]
        : cfg.default_model
    );
    return this._callWorker('embed', {
      modelId,
      text,
      backend: options.backend || cfg.execution_backend || 'auto',
      quantization: options.quantization || cfg.quantization || 'q8',
    });
  }

  /**
   * Сравнивает семантическое сходство двух фраз локально в браузере.
   */
  async compareSimilarity(textA, textB, options = {}) {
    const cfg = await this.getConfig();
    const modelId = options.modelId || cfg.default_model || 'Xenova/multilingual-e5-small';
    return this._callWorker('similarity', {
      modelId,
      textA,
      textB,
      backend: options.backend || cfg.execution_backend || 'auto',
      quantization: options.quantization || cfg.quantization || 'q8',
    });
  }
}

if (typeof window !== 'undefined') {
  window.LocalBertEngine = window.LocalBertEngine || new LocalBertClient();
}
