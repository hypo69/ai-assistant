# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Common Models Suite
# =============================================================================
# Description:
#   Комплексный набор модульных и интеграционных тестов для общего модуля
#   управления моделями ИИ (apps/common/models) и его веб-интерфейса
#   (apps/common/webgui/tab_models).
#
# File: test_common_models.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 04:26:00
# =============================================================================

from __future__ import annotations

"""Тесты общего модуля моделей ИИ apps.common.models и вкладки tab_models."""

import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.common.models import (
    ModelsService,
    SetModelRequest,
    TestModelPayload,
    get_provider_config,
    load_root_config,
    models_router,
    resolve_active_config_path,
    save_ai_config,
    save_root_config,
    update_provider_config,
)


@pytest.fixture
def client() -> TestClient:
    """Создает тестовый HTTP-клиент с подключенным models_router."""
    app = FastAPI(title="Test Common Models")
    app.include_router(models_router)
    return TestClient(app)


def test_common_models_package_exports() -> None:
    """Проверяет экспорт всех ключевых компонентов из apps.common.models."""
    assert models_router is not None
    assert ModelsService is not None
    assert SetModelRequest is not None
    assert TestModelPayload is not None
    assert callable(resolve_active_config_path)
    assert callable(save_ai_config)
    assert callable(get_provider_config)
    assert callable(update_provider_config)
    assert callable(load_root_config)
    assert callable(save_root_config)


def test_backward_compatibility_router_models() -> None:
    """Проверяет обратную совместимость импортов из router_models."""
    from apps.ai_assistant.api.routers.router_models import (
        ModelsService as LegacyService,
        SetModelRequest as LegacySetModelRequest,
        TestModelPayload as LegacyTestModelPayload,
        resolve_active_config_path as legacy_resolve,
        router as legacy_router,
    )
    assert legacy_router is models_router
    assert LegacyService is ModelsService
    assert LegacySetModelRequest is SetModelRequest
    assert LegacyTestModelPayload is TestModelPayload
    assert legacy_resolve is resolve_active_config_path


def test_get_available_chat_models(client: TestClient) -> None:
    """Проверяет эндпоинт каталога доступных моделей."""
    res = client.get("/api/v1/chat/models")
    assert res.status_code == 200
    data = res.json()
    assert "models" in data
    assert "gemini" in data["models"]
    assert "onnx" in data["models"]


def test_get_active_model(client: TestClient) -> None:
    """Проверяет эндпоинт текущей активной модели."""
    res = client.get("/api/v1/chat/active-model")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert "model" in data
    assert "provider" in data


def test_set_active_model(client: TestClient) -> None:
    """Проверяет установку активной модели через SetModelRequest."""
    res = client.post(
        "/api/v1/tc/model",
        json={"model": "gemini-2.5-flash", "provider": "gemini", "save_to_config": False}
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "success"
    assert data.get("model") == "gemini-2.5-flash"
    assert data.get("provider") == "gemini"


def test_user_auth_settings_and_favorites(client: TestClient) -> None:
    """Проверяет эндпоинты настроек пользователя и избранных моделей."""
    res_get = client.get("/api/v1/auth/settings")
    assert res_get.status_code == 200
    data = res_get.json()
    assert "status" in data

    # Добавление в избранное
    test_model = "test-custom-model"
    res_add = client.post(f"/api/v1/auth/favorites/{test_model}", json={"note": "Test note"})
    assert res_add.status_code == 200
    fav_data = res_add.json()
    assert fav_data.get("status") == "ok"

    # Чтение избранного
    res_fav = client.get("/api/v1/auth/favorites")
    assert res_fav.status_code == 200
    assert test_model in res_fav.json().get("favorites", {})

    # Удаление из избранного
    res_del = client.delete(f"/api/v1/auth/favorites/{test_model}")
    assert res_del.status_code == 200
    assert test_model not in res_del.json().get("favorites", {})


def test_providers_config_endpoints(client: TestClient) -> None:
    """Проверяет эндпоинты конфигурации внешних и локальных провайдеров."""
    for prov in ("foundry", "ollama", "agy", "onnx"):
        res = client.get(f"/api/v1/{prov}/config")
        assert res.status_code == 200, f"GET /api/v1/{prov}/config failed"


def test_local_bert_endpoints(client: TestClient) -> None:
    """Проверяет эндпоинты каталога и настроек браузерного BERT."""
    res_cat = client.get("/api/v1/local-bert/catalog")
    assert res_cat.status_code == 200
    data_cat = res_cat.json()
    assert data_cat.get("status") == "success"
    assert "models" in data_cat
    assert "languages" in data_cat

    res_cfg = client.get("/api/v1/local-bert/config")
    assert res_cfg.status_code == 200


def test_models_summary_endpoint(client: TestClient) -> None:
    """Проверяет эндпоинт сводки состояния моделей."""
    res = client.get("/api/v1/models/summary")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "active"
    assert "default_provider" in data
    assert "providers" in data


def test_common_webgui_tab_models_assets() -> None:
    """Проверяет наличие и целостность всех статических ассетов apps/common/webgui/tab_models."""
    tab_dir = Path("apps/common/webgui/tab_models")
    assert tab_dir.exists(), "Каталог apps/common/webgui/tab_models не существует"

    # Файлы верхнего уровня
    assert (tab_dir / "index.html").exists()
    assert (tab_dir / "main.js").exists()
    assert (tab_dir / "menu_config.json").exists()
    assert (tab_dir / "README.md").exists()

    # Субпанели
    assert (tab_dir / "common" / "ui_utils.js").exists()
    assert (tab_dir / "panel_models_catalog" / "panel.js").exists()
    assert (tab_dir / "panel_models_catalog" / "test.js").exists()
    assert (tab_dir / "panel_gemini_keys" / "panel.js").exists()
    assert (tab_dir / "panel_agy_keys" / "panel.js").exists()
    assert (tab_dir / "panel_google_accounts" / "panel.js").exists()
    assert (tab_dir / "panel_providers_config" / "panel.js").exists()
    assert (tab_dir / "panel_local_bert" / "panel.js").exists()

    # Проверка разметки index.html
    html_content = (tab_dir / "index.html").read_text(encoding="utf-8")
    assert "panel-models-aktivnaya-model-i-proverka" in html_content
    assert "pill-gemini" in html_content
    assert "pill-agy" in html_content
    assert "pill-google-accounts" in html_content
    assert "pill-foundry" in html_content
    assert "pill-ollama" in html_content
    assert "pill-onnx" in html_content
    assert "pill-local-bert" in html_content

    # Проверка menu_config.json
    menu_cfg = json.loads((tab_dir / "menu_config.json").read_text(encoding="utf-8"))
    subtabs_items = menu_cfg.get("subtabs", {}).get("items", [])
    subtabs = [item["id"] for item in subtabs_items]
    assert "gemini" in subtabs
    assert "agy" in subtabs
    assert "google-accounts" in subtabs
    assert "foundry" in subtabs
    assert "ollama" in subtabs
    assert "onnx" in subtabs
    assert "local-bert" in subtabs
