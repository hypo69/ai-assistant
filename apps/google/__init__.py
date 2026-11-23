# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Workspace App - Package Initialization
# =============================================================================
# Description:
#   Точка входа пакета apps.google. Экспортирует роутеры сервисов Google Workspace
#   (Gmail, Calendar, Drive, Contacts) и базовые сервисы управления.
#
# File: __init__.py
# Package: apps.google
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:00:00
# =============================================================================

from __future__ import annotations

"""Пакет интеграции с Google Workspace (Gmail, Calendar, Drive, Contacts)."""

from pathlib import Path

GOOGLE_APP_DIR: Path = Path(__file__).resolve().parent
GOOGLE_WEBGUI_DIR: Path = GOOGLE_APP_DIR / "webgui"

from apps.google.api.routers.router_gmail import router as gmail_router
from apps.google.api.routers.router_calendar import router as calendar_router
from apps.google.api.routers.router_drive import router as drive_router
from apps.google.api.routers.router_contacts import router as contacts_router

__all__ = [
    "GOOGLE_APP_DIR",
    "GOOGLE_WEBGUI_DIR",
    "gmail_router",
    "calendar_router",
    "drive_router",
    "contacts_router",
]
