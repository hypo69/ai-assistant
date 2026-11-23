# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Local Browser BERT Package
# =============================================================================
# Description:
#   Пакет управления компактными BERT-моделями (ONNX INT8/FP32) для
#   клиентского инференса в браузере Electron (WebGPU / WASM).
#
# File: __init__.py
# Project: ai-windows-admin
# Package: src.ai.local_bert
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 00:45:00
# =============================================================================

from __future__ import annotations
"""Пакет каталога и настроек локальных BERT-моделей для браузерного инференса."""

from src.ai.local_bert.catalog import (
    LOCAL_BERT_MODELS,
    LocalBertModelInfo,
    get_local_bert_model,
    list_local_bert_models,
    resolve_model_for_language,
)
from src.ai.local_bert.settings import (
    LocalBertSettings,
    LocalBertSettingsManager,
)

__all__ = [
    "LOCAL_BERT_MODELS",
    "LocalBertModelInfo",
    "LocalBertSettings",
    "LocalBertSettingsManager",
    "get_local_bert_model",
    "list_local_bert_models",
    "resolve_model_for_language",
]
