# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Test File Explorer & Workspace Dropdown Synchronization
# =============================================================================
# Description:
#   Тесты сквозной синхронизации между выпадающими списками рабочих пространств
#   и файловым менеджером (IDE File Explorer / Primary Side Bar Explorer).
#   Проверяют:
#   - Наличие функций setActiveWorkspaceId и getActiveWorkspaceId в top_workspace_dropdown.js
#   - Синхронизацию вызова refreshFileTree в top_workspace_dropdown.js и drawer_workspaces.js
#   - Обработку смены в селекторе ws-selector в panel.js с вызовом refreshFileTree
#   - Подписку проводника файлов на события workspace:changed, context:changed, repo:changed, hashchange
#
# File: test_file_explorer_workspace_sync.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 18:22:00
# =============================================================================

from __future__ import annotations
"""Тесты синхронизации файлового менеджера и выпадающего списка рабочих пространств."""

from pathlib import Path
import pytest

_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"


def test_top_workspace_dropdown_sync_contract() -> None:
    """Проверяет контракт синхронизации и экспорта в top_workspace_dropdown.js."""
    js_path = _WEBGUI_DIR / "js" / "top_workspace_dropdown.js"
    assert js_path.exists(), "top_workspace_dropdown.js не найден"
    content = js_path.read_text(encoding="utf-8")

    # 1. Экспорт функций управления активным пространством
    assert "export function setActiveWorkspaceId(" in content
    assert "export function getActiveWorkspaceId()" in content
    assert "window.setActiveWorkspaceId = setActiveWorkspaceId" in content
    assert "window.getActiveWorkspaceId = getActiveWorkspaceId" in content

    # 2. Вызов refreshFileTree при обновлении дропдауна
    assert "window.refreshFileTree(cleanWs)" in content
    assert "window.refreshFileTree(wsId)" in content


def test_drawer_workspaces_syncs_file_tree() -> None:
    """Проверяет, что при выборе пространства в drawer_workspaces.js обновляется файловый менеджер."""
    js_path = _WEBGUI_DIR / "js" / "drawer_workspaces.js"
    assert js_path.exists(), "drawer_workspaces.js не найден"
    content = js_path.read_text(encoding="utf-8")

    assert "window.refreshFileTree(finalWsId)" in content
    assert "window.setActiveWorkspaceId(finalWsId)" in content
    assert "new CustomEvent('workspace:changed'" in content


def test_panel_workspace_select_syncs_file_tree() -> None:
    """Проверяет синхронизацию файлового менеджера при изменении селектора #ws-selector."""
    js_path = _WEBGUI_DIR / "tab_workspace" / "panel_workspace_select" / "panel.js"
    assert js_path.exists(), "panel.js не найден"
    content = js_path.read_text(encoding="utf-8")

    assert "window.refreshFileTree(selectedWs)" in content
    assert "window.setActiveWorkspaceId(selectedWs)" in content
    assert "new CustomEvent('workspace:changed'" in content


def test_ide_file_explorer_subscribes_to_sync_events() -> None:
    """Проверяет подписку файлового менеджера на события синхронизации и хэш URL."""
    js_path = _WEBGUI_DIR / "js" / "ide_file_explorer.js"
    assert js_path.exists(), "ide_file_explorer.js не найден"
    content = js_path.read_text(encoding="utf-8")

    assert "document.addEventListener('workspace:changed'" in content
    assert "document.addEventListener('context:changed'" in content
    assert "document.addEventListener('repo:changed'" in content
    assert "window.addEventListener('hashchange'" in content
    assert "window.refreshFileTree = refreshFileTree" in content


def test_ide_file_explorer_deduplication_and_debouncing_contract() -> None:
    """Проверяет наличие механизмов сквозного дебаунса и дедупликации сетевых запросов."""
    exp_path = _WEBGUI_DIR / "js" / "ide_file_explorer.js"
    assert exp_path.exists(), "ide_file_explorer.js не найден"
    exp_content = exp_path.read_text(encoding="utf-8")

    assert "inFlightExplorerFetches" in exp_content
    assert "explorerResponseCache" in exp_content
    assert "treeDebounceTimer" in exp_content
    assert "invalidateExplorerFileTreeCache" in exp_content

    utils_path = _WEBGUI_DIR / "tab_workspace" / "common" / "ui_utils.js"
    assert utils_path.exists(), "ui_utils.js не найден"
    utils_content = utils_path.read_text(encoding="utf-8")

    assert "recentResponseCache" in utils_content
    assert "clearFetchJsonCache" in utils_content


def test_linked_directory_auto_syncs_sidebar_explorer_contract() -> None:
    """Проверяет автообновление боковой панели дерева файлов при подключении внешней директории."""
    exp_content = (_WEBGUI_DIR / "js" / "ide_file_explorer.js").read_text(encoding="utf-8")
    assert "autoExpandedLinkedFolders" in exp_content
    assert "invalidateExplorerFileTreeCache(wsId);" in exp_content

    cws_content = (_WEBGUI_DIR / "tab_create_workspace" / "main.js").read_text(encoding="utf-8")
    assert "workspace:items-changed" in cws_content
    assert "notifyExplorerItemsChanged(" in cws_content

    trk_content = (_WEBGUI_DIR / "tab_workspace" / "panel_workspace_select" / "tracking_controller.js").read_text(encoding="utf-8")
    assert "workspace:items-changed" in trk_content
    assert "invalidateExplorerFileTreeCache" in trk_content

    ws_main_content = (_WEBGUI_DIR / "tab_workspace" / "main.js").read_text(encoding="utf-8")
    assert "workspace:items-changed" in ws_main_content


@pytest.mark.asyncio
async def test_linked_directory_git_tracking_without_physical_copy(tmp_path: Path) -> None:
    """Проверяет, что привязка внешней директории фиксируется в Git без копирования файлов в assets/."""
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

    workspaces_root = tmp_path / "workspaces"
    base_dir = tmp_path / "base_data"
    ext_dir = tmp_path / "דוד משה"
    ext_dir.mkdir(parents=True)
    nested_dir = ext_dir / "sub"
    nested_dir.mkdir()
    (ext_dir / "דוד משה.txt").write_text("לדוד משה היתה חווה", encoding="utf-8")
    (nested_dir / "note.txt").write_text("nested content", encoding="utf-8")

    wm = WorkspaceManager(base_dir=base_dir, workspaces_dir=workspaces_root)
    wm.create_or_select_workspace(workspace_id="דוד_משה", name="דוד משה", language="he")

    res = await wm.add_items_to_workspace(
        workspace_id="דוד_משה",
        paths=[str(ext_dir)],
        copy_to_workspace=False,
    )
    assert res["status"] == "ok"

    ws_path = wm.registry.workspace_path("דוד_משה")
    # 1. Физического копирования в assets/ или корень рабочего пространства нет
    assert not (ws_path / "assets" / "דוד משה.txt").exists()
    assert not (ws_path / "דוד משה.txt").exists()

    # 2. Git реально закоммитил .tracked_sources.json и снимки из .extracted_snapshots/
    tracked_files = wm._run_git(ws_path, ["ls-files"])
    assert ".tracked_sources.json" in tracked_files
    assert ".extracted_snapshots/" in tracked_files

    # 3. Дерево директории для боковой панели подхватывает саму папку и вложенные файлы без копирования
    dc = wm.get_directory_contents("דוד_משה")
    by_rel = {item["rel_path"]: item for item in dc["items"]}
    assert "דוד משה" in by_rel
    assert by_rel["דוד משה"]["is_dir"] is True
    assert by_rel["דוד משה"]["source_mode"] == "linked"
    assert "דוד משה/דוד משה.txt" in by_rel
    assert by_rel["דוד משה/דוד משה.txt"]["source_mode"] == "linked"
    assert "דוד משה/sub/note.txt" in by_rel
    assert by_rel["דוד משה/sub/note.txt"]["source_mode"] == "linked"
