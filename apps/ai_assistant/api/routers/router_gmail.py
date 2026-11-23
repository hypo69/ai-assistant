# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Gmail Management Router (Re-export Proxy)
# =============================================================================
# Description:
#   Прокси-реэкспорт роутера Gmail из вынесенного микроприложения apps.google.
#
# File: router_gmail.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:00:00
# =============================================================================

from __future__ import annotations

"""Реэкспорт роутера Gmail из apps.google."""

from apps.google.api.routers.router_gmail import router

__all__ = ["router"]
