# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Common Models - Package Init
# =============================================================================
# Description:
#   Пакет общесистемного управления моделями ИИ, провайдерами, API-ключами,
#   системными инструкциями и тестированием на уровне приложений.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.common.models
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 00:10:00
# =============================================================================

from __future__ import annotations

"""Экспорт компонентов общего модуля управления моделями ИИ."""

from apps.common.models.embedding_service import (
    EmbeddingModelsService,
    save_embedding_config,
)
from apps.common.models.models import (
    SetEmbeddingModelRequest,
    SetModelRequest,
    TestEmbeddingPayload,
    TestModelPayload,
)
from apps.common.models.router import router as models_router
from apps.common.models.service import (
    ModelsService,
    get_provider_config,
    load_root_config,
    resolve_active_config_path,
    save_ai_config,
    save_root_config,
    update_provider_config,
)

__all__ = [
    "EmbeddingModelsService",
    "ModelsService",
    "SetEmbeddingModelRequest",
    "SetModelRequest",
    "TestEmbeddingPayload",
    "TestModelPayload",
    "get_provider_config",
    "load_root_config",
    "models_router",
    "resolve_active_config_path",
    "save_ai_config",
    "save_embedding_config",
    "save_root_config",
    "update_provider_config",
]
