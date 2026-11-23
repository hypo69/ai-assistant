# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Users Storage & Auth Tests
# =============================================================================
# Description:
#   Модульные тесты для хранилища UsersStorage, сервиса UserService
#   и проверки отображения аватара/профиля пользователя в router_auth.
#
# File: test_users_storage_and_auth.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 02:15:00
# =============================================================================

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from apps.ai_assistant.core.users.models import UserModel
from apps.ai_assistant.core.users.service import UserService, compute_gravatar_url
from apps.ai_assistant.core.users.storage import UsersStorage
from apps.ai_assistant.api.routers.router_auth import _get_active_auth_state


@pytest.fixture
def temp_users_storage(tmp_path: Path) -> UsersStorage:
    """Фикстура для изолированного временного хранилища пользователей."""
    db_file = tmp_path / "test_users.db"
    return UsersStorage(db_path=db_file)


def test_users_storage_crud(temp_users_storage: UsersStorage):
    """Проверяет базовые CRUD операции хранилища UsersStorage."""
    user = UserModel(
        username="test_admin",
        email="admin@example.com",
        full_name="Test Administrator",
        picture="https://example.com/avatar.png",
        role="admin",
        auth_provider="google",
    )
    saved = temp_users_storage.upsert_user(user)
    assert saved.username == "test_admin"

    loaded = temp_users_storage.get_user_by_username("test_admin")
    assert loaded is not None
    assert loaded.email == "admin@example.com"
    assert loaded.picture == "https://example.com/avatar.png"

    # Обновление полей
    updated = temp_users_storage.update_user_fields(
        "test_admin",
        full_name="New Name",
        picture="https://example.com/new.png",
    )
    assert updated is not None
    assert updated.full_name == "New Name"
    assert updated.picture == "https://example.com/new.png"

    # Список и удаление
    all_users = temp_users_storage.list_users()
    assert len(all_users) == 1

    deleted = temp_users_storage.delete_user("test_admin")
    assert deleted is True
    assert temp_users_storage.get_user_by_username("test_admin") is None


def test_user_service_fallback_gravatar(temp_users_storage: UsersStorage):
    """Проверяет генерацию fallback аватара через Gravatar при отсутствии фото в OAuth."""
    service = UserService(storage=temp_users_storage)

    gravatar = compute_gravatar_url("e.cat.co.il@gmail.com")
    assert "gravatar.com/avatar/" in gravatar

    user = service.get_or_sync_active_user(
        username="davidka",
        email="e.cat.co.il@gmail.com",
        picture="",
        has_google=True,
    )
    assert user.username == "davidka"
    assert user.picture != ""
    assert "gravatar.com" in user.picture


def test_get_active_auth_state_returns_picture():
    """Проверяет, что router_auth возвращает URL фото, а не None."""
    state = _get_active_auth_state()
    assert "picture" in state
    if state.get("authenticated"):
        assert state["picture"] is not None
        assert len(state["picture"]) > 0
