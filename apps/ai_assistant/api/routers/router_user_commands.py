# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant API - Router User Commands
# =============================================================================
# Description:
#   REST API эндпоинты для пользовательской базы знаний команд и сниппетов.
#   Обеспечивает CRUD-операции, фильтрацию, переключение избранного и
#   выполнение команд на локальном хосте.
#
# File: router_user_commands.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 01:25:00
# =============================================================================

from __future__ import annotations

"""REST API роутер базы знаний пользовательских команд."""

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from apps.ai_assistant.core.user_commands.models import (
    UserCommand,
    UserCommandCreate,
    UserCommandExecuteRequest,
    UserCommandExecuteResult,
)
from apps.ai_assistant.core.user_commands.service import UserCommandsService

router = APIRouter(prefix="/api/v1/user-commands", tags=["user-commands"])

_commands_service: Optional[UserCommandsService] = None


def get_commands_service() -> UserCommandsService:
    """Возвращает инициализированный экземпляр сервиса команд."""
    global _commands_service
    if _commands_service is None:
        _commands_service = UserCommandsService()
    return _commands_service


@router.get("/list", summary="Список команд пользователя")
async def list_user_commands(
    category: Optional[str] = Query(None, description="Фильтр по категории"),
    shell: Optional[str] = Query(None, description="Фильтр по оболочке"),
    favorite: bool = Query(False, description="Только избранные команды"),
    query: Optional[str] = Query(None, description="Поисковый запрос"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Возвращает список команд с фильтрацией и полнотекстовым поиском."""
    def _do_list() -> Dict[str, Any]:
        srv = get_commands_service()
        items = srv.list_commands(
            category=category,
            shell=shell,
            favorite_only=favorite,
            query=query,
            limit=limit,
            offset=offset,
        )
        return {"items": [it.model_dump() for it in items], "total": len(items)}

    return await asyncio.to_thread(_do_list)


@router.get("/categories", summary="Список категорий команд")
async def get_user_command_categories() -> Dict[str, Any]:
    """Возвращает список уникальных категорий команд."""
    def _do_cats() -> List[str]:
        srv = get_commands_service()
        return srv.list_categories()

    cats = await asyncio.to_thread(_do_cats)
    return {"categories": cats}


@router.get("/item/{command_id}", summary="Получение команды по ID")
async def get_user_command_item(command_id: str) -> Dict[str, Any]:
    """Возвращает команду по идентификатору."""
    def _do_get():
        srv = get_commands_service()
        return srv.get_command(command_id)

    item = await asyncio.to_thread(_do_get)
    if not item:
        raise HTTPException(status_code=404, detail=f"Команда '{command_id}' не найдена")
    return item.model_dump()


@router.post("/save", summary="Создание или обновление команды")
async def save_user_command(payload: UserCommandCreate) -> Dict[str, Any]:
    """Создает новую команду или обновляет существующую."""
    def _do_save():
        srv = get_commands_service()
        return srv.save_command(payload)

    saved = await asyncio.to_thread(_do_save)
    return {"status": "ok", "command": saved.model_dump()}


@router.delete("/item/{command_id}", summary="Удаление команды")
async def delete_user_command(command_id: str) -> Dict[str, Any]:
    """Удаляет команду по идентификатору."""
    def _do_del():
        srv = get_commands_service()
        return srv.delete_command(command_id)

    deleted = await asyncio.to_thread(_do_del)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Команда '{command_id}' не найдена")
    return {"status": "ok", "deleted": True}


@router.post("/toggle-favorite/{command_id}", summary="Переключение статуса 'избранное'")
async def toggle_command_favorite(command_id: str) -> Dict[str, Any]:
    """Переключает статус избранного для команды."""
    def _do_fav():
        srv = get_commands_service()
        return srv.toggle_favorite(command_id)

    fav = await asyncio.to_thread(_do_fav)
    return {"status": "ok", "favorite": fav}


@router.post("/execute", summary="Интерактивный запуск команды")
async def execute_user_command(req: UserCommandExecuteRequest) -> UserCommandExecuteResult:
    """Выполняет команду на хосте и возвращает вывод консоли."""
    def _do_exec():
        srv = get_commands_service()
        return srv.execute_command(
            command_id=req.command_id,
            parameters=req.parameters,
            timeout_sec=req.timeout_sec,
            as_admin=req.as_admin,
        )

    res = await asyncio.to_thread(_do_exec)
    return res


@router.get("/export-markdown", summary="Экспорт шпаргалки в Markdown")
async def export_commands_markdown() -> PlainTextResponse:
    """Возвращает сгенерированный Markdown файл со всеми командами."""
    def _do_export() -> str:
        srv = get_commands_service()
        srv.storage.sync_to_markdown()
        if srv.storage.md_path.is_file():
            return srv.storage.md_path.read_text(encoding="utf-8")
        return ""

    content = await asyncio.to_thread(_do_export)
    return PlainTextResponse(content=content, media_type="text/markdown")
