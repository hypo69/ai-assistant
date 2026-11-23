# Модуль локальных браузерных BERT-моделей (`src.ai.local_bert`)

**Updated:** 2026-11-16 00:45:00

## Назначение

Модуль управляет каталогом и настройками компактных BERT-подобных моделей (ONNX INT8 / FP32), исполняемых напрямую в браузерном движке Electron (`Transformers.js` + `onnxruntime-web` поверх **WebGPU** или **WASM SIMD**).

## Состав пакета

* `catalog.py` — реестр проверенных компактных моделей для языков `ru`, `en`, `he`, `uk` (мультиязычные `multilingual-e5-small`, `paraphrase-multilingual-MiniLM-L12-v2`, `mmBERT-small-ONNX` и специализированные `rubert-tiny2-int8`, `all-MiniLM-L6-v2`, `heBERT`).
* `settings.py` — Pydantic-схема `LocalBertSettings` и менеджер `LocalBertSettingsManager` для чтения и атомарного сохранения конфигурации в `config.json`.
* `__init__.py` — публичный API пакета.
