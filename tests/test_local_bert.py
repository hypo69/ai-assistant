# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests for Local Browser BERT Module & API
# =============================================================================
# Description:
#   Юнит-тесты каталога компактных BERT-моделей, менеджера настроек
#   src.ai.local_bert и FastAPI эндпоинтов /api/v1/local-bert/*.
#
# File: test_local_bert.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 04:26:00
# =============================================================================

from __future__ import annotations
"""Тесты модуля локальных браузерных BERT-моделей."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.local_bert import (
    LocalBertSettings,
    LocalBertSettingsManager,
    get_local_bert_model,
    list_local_bert_models,
    resolve_model_for_language,
)
from apps.ai_assistant.api.routers.router_models import router as models_router


def test_catalog_covers_all_supported_languages() -> None:
    """Проверяет наличие компактных моделей для всех языков интерфейса (ru, en, he, uk)."""
    for lang in ("ru", "en", "he", "uk"):
        models = list_local_bert_models(language=lang)
        assert len(models) >= 1, f"Не найдены модели для языка {lang}"

    default_model = get_local_bert_model("Xenova/multilingual-e5-small")
    assert default_model is not None
    assert default_model.is_multilingual is True
    assert default_model.size_int8_mb < 50


def test_resolve_model_for_language_modes() -> None:
    """Проверяет выбор модели в мультиязычном и по-языковом режимах."""
    per_lang = {"ru": "TrendHD/rubert-tiny2-int8", "en": "Xenova/all-MiniLM-L6-v2"}
    assert (
        resolve_model_for_language("ru", "multilingual", "Xenova/multilingual-e5-small", per_lang)
        == "Xenova/multilingual-e5-small"
    )
    assert (
        resolve_model_for_language("ru", "per_language", "Xenova/multilingual-e5-small", per_lang)
        == "TrendHD/rubert-tiny2-int8"
    )


def test_settings_manager_roundtrip(tmp_path: Path) -> None:
    """Проверяет сохранение и загрузку настроек LocalBertSettingsManager."""
    cfg_path = tmp_path / "config.json"
    manager = LocalBertSettingsManager(config_path=cfg_path)

    initial = manager.load()
    assert initial.enabled is True
    assert initial.default_model == "Xenova/multilingual-e5-small"

    updated = LocalBertSettings(
        enabled=True,
        mode="per_language",
        default_model="Xenova/paraphrase-multilingual-MiniLM-L12-v2",
        execution_backend="webgpu",
        quantization="q8",
        enable_intent_routing=False,
        enable_semantic_cache=True,
        semantic_cache_threshold=0.95,
    )
    saved = manager.save(updated)
    assert saved.mode == "per_language"

    reloaded = manager.load()
    assert reloaded.mode == "per_language"
    assert reloaded.execution_backend == "webgpu"
    assert reloaded.semantic_cache_threshold == 0.95
    assert reloaded.enable_intent_routing is False


def test_local_bert_api_endpoints(tmp_path: Path, monkeypatch) -> None:
    """Проверяет эндпоинты /api/v1/local-bert/catalog и /api/v1/local-bert/config."""
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(
        "apps.ai_assistant.api.routers.router_models.resolve_active_config_path",
        lambda: cfg_path,
    )

    app = FastAPI()
    app.include_router(models_router)
    client = TestClient(app)

    cat_resp = client.get("/api/v1/local-bert/catalog?language=he")
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    assert cat_data["status"] == "success"
    assert any(m["model_id"] == "codewithkyrian/heBERT" for m in cat_data["models"])

    post_resp = client.post(
        "/api/v1/local-bert/config",
        json={
            "enabled": True,
            "mode": "per_language",
            "default_model": "Xenova/multilingual-e5-small",
            "execution_backend": "wasm",
            "quantization": "q8",
            "semantic_cache_threshold": 0.9,
        },
    )
    assert post_resp.status_code == 200
    assert post_resp.json()["config"]["execution_backend"] == "wasm"

    get_resp = client.get("/api/v1/local-bert/config")
    assert get_resp.status_code == 200
    assert get_resp.json()["mode"] == "per_language"
    assert get_resp.json()["execution_backend"] == "wasm"
