# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests for Embedding Models Catalog, Service & API
# =============================================================================
# Description:
#   Юнит- и интеграционные тесты для каталога моделей эмбеддингов
#   (src.ai.orchestration.embedding_models), сервиса EmbeddingModelsService,
#   REST API /api/v1/embeddings/* и WebGUI ассетов панели эмбеддингов.
#
# File: test_embedding_models.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 00:15:00
# =============================================================================

from __future__ import annotations

"""Тесты подсистемы моделей эмбеддингов и REST API /api/v1/embeddings/*."""

from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.common.models import (
    EmbeddingModelsService,
    SetEmbeddingModelRequest,
    TestEmbeddingPayload,
    models_router,
)
from src.ai.orchestration.capability_registry import AICapability, CapabilityRegistry
from src.ai.orchestration.embedding_models import (
    get_all_embedding_models,
    get_available_embedding_models,
)


@pytest.fixture
def client() -> TestClient:
    """Создаёт тестовый HTTP-клиент с подключенным models_router."""
    app = FastAPI(title="Test Embedding Models")
    app.include_router(models_router)
    return TestClient(app)


def test_embedding_models_catalog_providers() -> None:
    """Проверяет каталог моделей эмбеддингов по всем поддерживаемым провайдерам."""
    catalog = get_all_embedding_models()
    for provider in ("local_bert", "gemini", "ollama", "openai", "hash"):
        assert provider in catalog
        assert len(catalog[provider]) >= 1

    assert "Xenova/multilingual-e5-small" in catalog["local_bert"]
    assert "gemini-embedding-001" in catalog["gemini"]
    assert "nomic-embed-text" in catalog["ollama"]
    assert "hash-md5-256" in catalog["hash"]

    assert get_available_embedding_models("unknown_provider") == []


def test_capability_registry_contains_embedding_models() -> None:
    """Проверяет регистрацию моделей эмбеддингов в CapabilityRegistry."""
    registry = CapabilityRegistry()
    emb_models = registry.find_by_capability(AICapability.EMBEDDING)
    ids = {m.id for m in emb_models}
    assert "local_bert:Xenova/multilingual-e5-small" in ids
    assert "gemini:gemini-embedding-001" in ids
    assert "ollama:nomic-embed-text" in ids


def test_embeddings_api_catalog_and_active(client: TestClient) -> None:
    """Проверяет GET /api/v1/embeddings/models и GET /api/v1/embeddings/active-model."""
    res_models = client.get("/api/v1/embeddings/models")
    assert res_models.status_code == 200
    data = res_models.json()
    assert data["status"] == "ok"
    assert "local_bert" in data["models"]
    assert "local_bert" in data["browser_providers"]

    res_active = client.get("/api/v1/embeddings/active-model")
    assert res_active.status_code == 200
    active = res_active.json()
    assert active["status"] == "ok"
    assert active["provider"]
    assert active["model"]
    assert active["dimension"] > 0


def test_embeddings_api_set_and_test_hash_and_browser(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Проверяет сохранение активной модели и тестирование hash / local_bert."""
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr("apps.common.models.service.resolve_active_config_path", lambda: cfg_path)
    monkeypatch.setattr("src.user_settings._SETTINGS_FILE", tmp_path / "user_settings.json")

    res_set = client.post(
        "/api/v1/embeddings/model",
        json={"provider": "local_bert", "model": "Xenova/multilingual-e5-small", "save_to_config": True},
    )
    assert res_set.status_code == 200
    set_data = res_set.json()
    assert set_data["status"] == "success"
    assert set_data["provider"] == "local_bert"
    assert set_data["dimension"] == 384

    res_test_hash = client.post(
        "/api/v1/embeddings/test",
        json={"provider": "hash", "model": "hash-md5-256", "text": "Тестовый текст для вектора"},
    )
    assert res_test_hash.status_code == 200
    hash_data = res_test_hash.json()
    assert hash_data["status"] == "success"
    assert hash_data["dimensions"] == 256
    assert len(hash_data["vector_preview"]) == 6

    res_test_browser = client.post(
        "/api/v1/embeddings/test",
        json={"provider": "local_bert", "model": "Xenova/multilingual-e5-small", "text": "Привет"},
    )
    assert res_test_browser.status_code == 200
    assert res_test_browser.json()["status"] == "browser_required"


def test_embedding_webgui_assets_synchronized() -> None:
    """Проверяет наличие и синхронизацию WebGUI панели эмбеддингов в обоих слоях."""
    for base in (Path("apps/ai_assistant/api/webgui/tab_models"), Path("apps/common/webgui/tab_models")):
        assert (base / "panel_embedding_models" / "panel.js").exists()
        html = (base / "index.html").read_text(encoding="utf-8")
        assert "panel-models-embedding-model" in html
        assert "embedding-provider-select" in html
        assert "embedding-model-select" in html
        assert "btn-embedding-test-send" in html
