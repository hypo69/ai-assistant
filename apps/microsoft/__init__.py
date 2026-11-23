# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Microsoft 365 & Office App - Package Initialization
# =============================================================================
# Description:
#   Точка входа пакета apps.microsoft. Экспортирует роутеры сервисов Microsoft 365
#   (Outlook, Office, OneDrive) и путь к директории веб-интерфейса.
#
# File: __init__.py
# Package: apps.microsoft
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:00:00
# =============================================================================

from __future__ import annotations

"""Пакет интеграции с Microsoft 365 и Office."""

from pathlib import Path

MICROSOFT_APP_DIR: Path = Path(__file__).resolve().parent
MICROSOFT_WEBGUI_DIR: Path = MICROSOFT_APP_DIR / "webgui"

from apps.microsoft.api.routers.router_outlook import router as outlook_router

__all__ = [
    "MICROSOFT_APP_DIR",
    "MICROSOFT_WEBGUI_DIR",
    "outlook_router",
]
