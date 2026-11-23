# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Contacts Router (Re-export Proxy)
# =============================================================================
# Description:
#   Прокси-реэкспорт роутера Contacts из вынесенного микроприложения apps.google.
#
# File: router_contacts.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:00:00
# =============================================================================

from __future__ import annotations

"""Реэкспорт роутера Contacts из apps.google."""

from apps.google.api.routers.router_contacts import router

__all__ = ["router"]
