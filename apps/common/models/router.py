# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Common Models - FastAPI Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор управления моделями ИИ, провайдерами (Gemini, Foundry,
#   Ollama, AGY, ONNX, Local BERT), системной инструкцией и тестированием
#   на уровне общих сервисов приложений.
#
# File: router.py
# Package: apps.common.models
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 00:10:00
# =============================================================================

from __future__ import annotations

"""FastAPI маршрутизатор моделей, провайдеров и настроек ИИ."""

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from apps.common.models.embedding_service import EmbeddingModelsService
from apps.common.models.models import (
    SetEmbeddingModelRequest,
    SetModelRequest,
    TestEmbeddingPayload,
    TestModelPayload,
)
from apps.common.models.service import (
    ModelsService,
    get_provider_config,
    resolve_active_config_path,
    update_provider_config,
)

router = APIRouter(tags=["AI Models & Providers"])


# -----------------------------------------------------------------------------
# Эндпоинты каталога и выбора моделей
# -----------------------------------------------------------------------------

@router.get("/api/v1/chat/models", summary="Каталог доступных моделей по провайдерам")
async def get_available_chat_models(refresh: bool = False, include_unsupported: bool = False) -> Dict[str, Any]:
    """Возвращает сгруппированный список моделей для всех поддерживаемых провайдеров."""
    return ModelsService.get_available_chat_models(refresh=refresh, include_unsupported=include_unsupported)


@router.get("/api/v1/chat/active-model", summary="Текущая активная модель")
@router.get("/api/v1/tc/model", summary="Текущая модель TC")
async def get_active_model() -> Dict[str, Any]:
    """Возвращает текущую выбранную модель и провайдер."""
    return ModelsService.get_active_model()


@router.post("/api/v1/tc/model", summary="Сохранить активную модель")
@router.post("/api/v1/chat/model", summary="Установить модель чата")
async def set_active_model(req: SetModelRequest) -> Dict[str, Any]:
    """Сохраняет выбранную модель и провайдер в конфигурации и настройках пользователя."""
    return ModelsService.set_active_model(req)


# -----------------------------------------------------------------------------
# Эндпоинты настроек пользователя и избранных моделей (/api/v1/auth/settings, /api/v1/auth/favorites)
# -----------------------------------------------------------------------------

@router.get("/api/v1/auth/settings", summary="Чтение настроек профиля пользователя (v1)")
async def get_user_auth_settings() -> Dict[str, Any]:
    """Возвращает сохраненные настройки пользователя, включая избранные модели."""
    return ModelsService.get_user_auth_settings()


@router.post("/api/v1/auth/settings", summary="Сохранение настроек пользователя (v1)")
async def update_user_auth_settings(request: Request) -> Dict[str, Any]:
    """Обновляет пользовательские настройки и активную модель."""
    try:
        body = await request.json()
        model_name = body.get("model")
        provider = body.get("provider", "")
        ModelsService.update_user_auth_settings(model_name=model_name, provider=provider)
        return {"status": "ok", "saved": body}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.get("/api/v1/auth/favorites", summary="Список избранных моделей")
async def get_favorite_models() -> Dict[str, Any]:
    """Возвращает словарь избранных моделей и заметок к ним."""
    return ModelsService.get_favorite_models()


@router.post("/api/v1/auth/favorites/{model_name:path}", summary="Добавить модель в избранное")
async def add_favorite_model(model_name: str, request: Request) -> Dict[str, Any]:
    """Добавляет модель в избранное с опциональной заметкой и меткой UTC ISO 8601."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    note = body.get("note", "")
    try:
        return await asyncio.to_thread(ModelsService.add_favorite_model, model_name, note)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.delete("/api/v1/auth/favorites/{model_name:path}", summary="Удалить модель из избранного")
async def delete_favorite_model(model_name: str) -> Dict[str, Any]:
    """Удаляет модель из списка избранного."""
    try:
        return ModelsService.delete_favorite_model(model_name)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# -----------------------------------------------------------------------------
# Тестирование модели в реальном времени (/api/v1/chat/test-model)
# -----------------------------------------------------------------------------

@router.post("/api/v1/chat/test-model", summary="Интерактивное тестирование генерации модели")
async def test_model_endpoint(req: TestModelPayload) -> Dict[str, Any]:
    """Отправляет тестовый запрос к указанной модели и возвращает результат."""
    return await ModelsService.test_model(req)


# -----------------------------------------------------------------------------
# Эндпоинты системной инструкции (System Instruction)
# -----------------------------------------------------------------------------

@router.get("/api/v1/tc/model-instruction", summary="Получить системную инструкцию TC")
@router.get("/api/v1/chat/model-instruction", summary="Получить системную инструкцию Chat")
async def get_system_instruction() -> Dict[str, Any]:
    """Возвращает текущую системную инструкцию ИИ."""
    content = ModelsService.get_system_instruction()
    return {"status": "success", "content": content}


@router.post("/api/v1/tc/model-instruction", summary="Сохранить системную инструкцию TC")
@router.post("/api/v1/chat/model-instruction", summary="Сохранить системную инструкцию Chat")
async def save_system_instruction(request: Request) -> Dict[str, Any]:
    """Сохраняет системную инструкцию ИИ на диск и в профиль пользователя."""
    try:
        body = await request.json()
        content = body.get("content") or body.get("instruction") or body.get("system_instruction") or ""
        if content:
            await asyncio.to_thread(ModelsService.save_system_instruction, content)
        return {"status": "success", "content": content}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# -----------------------------------------------------------------------------
# Эндпоинты конфигурации провайдеров (Foundry, Ollama, AGY, ONNX)
# -----------------------------------------------------------------------------

@router.get("/api/v1/foundry/config", summary="Настройки Foundry")
async def get_foundry_config() -> Dict[str, Any]:
    """Получить параметры подключения к Microsoft Foundry Local."""
    return get_provider_config("foundry")


@router.post("/api/v1/foundry/config", summary="Сохранить настройки Foundry")
async def save_foundry_config(request: Request) -> Dict[str, Any]:
    """Сохранить параметры подключения к Microsoft Foundry Local."""
    body = await request.json()
    return update_provider_config("foundry", body)


@router.get("/api/v1/ollama/config", summary="Настройки Ollama")
async def get_ollama_config() -> Dict[str, Any]:
    """Получить параметры подключения к локальному серверу Ollama."""
    return get_provider_config("ollama")


@router.post("/api/v1/ollama/config", summary="Сохранить настройки Ollama")
async def save_ollama_config(request: Request) -> Dict[str, Any]:
    """Сохранить параметры подключения к серверу Ollama."""
    body = await request.json()
    return update_provider_config("ollama", body)


@router.get("/api/v1/agy/config", summary="Настройки Antigravity (AGY)")
async def get_agy_config() -> Dict[str, Any]:
    """Получить параметры конфигурации Google Antigravity (AGY)."""
    return get_provider_config("agy")


@router.post("/api/v1/agy/config", summary="Сохранить настройки Antigravity (AGY)")
async def save_agy_config(request: Request) -> Dict[str, Any]:
    """Сохранить параметры конфигурации Google Antigravity (AGY)."""
    body = await request.json()
    return update_provider_config("agy", body)


@router.get("/api/v1/onnx/config", summary="Настройки ONNX")
async def get_onnx_config() -> Dict[str, Any]:
    """Получить параметры конфигурации ONNX / DirectML."""
    return get_provider_config("onnx")


@router.post("/api/v1/onnx/config", summary="Сохранить настройки ONNX")
async def save_onnx_config(request: Request) -> Dict[str, Any]:
    """Сохранить параметры конфигурации ONNX / DirectML."""
    body = await request.json()
    return update_provider_config("onnx", body)


# -----------------------------------------------------------------------------
# Эндпоинты локального браузерного BERT
# -----------------------------------------------------------------------------

@router.get("/api/v1/local-bert/catalog", summary="Каталог браузерных BERT-моделей")
async def get_local_bert_catalog(language: Optional[str] = None) -> Dict[str, Any]:
    """Возвращает каталог компактных ONNX BERT-моделей для Electron/браузера."""
    from src.ai.local_bert import list_local_bert_models

    models = [m.to_dict() for m in list_local_bert_models(language=language)]
    return {"status": "success", "models": models, "languages": ["ru", "en", "he", "uk"]}


@router.get("/api/v1/local-bert/config", summary="Настройки браузерного BERT")
async def get_local_bert_config() -> Dict[str, Any]:
    """Возвращает текущие настройки локального браузерного BERT-инференса."""
    from src.ai.local_bert import LocalBertSettingsManager

    manager = LocalBertSettingsManager(config_path=resolve_active_config_path())
    return manager.load().model_dump()


@router.post("/api/v1/local-bert/config", summary="Сохранить настройки браузерного BERT")
async def save_local_bert_config(request: Request) -> Dict[str, Any]:
    """Валидирует и сохраняет настройки локального браузерного BERT-инференса."""
    from src.ai.local_bert import LocalBertSettingsManager

    body = await request.json()
    manager = LocalBertSettingsManager(config_path=resolve_active_config_path())
    try:
        saved = manager.save(body)
        return {"status": "success", "config": saved.model_dump()}
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# -----------------------------------------------------------------------------
# Эндпоинты моделей эмбеддингов (/api/v1/embeddings/*)
# -----------------------------------------------------------------------------

@router.get("/api/v1/embeddings/models", summary="Каталог моделей эмбеддингов по провайдерам")
async def get_available_embedding_models(refresh: bool = False) -> Dict[str, Any]:
    """Возвращает сгруппированный список моделей эмбеддингов для всех провайдеров."""
    return EmbeddingModelsService.get_available_embedding_models(refresh=refresh)


@router.get("/api/v1/embeddings/active-model", summary="Текущая активная модель эмбеддингов")
async def get_active_embedding_model() -> Dict[str, Any]:
    """Возвращает текущую выбранную модель и провайдера эмбеддингов."""
    return EmbeddingModelsService.get_active_embedding_model()


@router.post("/api/v1/embeddings/model", summary="Сохранить активную модель эмбеддингов")
async def set_active_embedding_model(req: SetEmbeddingModelRequest) -> Dict[str, Any]:
    """Сохраняет выбранную модель и провайдера эмбеддингов в конфигурации и профиле."""
    return EmbeddingModelsService.set_active_embedding_model(req)


@router.post("/api/v1/embeddings/test", summary="Интерактивное тестирование модели эмбеддингов")
async def test_embedding_model_endpoint(req: TestEmbeddingPayload) -> Dict[str, Any]:
    """Отправляет тестовый текст в модель эмбеддингов и возвращает размерность и превью вектора."""
    return await EmbeddingModelsService.test_embedding_model(req)


# -----------------------------------------------------------------------------
# Сводка состояния моделей
# -----------------------------------------------------------------------------

@router.get("/api/v1/models/summary", summary="Сводка состояния моделей")
async def get_models_summary() -> Dict[str, Any]:
    """Возвращает общую сводку доступности провайдеров и моделей."""
    return ModelsService.get_models_summary()
