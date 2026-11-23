# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Common Models - Embedding Models Service
# =============================================================================
# Description:
#   Сервисный слой управления моделями эмбеддингов: каталог по провайдерам
#   (Local Browser BERT WebAssembly/WebGPU, Gemini, Ollama, OpenAI, Hash),
#   чтение/сохранение активной модели и живое тестирование векторизации.
#
# File: embedding_service.py
# Package: apps.common.models
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 00:09:00
# =============================================================================

from __future__ import annotations

"""Сервисный слой для управления и тестирования моделей эмбеддингов."""

import asyncio
import hashlib
import os
import re
import time
from typing import Any, Dict, List, Optional

import numpy as np
import requests

from logger import logger
from apps.common.models.models import SetEmbeddingModelRequest, TestEmbeddingPayload
from apps.common.models.service import (
    get_provider_config,
    load_root_config,
    save_root_config,
)

_WORD_RE = re.compile(r"\w+")
_KNOWN_DIMENSIONS: Dict[str, int] = {
    "gemini-embedding-001": 3072,
    "text-embedding-004": 768,
    "gemini-embedding-2": 3072,
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "bge-m3": 1024,
    "all-minilm": 384,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "hash-md5-256": 256,
    "hash-md5-384": 384,
    "hash-md5-768": 768,
}


def _resolve_model_dimension(provider: str, model_name: str) -> int:
    """Определяет ожидаемую размерность вектора для модели эмбеддингов."""
    clean = (model_name or "").replace("models/", "").strip()
    if provider == "local_bert":
        try:
            from src.ai.local_bert import get_local_bert_model
            meta = get_local_bert_model(clean)
            if meta:
                return meta.dimensions
        except Exception:
            pass
        return 384
    return _KNOWN_DIMENSIONS.get(clean, 384)


def save_embedding_config(
    provider: Optional[str] = None,
    model_name: str = "",
    dimension: Optional[int] = None,
) -> None:
    """Атомарно сохраняет активный провайдер и модель эмбеддингов в config.json."""
    cfg = load_root_config()
    ai_sec = cfg.setdefault("ai_providers_and_models_configuration", {})
    prov_norm = (provider or "").lower().strip()
    if prov_norm:
        ai_sec["embedding_provider"] = prov_norm
    if model_name:
        ai_sec["embedding_model"] = model_name.strip()
    if dimension is not None:
        ai_sec["embedding_dimension"] = int(dimension)
    elif prov_norm and model_name:
        ai_sec["embedding_dimension"] = _resolve_model_dimension(prov_norm, model_name)

    if prov_norm == "local_bert" and model_name:
        providers = ai_sec.setdefault("providers", {})
        lb_cfg = providers.setdefault("local_bert", {})
        lb_cfg["enabled"] = True
        lb_cfg["default_model"] = model_name.strip()

    save_root_config(cfg)


class EmbeddingModelsService:
    """Сервис управления и тестирования моделей эмбеддингов."""

    @staticmethod
    def get_available_embedding_models(refresh: bool = False) -> Dict[str, Any]:
        """Возвращает сгруппированный каталог моделей эмбеддингов и метаданные."""
        from src.ai.orchestration.embedding_models import get_all_embedding_models
        from src.ai.local_bert import list_local_bert_models

        grouped = get_all_embedding_models(force_refresh=refresh)
        local_bert_meta = {m.model_id: m.to_dict() for m in list_local_bert_models()}
        return {
            "status": "ok",
            "models": grouped,
            "browser_providers": ["local_bert"],
            "metadata": {
                "local_bert": local_bert_meta,
                "dimensions": dict(_KNOWN_DIMENSIONS),
            },
        }

    @staticmethod
    def get_active_embedding_model() -> Dict[str, Any]:
        """Возвращает текущую выбранную модель и провайдера эмбеддингов."""
        try:
            from src.user_settings import get_user_settings
            settings = get_user_settings()
            if settings.get("embedding_model"):
                prov = str(settings.get("embedding_provider") or "local_bert").lower().strip()
                mod = str(settings["embedding_model"]).strip()
                dim = int(settings.get("embedding_dimension") or _resolve_model_dimension(prov, mod))
                return {
                    "status": "ok",
                    "provider": prov,
                    "model": mod,
                    "dimension": dim,
                    "config_file": "user_settings",
                }
        except Exception:
            pass

        cfg = load_root_config()
        ai_sec = cfg.get("ai_providers_and_models_configuration", {})
        prov = str(ai_sec.get("embedding_provider") or "").lower().strip()
        model = str(ai_sec.get("embedding_model") or "").strip()

        if not prov or not model:
            lb_cfg = ai_sec.get("providers", {}).get("local_bert", {})
            if isinstance(lb_cfg, dict) and lb_cfg.get("enabled", True):
                prov = prov or "local_bert"
                model = model or str(lb_cfg.get("default_model") or "Xenova/multilingual-e5-small")
            else:
                prov = prov or "gemini"
                model = model or "gemini-embedding-001"

        dim = int(ai_sec.get("embedding_dimension") or _resolve_model_dimension(prov, model))
        return {
            "status": "ok",
            "provider": prov,
            "model": model,
            "dimension": dim,
            "config_file": "config.json",
        }

    @staticmethod
    def set_active_embedding_model(req: SetEmbeddingModelRequest) -> Dict[str, Any]:
        """Сохраняет выбранную модель эмбеддингов в профиле и config.json."""
        target_model = req.model.strip()
        provider = (req.provider or "").strip().lower()
        if not provider:
            if target_model.startswith(("Xenova/", "onnx-community/", "TrendHD/", "codewithkyrian/")):
                provider = "local_bert"
            elif target_model.startswith("hash-"):
                provider = "hash"
            elif "gemini" in target_model or target_model.startswith("text-embedding-004"):
                provider = "gemini"
            elif target_model.startswith("text-embedding-"):
                provider = "openai"
            else:
                provider = "ollama"

        dim = req.dimension or _resolve_model_dimension(provider, target_model)

        try:
            from src.user_settings import update_user_settings
            update_user_settings(
                embedding_provider=provider,
                embedding_model=target_model,
                embedding_dimension=dim,
            )
        except Exception as exc:
            logger.debug(f"[embedding_service] Ошибка обновления user_settings: {exc}")

        if req.save_to_config:
            save_embedding_config(provider=provider, model_name=target_model, dimension=dim)

        return {
            "status": "success",
            "message": f"Модель эмбеддингов {target_model} ({provider}) сохранена",
            "provider": provider,
            "model": target_model,
            "dimension": dim,
        }

    @staticmethod
    def _test_hash_embedding(text: str, model_name: str) -> List[float]:
        """Генерирует детерминированный локальный хэш-вектор для проверки."""
        dim = _resolve_model_dimension("hash", model_name)
        vec = np.zeros(dim, dtype=np.float32)
        for w in _WORD_RE.findall(text.lower()):
            idx = int.from_bytes(hashlib.md5(w.encode("utf-8", errors="replace")).digest()[:4], "little") % dim
            vec[idx] += 1.0
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    @staticmethod
    def _test_gemini_embedding(text: str, model_name: str) -> List[float]:
        """Выполняет тестовый запрос эмбеддинга через Google Gemini API с ротацией ключей."""
        from google import genai
        from src.ai.gemini.gemini_api_key_state import load_api_keys

        keys, _, _ = load_api_keys(skip_exhausted=True)
        if not keys:
            env_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY_1", "")
            if env_key:
                keys = [env_key]
        if not keys:
            raise RuntimeError("Не найдены активные API-ключи Google Gemini")

        full_model = model_name if model_name.startswith("models/") else f"models/{model_name}"
        last_err: Optional[Exception] = None
        for key in keys:
            try:
                client = genai.Client(api_key=key)
                resp = client.models.embed_content(model=full_model, contents=text)
                if resp and resp.embeddings:
                    return list(resp.embeddings[0].values)
            except Exception as exc:
                last_err = exc
                continue
        raise RuntimeError(f"Ошибка Gemini Embeddings ({full_model}): {last_err}")

    @staticmethod
    def _test_ollama_embedding(text: str, model_name: str) -> List[float]:
        """Выполняет тестовый запрос эмбеддинга через локальный сервер Ollama."""
        ollama_cfg = get_provider_config("ollama")
        base_url = (ollama_cfg.get("base_url") or "http://localhost:11434").rstrip("/")
        resp = requests.post(
            f"{base_url}/api/embed",
            json={"model": model_name, "input": text},
            timeout=(3.0, 20.0),
        )
        if resp.status_code == 404:
            resp = requests.post(
                f"{base_url}/api/embeddings",
                json={"model": model_name, "prompt": text},
                timeout=(3.0, 20.0),
            )
        resp.raise_for_status()
        data = resp.json()
        if "embeddings" in data and data["embeddings"]:
            return list(data["embeddings"][0])
        if "embedding" in data and data["embedding"]:
            return list(data["embedding"])
        raise RuntimeError("Ollama вернула пустой вектор эмбеддинга")

    @staticmethod
    def _test_openai_embedding(text: str, model_name: str) -> List[float]:
        """Выполняет тестовый запрос эмбеддинга через OpenAI-совместимый API."""
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Не задан OPENAI_API_KEY в переменных окружения")
        base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        resp = requests.post(
            f"{base_url}/embeddings",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model_name, "input": text},
            timeout=(5.0, 20.0),
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", [])
        if items and "embedding" in items[0]:
            return list(items[0]["embedding"])
        raise RuntimeError("OpenAI API вернул пустой вектор эмбеддинга")

    @staticmethod
    async def test_embedding_model(req: TestEmbeddingPayload) -> Dict[str, Any]:
        """Выполняет живой тест выбранной модели эмбеддингов."""
        t0 = time.perf_counter()
        active = EmbeddingModelsService.get_active_embedding_model()
        provider = (req.provider or active.get("provider") or "hash").strip().lower()
        model_name = (req.model or active.get("model") or "hash-md5-256").strip()
        text = (req.text or "Проверка семантического поиска и генерации векторов").strip()

        if provider == "local_bert":
            return {
                "status": "browser_required",
                "provider": provider,
                "model": model_name,
                "message": "Модель выполняется локально в браузере через WebAssembly / WebGPU (Transformers.js).",
            }

        try:
            if provider == "hash":
                vector = EmbeddingModelsService._test_hash_embedding(text, model_name)
            elif provider == "gemini":
                vector = await asyncio.to_thread(EmbeddingModelsService._test_gemini_embedding, text, model_name)
            elif provider == "ollama":
                vector = await asyncio.to_thread(EmbeddingModelsService._test_ollama_embedding, text, model_name)
            elif provider == "openai":
                vector = await asyncio.to_thread(EmbeddingModelsService._test_openai_embedding, text, model_name)
            else:
                raise ValueError(f"Неподдерживаемый провайдер эмбеддингов: {provider}")

            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            preview = [round(float(v), 5) for v in vector[:6]]
            return {
                "status": "success",
                "provider": provider,
                "model": model_name,
                "dimensions": len(vector),
                "vector_preview": preview,
                "duration_ms": duration_ms,
            }
        except Exception as exc:
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            logger.warning(f"[embedding_service] Ошибка теста эмбеддинга {provider}/{model_name}: {exc}")
            return {
                "status": "error",
                "provider": provider,
                "model": model_name,
                "message": str(exc),
                "duration_ms": duration_ms,
            }


__all__ = [
    "EmbeddingModelsService",
    "save_embedding_config",
]
