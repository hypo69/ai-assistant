# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Calendar Router (Re-export Proxy)
# =============================================================================
# Description:
#   Прокси-реэкспорт роутера Calendar из вынесенного микроприложения apps.google.
#
# File: router_calendar.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:00:00
# =============================================================================

from __future__ import annotations

"""Реэкспорт роутера Calendar из apps.google."""

from apps.google.api.routers.router_calendar import router

__all__ = ["router"]
