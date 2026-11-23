/**
 * =============================================================================
 * Название: Web Worker браузерного BERT-инференса (Transformers.js + WebGPU/WASM)
 * =============================================================================
 * Описание:
 *   Выполняет загрузку компактных ONNX-моделей (INT8/FP32) и расчёт
 *   эмбеддингов / косинусного сходства в отдельном потоке без блокировки UI.
 *
 * Файл: local-bert-worker.js
 * Пакет: apps/ai_assistant/api/webgui/js
 * Автор: hypo69
 * Updated: 2026-11-16 00:47:00
 * =============================================================================
 */

const TRANSFORMERS_CDN = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3/+esm';

let transformersModule = null;
let activePipeline = null;
let activeKey = '';
let activeDevice = 'wasm';

/**
 * Загружает библиотеку Transformers.js по первому требованию.
 */
async function ensureTransformers() {
  if (!transformersModule) {
    transformersModule = await import(TRANSFORMERS_CDN);
    if (transformersModule.env) {
      transformersModule.env.allowLocalModels = false;
      transformersModule.env.useBrowserCache = true;
    }
  }
  return transformersModule;
}

/**
 * Выбирает доступный бэкенд исполнения (WebGPU или WASM).
 * @param {string} requestedBackend - 'auto' | 'webgpu' | 'wasm'
 * @returns {Promise<string>}
 */
async function resolveDevice(requestedBackend) {
  if (requestedBackend === 'wasm') return 'wasm';
  if (typeof navigator !== 'undefined' && navigator.gpu) {
    try {
      const adapter = await navigator.gpu.requestAdapter();
      if (adapter) return 'webgpu';
    } catch (_) {
      // Переход на резервный WASM-бэкенд
    }
  }
  return 'wasm';
}

/**
 * Инициализирует или возвращает закешированный pipeline для выбранной модели.
 */
async function getExtractor(modelId, backend = 'auto', quantization = 'q8') {
  const device = await resolveDevice(backend);
  const dtype = quantization === 'fp32' ? 'fp32' : 'q8';
  const cacheKey = `${modelId}::${device}::${dtype}`;

  if (activePipeline && activeKey === cacheKey) {
    return { extractor: activePipeline, device: activeDevice };
  }

  const { pipeline } = await ensureTransformers();
  const progressCallback = (info) => {
    self.postMessage({ type: 'progress', info });
  };

  try {
    activePipeline = await pipeline('feature-extraction', modelId, {
      device,
      dtype,
      progress_callback: progressCallback,
    });
    activeDevice = device;
  } catch (err) {
    if (device === 'webgpu') {
      // Резервный запуск на WASM, если WebGPU-шейдер не скомпилировался
      activePipeline = await pipeline('feature-extraction', modelId, {
        device: 'wasm',
        dtype,
        progress_callback: progressCallback,
      });
      activeDevice = 'wasm';
    } else {
      throw err;
    }
  }

  activeKey = `${modelId}::${activeDevice}::${dtype}`;
  return { extractor: activePipeline, device: activeDevice };
}

/**
 * Вычисляет косинусное сходство двух нормализованных векторов.
 */
function cosineSimilarity(vecA, vecB) {
  let dot = 0;
  let normA = 0;
  let normB = 0;
  const len = Math.min(vecA.length, vecB.length);
  for (let i = 0; i < len; i += 1) {
    dot += vecA[i] * vecB[i];
    normA += vecA[i] * vecA[i];
    normB += vecB[i] * vecB[i];
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  return denom > 0 ? dot / denom : 0;
}

self.addEventListener('message', async (event) => {
  const { id, action, payload } = event.data || {};
  try {
    if (action === 'embed') {
      const t0 = performance.now();
      const { modelId, text, backend, quantization } = payload;
      const { extractor, device } = await getExtractor(modelId, backend, quantization);
      const output = await extractor(text, { pooling: 'mean', normalize: true });
      const elapsedMs = Math.round((performance.now() - t0) * 100) / 100;
      self.postMessage({
        id,
        type: 'result',
        result: {
          vector: Array.from(output.data),
          dimensions: output.data.length,
          device,
          elapsedMs,
        },
      });
      return;
    }

    if (action === 'similarity') {
      const t0 = performance.now();
      const { modelId, textA, textB, backend, quantization } = payload;
      const { extractor, device } = await getExtractor(modelId, backend, quantization);
      const outA = await extractor(textA, { pooling: 'mean', normalize: true });
      const outB = await extractor(textB, { pooling: 'mean', normalize: true });
      const score = cosineSimilarity(outA.data, outB.data);
      const elapsedMs = Math.round((performance.now() - t0) * 100) / 100;
      self.postMessage({
        id,
        type: 'result',
        result: {
          similarity: Math.round(score * 10000) / 10000,
          dimensions: outA.data.length,
          device,
          elapsedMs,
        },
      });
      return;
    }

    throw new Error(`Неизвестное действие воркера: ${action}`);
  } catch (err) {
    self.postMessage({
      id,
      type: 'error',
      error: err && err.message ? err.message : String(err),
    });
  }
});
