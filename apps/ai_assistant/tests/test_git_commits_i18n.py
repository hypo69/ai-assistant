# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Git Commits i18n Verification
# =============================================================================
# Description:
#   Тесты для проверки мультиязычности Git коммитов и интерфейса вкладки #tab-commits:
#   - Проверка словарей GIT_COMMIT_I18N на полноту ключей во всех 4 языках (ru, he, en, uk)
#   - Проверка нормализации тегов языков (he-IL, ua, en-US)
#   - Проверка форматирования сообщений коммитов на иврите, английском, украинском и русском
#   - Проверка наличия и корректности переводов ui.commits в файлах локализации
#
# File: test_git_commits_i18n.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 18:35:00
# =============================================================================

from __future__ import annotations
"""Тесты валидации мультиязычности коммитов и вкладки #tab-commits."""

import json
from pathlib import Path
import pytest

from apps.ai_assistant.core.git_i18n import (
    GIT_COMMIT_I18N,
    get_git_commit_msg,
    normalize_git_lang,
)


def test_git_commit_i18n_keys_completeness() -> None:
    """Проверяет, что все ключи присутствуют во всех поддерживаемых языках."""
    base_keys = set(GIT_COMMIT_I18N["ru"].keys())
    for lang in ["he", "en", "uk"]:
        assert lang in GIT_COMMIT_I18N, f"Язык {lang} отсутствует в GIT_COMMIT_I18N"
        lang_keys = set(GIT_COMMIT_I18N[lang].keys())
        missing = base_keys - lang_keys
        assert not missing, f"В языке {lang} отсутствуют ключи: {missing}"


def test_normalize_git_lang() -> None:
    """Проверяет нормализацию различных форматов языковых тегов."""
    assert normalize_git_lang("he") == "he"
    assert normalize_git_lang("he-IL") == "he"
    assert normalize_git_lang("HE_il") == "he"
    assert normalize_git_lang("ua") == "uk"
    assert normalize_git_lang("uk-UA") == "uk"
    assert normalize_git_lang("en-US") == "en"
    assert normalize_git_lang("ru-RU") == "ru"
    assert normalize_git_lang("") == "ru"
    assert normalize_git_lang(None) == "ru"
    assert normalize_git_lang("unknown_lang") == "ru"


def test_hebrew_commit_messages() -> None:
    """Проверяет генерацию сообщений коммитов на иврите."""
    init_msg = get_git_commit_msg("git_init", lang="he")
    assert "תצורה ראשונית" in init_msg

    idx_msg = get_git_commit_msg("index_linked_file", lang="he", name="מסמך.txt")
    assert "אינדוקס קובץ מקושר מסמך.txt" == idx_msg

    create_msg = get_git_commit_msg("file_create", lang="he", name="test.md")
    assert "נוצר קובץ: test.md" == create_msg

    del_msg = get_git_commit_msg("file_delete", lang="he", name="test.md")
    assert "נמחק קובץ: test.md" == del_msg

    update_msg = get_git_commit_msg("file_update", lang="he", name="test.md")
    assert "עודכן: test.md" == update_msg

    watchdog_msg = get_git_commit_msg("watchdog_change", lang="he", name="data.txt")
    assert "Watchdog: שינוי ב-data.txt" == watchdog_msg


def test_english_and_ukrainian_commit_messages() -> None:
    """Проверяет генерацию сообщений коммитов на английском и украинском."""
    en_msg = get_git_commit_msg("index_linked_file", lang="en", name="doc.txt")
    assert en_msg == "Index linked file doc.txt"

    uk_msg = get_git_commit_msg("index_linked_file", lang="uk", name="doc.txt")
    assert uk_msg == "Індексація пов'язаного файлу doc.txt"


def test_ui_commits_locales_synchronized() -> None:
    """Проверяет синхронизацию ключей ui.commits в двух слоях WebGUI (api/webgui и common/webgui)."""
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    locales_api = base_dir / "apps" / "ai_assistant" / "api" / "webgui" / "locales"
    locales_common = base_dir / "apps" / "common" / "webgui" / "locales"

    for ldir in [locales_api, locales_common]:
        for lang in ["ru", "he", "en", "uk"]:
            fpath = ldir / f"{lang}.json"
            assert fpath.exists(), f"Файл {fpath} не найден"
            data = json.loads(fpath.read_text(encoding="utf-8"))
            commits_ui = data.get("ui", {}).get("commits", {})
            assert commits_ui, f"В {fpath} отсутствует ui.commits"

            # Проверяем обязательные ключи таблицы
            assert "txt_37157665" in commits_ui  # Заголовок 'Сообщение'
            assert "txt_fb3df31b" in commits_ui  # Заголовок 'Действия'
            assert "commitsCountSuffix" in commits_ui
            assert "notFound" in commits_ui
            assert "authorUnknown" in commits_ui

            # Для иврита проверяем, что используются дружелюбные бизнес-термины без Git-жаргона
            if lang == "he":
                assert commits_ui["txt_37157665"] == "מה קרה"
                assert commits_ui["txt_fb3df31b"] == "פעולות"
                assert commits_ui["commitsCountSuffix"] == "אירועים"
                assert commits_ui["notFound"] == "אין עדיין רשומות ביומן"
                assert commits_ui["authorUnknown"] == "מערכת"

            # Проверяем синхронизацию ключей дружелюбного сравнения версий (ui.diff)
            diff_ui = data.get("ui", {}).get("diff", {})
            assert diff_ui, f"В {fpath} отсутствует ui.diff"
            for req_key in ("modeFriendly", "modeRaw", "onlyChanges", "addedLabel", "removedLabel"):
                assert req_key in diff_ui, f"В {fpath} отсутствует ключ ui.diff.{req_key}"
