# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - User Profile Package
# =============================================================================
# Description:
#   Пакет управления пользователями, профилями и базой данных data/users.db.
#
# File: __init__.py
# Package: apps.ai_assistant.core.users
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 02:15:00
# =============================================================================

from __future__ import annotations

"""Пакет управления пользователями и базой данных data/users.db."""

from .models import UserModel
from .service import UserService, user_service
from .storage import UsersStorage

__all__ = [
    "UserModel",
    "UsersStorage",
    "UserService",
    "user_service",
]
