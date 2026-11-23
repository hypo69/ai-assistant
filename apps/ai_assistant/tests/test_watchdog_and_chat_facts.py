# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Watchdog, Media Audio Extraction & Chat Facts
# =============================================================================
# Description:
#   Комплексный набор тестов для проверки:
#   1. Извлечения звуковой дорожки из медиафайлов (MP3, MP4, MKV и др.) через ffmpeg.
#   2. Реального наблюдателя watchdog.Observer (автокоммиты Git в рабочей области
#      и условный автозахват транскрибации по флагу config.json).
#   3. Добавления фактов через чат во внутренние файлы рабочей области, SQLite,
#      FAISS, Obsidian и Git, а также немедленного поиска через QA.
#   4. REST API (/watchdog/config, /workspaces/{id}/facts) и WebGUI (тумблер и кнопки).
#
# File: test_watchdog_and_chat_facts.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 02:38:00
# =============================================================================

from __future__ import annotations
"""Тесты watchdog, условной транскрибации медиафайлов и добавления фактов через чат."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import AsyncMock, patch

from bs4 import BeautifulSoup
from httpx import ASGITransport, AsyncClient
import pytest

from apps.ai_assistant.core.content_extractor import ContentExtractor
from apps.ai_assistant.core.qa_engine import KnowledgeQAEngine
from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.core.workspace_watchdog import (
    WatchTarget,
    WorkspaceWatchdogService,
    load_watchdog_config,
    save_watchdog_config,
)
from apps.ai_assistant.main import app


@pytest.fixture()
def isolated_wm(tmp_path: Path) -> WorkspaceManager:
    """Создаёт изолированный WorkspaceManager во временной директории."""
    wm = WorkspaceManager(
        base_dir=tmp_path / "base_data",
        workspaces_dir=tmp_path / "workspaces",
    )
    wm.create_or_select_workspace("test_wd", name="Тест Watchdog", language="ru")
    return wm


@pytest.mark.asyncio
async def test_media_audio_track_extraction_and_no_audio_skip(tmp_path: Path) -> None:
    """Проверяет извлечение звуковой дорожки из MP4 и пропуск видео без звука."""
    extractor = ContentExtractor()
    assert extractor.is_media_with_audio_extension("clip.mp4") is True
    assert extractor.is_media_with_audio_extension("call.mp3") is True
    assert extractor.is_media_with_audio_extension("doc.txt") is False

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        pytest.skip("ffmpeg не установлен в PATH")

    # 1. Создаём MP4 со звуковой дорожкой
    mp4_audio = tmp_path / "with_audio.mp4"
    subprocess.run(
        [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.5",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
            "-shortest", str(mp4_audio),
        ],
        check=True,
        capture_output=True,
    )
    # 2. Создаём немое MP4 без звуковой дорожки
    mp4_silent = tmp_path / "silent.mp4"
    subprocess.run(
        [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.5",
            "-an", str(mp4_silent),
        ],
        check=True,
        capture_output=True,
    )

    assert extractor.has_audio_track(mp4_audio) is True
    assert extractor.has_audio_track(mp4_silent) is False

    with patch("apps.ai_assistant.core.content_extractor.audio2text", new=AsyncMock(return_value="Тестовая речь из видео.")) as mock_a2t:
        res_audio = await extractor.extract(mp4_audio, audio_mode="model")
        assert res_audio["text"] == "Тестовая речь из видео."
        assert res_audio["has_audio"] is True
        assert res_audio["source_type"] == "media_audio"
        assert mock_a2t.await_count == 1
        called_audio_path = Path(mock_a2t.call_args.args[0])
        assert called_audio_path.suffix == ".mp3"
        # Временный файл должен быть удалён после транскрибации
        assert not called_audio_path.exists()

        res_silent = await extractor.extract(mp4_silent, audio_mode="model")
        assert res_silent["source_type"] == "media_no_audio"
        assert res_silent["has_audio"] is False
        assert res_silent["text"] == ""
        assert mock_a2t.await_count == 1


@pytest.mark.asyncio
async def test_watchdog_config_and_conditional_transcription(isolated_wm: WorkspaceManager, tmp_path: Path) -> None:
    """Проверяет условие автозахвата транскрибации в config.json и автокоммиты Git в рабочей области."""
    cfg_path = tmp_path / "config.json"
    save_watchdog_config({"enabled": True, "auto_transcribe_media": False, "auto_git_commit": True, "debounce_seconds": 0.3}, cfg_path)
    loaded = load_watchdog_config(cfg_path)
    assert loaded["auto_transcribe_media"] is False
    assert loaded["auto_git_commit"] is True

    wd = WorkspaceWatchdogService(workspace_manager=isolated_wm, config_path=cfg_path)

    # 1. Проверяем автокоммит Git при изменении файла внутри папки рабочей области
    ws_info = isolated_wm.registry.get_workspace("test_wd")
    ws_path = Path(ws_info["path"])
    note_file = ws_path / "manual_note.txt"
    note_file.write_text("Иван починил трактор.", encoding="utf-8")

    ws_target = WatchTarget(kind="workspace", workspace_id="test_wd", root_path=ws_path)
    ev_res = await wd.process_file_event(ws_target, note_file, "created")
    assert ev_res["status"] == "ok"
    assert isolated_wm._run_git(ws_path, ["status", "--porcelain"]) == ""
    log_out = isolated_wm._run_git(ws_path, ["log", "-n", "3", "--oneline"])
    assert "Watchdog" in log_out

    # 2. Проверяем внешний источник с mp3 при auto_transcribe_media=False -> транскрибация не запускается
    ext_dir = tmp_path / "external_folder"
    ext_dir.mkdir(parents=True, exist_ok=True)
    isolated_wm.link_source("test_wd", str(ext_dir), name="Внешняя папка", auto_watch=True)
    mp3_file = ext_dir / "call.mp3"
    mp3_file.write_bytes(b"ID3_FAKE_MP3_DATA")
    ext_target = WatchTarget(kind="linked_source", workspace_id="test_wd", root_path=ext_dir)

    with patch("apps.ai_assistant.core.content_extractor.audio2text", new=AsyncMock(return_value="Давид позвонил Шмулику.")) as mock_a2t:
        skipped_res = await wd.process_file_event(ext_target, mp3_file, "created")
        assert skipped_res["status"] == "skipped_transcribe"
        assert mock_a2t.await_count == 0

        # 3. Включаем тумблер auto_transcribe_media=True -> транскрибация запускается и индексируется
        save_watchdog_config({"auto_transcribe_media": True}, cfg_path)
        ok_res = await wd.process_file_event(ext_target, mp3_file, "created")
        assert ok_res["status"] == "ok"
        assert ok_res["action"] == "media_transcribed"
        assert mock_a2t.await_count == 1

    docs = isolated_wm.store.list_documents("test_wd")
    assert any(d["document_id"] == "call.mp3" for d in docs)

    # 4. Проверяем реальный запуск и остановку Observer
    loop = asyncio.get_running_loop()
    wd.start(loop)
    try:
        assert wd.is_running() is True
        status = wd.get_status()
        assert status["watched_count"] >= 2
    finally:
        wd.stop()
        assert wd.is_running() is False


@pytest.mark.asyncio
async def test_add_fact_from_chat_persists_internal_files_and_qa(isolated_wm: WorkspaceManager) -> None:
    """Проверяет добавление факта через чат: запись в chat_facts.md, Git, SQLite, Obsidian и ответ QA."""
    res1 = isolated_wm.add_fact_from_chat("test_wd", "Давид купил трактор.")
    assert res1["status"] == "ok"
    assert res1["document_id"] == "chat_facts.md"
    internal_file = Path(res1["internal_file_path"])
    assert internal_file.exists()
    content1 = internal_file.read_text(encoding="utf-8")
    assert "Давид купил трактор." in content1

    # Добавляем второй факт (свободная фраза без совпадения regex-шаблона)
    res2 = isolated_wm.add_fact_from_chat("test_wd", "На ферме живёт сторожевой пёс")
    assert res2["status"] == "ok"
    content2 = internal_file.read_text(encoding="utf-8")
    assert "Давид купил трактор." in content2
    assert "На ферме живёт сторожевой пёс." in content2

    kb_text = Path(res2["knowledge_base_file"]).read_text(encoding="utf-8")
    assert "chat_facts" in kb_text

    # Проверяем, что оба факта активны в SQLite (первый не стал stale при добавлении второго!)
    facts = isolated_wm.store.get_facts("test_wd", document_id="chat_facts.md", include_stale=False)
    assert len(facts) >= 2

    # Проверяем ответ QA по добавленному факту
    qa = KnowledgeQAEngine(workspace_manager=isolated_wm)
    ans = await qa.ask("Кто купил трактор?", workspace_id="test_wd", mode="local_only")
    assert "давид" in ans["answer"].lower()


@pytest.mark.asyncio
async def test_api_watchdog_config_and_chat_facts_endpoints(isolated_wm: WorkspaceManager, tmp_path: Path) -> None:
    """Проверяет REST API /watchdog/config и /workspaces/{id}/facts."""
    cfg_path = tmp_path / "api_config.json"
    save_watchdog_config({"enabled": False, "auto_transcribe_media": True, "auto_git_commit": True, "debounce_seconds": 1.0}, cfg_path)
    isolated_wd = WorkspaceWatchdogService(workspace_manager=isolated_wm, config_path=cfg_path)

    with (
        patch("apps.ai_assistant.api.routers.router_knowledge._workspace_manager", isolated_wm),
        patch("apps.ai_assistant.api.routers.router_knowledge._watchdog_service", isolated_wd),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r_get = await client.get("/api/v1/watchdog/config")
            assert r_get.status_code == 200
            assert r_get.json()["config"]["auto_transcribe_media"] is True

            r_post = await client.post("/api/v1/watchdog/config", json={"auto_transcribe_media": False})
            assert r_post.status_code == 200
            assert r_post.json()["config"]["auto_transcribe_media"] is False
            assert load_watchdog_config(cfg_path)["auto_transcribe_media"] is False

            r_fact = await client.post(
                "/api/v1/workspaces/test_wd/facts",
                json={"fact_text": "Мама вымыла раму"},
            )
            assert r_fact.status_code == 200
            body = r_fact.json()
            assert body["status"] == "ok"
            assert body["document_id"] == "chat_facts.md"
            assert body["facts_count"] >= 1


def test_webgui_toggles_buttons_and_locales() -> None:
    """Проверяет наличие тумблеров автотранскрибации, кнопок добавления факта и переводов во всех 4 локалях."""
    webgui_dir = Path(__file__).resolve().parent.parent / "api" / "webgui"

    index_html = (webgui_dir / "index.html").read_text(encoding="utf-8")
    ws_html = (webgui_dir / "tab_workspace" / "index.html").read_text(encoding="utf-8")
    chat_html = (webgui_dir / "tab_chat" / "index.html").read_text(encoding="utf-8")

    assert 'id="user-settings-auto-transcribe-toggle"' in index_html
    assert 'id="ws-sources-auto-transcribe-toggle"' in ws_html
    assert 'id="ws-chat-add-fact-btn"' in ws_html
    assert 'id="chat-add-fact-btn"' in chat_html

    # Проверяем, что новые элементы с data-i18n имеют id
    for html_name, raw in [("index.html", index_html), ("tab_workspace/index.html", ws_html), ("tab_chat/index.html", chat_html)]:
        soup = BeautifulSoup(raw, "html.parser")
        for el_id in ("user-settings-auto-transcribe-label", "user-settings-auto-transcribe-hint", "ws-sources-auto-transcribe-label", "ws-chat-add-fact-btn-text", "chat-add-fact-btn-text"):
            found = soup.find(id=el_id)
            if found:
                assert found.get("data-i18n"), f"Нет data-i18n у {el_id} в {html_name}"

    expected_user_keys = ["watchdogSectionTitle", "autoTranscribeLabel", "autoTranscribeHint", "autoGitCommitLabel"]
    expected_ws_keys = [
        "watchdogAutoTranscribeLabel",
        "watchdogAutoTranscribeHint",
        "chatAddFactBtn",
        "chatAddFactTitle",
        "chatAddingFactStatus",
        "chatFactSavedMsg",
        "chatFactSavedStatus",
        "chatFactAddError",
        "chatFactsInFile",
    ]
    for lang in ("ru", "en", "he", "uk"):
        loc = json.loads((webgui_dir / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
        for k in expected_user_keys:
            assert k in loc.get("userSettings", {}), f"Отсутствует userSettings.{k} в {lang}.json"
        for k in expected_ws_keys:
            assert k in loc.get("workspace", {}), f"Отсутствует workspace.{k} в {lang}.json"


def test_watchdog_ignores_runtime_state_and_workspaces_dir(isolated_wm: WorkspaceManager, tmp_path: Path) -> None:
    """Проверяет игнорирование electron_state.json, SQLite-журналов и файлов внутри workspaces_dir для linked_source."""
    cfg_path = tmp_path / "ignore_config.json"
    wd = WorkspaceWatchdogService(workspace_manager=isolated_wm, config_path=cfg_path)
    parent_root = isolated_wm.workspaces_dir.parent
    target = WatchTarget(kind="linked_source", workspace_id="test_wd", root_path=parent_root)

    assert wd._should_ignore_path(target, parent_root / "data" / "electron_state.json") is True
    assert wd._should_ignore_path(target, parent_root / "data" / "knowledge_store.db-wal") is True
    assert wd._should_ignore_path(target, parent_root / "data" / "knowledge_store.db-shm") is True
    assert wd._should_ignore_path(target, isolated_wm.workspaces_dir / "test_wd" / "notes.txt") is True
    assert wd._should_ignore_path(target, parent_root / "docs" / "regular_note.md") is False


def test_tracked_sources_atomic_write_concurrent_and_winerror32(
    isolated_wm: WorkspaceManager,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет устойчивость обновления .tracked_sources.json при WinError 32 и параллельных потоках."""
    src_dir = tmp_path / "external_src"
    src_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for idx in range(4):
        f = src_dir / f"doc_{idx}.txt"
        f.write_text(f"Содержимое документа {idx}", encoding="utf-8")
        files.append(f)

    real_replace = os.replace
    fail_counter = {"n": 0}

    def flaky_replace(src, dst):
        if str(dst).endswith(".tracked_sources.json") and fail_counter["n"] < 2:
            fail_counter["n"] += 1
            err = PermissionError(13, "Процесс не может получить доступ к файлу", str(src), 32, str(dst))
            err.winerror = 32
            raise err
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)

    def _worker(idx: int) -> None:
        f = files[idx]
        isolated_wm.index_document_from_source(
            workspace_id="test_wd",
            document_id=f.name,
            content=f.read_text(encoding="utf-8"),
            file_path=str(f),
            commit_message=f"Sync {f.name}",
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(_worker, range(4)))

    manifest_file = isolated_wm.workspaces_dir / "test_wd" / ".tracked_sources.json"
    assert manifest_file.exists()
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    for idx in range(4):
        assert f"doc_{idx}.txt" in manifest_data
    assert fail_counter["n"] == 2
    assert not list(manifest_file.parent.glob("*.tmp"))


@pytest.mark.asyncio
async def test_watchdog_concurrent_events_serialized_without_db_lock(
    isolated_wm: WorkspaceManager,
    tmp_path: Path,
) -> None:
    """Проверяет отсутствие 'database is locked' при одновременной пачке событий modified в одном workspace."""
    src_dir = tmp_path / "burst_src"
    src_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for idx in range(6):
        f = src_dir / f"module_{idx}.js"
        f.write_text(f"// Модуль {idx}\nexport const value_{idx} = {idx};\n", encoding="utf-8")
        files.append(f)

    cfg_path = tmp_path / "burst_config.json"
    wd = WorkspaceWatchdogService(workspace_manager=isolated_wm, config_path=cfg_path)
    target = WatchTarget(kind="linked_source", workspace_id="test_wd", root_path=src_dir)

    results = await asyncio.gather(
        *(wd.process_file_event(target, f, "modified") for f in files)
    )

    assert all(r.get("status") == "ok" for r in results), f"Обнаружены ошибки обработки: {results}"
    assert wd._stats["errors"] == 0


def test_sqlite_concurrent_store_and_graph_writes_no_lock_error(
    isolated_wm: WorkspaceManager,
    tmp_path: Path,
) -> None:
    """Проверяет конкурентную запись в knowledge_store.db из KnowledgeStore и TemporalCodeGraph без database is locked."""
    def _write_worker(idx: int) -> None:
        doc_id = f"concurrent_{idx}.txt"
        fp = tmp_path / doc_id
        isolated_wm.store.store_document_and_facts(
            workspace_id="test_wd",
            document_id=doc_id,
            file_path=str(fp),
            raw_content=f"Тестовый документ номер {idx} с фактом {idx}",
            commit_hash=f"rev_{idx}",
            analysis_result={
                "language": "ru",
                "analyzer": "TestAnalyzer",
                "chunks": [{"chunk_index": 0, "text": f"Факт {idx}"}],
                "entities": [],
                "facts": [],
            },
        )
        isolated_wm.graph.add_link(
            source_id=doc_id,
            target_id=f"entity_{idx}",
            relation_type="mentions",
            valid_from=f"rev_{idx}",
            workspace_id="test_wd",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_write_worker, range(16)))

    stats = isolated_wm.store.get_workspace_stats("test_wd")
    assert stats["documents_count"] >= 16
