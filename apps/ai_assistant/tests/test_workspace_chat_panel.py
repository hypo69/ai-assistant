"""
=============================================================================
Process Name: Test AI Assistant Workspace Chat Panel & Resolution
=============================================================================
Description:
    Модульные тесты для проверки клиентской панели диалога с ИИ (Чат)
    tab_workspace (#tab-workspace#panel-chat), многоуровневого разрешения
    идентификатора рабочего пространства (включая имена на иврите דוד משה / דוד_משה),
    передачи функции getWorkspaceId из main.js и интернационализации (i18n).

File: test_workspace_chat_panel.py
Package: apps/ai_assistant/tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-19 21:11:00
=============================================================================
"""

import json
from pathlib import Path
import pytest

_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"


def test_workspace_chat_panel_script_structure() -> None:
    """Проверяет структуру клиентского модуля panel_chat/panel.js."""
    panel_js_path = _WEBGUI_DIR / "tab_workspace" / "panel_chat" / "panel.js"
    assert panel_js_path.exists(), f"Файл {panel_js_path} не найден"

    content = panel_js_path.read_text(encoding="utf-8")

    # 1. Проверяем наличие ключевых функций
    assert "function resolveCurrentWorkspaceId(" in content, "Функция resolveCurrentWorkspaceId не найдена"
    assert "function sendChatMessage(" in content, "Функция sendChatMessage не найдена"
    assert "function initChatPanel(" in content, "Функция initChatPanel не найдена"
    assert "function clearChatHistory(" in content, "Функция clearChatHistory не найдена"

    # 2. Проверяем многоуровневое разрешение workspace_id
    assert "getWorkspaceIdCallback" in content, "Проверка коллбека getWorkspaceIdCallback не найдена"
    assert "getCurrentWorkspaceId()" in content, "Вызов getCurrentWorkspaceId() не найден"
    assert "window.currentWorkspaceId" in content, "Проверка window.currentWorkspaceId не найдена"
    assert "window.getActiveWorkspaceId" in content, "Проверка window.getActiveWorkspaceId не найдена"
    assert "location.hash" in content, "Проверка URL hash не найдена"
    assert "ai_assistant_active_workspace" in content, "Проверка localStorage не найдена"

    # 3. Проверяем интернационализацию i18n
    assert "workspace.chatErrorNoWorkspace" in content, "Ключ i18n chatErrorNoWorkspace не найден"
    assert "workspace.chatErrorGeneration" in content, "Ключ i18n chatErrorGeneration не найден"
    assert "workspace.chatAiThinking" in content, "Ключ i18n chatAiThinking не найден"
    assert "workspace.chatSendingStatus" in content, "Ключ i18n chatSendingStatus не найден"


def test_workspace_main_js_initializes_chat_with_getter() -> None:
    """Проверяет, что tab_workspace/main.js передает getWorkspaceId в initChatPanel."""
    main_js_path = _WEBGUI_DIR / "tab_workspace" / "main.js"
    assert main_js_path.exists(), f"Файл {main_js_path} не найден"

    content = main_js_path.read_text(encoding="utf-8")

    assert "initChatPanel(getWorkspaceId);" in content, "initChatPanel(getWorkspaceId) не найден в main.js"
    assert "document.addEventListener('workspace:changed'" in content, "Слушатель workspace:changed не найден"


def test_workspace_select_panel_fallback_support() -> None:
    """Проверяет отказоустойчивость getCurrentWorkspaceId в panel_workspace_select/panel.js."""
    select_panel_path = _WEBGUI_DIR / "tab_workspace" / "panel_workspace_select" / "panel.js"
    assert select_panel_path.exists(), f"Файл {select_panel_path} не найден"

    content = select_panel_path.read_text(encoding="utf-8")

    assert "window.getCurrentWorkspaceId = getCurrentWorkspaceId;" in content
    assert "window.setCurrentWorkspaceId = setCurrentWorkspaceId;" in content
    assert "window.currentWorkspaceId = currentWorkspaceId;" in content
    assert "window.getActiveWorkspaceId" in content


def test_chat_and_subtabs_i18n_keys_present_in_all_locales() -> None:
    """Проверяет наличие всех необходимых ключей чата и субпанелей во всех языковых файлах."""
    required_keys = [
        "chatErrorNoWorkspace",
        "chatErrorGeneration",
        "chatSendingStatus",
        "chatAiThinking",
        "chatNoAnswer",
        "chatDocumentFallback",
        "chatSuccessStatus",
        "chatErrorStatus",
        "chatReadyStatus",
        "chatClearTitle",
        "chatClearBtn",
        "chatEmptyTitle",
        "chatEmptyDesc",
        "chatInputPlaceholder",
        "chatSendBtn",
        "chatFactsInFile",
        "chatScheduleDefaultBtn",
        "chatScheduleDateTime",
        "chatScheduleAddress",
        "chatScheduleAttendees",
        "chatScheduleReminders",
        "chatScheduleRemindersValue",
        "chatScheduleIcsFile",
        "chatScheduleGcalCreated",
    ]

    for lang in ["ru", "en", "he", "uk"]:
        locale_path = _WEBGUI_DIR / "locales" / f"{lang}.json"
        assert locale_path.exists(), f"Файл локали {locale_path} не найден"

        data = json.loads(locale_path.read_text(encoding="utf-8"))
        ws_data = data.get("workspace", {})

        for key in required_keys:
            assert key in ws_data, f"Ключ '{key}' отсутствует в {lang}.json"
            assert len(ws_data[key].strip()) > 0, f"Ключ '{key}' пуст в {lang}.json"


def test_calendar_tab_and_scenario_i18n_compliance() -> None:
    """Проверяет отсутствие захардкоженного русского языка в tab_calendar/main.js и pack.json сценария דוד משה."""
    cal_js_path = _WEBGUI_DIR / "tab_calendar" / "main.js"
    assert cal_js_path.exists()
    cal_js = cal_js_path.read_text(encoding="utf-8")

    # Дата/время должны форматироваться по активной локали интерфейса (getActiveLocale()), а не undefined
    assert "getActiveLocale()" in cal_js
    assert "toLocaleString(getActiveLocale()" in cal_js
    assert "i18n:languageChanged" in cal_js

    # Проверяем мультиязычность calendar_event и purchase_scenario в pack.json
    pack_path = _WEBGUI_DIR.parent.parent / "demo_scenarios" / "david_moshe" / "pack.json"
    assert pack_path.exists()
    pack_data = json.loads(pack_path.read_text(encoding="utf-8"))
    cal_ev = pack_data["purchase_scenario"]["calendar_event"]
    assert "Осмотр коровы" not in cal_ev["summary"], "В summary события по умолчанию не должно быть русского текста"
    assert "Совместный осмотр" not in cal_ev["description"], "В description по умолчанию не должно быть русского текста"
    for lang in ("he", "ru", "en", "uk"):
        assert lang in cal_ev.get("summary_i18n", {})
        assert lang in cal_ev.get("description_i18n", {})

