# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Unified RAG Unit Tests
# =============================================================================
# Description:
#   Модульные тесты для TextRAG, PixelRAG, LogRAG и UnifiedKnowledgeHub.
#
# Usage Examples:
#   pytest src/ai/rag/tests/test_unified_rag.py -v
#
# File: test_unified_rag.py
# Project: ai-windows-admin
# Package: src.ai.rag.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 19:28:30
# =============================================================================

from __future__ import annotations
"""Модульные тесты для TextRAG, PixelRAG, LogRAG, CodebaseRAG и UnifiedKnowledgeHub."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.ai.rag.codebase_rag import CodebaseRAG
from src.ai.rag.text_rag import TextRAG
from src.ai.rag.pixel_rag import PixelRAG
from src.ai.rag.log_rag import LogRAG
from src.ai.rag.router import init_router
from src.ai.rag.unified_hub import UnifiedKnowledgeHub
try:
    from apps.windows.wikillm.models import ArtifactType, KnowledgeEntity, KnowledgeSource
except ImportError:
    from src.ai.wikillm.models import ArtifactType, KnowledgeEntity, KnowledgeSource


def test_text_rag_crud_and_search(tmp_path: Path) -> None:
    """Проверка добавления документов, сохранения и поиска в TextRAG."""
    index_path = tmp_path / "test_text_index"
    rag = TextRAG(db_path=index_path, dimension=64)

    docs = [
        {"id": "doc1", "text": "Ошибка инициализации DirectML в Windows 11", "meta": {"category": "ml"}},
        {"id": "doc2", "text": "Настройка сетевого интерфейса и DNS серверов", "meta": {"category": "network"}},
    ]
    added = rag.add_documents(docs)
    assert added == 2
    assert rag.count() == 2

    results = rag.search("DirectML Windows", top_k=2)
    assert len(results) > 0
    assert results[0]["id"] == "doc1"

    # Удаление документа
    rag.delete_document("doc1")
    assert rag.count() == 1


def test_pixel_rag_indexing_and_search(tmp_path: Path) -> None:
    """Проверка индексации скриншотов и поиска в PixelRAG."""
    pixel_rag = PixelRAG(storage_dir=tmp_path / "pixels")
    img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"

    entry = pixel_rag.index_image_bytes(
        data=img_bytes,
        filename="bsod_dialog.png",
        title="Скриншот экрана критической ошибки",
        ocr_text="CRITICAL_PROCESS_DIED 0x000000EF",
        metadata={"source": "telemetry"},
    )
    assert entry["id"].startswith("img_")
    assert pixel_rag.get_status()["total_images"] == 1

    # Поиск по OCR тексту
    search_res = pixel_rag.search_by_text("CRITICAL_PROCESS", top_k=2)
    assert len(search_res) == 1
    assert search_res[0]["filename"] == "bsod_dialog.png"

    # Визуальный поиск по байтам
    visual_res = pixel_rag.search_by_visual(img_bytes, top_k=2)
    assert len(visual_res) == 1
    assert visual_res[0]["score"] >= 0.95


def test_log_rag_chunking_and_wiki_linkage(tmp_path: Path) -> None:
    """Проверка добавления лог-чанков и связывания с базой знаний в LogRAG."""
    log_rag = LogRAG(storage_dir=tmp_path / "logs")
    chunk = log_rag.add_log_chunk(
        chunk_id="chunk_10016",
        title="DistributedCOM DCOM Permission Error",
        content="The application-specific permission settings do not grant Local Activation permission for the COM Server application",
        channel="System",
        provider="DistributedCOM",
        event_ids=[10016],
    )
    assert chunk["id"] == "chunk_10016"

    # Поиск по чанкам
    search_res = log_rag.search_chunks("DistributedCOM permission", top_k=2)
    assert len(search_res) == 1
    assert search_res[0]["id"] == "chunk_10016"

    # Проверка создания сущности в WikiStorage
    ent = log_rag.wiki_storage.get_entity("windows_event:DistributedCOM:10016")
    assert ent is not None
    assert ent.diagnostic_info is not None
    assert len(ent.diagnostic_info.symptoms) > 0


@pytest.mark.asyncio
async def test_unified_knowledge_hub_resolution(tmp_path: Path) -> None:
    """Проверка сквозного разрешения через UnifiedKnowledgeHub."""
    hub = UnifiedKnowledgeHub(base_dir=tmp_path / "unified")

    # Сохраняем сущность в WikiLLM
    test_ent = KnowledgeEntity(
        canonical_key="win32:0x80070490",
        entity_type=ArtifactType.WINDOWS_ERROR,
        name="ERROR_NOT_FOUND",
        summary="Элемент не найден в хранилище компонентов Windows.",
        provenance_source=KnowledgeSource.DOCUMENTED,
    )
    hub.wikillm.storage.save_entity(test_ent)

    # Добавляем текстовый документ
    hub.text_rag.add_documents([
        {"id": "kb1", "text": "Инструкция по устранению ошибки 0x80070490 через DISM", "meta": {}}
    ])

    # Разрешение через Hub
    res = await hub.resolve_query("0x80070490", sync_gemini=False)
    assert res["source"] == "wikillm"
    assert res["wikillm"]["canonical_key"] == "win32:0x80070490"
    assert len(res["text_rag_matches"]) > 0

    # Мульти-поиск
    all_res = hub.search_all("0x80070490")
    assert all_res["total_found"] >= 1


@pytest.mark.asyncio
async def test_codebase_rag_ast_indexing_and_diagnosis(tmp_path: Path) -> None:
    """Проверка индексации AST Python и Markdown-документации, поиска символов и выдачи заключений по логам и ошибкам."""
    src_dir = tmp_path / "sample_proj"
    src_dir.mkdir(parents=True, exist_ok=True)

    py_file = src_dir / "payment_processor.py"
    py_file.write_text(
        '''"""Модуль обработки платежных транзакций."""

class PaymentProcessor:
    """Процессор расчетов и комиссий."""

    def calculate_fee(self, amount: float, rate: float) -> float:
        """Расчет комиссии по ставке.

        Выбрасывает ZeroDivisionError при нулевом делителе.
        """
        if rate < 0:
            raise ValueError("Ставка комиссии не может быть отрицательной")
        return amount / rate
''',
        encoding="utf-8",
    )

    md_file = src_dir / "README.md"
    md_file.write_text(
        "# Платежный шлюз\n\nКласс `PaymentProcessor` отвечает за расчет комиссий в `payment_processor.py`.\n",
        encoding="utf-8",
    )

    code_rag = CodebaseRAG(storage_dir=tmp_path / "code_idx", dimension=64)
    stats = code_rag.build_index(project_root=src_dir, index_name="test_code")
    assert stats["total_files"] == 2
    assert stats["total_symbols"] >= 2
    assert stats["total_chunks"] >= 3

    # Поиск AST-символа
    syms = code_rag.search_symbols("calculate_fee", index_name="test_code")
    assert len(syms) >= 1
    assert syms[0]["symbol"] == "PaymentProcessor.calculate_fee"
    assert syms[0]["path"] == "payment_processor.py"

    # Диагностика по списку логов и стек-трейсу (детерминированный AST режим)
    conclusion = await code_rag.diagnose(
        question="Почему падает расчет комиссии?",
        logs=[
            "2026-10-31 18:00:01 [INFO] Запуск транзакции ID=99",
            "2026-10-31 18:00:02 [ERROR] Сбой в payment_processor.py:14",
        ],
        error_message='File "payment_processor.py", line 14, in calculate_fee\nZeroDivisionError: float division by zero',
        index_name="test_code",
        use_llm=False,
    )

    assert conclusion.severity == "error"
    assert "ZeroDivisionError" in conclusion.root_cause
    assert len(conclusion.affected_locations) > 0
    assert conclusion.affected_locations[0].file_path == "payment_processor.py"
    assert "calculate_fee" in conclusion.affected_locations[0].symbol_name
    assert len(conclusion.remediation_steps) >= 1


def test_codebase_rag_fastapi_router_endpoints(tmp_path: Path) -> None:
    """Проверка REST API эндпоинтов /api/rag/codebase/*."""
    proj_dir = tmp_path / "api_proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "worker.py").write_text(
        "def run_worker_task(task_id: int) -> bool:\n    '''Запуск воркера.'''\n    if task_id <= 0:\n        raise RuntimeError('Invalid task_id')\n    return True\n",
        encoding="utf-8",
    )

    hub = UnifiedKnowledgeHub(base_dir=tmp_path / "hub_data")
    app = FastAPI()
    app.include_router(init_router(hub))
    client = TestClient(app)

    # 1. Сборка индекса через POST /api/rag/codebase/build
    build_resp = client.post(
        "/api/rag/codebase/build",
        json={"project_root": str(proj_dir), "index_name": "codebase"},
    )
    assert build_resp.status_code == 200
    assert build_resp.json()["result"]["total_symbols"] == 1

    # 2. Список индексов через GET /api/rag/codebase/indexes
    idx_resp = client.get("/api/rag/codebase/indexes")
    assert idx_resp.status_code == 200
    assert len(idx_resp.json()["indexes"]) == 1

    # 3. Поиск символов через POST /api/rag/codebase/symbols
    sym_resp = client.post(
        "/api/rag/codebase/symbols",
        json={"symbol": "run_worker_task", "index_name": "codebase"},
    )
    assert sym_resp.status_code == 200
    assert sym_resp.json()["total_found"] == 1

    # 4. Заключение по ошибке и логам через POST /api/rag/codebase/diagnose
    diag_resp = client.post(
        "/api/rag/codebase/diagnose",
        json={
            "question": "Из-за чего останавливается воркер?",
            "logs": ["[CRITICAL] worker.py:4 task_id=0 rejected"],
            "error_message": 'File "worker.py", line 4, in run_worker_task\nRuntimeError: Invalid task_id',
            "index_name": "codebase",
            "use_llm": False,
        },
    )
    assert diag_resp.status_code == 200
    payload = diag_resp.json()
    assert "RuntimeError" in payload["root_cause"]
    assert payload["affected_locations"][0]["file_path"] == "worker.py"


def test_text_rag_agy_provider_uses_deterministic_embeddings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет, что при провайдере AGY не вызывается Gemini API и используются детерминированные эмбеддинги."""
    # Эмулируем ошибку, если кто-то попытается вызвать google.genai
    def _mock_load_api_keys(*args, **kwargs):
        raise AssertionError("google.genai не должен вызываться для провайдера agy!")

    monkeypatch.setattr("src.ai.gemini.gemini_api_key_state.load_api_keys", _mock_load_api_keys)

    index_path = tmp_path / "faiss_indices" / "ws_דוד_משה"
    rag = TextRAG(db_path=index_path, dimension=256, provider="agy")
    assert rag.provider == "agy"

    docs = [
        {"id": "doc1", "text": "Шалом из Иерусалима", "meta": {"lang": "he"}},
        {"id": "doc2", "text": "Тестирование векторного RAG", "meta": {"lang": "ru"}},
    ]
    added = rag.add_documents(docs)
    assert added == 2
    assert rag.count() == 2

    # Проверяем поиск
    hits = rag.search("Шалом", top_k=2)
    assert len(hits) > 0
    assert hits[0]["id"] == "doc1"


def test_text_rag_concurrent_save_and_hebrew_path(tmp_path: Path) -> None:
    """Проверяет параллельное сохранение в каталог с ивритом без конфликтов блокировок файлов (PermissionError)."""
    import threading

    ws_dir = tmp_path / "workspaces" / "דוד_משה" / ".workspace" / "faiss_indices"
    index_path = ws_dir / "ws_דוד_משה"
    rag = TextRAG(db_path=index_path, dimension=128, provider="agy")

    errors: list[Exception] = []

    def _worker(thread_idx: int):
        try:
            for i in range(5):
                rag.add_documents([
                    {"id": f"th_{thread_idx}_doc_{i}", "text": f"Текст потока {thread_idx} итерация {i}"}
                ])
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Ошибки при параллельном сохранении: {errors}"
    assert rag.count() == 20
    assert rag.meta_file.exists()





def test_text_rag_rotates_on_403_permission_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет, что при ошибке 403 PERMISSION_DENIED ключ деактивируется и выполняется ротация на следующий ключ пула."""
    from types import SimpleNamespace
    from src.ai.gemini.embeddings import clear_rpm_state

    clear_rpm_state()
    exhausted_marked: list[str] = []

    def _mock_load_api_keys(skip_exhausted: bool = True):
        return (["bad_key_403", "good_key_ok"], ["fmashulia", "masha.florenc"], [])

    def _mock_mark_exhausted(key_name: str) -> None:
        exhausted_marked.append(key_name)

    class _MockModels:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def embed_content(self, model: str, contents, config):
            if self.api_key == "bad_key_403":
                raise RuntimeError("403 PERMISSION_DENIED. {'error': {'code': 403, 'status': 'PERMISSION_DENIED'}}")
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=[0.25] * 64) for _ in contents]
            )

    class _MockClient:
        def __init__(self, api_key: str) -> None:
            self.models = _MockModels(api_key)

    monkeypatch.setattr("src.ai.gemini.embeddings.load_api_keys", _mock_load_api_keys)
    monkeypatch.setattr("src.ai.gemini.embeddings.mark_exhausted", _mock_mark_exhausted)
    monkeypatch.setattr("google.genai.Client", _MockClient)

    rag = TextRAG(db_path=tmp_path / "rot_index", dimension=64, provider="gemini")
    try:
        vecs = rag._embed(["тест ротации при 403"])
        assert len(vecs) == 1
        assert len(vecs[0]) == 64
        assert vecs[0] == [0.25] * 64
        assert exhausted_marked == ["fmashulia"]
    finally:
        clear_rpm_state()


def test_text_rag_rpm_limit_uses_cooldown_without_24h_exhaustion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет, что минутный лимит 429 RPM переводит ключ во временный cooldown без 24ч бана mark_exhausted."""
    from types import SimpleNamespace
    from src.ai.gemini.embeddings import clear_rpm_state

    clear_rpm_state()
    exhausted_marked: list[str] = []
    called_keys: list[str] = []

    def _mock_load_api_keys(skip_exhausted: bool = True):
        return (["rpm_key_1", "good_key_2"], ["xvuv", "backup_key"], [])

    def _mock_mark_exhausted(key_name: str) -> None:
        exhausted_marked.append(key_name)

    class _MockModels:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def embed_content(self, model: str, contents, config):
            called_keys.append(self.api_key)
            if self.api_key == "rpm_key_1":
                raise RuntimeError(
                    "429 RESOURCE_EXHAUSTED. EmbedContentRequestsPerMinutePerUserPerProjectPerModel-FreeTier. "
                    "Please retry in 50.3s. 'retryDelay': '50s'"
                )
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=[0.5] * 64) for _ in contents]
            )

    class _MockClient:
        def __init__(self, api_key: str) -> None:
            self.models = _MockModels(api_key)

    monkeypatch.setattr("src.ai.gemini.embeddings.load_api_keys", _mock_load_api_keys)
    monkeypatch.setattr("src.ai.gemini.embeddings.mark_exhausted", _mock_mark_exhausted)
    monkeypatch.setattr("google.genai.Client", _MockClient)

    rag = TextRAG(db_path=tmp_path / "rpm_index", dimension=64, provider="gemini")
    try:
        vecs1 = rag._embed(["первый запрос"])
        assert len(vecs1) == 1 and vecs1[0] == [0.5] * 64
        assert exhausted_marked == []
        assert called_keys == ["rpm_key_1", "good_key_2"]

        vecs2 = rag._embed(["второй запрос"])
        assert len(vecs2) == 1 and vecs2[0] == [0.5] * 64
        assert called_keys == ["rpm_key_1", "good_key_2", "good_key_2"]
    finally:
        clear_rpm_state()


def test_gemini_embeddings_round_robin_and_rpm_window_avoids_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет, что после 100 текстов на ключе №1 следующий пакет сразу уходит на ключ №2 без 429."""
    from types import SimpleNamespace
    from src.ai.gemini.embeddings import clear_rpm_state, embed_texts

    clear_rpm_state()
    called_keys: list[str] = []

    def _mock_load_api_keys(skip_exhausted: bool = True):
        return (["key_a", "key_b", "key_c"], ["aistros", "benavraham", "masha"], [])

    class _MockModels:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def embed_content(self, model: str, contents, config):
            called_keys.append(self.api_key)
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=[0.1] * 16) for _ in contents]
            )

    class _MockClient:
        def __init__(self, api_key: str) -> None:
            self.models = _MockModels(api_key)

    monkeypatch.setattr("src.ai.gemini.embeddings.load_api_keys", _mock_load_api_keys)
    monkeypatch.setattr("google.genai.Client", _MockClient)

    try:
        v1 = embed_texts(["t"] * 100, dimension=16)
        v2 = embed_texts(["t"] * 100, dimension=16)
        v3 = embed_texts(["t"] * 50, dimension=16)
        assert v1 is not None and len(v1) == 100
        assert v2 is not None and len(v2) == 100
        assert v3 is not None and len(v3) == 50
        assert called_keys == ["key_a", "key_b", "key_c"]
    finally:
        clear_rpm_state()


def test_text_rag_add_documents_sqlite_batch_and_dimension_adapter(tmp_path: Path) -> None:
    """Проверяет пакетную запись в SQLite BLOB и адаптацию размерности векторов на лету (128D vs 384D)."""
    db_base = tmp_path / "batch_index"
    rag_128 = TextRAG(db_path=db_base, dimension=128, provider="agy")
    docs = [
        {
            "id": f"ws1:doc{i}:c0",
            "text": f"Документ номер {i} с уникальной константой NODE_PX_{i}",
            "meta": {
                "workspace_id": "ws1",
                "document_id": f"doc{i}.py",
                "original_path": rf"C:\Users\dev\Projects\Deckor\src\doc{i}.py",
            },
        }
        for i in range(12)
    ]
    added = rag_128.add_documents(docs, batch_size=4)
    assert added == 12
    assert rag_128.count() == 12
    assert rag_128.db_file.exists()

    # Открываем ту же базу с другой размерностью (384D) — адаптер не должен падать
    rag_384 = TextRAG(db_path=db_base, dimension=384, provider="agy")
    hits = rag_384.search("NODE_PX_7", top_k=3, workspace_id="ws1", path_contains=r"Projects\Deckor\src")
    assert len(hits) >= 1
    assert hits[0]["id"] == "ws1:doc7:c0"
    assert hits[0]["bm25_rank"] is not None

    # Проверка delete_by_prefix и rename_prefix
    renamed = rag_384.rename_prefix("ws1:doc7:", "ws1:renamed7:", meta_updates={"document_id": "renamed7.py"})
    assert renamed == 1
    assert rag_384.delete_by_prefix("ws1:renamed7:") == 1
    assert rag_384.count() == 11


def test_mcp_rag_server_navigator_and_read_file_lines(tmp_path: Path) -> None:
    """Проверяет инструменты локального MCP-сервера (rag_search, read_file_lines, list_workspaces)."""
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager
    from apps.ai_assistant.mcp_rag_server import list_workspaces, rag_search, read_file_lines

    wm = WorkspaceManager(base_dir=tmp_path / "base", workspaces_dir=tmp_path / "workspaces")
    ws_id = "mcp_ws"
    wm.create_or_select_workspace(workspace_id=ws_id, name="MCP Test WS")

    empty_res = rag_search("AXIS_PX", workspace_id=ws_id, wm=wm)
    assert empty_res["reason"] == "out_of_scope"

    wm.import_document(
        workspace_id=ws_id,
        document_id="builder.py",
        content="NODE_PX = 11\nAXIS_PX = 9\ndef snap_node():\n    return NODE_PX + AXIS_PX\n",
    )

    found = rag_search("AXIS_PX", workspace_id=ws_id, wm=wm)
    assert found["status"] == "ok"
    assert found["reason"] == "matched"
    assert found["hits"][0]["document_id"] == "builder.py"

    workspaces = list_workspaces(wm=wm)
    assert any(w["workspace_id"] == ws_id and w["vectors_count"] >= 1 for w in workspaces)

    sample_file = tmp_path / "sample.py"
    sample_file.write_text("line1\nNODE_PX = 11\nAXIS_PX = 9\n", encoding="utf-8")
    read_res = read_file_lines(str(sample_file), start_line=2, end_line=3)
    assert read_res["status"] == "ok"
    assert "2: NODE_PX = 11" in read_res["content"]
    assert "3: AXIS_PX = 9" in read_res["content"]
