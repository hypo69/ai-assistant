# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Obsidian i18n
# =============================================================================
# Description:
#   Загрузчик словарей локализации и вспомогательные функции интернационализации
#   для компактного хранилища Obsidian Vault (`_Knowledge_Base.md`, блоки знаний
#   в документах и тематические конспекты `_Topics/<Тема>.md`).
#   Все переводы и настройки читаются из `obsidian_i18n.json` через `j_loads_ns`.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.obsidian_i18n import get_obsidian_locale
#
#     loc = get_obsidian_locale("he")
#     print(loc["kb_title"].format(ws_name="דוד משה"))
#
# File: obsidian_i18n.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 16:57:00
# =============================================================================

from __future__ import annotations
"""Мультиязычные словари шаблонов для Obsidian Vault, загружаемые из JSON-конфигурации."""

from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Optional

from src.utils.jjson import j_loads_ns

_I18N_CONFIG_PATH = Path(__file__).resolve().with_name("obsidian_i18n.json")


def _load_obsidian_i18n_cfg() -> SimpleNamespace:
    """Загружает конфигурацию локализации Obsidian Vault через j_loads_ns."""
    cfg = j_loads_ns(_I18N_CONFIG_PATH)
    if not vars(cfg):
        return SimpleNamespace()
    return cfg


def _ns_to_dict(ns: Optional[SimpleNamespace]) -> Dict[str, str]:
    """Преобразует SimpleNamespace в словарь строк."""
    if isinstance(ns, SimpleNamespace):
        return {k: str(v) for k, v in vars(ns).items()}
    if isinstance(ns, dict):
        return {str(k): str(v) for k, v in ns.items()}
    return {}


def _build_locales_map() -> Dict[str, Dict[str, str]]:
    """Формирует карту локалей из файла obsidian_i18n.json."""
    cfg = _load_obsidian_i18n_cfg()
    locales_ns = getattr(cfg, "locales", None)
    if not isinstance(locales_ns, SimpleNamespace):
        return {}
    return {lang: _ns_to_dict(val) for lang, val in vars(locales_ns).items()}


OBSIDIAN_I18N: Dict[str, Dict[str, str]] = _build_locales_map()


def normalize_obsidian_lang(language: Optional[str] = None) -> str:
    """Нормализует код языка для локализации шаблонов Obsidian Vault.

    Args:
        language: Исходный код языка (например, 'he', 'ua', 'uk', 'en', 'ru').

    Returns:
        str: Нормализованный код поддерживаемого языка из конфигурации.
    """
    cfg = _load_obsidian_i18n_cfg()
    default_lang = str(getattr(cfg, "default_language", "") or "")
    aliases_ns = getattr(cfg, "language_aliases", None)
    aliases = _ns_to_dict(aliases_ns)

    raw = (language or "").strip().lower().replace("_", "-").split("-")[0]
    if not raw or raw == "unknown":
        return default_lang

    mapped = aliases.get(raw, raw)
    return mapped if mapped in OBSIDIAN_I18N else default_lang


def get_obsidian_locale(language: Optional[str] = None) -> Dict[str, str]:
    """Возвращает словарь локализованных строк Obsidian Vault для указанного языка.

    Args:
        language: Код языка рабочей области или документа.

    Returns:
        Dict[str, str]: Словарь переведённых шаблонов и меток.
    """
    cfg = _load_obsidian_i18n_cfg()
    default_lang = str(getattr(cfg, "default_language", "") or "")
    norm = normalize_obsidian_lang(language)
    return OBSIDIAN_I18N.get(norm) or OBSIDIAN_I18N.get(default_lang, {})
