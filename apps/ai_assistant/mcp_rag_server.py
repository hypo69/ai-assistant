# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Local RAG MCP Server (stdio)
# =============================================================================
# Description:
#   Локальный MCP-сервер (транспорт stdio, 0 открытых портов) для подключения
#   гибридного SQLite RAG (BLOB float32 + FTS5 BM25 + RRF) к IDE-агентам
#   (Antigravity, Claude Code и др.) по протоколу «RAG-навигатор + точечное чтение».
#
# Usage Examples:
#   CLI (stdio):
#     py apps/ai_assistant/mcp_rag_server.py
#
# File: mcp_rag_server.py
# Project: ai-windows-admin
# Package: apps.ai_assistant
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-23 17:52:00
# =============================================================================

from __future__ import annotations
"""Локальный MCP-сервер (stdio) гибридного RAG-навигатора для IDE-агентов."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from apps.ai_assistant.core.workspace_manager import WorkspaceManager

_MAX_READ_LINES = 200
_SNIPPET_MAX_CHARS = 320
_WM_INSTANCE: Optional[WorkspaceManager] = None


def _get_wm() -> WorkspaceManager:
    """Лениво возвращает синглтон WorkspaceManager."""
    global _WM_INSTANCE
    if _WM_INSTANCE is None:
        _WM_INSTANCE = WorkspaceManager()
    return _WM_INSTANCE


def list_workspaces(wm: Optional[WorkspaceManager] = None) -> List[Dict[str, Any]]:
    """Возвращает список рабочих областей и краткий статус их RAG-индексов."""
    manager = wm or _get_wm()
    result: List[Dict[str, Any]] = []
    for ws in manager.list_workspaces():
        ws_id = ws["workspace_id"]
        status = manager.get_workspace_rag_status(ws_id)
        result.append({
            "workspace_id": ws_id,
            "name": ws.get("name", ws_id),
            "language": ws.get("language", "ru"),
            "documents_count": status["documents_count"],
            "vectors_count": status["vectors_count"],
            "status": status["status"],
        })
    return result


def workspace_status(workspace_id: str, wm: Optional[WorkspaceManager] = None) -> Dict[str, Any]:
    """Возвращает детальную статистику RAG-индекса указанной рабочей области."""
    manager = wm or _get_wm()
    return manager.get_workspace_rag_status(workspace_id)


def rag_search(
    query: str,
    workspace_id: str = "default",
    top_k: int = 5,
    document_id: str = "",
    path_contains: str = "",
    wm: Optional[WorkspaceManager] = None,
) -> Dict[str, Any]:
    """Выполняет гибридный поиск (SQLite BLOB + FTS5 BM25 + RRF) в режиме навигатора.

    Возвращает координаты совпадений (document_id, original_path, chunk_index, commit_hash,
    краткий сниппет) и типизированный статус ('matched', 'absent', 'out_of_scope').

    Args:
        query: Поисковый запрос на естественном языке или точный идентификатор.
        workspace_id: Идентификатор рабочей области.
        top_k: Максимальное число возвращаемых совпадений (1..20).
        document_id: Опциональный SQL-фильтр по идентификатору документа.
        path_contains: Опциональный SQL-фильтр подстроки пути (через INSTR).
        wm: Опциональный экземпляр WorkspaceManager (для DI и тестов).

    Returns:
        Словарь с полем status, reason и списком компактных результатов hits.
    """
    manager = wm or _get_wm()
    safe_k = max(1, min(int(top_k), 20))
    rag = manager.get_faiss_rag(workspace_id)

    if rag.count() == 0:
        return {
            "status": "empty",
            "reason": "out_of_scope",
            "workspace_id": workspace_id,
            "hits": [],
        }

    raw_hits = rag.search(
        query=query,
        top_k=safe_k,
        workspace_id=workspace_id,
        document_id=document_id or None,
        path_contains=path_contains or None,
        hybrid=True,
    )

    if not raw_hits:
        return {
            "status": "not_found",
            "reason": "absent",
            "workspace_id": workspace_id,
            "hits": [],
        }

    compact_hits: List[Dict[str, Any]] = []
    for item in raw_hits:
        meta = item.get("meta") or {}
        text = str(item.get("text") or "")
        snippet = text if len(text) <= _SNIPPET_MAX_CHARS else f"{text[:_SNIPPET_MAX_CHARS]}..."
        compact_hits.append({
            "id": item["id"],
            "document_id": meta.get("document_id", ""),
            "original_path": meta.get("original_path", ""),
            "chunk_index": meta.get("chunk_index", meta.get("sentence_index", 0)),
            "commit_hash": meta.get("commit_hash", ""),
            "score": item.get("score", 0.0),
            "vector_score": item.get("vector_score", 0.0),
            "bm25_rank": item.get("bm25_rank"),
            "snippet": snippet,
        })

    return {
        "status": "ok",
        "reason": "matched",
        "workspace_id": workspace_id,
        "hits": compact_hits,
    }


def read_file_lines(file_path: str, start_line: int = 1, end_line: int = 80) -> Dict[str, Any]:
    """Точечно читает заданный диапазон строк файла (до 200 строк за вызов).

    Используется агентом после rag_search для получения точных формул и кода без дампа всего файла.

    Args:
        file_path: Путь к файлу на диске.
        start_line: Начальный номер строки (1-based).
        end_line: Конечный номер строки (включительно).

    Returns:
        Словарь со статусом, диапазоном строк и содержимым.
    """
    target = Path(file_path)
    if not target.is_file():
        return {"status": "error", "reason": "absent", "error": f"Файл не найден: {file_path}"}

    s_line = max(1, int(start_line))
    e_line = max(s_line, min(int(end_line), s_line + _MAX_READ_LINES - 1))

    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(lines)
    sliced = lines[s_line - 1 : e_line]
    return {
        "status": "ok",
        "file_path": str(target),
        "start_line": s_line,
        "end_line": min(e_line, total),
        "total_lines": total,
        "content": "\n".join(f"{s_line + idx}: {line}" for idx, line in enumerate(sliced)),
    }


def build_mcp_server() -> Any:
    """Создаёт и регистрирует инструменты MCP-сервера (mcp 2.x MCPServer, транспорт stdio)."""
    from mcp.server.mcpserver import MCPServer

    server = MCPServer("ai-assistant-local-rag")

    @server.tool()
    def mcp_list_workspaces() -> List[Dict[str, Any]]:
        """Список рабочих областей и статус их локальных SQLite RAG-индексов."""
        return list_workspaces()

    @server.tool()
    def mcp_workspace_status(workspace_id: str) -> Dict[str, Any]:
        """Статистика документов и векторов указанной рабочей области."""
        return workspace_status(workspace_id)

    @server.tool()
    def mcp_rag_search(
        query: str,
        workspace_id: str = "default",
        top_k: int = 5,
        document_id: str = "",
        path_contains: str = "",
    ) -> Dict[str, Any]:
        """Гибридный поиск (Dense BLOB + FTS5 BM25 + RRF) в режиме навигатора."""
        return rag_search(
            query=query,
            workspace_id=workspace_id,
            top_k=top_k,
            document_id=document_id,
            path_contains=path_contains,
        )

    @server.tool()
    def mcp_read_file_lines(file_path: str, start_line: int = 1, end_line: int = 80) -> Dict[str, Any]:
        """Точечное чтение диапазона строк файла (до 200 строк за вызов)."""
        return read_file_lines(file_path=file_path, start_line=start_line, end_line=end_line)

    return server


if __name__ == "__main__":
    build_mcp_server().run(transport="stdio")
