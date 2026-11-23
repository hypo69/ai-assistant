# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Local Browser BERT Catalog
# =============================================================================
# Description:
#   Реестр компактных BERT-подобных моделей в формате ONNX (INT8/FP32),
#   совместимых с запуском напрямую в Electron Chromium (Transformers.js +
#   WebGPU / WASM) для русского, английского, иврита и украинского языков.
#
# File: catalog.py
# Project: ai-windows-admin
# Package: src.ai.local_bert
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 00:45:00
# =============================================================================

from __future__ import annotations
"""Реестр компактных ONNX BERT-моделей для браузерного инференса."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class LocalBertModelInfo:
    """Метаданные компактной BERT-модели для клиентского инференса.

    Attributes:
        model_id: Идентификатор репозитория модели на Hugging Face Hub.
        title: Краткое отображаемое название модели.
        languages: Кортеж поддерживаемых ISO-кодов языков ('ru', 'en', 'he', 'uk').
        is_multilingual: Признак мультиязычной модели.
        size_int8_mb: Ориентировочный размер квантованной INT8-версии в мегабайтах.
        size_fp32_mb: Ориентировочный размер полной FP32-версии в мегабайтах.
        dimensions: Размерность выходного вектора эмбеддинга.
        max_tokens: Максимальная длина контекста в токенах.
        query_prefix: Обязательный префикс для поисковых запросов (например, 'query: ').
        passage_prefix: Обязательный префикс для индексируемых фрагментов (например, 'passage: ').
        recommended_tasks: Список рекомендуемых задач ('embeddings', 'routing', 'cache').
        description_ru: Описание модели на русском языке.
    """

    model_id: str
    title: str
    languages: Tuple[str, ...]
    is_multilingual: bool
    size_int8_mb: int
    size_fp32_mb: int
    dimensions: int
    max_tokens: int
    query_prefix: str = ""
    passage_prefix: str = ""
    recommended_tasks: Tuple[str, ...] = ("embeddings", "routing", "cache")
    description_ru: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует метаданные модели в сериализуемый словарь."""
        data = asdict(self)
        data["languages"] = list(self.languages)
        data["recommended_tasks"] = list(self.recommended_tasks)
        return data


LOCAL_BERT_MODELS: Tuple[LocalBertModelInfo, ...] = (
    LocalBertModelInfo(
        model_id="Xenova/multilingual-e5-small",
        title="Multilingual E5 Small (Рекомендуемая)",
        languages=("ru", "en", "he", "uk"),
        is_multilingual=True,
        size_int8_mb=35,
        size_fp32_mb=118,
        dimensions=384,
        max_tokens=512,
        query_prefix="query: ",
        passage_prefix="passage: ",
        recommended_tasks=("embeddings", "routing", "cache"),
        description_ru="Оптимальная мультиязычная модель для ru/en/he/uk: единое векторное пространство и кросс-языковой поиск.",
    ),
    LocalBertModelInfo(
        model_id="Xenova/paraphrase-multilingual-MiniLM-L12-v2",
        title="Multilingual MiniLM L12 v2",
        languages=("ru", "en", "he", "uk"),
        is_multilingual=True,
        size_int8_mb=45,
        size_fp32_mb=120,
        dimensions=384,
        max_tokens=128,
        recommended_tasks=("embeddings", "cache"),
        description_ru="Компактная модель семантического сходства на 50+ языков без обязательных префиксов.",
    ),
    LocalBertModelInfo(
        model_id="onnx-community/mmBERT-small-ONNX",
        title="mmBERT Small (ModernBERT)",
        languages=("ru", "en", "he", "uk"),
        is_multilingual=True,
        size_int8_mb=85,
        size_fp32_mb=180,
        dimensions=384,
        max_tokens=1024,
        recommended_tasks=("embeddings", "routing"),
        description_ru="Современный мультиязычный энкодер с расширенным контекстом до 1024 токенов.",
    ),
    LocalBertModelInfo(
        model_id="TrendHD/rubert-tiny2-int8",
        title="RuBERT-tiny2 (INT8)",
        languages=("ru",),
        is_multilingual=False,
        size_int8_mb=30,
        size_fp32_mb=116,
        dimensions=312,
        max_tokens=2048,
        recommended_tasks=("embeddings", "routing", "cache"),
        description_ru="Сверхбыстрая 3-слойная модель для русского языка с контекстом до 2048 токенов.",
    ),
    LocalBertModelInfo(
        model_id="Xenova/all-MiniLM-L6-v2",
        title="all-MiniLM-L6-v2 (English)",
        languages=("en",),
        is_multilingual=False,
        size_int8_mb=23,
        size_fp32_mb=90,
        dimensions=384,
        max_tokens=256,
        recommended_tasks=("embeddings", "routing", "cache"),
        description_ru="Самая лёгкая и быстрая базовая модель для английского текста и кода.",
    ),
    LocalBertModelInfo(
        model_id="codewithkyrian/heBERT",
        title="HeBERT (Hebrew ONNX)",
        languages=("he",),
        is_multilingual=False,
        size_int8_mb=110,
        size_fp32_mb=436,
        dimensions=768,
        max_tokens=512,
        recommended_tasks=("embeddings", "routing"),
        description_ru="Специализированная модель для иврита в готовом ONNX-формате.",
    ),
)

_MODELS_BY_ID: Dict[str, LocalBertModelInfo] = {
    model.model_id: model for model in LOCAL_BERT_MODELS
}


def list_local_bert_models(language: Optional[str] = None) -> List[LocalBertModelInfo]:
    """Возвращает список доступных компактных BERT-моделей.

    Args:
        language: Опциональный ISO-код языка ('ru', 'en', 'he', 'uk') для фильтрации.

    Returns:
        List[LocalBertModelInfo]: Список подходящих описаний моделей.
    """
    if not language:
        return list(LOCAL_BERT_MODELS)
    lang_norm = language.lower().strip()
    return [m for m in LOCAL_BERT_MODELS if lang_norm in m.languages]


def get_local_bert_model(model_id: str) -> Optional[LocalBertModelInfo]:
    """Возвращает метаданные модели по её идентификатору.

    Args:
        model_id: Идентификатор модели (например, 'Xenova/multilingual-e5-small').

    Returns:
        Optional[LocalBertModelInfo]: Метаданные модели или None, если модель не в каталоге.
    """
    return _MODELS_BY_ID.get((model_id or "").strip())


def resolve_model_for_language(
    language: str,
    mode: str,
    default_model: str,
    per_language_models: Dict[str, str],
) -> str:
    """Определяет идентификатор модели для заданного языка с учётом режима работы.

    Args:
        language: ISO-код языка ('ru', 'en', 'he', 'uk').
        mode: Режим выбора ('multilingual' или 'per_language').
        default_model: Модель по умолчанию для мультиязычного режима.
        per_language_models: Словарь соответствия языка и модели.

    Returns:
        str: Идентификатор выбранной модели.
    """
    if mode == "per_language":
        lang_norm = (language or "").lower().strip()
        candidate = per_language_models.get(lang_norm, "").strip()
        if candidate:
            return candidate
    return default_model
