# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Gemini Embeddings Module
# =============================================================================
# Description:
#   Единый модуль генерации векторных представлений (эмбеддингов) Gemini с
#   инкапсулированной ротацией пула API-ключей, round-robin балансировкой,
#   sliding-window учётом минутной RPM-квоты (100 текстов/мин на ключ) и
#   автоматической обработкой 429/401/403.
#
# Usage Examples:
#   Python API:
#     from src.ai.gemini.embeddings import embed_texts
#
#     vectors = embed_texts(["Привет, мир"], dimension=256)
#
# File: embeddings.py
# Project: ai-windows-admin
# Package: src.ai.gemini
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-23 17:06:00
# =============================================================================

from __future__ import annotations
"""Генерация эмбеддингов Gemini с внутренней ротацией ключей и учётом RPM-квот."""

import json
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from logger import logger
from .errors import format_error_as_json
from .gemini_api_key_state import load_api_keys, mark_exhausted

_DEFAULT_EMBED_MODEL = "models/gemini-embedding-2"
_RPM_WINDOW_SECONDS = 60.0
_RPM_LIMIT_PER_KEY = 100
_MAX_RPM_WAIT_SECONDS = 65.0
_MAX_WAIT_CYCLES = 2
_MAX_CACHED_CLIENTS = 16

_RETRY_DELAY_RE = re.compile(
    r"(?:retry in\s+(\d+(?:\.\d+)?)s|['\"]retryDelay['\"]\s*:\s*['\"](\d+(?:\.\d+)?)s['\"])",
    re.IGNORECASE,
)
_RPM_LIMIT_TOKENS = (
    "perminute",
    "per_minute",
    "requests per minute",
    "embedcontentrequestsperminute",
)
_AUTH_DENIED_TOKENS = (
    "401",
    "403",
    "PERMISSION_DENIED",
    "API_KEY_INVALID",
    "API key not valid",
)

_STATE_LOCK = threading.Lock()
_KEY_USAGE: Dict[str, List[Tuple[float, int]]] = {}
_KEY_COOLDOWNS: Dict[str, float] = {}
_RR_CURSOR: int = 0
_CLIENTS: Dict[str, Any] = {}


def clear_rpm_state() -> None:
    """Сбрасывает локальное состояние RPM-квот, пауз, курсора ротации и кэша клиентов."""
    global _RR_CURSOR
    with _STATE_LOCK:
        _KEY_USAGE.clear()
        _KEY_COOLDOWNS.clear()
        _CLIENTS.clear()
        _RR_CURSOR = 0


def _is_rpm_quota_error(err_str: str) -> bool:
    """Определяет, относится ли ошибка 429 к временному минутному лимиту (RPM)."""
    lowered = err_str.lower()
    return any(token in lowered for token in _RPM_LIMIT_TOKENS)


def _parse_retry_delay(err_str: str, default: float = 60.0) -> float:
    """Извлекает рекомендованную задержку повтора (в секундах) из ответа Gemini API."""
    match = _RETRY_DELAY_RE.search(err_str)
    if match:
        raw = match.group(1) or match.group(2)
        if raw:
            try:
                return float(raw)
            except ValueError:
                pass
    return default


def _prune_usage_locked(key_name: str, now: float) -> List[Tuple[float, int]]:
    """Очищает устаревшие записи скользящего 60-секундного окна для ключа (вызывать под _STATE_LOCK)."""
    cutoff = now - _RPM_WINDOW_SECONDS
    entries = [item for item in _KEY_USAGE.get(key_name, []) if item[0] > cutoff]
    if entries:
        _KEY_USAGE[key_name] = entries
    else:
        _KEY_USAGE.pop(key_name, None)
    return entries


def _record_key_usage(key_name: str, text_count: int) -> None:
    """Фиксирует количество отправленных текстов в скользящем минутном окне ключа."""
    if not key_name or text_count <= 0:
        return
    now = time.monotonic()
    with _STATE_LOCK:
        entries = _prune_usage_locked(key_name, now)
        entries.append((now, int(text_count)))
        _KEY_USAGE[key_name] = entries


def _set_key_rpm_cooldown(key_name: str, delay_seconds: float) -> None:
    """Устанавливает временную паузу (cooldown) для ключа при получении 429 RPM от API."""
    if not key_name:
        return
    clamped = min(max(float(delay_seconds), 1.0), 120.0)
    with _STATE_LOCK:
        _KEY_COOLDOWNS[key_name] = time.monotonic() + clamped


def _select_key_candidate(
    api_keys: List[str],
    key_names: List[str],
    batch_len: int,
    tried: set[str],
) -> Tuple[Optional[Tuple[str, str]], Optional[float]]:
    """Выбирает ключ пула с доступной RPM-квотой по round-robin или возвращает время ожидания.

    Args:
        api_keys: Список значений API-ключей.
        key_names: Список имён API-ключей.
        batch_len: Количество текстов в текущем пакете.
        tried: Множество имён ключей, уже отклонённых в текущей попытке.

    Returns:
        Кортеж ((key_value, key_name) | None, min_wait_seconds | None).
    """
    global _RR_CURSOR
    n = len(api_keys)
    if n == 0:
        return None, None

    now = time.monotonic()
    best_wait: Optional[float] = None

    with _STATE_LOCK:
        start = _RR_CURSOR % n
        for offset in range(n):
            idx = (start + offset) % n
            name = key_names[idx]
            if name in tried:
                continue

            cd_until = _KEY_COOLDOWNS.get(name, 0.0)
            if cd_until > now:
                wait_cd = cd_until - now
                if best_wait is None or wait_cd < best_wait:
                    best_wait = wait_cd
                continue
            elif cd_until > 0.0:
                _KEY_COOLDOWNS.pop(name, None)

            entries = _prune_usage_locked(name, now)
            used = sum(cnt for _, cnt in entries)
            available = _RPM_LIMIT_PER_KEY - used

            # Ключ подходит, если в окне хватает квоты (либо окно пустое для пакета > лимита)
            if available >= batch_len or (batch_len > _RPM_LIMIT_PER_KEY and used == 0):
                _RR_CURSOR = (idx + 1) % n
                return (api_keys[idx], name), None

            # Вычисляем момент, когда освободится достаточно квоты в скользящем окне
            if entries:
                needed = batch_len - available
                freed = 0
                release_ts = entries[-1][0]
                for ts, cnt in entries:
                    freed += cnt
                    release_ts = ts
                    if freed >= needed:
                        break
                wait_win = max(0.5, (release_ts + _RPM_WINDOW_SECONDS) - now + 0.5)
                if best_wait is None or wait_win < best_wait:
                    best_wait = wait_win

    return None, best_wait


def _get_client(api_key: str) -> Any:
    """Возвращает кэшированный экземпляр google.genai.Client для указанного ключа."""
    from google import genai

    with _STATE_LOCK:
        client = _CLIENTS.get(api_key)
        if client is None:
            client = genai.Client(api_key=api_key)
            if len(_CLIENTS) >= _MAX_CACHED_CLIENTS:
                _CLIENTS.clear()
            _CLIENTS[api_key] = client
        return client


def _call_embed_api(
    api_key: str,
    key_name: str,
    texts: List[str],
    model: str,
    dimension: Optional[int],
    task_type: str,
) -> List[List[float]]:
    """Выполняет одиночный запрос embed_content к Gemini API."""
    from google.genai import types

    client = _get_client(api_key)
    sample_preview = texts[0] if len(texts[0]) <= 120 else f"{texts[0][:120]}..."
    logger.console(
        f"[GeminiEmbed] -> '{model}' (ключ: '{key_name}', текстов: {len(texts)}): \"{sample_preview}\""
    )
    cfg_kwargs: Dict[str, Any] = {"task_type": task_type}
    if dimension is not None:
        cfg_kwargs["output_dimensionality"] = dimension

    response = client.models.embed_content(
        model=model,
        contents=[types.Content(parts=[types.Part.from_text(text=t)]) for t in texts],
        config=types.EmbedContentConfig(**cfg_kwargs),
    )
    embeddings = [list(e.values) for e in (response.embeddings or [])]
    if not embeddings or (dimension is not None and any(len(v) != dimension for v in embeddings)):
        actual_dim = len(embeddings[0]) if embeddings else 0
        raise ValueError(
            f"Некорректная размерность векторов Gemini ({actual_dim} != {dimension})"
        )
    logger.console(
        f"[GeminiEmbed] <- '{model}' (ключ: '{key_name}'): "
        f"получено {len(embeddings)} вектор(ов) (размерность: {len(embeddings[0])})"
    )
    return embeddings


def embed_texts(
    texts: List[str],
    model: str = _DEFAULT_EMBED_MODEL,
    dimension: Optional[int] = None,
    task_type: str = "RETRIEVAL_DOCUMENT",
    api_key: Optional[str] = None,
) -> Optional[List[List[float]]]:
    """Генерирует эмбеддинги для списка текстов через Gemini API с внутренней ротацией ключей.

    Выполняет round-robin балансировку по пулу ключей с учётом скользящего минутного
    окна RPM (100 текстов/мин на ключ), ожидание освобождения ближайшего ключа при
    общей минутной паузе и автоматическое отключение исчерпанных/невалидных ключей.

    Args:
        texts: Список текстовых фрагментов для векторизации.
        model: Имя модели эмбеддингов Gemini.
        dimension: Требуемая размерность векторов (опционально).
        task_type: Тип задачи эмбеддингов (например, 'RETRIEVAL_DOCUMENT' или 'RETRIEVAL_QUERY').
        api_key: Прямой API-ключ (если передан, используется без пула ключей).

    Returns:
        Список векторов или None, если все ключи Gemini недоступны.
    """
    if not texts:
        return []

    model_name = (model or _DEFAULT_EMBED_MODEL).strip()
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"

    if api_key:
        try:
            return _call_embed_api(api_key, "direct_api_key", texts, model_name, dimension, task_type)
        except Exception as err:
            logger.debug(f"[GeminiEmbed] Ошибка прямого ключа Gemini: {err}")
            return None

    api_keys, key_names, _ = load_api_keys(skip_exhausted=True)
    if not api_keys:
        logger.debug("[GeminiEmbed] Нет доступных активных ключей Gemini в пуле.")
        return None

    tried: set[str] = set()
    wait_cycles = 0

    while True:
        candidate, wait_sec = _select_key_candidate(api_keys, key_names, len(texts), tried)

        if candidate is None:
            if wait_sec is not None and wait_sec <= _MAX_RPM_WAIT_SECONDS and wait_cycles < _MAX_WAIT_CYCLES:
                wait_cycles += 1
                logger.console(
                    f"[GeminiEmbed] Все ключи пула достигли минутного лимита RPM, "
                    f"ожидание {wait_sec:.1f}с до освобождения квоты..."
                )
                time.sleep(wait_sec)
                tried.clear()
                continue
            logger.warning("[GeminiEmbed] Все ключи Gemini недоступны или исчерпаны.")
            return None

        current_key, current_name = candidate
        try:
            vectors = _call_embed_api(current_key, current_name, texts, model_name, dimension, task_type)
            _record_key_usage(current_name, len(texts))
            return vectors
        except ValueError as dim_err:
            logger.warning(f"[GeminiEmbed] {dim_err}")
            return None
        except Exception as key_err:
            err_str = str(key_err)
            is_quota = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
            is_rpm = is_quota and _is_rpm_quota_error(err_str)
            is_auth_denied = any(token in err_str for token in _AUTH_DENIED_TOKENS)

            if is_rpm:
                delay_sec = _parse_retry_delay(err_str, default=60.0)
                _set_key_rpm_cooldown(current_name, delay_sec)
                logger.warning(
                    f"[GeminiEmbed] Ключ '{current_name}' достиг минутного лимита (429 RPM), "
                    f"пауза {delay_sec:.0f}с и переключение на следующий ключ пула."
                )
                continue

            if is_quota or is_auth_denied:
                tried.add(current_name)
                try:
                    mark_exhausted(current_name)
                except Exception:
                    pass
                reason = "суточная квота (429)" if is_quota else "доступ запрещён / невалидный ключ (401/403)"
                logger.warning(
                    f"[GeminiEmbed] Ключ '{current_name}' отклонён ({reason}), ротация на следующий ключ пула."
                )
                continue

            logger.debug(f"[GeminiEmbed] Ошибка Gemini API ({current_name}): {key_err}")
            return None


class GoogleGenerativeAIEmbeddingsMixin:
    """Миксин генерации эмбеддингов для GoogleGenerativeAI."""

    async def embed(self, text: str, model_name: str = _DEFAULT_EMBED_MODEL) -> np.ndarray | bool:
        """Генерирует векторное представление (эмбеддинг) для одного текста.

        Args:
            text: Исходный текст для векторизации.
            model_name: Имя модели эмбеддингов Gemini.

        Returns:
            Одномерный numpy-массив эмбеддинга или False при ошибке.
        """
        if not text:
            return False
        if hasattr(self, "_log_request_details"):
            self._log_request_details(method="embed", model=model_name, q=text)
        try:
            vectors = embed_texts([text], model=model_name)
            if vectors:
                arr = np.array(vectors[0])
                if hasattr(self, "_log_response_details"):
                    self._log_response_details(
                        method="embed",
                        model=model_name,
                        response_text=f"Vector generated successfully (shape: {arr.shape})",
                    )
                return arr
            err_empty = {
                "error": {
                    "code": 204,
                    "status": "EMPTY_EMBEDDING",
                    "message": "Empty embeddings response from model",
                    "model": model_name,
                }
            }
            logger.warning(
                f"GoogleGenerativeAI: Пустые эмбеддинги:\n{json.dumps(err_empty, ensure_ascii=False, indent=2)}"
            )
            return False
        except Exception as ex:
            err_json = format_error_as_json(ex, model=model_name)
            logger.error(f"GoogleGenerativeAI: Ошибка генерации эмбеддинга:\n{err_json}")
            return False
