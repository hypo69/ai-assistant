# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Unified Embeddings Router
# =============================================================================
# Description:
#   Единая точка маршрутизации генерации эмбеддингов для всех поддерживаемых
#   провайдеров ИИ (Gemini, Ollama, OpenAI, Foundry, ONNX/Local BERT, Hash).
#   Скрывает специфику каждого провайдера (ротация ключей, HTTP-вызовы,
#   fallback на детерминированный хэш-вектор) от потребителей (TextRAG и др.).
#
# Usage Examples:
#   Python API:
#     from src.ai.orchestration.embeddings import embed_texts
#
#     vectors = embed_texts(["Привет"], provider="gemini", dimension=256)
#
# File: embeddings.py
# Project: ai-windows-admin
# Package: src.ai.orchestration
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-23 17:23:00
# =============================================================================

from __future__ import annotations
"""Единый маршрутизатор генерации векторных представлений (эмбеддингов) по провайдерам."""

import hashlib
import os
import re
from typing import List, Optional

import numpy as np
import requests

from logger import logger
from src.ai.orchestration.model_manager import get_provider_config

_WORD_RE = re.compile(r"\w+")


def hash_embed(texts: List[str], dimension: int = 256) -> List[List[float]]:
    """Генерирует детерминированные локальные хэш-векторы заданной размерности.

    Args:
        texts: Список текстовых фрагментов.
        dimension: Размерность выходных векторов.

    Returns:
        Список нормализованных векторов длины dimension.
    """
    vectors: List[List[float]] = []
    for text in texts:
        vec = np.zeros(dimension, dtype=np.float32)
        for word in _WORD_RE.findall((text or "").lower()):
            idx = int.from_bytes(hashlib.md5(word.encode("utf-8", errors="replace")).digest()[:4], "little") % dimension
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        vectors.append(vec.tolist())
    return vectors


def _resolve_default_provider() -> str:
    """Возвращает провайдера по умолчанию из глобальной конфигурации."""
    try:
        from src.config import ai_cfg
        prov = getattr(ai_cfg, "default_provider", None)
        if prov:
            return str(prov).lower().strip()
    except Exception:
        pass
    return "gemini"


def _resolve_embedding_model(provider: str, explicit_model: str = "") -> str:
    """Определяет имя модели эмбеддингов с учётом явного аргумента и конфигурации."""
    if explicit_model and explicit_model.strip():
        return explicit_model.strip()
    try:
        from src.config import ai_cfg
        emb_model = getattr(ai_cfg, "embedding_model", None)
        if emb_model and str(emb_model).strip():
            return str(emb_model).strip()
    except Exception:
        pass
    defaults = {
        "gemini": "models/gemini-embedding-2",
        "ollama": "nomic-embed-text",
        "openai": "text-embedding-3-small",
        "openai_compat": "text-embedding-3-small",
        "foundry": "text-embedding-3-small",
    }
    return defaults.get(provider, "")


def _embed_ollama(texts: List[str], model: str, dimension: int) -> Optional[List[List[float]]]:
    """Генерирует эмбеддинги через локальный сервер Ollama."""
    ollama_cfg = get_provider_config("ollama")
    base_url = (ollama_cfg.get("base_url") or "http://localhost:11434").rstrip("/")
    emb_model = (model or "nomic-embed-text").replace("models/", "")
    preview = texts[0] if len(texts[0]) <= 120 else f"{texts[0][:120]}..."
    logger.console(f"[Embeddings:Ollama] -> '{emb_model}' (текстов: {len(texts)}): \"{preview}\"")
    resp = requests.post(
        f"{base_url}/api/embed",
        json={"model": emb_model, "input": texts},
        timeout=(3.0, 20.0),
    )
    if resp.status_code != 200:
        return None
    embeddings = resp.json().get("embeddings") or []
    if embeddings and len(embeddings) == len(texts) and all(len(v) == dimension for v in embeddings):
        logger.console(
            f"[Embeddings:Ollama] <- '{emb_model}': получено {len(embeddings)} вектор(ов) (размерность: {len(embeddings[0])})"
        )
        return embeddings
    return None


def _embed_openai_compat(
    texts: List[str],
    provider: str,
    model: str,
    dimension: int,
    api_key: Optional[str] = None,
) -> Optional[List[List[float]]]:
    """Генерирует эмбеддинги через OpenAI-совместимый API (OpenAI, Microsoft Foundry и др.)."""
    cfg = get_provider_config(provider)
    base_url = (cfg.get("base_url") or ("https://api.openai.com/v1" if provider == "openai" else "")).rstrip("/")
    if not base_url:
        return None
    token = api_key or cfg.get("api_key") or os.getenv("OPENAI_API_KEY", "")
    emb_model = (model or "text-embedding-3-small").replace("models/", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {"model": emb_model, "input": texts}
    if dimension > 0 and provider == "openai":
        payload["dimensions"] = dimension

    preview = texts[0] if len(texts[0]) <= 120 else f"{texts[0][:120]}..."
    logger.console(f"[Embeddings:{provider}] -> '{emb_model}' (текстов: {len(texts)}): \"{preview}\"")
    resp = requests.post(f"{base_url}/embeddings", json=payload, headers=headers, timeout=(5.0, 30.0))
    if resp.status_code != 200:
        return None
    items = resp.json().get("data") or []
    embeddings = [item.get("embedding") for item in items if isinstance(item, dict) and item.get("embedding")]
    if embeddings and len(embeddings) == len(texts) and all(len(v) == dimension for v in embeddings):
        logger.console(
            f"[Embeddings:{provider}] <- '{emb_model}': получено {len(embeddings)} вектор(ов) (размерность: {len(embeddings[0])})"
        )
        return embeddings
    return None


def embed_texts(
    texts: List[str],
    provider: Optional[str] = None,
    model: str = "",
    dimension: int = 256,
    task_type: str = "RETRIEVAL_DOCUMENT",
    api_key: Optional[str] = None,
) -> List[List[float]]:
    """Единая точка генерации эмбеддингов для всех провайдеров ИИ с безопасным fallback.

    Маршрутизирует запрос к выбранному провайдеру ('gemini', 'ollama', 'openai',
    'foundry', 'onnx', 'local_bert', 'hash', 'agy') и возвращает векторы заданной размерности.

    Args:
        texts: Список текстовых фрагментов для векторизации.
        provider: Имя провайдера ИИ (если не задано, берётся из конфигурации).
        model: Имя модели эмбеддингов (опционально).
        dimension: Требуемая размерность векторов.
        task_type: Тип задачи эмбеддингов (для провайдеров, поддерживающих task_type).
        api_key: Прямой API-ключ (опционально).

    Returns:
        Список векторов размерности dimension для каждого элемента texts.
    """
    if not texts:
        return []

    prov = (provider or _resolve_default_provider()).lower().strip()
    emb_model = _resolve_embedding_model(prov, model)

    try:
        if prov == "gemini" or (api_key and prov not in ("openai", "openai_compat", "foundry")):
            from src.ai.gemini.embeddings import embed_texts as gemini_embed_texts

            vecs = gemini_embed_texts(
                texts=texts,
                model=emb_model or "models/gemini-embedding-2",
                dimension=dimension,
                task_type=task_type,
                api_key=api_key,
            )
            if vecs and len(vecs) == len(texts):
                return vecs

        elif prov == "ollama":
            vecs = _embed_ollama(texts, emb_model, dimension)
            if vecs:
                return vecs

        elif prov in ("openai", "openai_compat", "foundry"):
            vecs = _embed_openai_compat(texts, prov, emb_model, dimension, api_key=api_key)
            if vecs:
                return vecs

        else:
            logger.debug(
                f"[Embeddings] Для провайдера '{prov}' используются детерминированные локальные эмбеддинги."
            )
            return hash_embed(texts, dimension=dimension)

    except Exception as exc:
        logger.debug(f"[Embeddings] Провайдер '{prov}' недоступен ({exc}), переход на детерминированный хэш-эмбеддинг.")

    return hash_embed(texts, dimension=dimension)


__all__ = ["embed_texts", "hash_embed"]
