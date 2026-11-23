# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Git i18n
# =============================================================================
# Description:
#   Загрузчик словарей локализации и вспомогательные функции интернационализации
#   для автоматически формируемых Git commit сообщений в рабочих пространствах.
#   Все переводы и настройки читаются из `git_i18n.json` через `j_loads_ns`.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.git_i18n import get_git_commit_msg
#
#     msg = get_git_commit_msg("index_linked_file", lang="he", name="doc.txt")
#     print(msg)  # "אינדוקס קובץ מקושר doc.txt"
#
# File: git_i18n.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 16:57:00
# =============================================================================

from __future__ import annotations
"""Мультиязычные шаблоны для Git commit сообщений, загружаемые из JSON-конфигурации."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

from src.utils.jjson import j_loads_ns

_GIT_I18N_CONFIG_PATH = Path(__file__).resolve().with_name("git_i18n.json")


def _load_git_i18n_cfg() -> SimpleNamespace:
    """Загружает конфигурацию локализации Git-коммитов через j_loads_ns."""
    cfg = j_loads_ns(_GIT_I18N_CONFIG_PATH)
    if not vars(cfg):
        return SimpleNamespace()
    return cfg


def _build_git_locales() -> Dict[str, Dict[str, str]]:
    """Формирует карту локализованных шаблонов коммитов из git_i18n.json."""
    cfg = _load_git_i18n_cfg()
    locales_ns = getattr(cfg, "locales", None)
    if not isinstance(locales_ns, SimpleNamespace):
        return {}
    return {
        lang: {k: str(v) for k, v in vars(val).items()}
        for lang, val in vars(locales_ns).items()
        if isinstance(val, SimpleNamespace)
    }


GIT_COMMIT_I18N: Dict[str, Dict[str, str]] = _build_git_locales()


def normalize_git_lang(lang: Optional[str]) -> str:
    """Нормализует код языка к поддерживаемому ключу из git_i18n.json.

    Args:
        lang: Входной код языка или локали (например 'he-IL', 'ua', 'uk-UA').

    Returns:
        str: Нормализованный базовый код языка.
    """
    cfg = _load_git_i18n_cfg()
    default_lang = str(getattr(cfg, "default_language", "") or "")
    if not lang:
        return default_lang
    clean = str(lang).strip().lower().replace("_", "-").split("-")[0]
    if clean == "ua":
        return "uk"
    if clean in GIT_COMMIT_I18N:
        return clean
    return default_lang


def get_git_commit_msg(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """Возвращает локализованное сообщение Git коммита с подстановкой параметров.

    Args:
        key: Идентификатор шаблона сообщения.
        lang: Код языка (при None используется default_language из git_i18n.json).
        **kwargs: Параметры для форматирования строки шаблона.

    Returns:
        str: Сформированное локализованное сообщение коммита.
    """
    cfg = _load_git_i18n_cfg()
    default_lang = str(getattr(cfg, "default_language", "") or "")
    norm_lang = normalize_git_lang(lang)
    lang_dict = GIT_COMMIT_I18N.get(norm_lang) or GIT_COMMIT_I18N.get(default_lang, {})
    template = lang_dict.get(key)
    if not template:
        template = GIT_COMMIT_I18N.get(default_lang, {}).get(key, key)
    try:
        return template.format(**kwargs)
    except Exception:
        return template
