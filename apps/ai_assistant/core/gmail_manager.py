# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Gmail Manager (Re-export Proxy)
# =============================================================================
# Description:
#   Прокси-реэкспорт сервиса управления Gmail из apps.google.core.
#
# File: gmail_manager.py
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:00:00
# =============================================================================

from __future__ import annotations

"""Реэкспорт сервиса управления Gmail из apps.google.core."""

from apps.google.core.gmail_manager import (
    GmailManager,
    gmail_manager,
)

__all__ = ["GmailManager", "gmail_manager"]
