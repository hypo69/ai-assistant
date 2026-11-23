# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - User Profile & Accounts Data Models
# =============================================================================
# Description:
#   Модели данных пользователя, схемы хранения в SQLite и сериализации профиля
#   для аутентификации через Google OAuth 2.0 и локального режима.
#
# File: models.py
# Package: apps.ai_assistant.core.users
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 02:15:00
# =============================================================================

from __future__ import annotations

"""Модели данных учетных записей пользователей."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional
import uuid


def get_current_iso_time() -> str:
    """Возвращает текущую временную метку UTC в формате ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class UserModel:
    """Модель учетной записи пользователя в локальной базе данных."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    email: str = ""
    full_name: str = ""
    picture: str = ""
    role: str = "admin"
    auth_provider: str = "google"
    is_active: bool = True
    preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=get_current_iso_time)
    updated_at: str = field(default_factory=get_current_iso_time)
    last_login_at: str = field(default_factory=get_current_iso_time)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует модель в словарь."""
        return asdict(self)

    @classmethod
    def from_row(cls, row: Any) -> UserModel:
        """Создает экземпляр модели из строки sqlite3.Row или словаря."""
        if hasattr(row, "keys"):
            data = dict(row)
        else:
            data = dict(row)

        prefs = data.get("preferences_json") or data.get("preferences") or "{}"
        if isinstance(prefs, str):
            try:
                preferences_dict = json.loads(prefs)
            except Exception:
                preferences_dict = {}
        elif isinstance(prefs, dict):
            preferences_dict = prefs
        else:
            preferences_dict = {}

        return cls(
            id=str(data.get("id") or str(uuid.uuid4())),
            username=str(data.get("username") or ""),
            email=str(data.get("email") or ""),
            full_name=str(data.get("full_name") or ""),
            picture=str(data.get("picture") or ""),
            role=str(data.get("role") or "admin"),
            auth_provider=str(data.get("auth_provider") or "google"),
            is_active=bool(data.get("is_active", 1)),
            preferences=preferences_dict,
            created_at=str(data.get("created_at") or get_current_iso_time()),
            updated_at=str(data.get("updated_at") or get_current_iso_time()),
            last_login_at=str(data.get("last_login_at") or get_current_iso_time()),
        )
