# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Local Browser BERT Settings
# =============================================================================
# Description:
#   Управление конфигурацией браузерного BERT-инференса (WebGPU / WASM):
#   Pydantic-валидация, загрузка и атомарное сохранение в config.json.
#
# File: settings.py
# Project: ai-windows-admin
# Package: src.ai.local_bert
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 00:45:00
# =============================================================================

from __future__ import annotations
"""Конфигурация и валидация настроек локальных браузерных BERT-моделей."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from header import __root__
from logger import logger


DEFAULT_PER_LANGUAGE_MODELS: Dict[str, str] = {
    "ru": "TrendHD/rubert-tiny2-int8",
    "en": "Xenova/all-MiniLM-L6-v2",
    "he": "codewithkyrian/heBERT",
    "uk": "Xenova/multilingual-e5-small",
}


class LocalBertSettings(BaseModel):
    """Схема настроек браузерного инференса компактных BERT-моделей.

    Attributes:
        enabled: Включён ли локальный браузерный инференс в Electron/WebGUI.
        mode: Режим выбора моделей ('multilingual' — одна общая, 'per_language' — своя на язык).
        default_model: Модель по умолчанию для мультиязычного режима.
        per_language_models: Соответствие ISO-кода языка и идентификатора модели.
        execution_backend: Предпочтительный бэкенд исполнения ('auto', 'webgpu', 'wasm').
        quantization: Тип весов ('q8' для INT8 или 'fp32' для полной точности).
        enable_intent_routing: Использовать ли BERT для быстрого роутинга намерений.
        enable_semantic_cache: Использовать ли семантический кэш ответов в браузере.
        semantic_cache_threshold: Порог косинусного сходства для попадания в кэш.
    """

    enabled: bool = True
    mode: Literal["multilingual", "per_language"] = "multilingual"
    default_model: str = "Xenova/multilingual-e5-small"
    per_language_models: Dict[str, str] = Field(
        default_factory=lambda: dict(DEFAULT_PER_LANGUAGE_MODELS)
    )
    execution_backend: Literal["auto", "webgpu", "wasm"] = "auto"
    quantization: Literal["q8", "fp32"] = "q8"
    enable_intent_routing: bool = True
    enable_semantic_cache: bool = True
    semantic_cache_threshold: float = Field(default=0.92, ge=0.5, le=0.99)


class LocalBertSettingsManager:
    """Менеджер чтения и атомарного сохранения настроек браузерного BERT."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Инициализирует менеджер с явным путём к файлу конфигурации.

        Args:
            config_path: Путь к config.json. По умолчанию используется корневой config.json.
        """
        self.config_path = config_path or (__root__ / "config.json")

    def _read_root_config(self) -> Dict[str, Any]:
        """Считывает весь JSON-файл конфигурации, возвращая пустой словарь при отсутствии."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning(f"[LocalBert] Ошибка чтения {self.config_path}: {exc}")
            return {}

    def _atomic_write_root_config(self, data: Dict[str, Any]) -> None:
        """Атомарно записывает обновлённый JSON-файл конфигурации на диск."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.config_path.with_suffix(f"{self.config_path.suffix}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.config_path)

    def load(self) -> LocalBertSettings:
        """Загружает и валидирует текущие настройки локального BERT.

        Returns:
            LocalBertSettings: Валидированный объект настроек.
        """
        cfg = self._read_root_config()
        ai_sec = cfg.get("ai_providers_and_models_configuration", {})
        providers = ai_sec.get("providers", {}) if isinstance(ai_sec, dict) else {}
        raw = providers.get("local_bert", {}) if isinstance(providers, dict) else {}
        if not isinstance(raw, dict):
            raw = {}
        merged_langs = dict(DEFAULT_PER_LANGUAGE_MODELS)
        if isinstance(raw.get("per_language_models"), dict):
            merged_langs.update(
                {str(k): str(v) for k, v in raw["per_language_models"].items() if v}
            )
        payload = {**raw, "per_language_models": merged_langs}
        return LocalBertSettings.model_validate(payload)

    def save(self, settings: LocalBertSettings | Dict[str, Any]) -> LocalBertSettings:
        """Валидирует и сохраняет настройки локального BERT в config.json.

        Args:
            settings: Экземпляр LocalBertSettings или словарь с параметрами.

        Returns:
            LocalBertSettings: Сохранённый и провалидированный объект настроек.
        """
        validated = (
            settings
            if isinstance(settings, LocalBertSettings)
            else LocalBertSettings.model_validate(settings)
        )
        cfg = self._read_root_config()
        ai_sec = cfg.setdefault("ai_providers_and_models_configuration", {})
        providers = ai_sec.setdefault("providers", {})
        providers["local_bert"] = validated.model_dump()
        self._atomic_write_root_config(cfg)
        logger.info(
            f"[LocalBert] Настройки сохранены: режим={validated.mode}, "
            f"бэкенд={validated.execution_backend}, модель={validated.default_model}"
        )
        return validated
