# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant API - Router File History
# =============================================================================
# Description:
#   REST API маршрутизатор для доступа к истории версий Git: коммиты,
#   построчный diff с фильтрацией бинарных файлов, blame и таймлайн.
#
# Usage Examples:
#   FastAPI Endpoint:
#     GET /api/v1/history?file_path=apps/ai_assistant/main.py&limit=10
#     GET /api/v1/diff?commit_hash=a1b2c3&file_path=apps/ai_assistant/main.py
#     GET /api/v1/timeline?file_path=apps/ai_assistant/main.py
#     GET /api/v1/blame?file_path=apps/ai_assistant/main.py
#
# File: router_file_history.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 18:45:00
# =============================================================================

from __future__ import annotations
"""Маршрутизатор эндпоинтов истории Git, диффов и таймлайна с поддержкой рабочих областей."""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from logger import logger
from apps.ai_assistant.api.schemas import (
    BlameResponse,
    CommitSummary,
    DiffResponse,
    TimelineResponse,
)
from apps.ai_assistant.core.git_history_engine import GitHistoryEngine
from apps.ai_assistant.core.repo_resolver import resolve_repo_path
from apps.ai_assistant.git_adapter import GitAdapter

router = APIRouter(prefix="/api/v1", tags=["File History"])
_default_git_engine = GitHistoryEngine()


def _get_engine(workspace_id: Optional[str] = None, repo_path: Optional[str] = None) -> GitHistoryEngine:
    """Возвращает движок истории Git для указанной рабочей области или репозитория по умолчанию."""
    if not workspace_id and not repo_path:
        return _default_git_engine
    target = resolve_repo_path(workspace_id=workspace_id, repo_path=repo_path)
    return GitHistoryEngine(repo_path=target)


@router.get("/history", response_model=List[CommitSummary], summary="История коммитов файла или проекта")
async def get_history(
    file_path: Optional[str] = Query(None, description="Относительный путь к файлу"),
    limit: int = Query(50, ge=1, le=200, description="Максимальное число коммитов"),
    search: Optional[str] = Query(None, description="Поисковый запрос по сообщениям коммитов"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    repo_path: Optional[str] = Query(None, description="Путь к репозиторию Git"),
) -> List[CommitSummary]:
    """Возвращает структурированный список коммитов с информацией об авторе и изменениях."""
    try:
        engine = await asyncio.to_thread(_get_engine, workspace_id, repo_path)
        return await engine.get_file_history(file_path=file_path, limit=limit, search_query=search)
    except Exception as exc:
        logger.error(f"[RouterFileHistory] Ошибка получения истории: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения истории Git: {exc}")


@router.get("/diff", response_model=DiffResponse, summary="Получение diff изменений коммита")
async def get_diff(
    commit_hash: str = Query(..., description="Хэш коммита"),
    file_path: Optional[str] = Query(None, description="Путь к файлу (опционально)"),
    parent_hash: Optional[str] = Query(None, description="Хэш родительского коммита (опционально)"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    repo_path: Optional[str] = Query(None, description="Путь к репозиторию Git"),
) -> DiffResponse:
    """Возвращает diff изменений между ревизиями с защитой от переполнения буфера."""
    if commit_hash.strip().startswith("-") or (parent_hash and parent_hash.strip().startswith("-")):
        raise HTTPException(status_code=400, detail="Недопустимый формат commit_hash: ведущий дефис запрещён")
    try:
        engine = await asyncio.to_thread(_get_engine, workspace_id, repo_path)
        return await engine.get_diff(commit_hash=commit_hash, file_path=file_path, parent_hash=parent_hash)
    except Exception as exc:
        logger.error(f"[RouterFileHistory] Ошибка формирования diff: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка формирования diff: {exc}")


@router.get("/timeline", response_model=TimelineResponse, summary="Таймлайн жизненного цикла файла")
async def get_timeline(
    file_path: str = Query(..., description="Путь к файлу в репозитории"),
    limit: int = Query(50, ge=1, le=200, description="Количество точек шкалы времени"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    repo_path: Optional[str] = Query(None, description="Путь к репозиторию Git"),
) -> TimelineResponse:
    """Формирует хронологическую шкалу контрольных точек изменений файла."""
    try:
        engine = await asyncio.to_thread(_get_engine, workspace_id, repo_path)
        return await engine.get_timeline(file_path=file_path, limit=limit)
    except Exception as exc:
        logger.error(f"[RouterFileHistory] Ошибка формирования таймлайна: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка формирования таймлайна: {exc}")


@router.get("/blame", response_model=BlameResponse, summary="Построчная аннотация авторства (blame)")
async def get_blame(
    file_path: str = Query(..., description="Путь к файлу"),
    commit_hash: Optional[str] = Query(None, description="Срез репозитория на конкретный коммит"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    repo_path: Optional[str] = Query(None, description="Путь к репозиторию Git"),
) -> BlameResponse:
    """Возвращает построчный blame для детального аудита изменений строк кода."""
    commit = commit_hash or "HEAD"
    if commit.strip().startswith("-"):
        raise HTTPException(status_code=400, detail="Недопустимый формат commit_hash: ведущий дефис запрещён")
    try:
        engine = await asyncio.to_thread(_get_engine, workspace_id, repo_path)
        return await engine.get_blame(file_path=file_path, commit_hash=commit)
    except Exception as exc:
        logger.error(f"[RouterFileHistory] Ошибка построения blame: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения git blame: {exc}")


@router.get("/content", summary="Получение содержимого файла на указанный коммит")
async def get_file_content(
    file_path: str = Query(..., description="Путь к файлу"),
    commit_hash: str = Query("HEAD", description="Хэш коммита или ветка"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    repo_path: Optional[str] = Query(None, description="Путь к репозиторию Git"),
) -> Dict[str, Any]:
    """Возвращает текстовое содержимое файла в выбранной ревизии."""
    if commit_hash.strip().startswith("-"):
        raise HTTPException(status_code=400, detail="Недопустимый формат commit_hash: ведущий дефис запрещён")
    try:
        from apps.common.file_editor.catalog import SupportedFileCatalog
        engine = await asyncio.to_thread(_get_engine, workspace_id, repo_path)
        content = await engine.get_file_content(commit_hash=commit_hash, file_path=file_path)
        blob_hash = await engine.get_blob_hash(commit_hash=commit_hash, file_path=file_path)
        direction = SupportedFileCatalog.detect_text_direction(content, file_path)
        return {
            "file_path": file_path,
            "commit_hash": commit_hash,
            "blob_hash": blob_hash,
            "content": content,
            "direction": direction,
            "lines_count": len(content.splitlines()),
        }
    except Exception as exc:
        logger.error(f"[RouterFileHistory] Ошибка чтения содержимого файла: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения файла: {exc}")


_BINARY_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".mp3", ".wav", ".ogg", ".mp4", ".avi", ".mkv", ".mov",
    ".exe", ".dll", ".pyd", ".so", ".db", ".sqlite", ".sqlite3",
}
_MAX_COMPARE_TEXT_BYTES = 200_000


def _is_binary_path(file_path: str) -> bool:
    """Проверяет, относится ли расширение файла к бинарным форматам."""
    return Path(file_path).suffix.lower() in _BINARY_EXTENSIONS


def _read_current_disk_file(repo_root: Path, file_path: str) -> tuple[Optional[str], bool]:
    """Читает текущую версию файла с диска с защитой от выхода за пределы репозитория и бинарников."""
    try:
        resolved_root = repo_root.resolve()
        candidate = (resolved_root / file_path).resolve()
        candidate.relative_to(resolved_root)
    except Exception:
        return None, False

    if not candidate.exists() or not candidate.is_file():
        return None, False

    if _is_binary_path(file_path):
        return None, True

    try:
        raw = candidate.read_bytes()[:_MAX_COMPARE_TEXT_BYTES]
        if b"\x00" in raw[:4096]:
            return None, True
        return raw.decode("utf-8", errors="replace"), False
    except Exception:
        return None, False


@router.get("/commit-compare", summary="Двухпанельное сравнение файлов коммита с нынешней версией")
async def get_commit_compare(
    commit_hash: str = Query(..., description="Хэш выбранного коммита (версии)"),
    max_files: int = Query(10, ge=1, le=10, description="Максимум открываемых пар сравнения (не более 10)"),
    include_other_commits: bool = Query(False, description="Включать ли другие коммиты этих файлов (до 10)"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    repo_path: Optional[str] = Query(None, description="Путь к репозиторию Git"),
) -> Dict[str, Any]:
    """Возвращает пары сравнения «Закоммиченная версия ↔ Нынешняя версия» для файлов выбранного сохранения."""
    if commit_hash.strip().startswith("-"):
        raise HTTPException(status_code=400, detail="Недопустимый формат commit_hash: ведущий дефис запрещён")

    try:
        target_repo = await asyncio.to_thread(resolve_repo_path, workspace_id=workspace_id, repo_path=repo_path)
        repo_root = Path(target_repo)
        adapter = GitAdapter(repo_path=target_repo)
        engine = GitHistoryEngine(repo_path=target_repo)

        commit_info, changes = await asyncio.to_thread(adapter.get_commit_details, commit_hash)
        total_changed_files = len(changes)
        selected_changes = changes[:max_files]

        comparisons: List[Dict[str, Any]] = []
        other_commit_candidates: List[Dict[str, Any]] = []
        current_cache: Dict[str, tuple[str, bool]] = {}

        for ch in selected_changes:
            fp = ch.file_path
            is_bin = _is_binary_path(fp)

            disk_text, disk_bin = await asyncio.to_thread(_read_current_disk_file, repo_root, fp)
            is_bin = is_bin or disk_bin

            if is_bin:
                current_text = ""
                committed_text = ""
            else:
                if disk_text is not None:
                    current_text = disk_text
                else:
                    try:
                        current_text = (await engine.get_file_content(commit_hash="HEAD", file_path=fp))[:_MAX_COMPARE_TEXT_BYTES]
                    except Exception:
                        current_text = ""
                try:
                    committed_text = (await engine.get_file_content(commit_hash=commit_hash, file_path=fp))[:_MAX_COMPARE_TEXT_BYTES]
                except Exception:
                    committed_text = ""

            current_cache[fp] = (current_text, is_bin)

            # Проверяем, есть ли другие сохранения этого файла
            other_for_file: List[Dict[str, Any]] = []
            try:
                hist = await engine.get_file_history(file_path=fp, limit=10)
                for h_item in hist:
                    h_hash = getattr(h_item, "commit_hash", "")
                    if h_hash and not h_hash.startswith(commit_hash[:8]) and not commit_hash.startswith(h_hash[:8]):
                        other_for_file.append({
                            "file_path": fp,
                            "change_type": ch.change_type,
                            "commit_hash": h_hash,
                            "timestamp": getattr(h_item, "timestamp", ""),
                            "author": getattr(h_item, "author", ""),
                            "message": getattr(h_item, "message", ""),
                        })
            except Exception:
                pass

            other_commit_candidates.extend(other_for_file)

            from apps.common.file_editor.catalog import SupportedFileCatalog
            item_dir = (
                "ltr"
                if is_bin
                else SupportedFileCatalog.detect_text_direction(current_text or committed_text, fp)
            )
            comparisons.append({
                "file_path": fp,
                "change_type": ch.change_type,
                "is_binary": is_bin,
                "direction": item_dir,
                "committed_hash": commit_hash,
                "committed_timestamp": getattr(commit_info, "timestamp", "") if commit_info else "",
                "committed_author": getattr(commit_info, "author", "") if commit_info else "",
                "committed_message": getattr(commit_info, "message", "") if commit_info else "",
                "committed_content": committed_text,
                "current_content": current_text,
                "is_selected_commit": True,
            })

        # Если пользователь захотел открыть и другие коммиты — добавляем до лимита max_files (<= 10)
        if include_other_commits and len(comparisons) < max_files:
            from apps.common.file_editor.catalog import SupportedFileCatalog
            for cand in other_commit_candidates:
                if len(comparisons) >= max_files:
                    break
                fp = cand["file_path"]
                cur_text, is_bin = current_cache.get(fp, ("", _is_binary_path(fp)))
                if is_bin:
                    comp_text = ""
                else:
                    try:
                        comp_text = (await engine.get_file_content(commit_hash=cand["commit_hash"], file_path=fp))[:_MAX_COMPARE_TEXT_BYTES]
                    except Exception:
                        comp_text = ""
                cand_dir = (
                    "ltr"
                    if is_bin
                    else SupportedFileCatalog.detect_text_direction(cur_text or comp_text, fp)
                )
                comparisons.append({
                    "file_path": fp,
                    "change_type": cand["change_type"],
                    "is_binary": is_bin,
                    "direction": cand_dir,
                    "committed_hash": cand["commit_hash"],
                    "committed_timestamp": cand["timestamp"],
                    "committed_author": cand["author"],
                    "committed_message": cand["message"],
                    "committed_content": comp_text,
                    "current_content": cur_text,
                    "is_selected_commit": False,
                })

        return {
            "commit_hash": commit_hash,
            "commit_message": getattr(commit_info, "message", "") if commit_info else "",
            "commit_timestamp": getattr(commit_info, "timestamp", "") if commit_info else "",
            "commit_author": getattr(commit_info, "author", "") if commit_info else "",
            "total_changed_files": total_changed_files,
            "max_files_limit": max_files,
            "has_multiple_commits": len(other_commit_candidates) > 0,
            "other_commits_count": len(other_commit_candidates),
            "include_other_commits": include_other_commits,
            "comparisons": comparisons,
        }
    except Exception as exc:
        logger.error(f"[RouterFileHistory] Ошибка двухпанельного сравнения коммита: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка сравнения версий: {exc}")
