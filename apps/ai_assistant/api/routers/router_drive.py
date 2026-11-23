# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Drive Router (Re-export Proxy)
# =============================================================================
# Description:
#   Прокси-реэкспорт роутера Drive из вынесенного микроприложения apps.google.
#
# File: router_drive.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:00:00
# =============================================================================

from __future__ import annotations

"""Реэкспорт роутера Drive из apps.google."""

from apps.google.api.routers.router_drive import router

__all__ = ["router"]
