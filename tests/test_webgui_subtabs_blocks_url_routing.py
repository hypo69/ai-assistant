# -*- coding: utf-8 -*-
"""
=============================================================================
Название: Тестирование канонической URL-маршрутизации субпанелей и блоков WebGUI
=============================================================================
Описание:
    Автоматизированный комплекс тестов TDD для валидации канонической
    двухуровневой маршрутизации URL (#tab-<tabId>#panel-<panelId>#block-<blockId>)
    в интерфейсах проекта AI-Assistant.

Файл: tests/test_webgui_subtabs_blocks_url_routing.py
Пакет: tests
Автор: hypo69
Updated: 2026-11-12 02:40:00
=============================================================================
"""

import re
from pathlib import Path
import pytest


WORKSPACE_ROOT = Path(r"c:\Users\onela\AppData\Local\AI-Assistant")
WEBGUI_ROOT = WORKSPACE_ROOT / "apps" / "ai_assistant" / "api" / "webgui"


def test_tab_core_set_panel_hash_implementation():
    """Проверяет реализацию функции setPanelHash в tab-core.js."""
    tab_core_path = WEBGUI_ROOT / "js" / "tab-core.js"
    assert tab_core_path.is_file(), f"Файл не найден: {tab_core_path}"
    content = tab_core_path.read_text(encoding="utf-8")

    assert "export function setPanelHash(tabId, panelId, blockId = null)" in content
    assert "normPanel = cleanPanel.startsWith('panel-') ? cleanPanel : `panel-${cleanPanel}`" in content
    assert "normBlock = cleanBlock.startsWith('block-') ? cleanBlock : `block-${cleanBlock}`" in content
    assert "#${normTab}#${normPanel}${blockSuffix}" in content


def test_common_tab_core_set_panel_hash():
    """Проверяет наличие setPanelHash в apps/common/webgui/js/tab-core.js."""
    common_tab_core = WORKSPACE_ROOT / "apps" / "common" / "webgui" / "js" / "tab-core.js"
    assert common_tab_core.is_file(), f"Файл не найден: {common_tab_core}"
    content = common_tab_core.read_text(encoding="utf-8")

    assert "export function setPanelHash(tabId, panelId, blockId = null)" in content
    assert "#${normTab}#${normPanel}${blockSuffix}" in content


def test_main_orchestrator_block_id_support():
    """Проверяет поддержку blockId в главном оркестраторе main.js."""
    main_js_path = WEBGUI_ROOT / "js" / "main.js"
    assert main_js_path.is_file(), f"Файл не найден: {main_js_path}"
    content = main_js_path.read_text(encoding="utf-8")

    assert "blockId = part;" in content
    assert "blockId: blockId ? blockId.replace(/^block-/, '') : null" in content
    assert "window.switchWorkspaceSubTab(targetPanelId, false, parsedUrl.blockId)" in content


def test_tab_tasks_canonical_routing():
    """Проверяет каноническую нормализацию и маршрутизацию в tab_tasks."""
    tasks_html = WEBGUI_ROOT / "tab_tasks" / "index.html"
    tasks_js = WEBGUI_ROOT / "tab_tasks" / "main.js"
    assert tasks_html.is_file() and tasks_js.is_file()

    html_content = tasks_html.read_text(encoding="utf-8")
    js_content = tasks_js.read_text(encoding="utf-8")

    # Панели в HTML
    for panel in ["panel-cases", "panel-intake", "panel-coordination", "panel-docs"]:
        assert f'data-panel-id="{panel}"' in html_content

    # Нормализация в JS
    assert "normalizePanelId" in js_content
    assert "#tab-tasks#${canonicalPanel}${blockSuffix}" in js_content
    assert "setupTasksHashRouting" in js_content


def test_tab_models_block_id_and_routing():
    """Проверяет наличие вложенных блоков и маршрутизацию в tab_models."""
    models_html = WEBGUI_ROOT / "tab_models" / "index.html"
    models_js = WEBGUI_ROOT / "tab_models" / "main.js"
    assert models_html.is_file() and models_js.is_file()

    html_content = models_html.read_text(encoding="utf-8")
    js_content = models_js.read_text(encoding="utf-8")

    # Вложенные блоки режимов credentials Google Accounts
    assert 'data-block-id="block-file"' in html_content
    assert 'data-block-id="block-json"' in html_content

    # Маршрутизация в JS
    assert "initTabUrlHashRouting" in js_content
    assert "blockPart = parts.find((p) => p.startsWith('block-'));" in js_content
    assert "#${canonicalTabId}#${canonicalPanel}#${normBlock}" in js_content


def test_tab_plugins_block_id_and_routing():
    """Проверяет наличие вложенных блоков скоупа и маршрутизацию в tab_plugins."""
    plugins_html = WEBGUI_ROOT / "tab_plugins" / "index.html"
    plugins_js = WEBGUI_ROOT / "tab_plugins" / "main.js"
    assert plugins_html.is_file() and plugins_js.is_file()

    html_content = plugins_html.read_text(encoding="utf-8")
    js_content = plugins_js.read_text(encoding="utf-8")

    # Вложенные блоки фильтрации скоупа
    assert 'data-block-id="block-all"' in html_content
    assert 'data-block-id="block-system"' in html_content
    assert 'data-block-id="block-developer"' in html_content
    assert 'data-block-id="block-user"' in html_content

    # Маршрутизация в JS
    assert "initTabUrlHashRouting" in js_content
    assert "#tab-plugins#panel-installed#${normBlock}" in js_content


def test_tab_tooltips_block_id_and_routing():
    """Проверяет наличие языковых блоков и маршрутизацию в tab_tooltips."""
    tooltips_html = WEBGUI_ROOT / "tab_tooltips" / "index.html"
    tooltips_js = WEBGUI_ROOT / "tab_tooltips" / "main.js"
    assert tooltips_html.is_file() and tooltips_js.is_file()

    html_content = tooltips_html.read_text(encoding="utf-8")
    js_content = tooltips_js.read_text(encoding="utf-8")

    # Языковые блоки
    for lang in ["block-ru", "block-en", "block-he", "block-uk"]:
        assert f'data-block-id="{lang}"' in html_content

    # Маршрутизация в JS
    assert "switchToSubtab(panelId, blockId = null, updateHash = true)" in js_content
    assert "#tab-tooltips#panel-editor#${normBlock}" in js_content
    assert "syncFromHash" in js_content


def test_tab_doc_categorizer_routing():
    """Проверяет URL маршрутизацию в tab_doc_categorizer."""
    doc_cat_html = WEBGUI_ROOT / "tab_doc_categorizer" / "index.html"
    doc_cat_js = WEBGUI_ROOT / "tab_doc_categorizer" / "main.js"
    assert doc_cat_html.is_file() and doc_cat_js.is_file()

    html_content = doc_cat_html.read_text(encoding="utf-8")
    js_content = doc_cat_js.read_text(encoding="utf-8")

    for panel in ["panel-catalog", "panel-uncertain", "panel-rag"]:
        assert f'data-panel-id="{panel}"' in html_content

    assert "canonicalTabId = 'tab-doc-categorizer'" in js_content
    assert "#${canonicalTabId}#${canonicalPanel}" in js_content


def test_standards_documentation():
    """Проверяет фиксацию стандарта маршрутизации в документации и навыках."""
    webgui_md = WORKSPACE_ROOT / ".ai" / "instructions" / "standards" / "WEBGUI.md"
    menu_md = WORKSPACE_ROOT / ".ai" / "instructions" / "standards" / "SUBTABS_AND_BLOCKS_MENU.md"
    skill_md = WORKSPACE_ROOT / ".agents" / "skills" / "webgui-developer" / "SKILL.md"

    assert webgui_md.is_file()
    assert menu_md.is_file()
    assert skill_md.is_file()

    webgui_txt = webgui_md.read_text(encoding="utf-8")
    menu_txt = menu_md.read_text(encoding="utf-8")
    skill_txt = skill_md.read_text(encoding="utf-8")

    assert "3.3 Двухуровневая маршрутизация URL (#tab-<tabId>#panel-<panelId>#block-<blockId>)" in webgui_txt
    assert "#tab-<tabId>#panel-<panelId>#block-<blockId>" in menu_txt
    assert "Каноническая двухуровневая URL-маршрутизация" in skill_txt
