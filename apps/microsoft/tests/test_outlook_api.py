# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Microsoft App Tests - Outlook Suite
# =============================================================================
# Description:
#   Модульные тесты для OutlookManager и REST API приложения Microsoft (/api/v1/microsoft/outlook).
#
# File: test_outlook_api.py
# Package: apps.microsoft.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:00:00
# =============================================================================

from __future__ import annotations

"""Тестирование OutlookManager и REST API Microsoft."""

from unittest.mock import MagicMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.main import app
from apps.microsoft.core.outlook_manager import OutlookManager, _decode_mime_words


def test_decode_mime_words() -> None:
    """Проверяет декодирование MIME заголовков."""
    assert _decode_mime_words(None) == ""
    assert _decode_mime_words("Hello World") == "Hello World"
    # ISO-8859-1 / UTF-8 закодированная строка
    raw = "=?utf-8?B?0KLQtdGB0YI=?="
    assert "Тест" in _decode_mime_words(raw)


def test_outlook_manager_status() -> None:
    """Проверяет получение статуса Outlook."""
    mgr = OutlookManager()
    with patch.object(mgr, "get_config", return_value={"username": "user@outlook.com", "password": "pwd"}):
        status = mgr.get_status()
        assert status["configured"] is True
        assert status["account"] == "user@outlook.com"
        assert "Microsoft Outlook" in status["provider"]


@pytest.mark.asyncio
async def test_api_outlook_status_endpoint() -> None:
    """Проверяет эндпоинт GET /api/v1/microsoft/outlook/status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/microsoft/outlook/status")
        assert res.status_code == 200
        data = res.json()
        assert "configured" in data
        assert "provider" in data


@pytest.mark.asyncio
async def test_api_outlook_send_validation() -> None:
    """Проверяет валидацию эндпоинта отправки письма без конфигурации."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "to": "test@example.com",
            "subject": "Тестовая тема",
            "body": "Тестовое сообщение",
            "is_html": False
        }
        with patch("apps.microsoft.api.routers.router_outlook.outlook_manager.send_message", side_effect=ValueError("Учетная запись Outlook не настроена")):
            res = await client.post("/api/v1/microsoft/outlook/send", json=payload)
            assert res.status_code == 400
            assert "Учетная запись Outlook не настроена" in res.json()["detail"]
