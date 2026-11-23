# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Models & Providers Management Router (Adapter)
# =============================================================================
# Description:
#   Маршрутизатор моделей ИИ для приложения AI Assistant.
#   Делегирует всю логику общему пакету apps.common.models.
#
# File: router_models.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 00:10:00
# =============================================================================

from __future__ import annotations

"""Адаптер маршрутизатора моделей ИИ к общему модулю apps.common.models."""

from apps.common.models import (
    EmbeddingModelsService,
    ModelsService,
    SetEmbeddingModelRequest,
    SetModelRequest,
    TestEmbeddingPayload,
    TestModelPayload,
    get_provider_config,
    load_root_config,
    models_router as router,
    resolve_active_config_path,
    save_ai_config,
    save_embedding_config,
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
    "resolve_active_config_path",
    "router",
    "save_ai_config",
    "save_embedding_config",
    "save_root_config",
    "update_provider_config",
]
