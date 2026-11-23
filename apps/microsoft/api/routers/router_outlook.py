# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Microsoft 365 App - Outlook Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор управления почтовым клиентом Outlook (Microsoft 365).
#   Обеспечивает получение статуса, выборку писем и отправку сообщений.
#
# Usage Examples:
#   GET  /api/v1/microsoft/outlook/status
#   GET  /api/v1/microsoft/outlook/messages
#   POST /api/v1/microsoft/outlook/send
#
# File: router_outlook.py
# Package: apps.microsoft.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:00:00
# =============================================================================

from __future__ import annotations

"""REST API маршрутизатор для работы с Microsoft Outlook."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from apps.microsoft.core.outlook_manager import outlook_manager
from logger import logger

router = APIRouter(prefix="/api/v1/microsoft/outlook", tags=["Microsoft Outlook"])


class OutlookSendPayload(BaseModel):
    """Схема отправки сообщения через Outlook."""
    to: str = Field(..., description="Email получателя")
    subject: str = Field(..., description="Тема письма")
    body: str = Field(..., description="Тело письма")
    is_html: bool = Field(default=False, description="Флаг HTML разметки")


@router.get("/status", summary="Статус подключения Outlook")
async def get_outlook_status() -> Dict[str, Any]:
    """Возвращает информацию о текущем состоянии учетной записи Outlook."""
    return outlook_manager.get_status()


@router.get("/messages", summary="Получить список последних писем Outlook")
async def list_outlook_messages(
    limit: int = Query(default=10, ge=1, le=50, description="Количество писем"),
    folder: str = Query(default="INBOX", description="Почтовая папка"),
) -> List[Dict[str, Any]]:
    """Возвращает список заголовков последних писем из папки Outlook."""
    return outlook_manager.list_messages(limit=limit, folder=folder)


@router.post("/send", summary="Отправить письмо через Outlook")
async def send_outlook_message(payload: OutlookSendPayload) -> Dict[str, Any]:
    """Отправляет электронное письмо через SMTP Microsoft 365 / Outlook."""
    try:
        return outlook_manager.send_message(
            to=payload.to,
            subject=payload.subject,
            body=payload.body,
            is_html=payload.is_html,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"[router_outlook] Ошибка отправки: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
