# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Embedding Models Manager
# =============================================================================
# Description:
#   Каталог, обнаружение и кэширование моделей эмбеддингов для всех
#   поддерживаемых провайдеров (Gemini, Ollama, OpenAI, Local Browser BERT,
#   локальный детерминированный хэш-эмбеддер).
#
# Usage Examples:
#   Python API:
#     from src.ai.orchestration.embedding_models import (
#         get_available_embedding_models,
#         get_all_embedding_models,
#     )
#
#     models = get_available_embedding_models("gemini")
#     catalog = get_all_embedding_models()
#
# File: embedding_models.py
# Project: ai-windows-admin
# Package: src.ai.orchestration
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 00:08:00
# =============================================================================

from __future__ import annotations

"""Менеджер обнаружения и каталога моделей эмбеддингов по провайдерам."""

import os
import threading
from typing import Any, Dict, List

import requests
from google import genai

from logger import logger
from src.ai.orchestration.model_manager import (
    _get_provider_cfg,
    _normalize_model_name,
    is_provider_enabled,
)

_EMBEDDING_CACHE: Dict[str, List[str]] = {}
_EMBEDDING_CACHE_LOCK = threading.RLock()

_DEFAULT_GEMINI_EMBEDDINGS: List[str] = [
    "gemini-embedding-001",
    "text-embedding-004",
    "gemini-embedding-2",
]

_DEFAULT_OLLAMA_EMBEDDINGS: List[str] = [
    "nomic-embed-text",
    "mxbai-embed-large",
    "bge-m3",
    "all-minilm",
]

_DEFAULT_OPENAI_EMBEDDINGS: List[str] = [
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
]

_DEFAULT_HASH_EMBEDDINGS: List[str] = [
    "hash-md5-256",
    "hash-md5-384",
    "hash-md5-768",
]

_OLLAMA_EMBED_KEYWORDS = ("embed", "bge", "minilm", "e5", "nomic", "mxbai", "gte", "jina")


def _fetch_gemini_embedding_models(api_key: str = "") -> List[str]:
    """Получает список моделей эмбеддингов Google Gemini через SDK с fallback-каталогом."""
    discovered: List[str] = []
    key_to_use = api_key
    if not key_to_use:
        try:
            from src.ai.gemini.gemini_api_key_state import load_api_keys
            keys, _, _ = load_api_keys()
            if keys:
                key_to_use = keys[0]
        except Exception as exc:
            logger.debug(f"[EmbeddingModels] Не удалось загрузить ключ Gemini: {exc}")
        if not key_to_use:
            key_to_use = os.getenv("GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY_1", "")

    if key_to_use:
        try:
            client = genai.Client(api_key=key_to_use)
            for model in client.models.list():
                raw_name = getattr(model, "name", "") or ""
                norm = _normalize_model_name(raw_name)
                actions = (
                    getattr(model, "supported_actions", None)
                    or getattr(model, "supported_generation_methods", None)
                    or []
                )
                is_embed = any("embed" in str(a).lower() for a in actions) or "embedding" in norm.lower()
                if is_embed and norm and norm not in discovered:
                    discovered.append(norm)
        except Exception as exc:
            logger.debug(f"[EmbeddingModels] Не удалось опросить Gemini SDK для эмбеддингов: {exc}")

    combined = list(discovered)
    for fb in _DEFAULT_GEMINI_EMBEDDINGS:
        if fb not in combined:
            combined.append(fb)
    return combined


def _fetch_ollama_embedding_models() -> List[str]:
    """Получает список установленных моделей эмбеддингов с локального сервера Ollama."""
    ollama_cfg = _get_provider_cfg("ollama")
    base_url = (ollama_cfg.get("base_url") or "http://localhost:11434").rstrip("/")
    discovered: List[str] = []

    if is_provider_enabled("ollama"):
        try:
            resp = requests.get(f"{base_url}/api/tags", timeout=(1.5, 3.0))
            if resp.status_code == 200:
                data: Dict[str, Any] = resp.json()
                for item in data.get("models", []):
                    name = str(item.get("name", "")).strip()
                    low = name.lower()
                    if name and any(kw in low for kw in _OLLAMA_EMBED_KEYWORDS):
                        if name not in discovered:
                            discovered.append(name)
        except Exception as exc:
            logger.debug(f"[EmbeddingModels] Ollama ({base_url}) недоступна при опросе эмбеддингов: {exc}")

    for fb in _DEFAULT_OLLAMA_EMBEDDINGS:
        if fb not in discovered:
            discovered.append(fb)
    return discovered


def _fetch_local_bert_embedding_models() -> List[str]:
    """Возвращает идентификаторы компактных браузерных BERT-моделей (ONNX WebAssembly/WebGPU)."""
    from src.ai.local_bert import list_local_bert_models

    return [m.model_id for m in list_local_bert_models()]


def get_available_embedding_models(
    provider: str = "gemini",
    api_key: str = "",
    force_refresh: bool = False,
) -> List[str]:
    """Возвращает список доступных моделей эмбеддингов для указанного провайдера.

    Args:
        provider: Имя провайдера ('local_bert', 'gemini', 'ollama', 'openai', 'hash').
        api_key: Опциональный API-ключ для Gemini.
        force_refresh: Принудительно обновить кэш.

    Returns:
        List[str]: Список идентификаторов моделей эмбеддингов.
    """
    prov = (provider or "gemini").lower().strip()
    with _EMBEDDING_CACHE_LOCK:
        if not force_refresh and prov in _EMBEDDING_CACHE and _EMBEDDING_CACHE[prov]:
            return list(_EMBEDDING_CACHE[prov])

    if prov == "gemini":
        models = _fetch_gemini_embedding_models(api_key=api_key)
    elif prov == "ollama":
        models = _fetch_ollama_embedding_models()
    elif prov in ("openai", "openai_compat"):
        models = list(_DEFAULT_OPENAI_EMBEDDINGS)
    elif prov in ("local_bert", "bert", "browser_bert"):
        prov = "local_bert"
        models = _fetch_local_bert_embedding_models()
    elif prov == "hash":
        models = list(_DEFAULT_HASH_EMBEDDINGS)
    else:
        return []

    with _EMBEDDING_CACHE_LOCK:
        _EMBEDDING_CACHE[prov] = list(models)
    return list(models)


def get_all_embedding_models(force_refresh: bool = False) -> Dict[str, List[str]]:
    """Возвращает сгруппированный каталог моделей эмбеддингов по всем провайдерам.

    Args:
        force_refresh: Принудительно сбросить кэш и заново опросить провайдеров.

    Returns:
        Dict[str, List[str]]: Словарь вида {'local_bert': [...], 'gemini': [...], ...}.
    """
    return {
        "local_bert": get_available_embedding_models("local_bert", force_refresh=force_refresh),
        "gemini": get_available_embedding_models("gemini", force_refresh=force_refresh),
        "ollama": get_available_embedding_models("ollama", force_refresh=force_refresh),
        "openai": get_available_embedding_models("openai", force_refresh=force_refresh),
        "hash": get_available_embedding_models("hash", force_refresh=force_refresh),
    }


__all__ = [
    "get_available_embedding_models",
    "get_all_embedding_models",
]
