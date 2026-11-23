# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant User Commands Package
# =============================================================================
# Description:
#   Пакет пользовательской базы знаний команд, шпаргалок и сниппетов.
#
# File: __init__.py
# Package: apps.ai_assistant.core.user_commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 01:23:00
# =============================================================================

from __future__ import annotations

from .models import (
    UserCommand,
    UserCommandCreate,
    UserCommandUpdate,
    UserCommandExecuteRequest,
    UserCommandExecuteResult,
)
from .service import UserCommandsService
from .storage import UserCommandsStorage

__all__ = [
    "UserCommand",
    "UserCommandCreate",
    "UserCommandUpdate",
    "UserCommandExecuteRequest",
    "UserCommandExecuteResult",
    "UserCommandsService",
    "UserCommandsStorage",
]
