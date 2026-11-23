# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Gmail RAG Service (Re-export Proxy)
# =============================================================================
# Description:
#   Прокси-реэкспорт сервиса RAG для Gmail из apps.google.core.
#
# File: gmail_rag_service.py
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:00:00
# =============================================================================

from __future__ import annotations

"""Реэкспорт сервиса RAG для Gmail из apps.google.core."""

from apps.google.core.gmail_rag_service import (
    GmailRagService,
    gmail_rag_service,
)

__all__ = ["GmailRagService", "gmail_rag_service"]
