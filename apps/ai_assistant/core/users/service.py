# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - User Profile Service
# =============================================================================
# Description:
#   Сервис управления учетными записями, профилями и синхронизацией данных
#   пользователя с Google OAuth 2.0 и локальной базой data/users.db.
#
# File: service.py
# Package: apps.ai_assistant.core.users
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 02:15:00
# =============================================================================

from __future__ import annotations

"""Сервис работы с пользователями и профилями."""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import logger
from .models import UserModel, get_current_iso_time
from .storage import UsersStorage


def compute_gravatar_url(email: str, size: int = 96) -> str:
    """Генерирует URL аватара Gravatar по email адресу."""
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return ""
    email_hash = hashlib.md5(clean_email.encode("utf-8")).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d=mp"


class UserService:
    """Сервис бизнес-логики учетных записей и профилей пользователей."""

    def __init__(self, storage: Optional[UsersStorage] = None) -> None:
        """Инициализирует сервис с подключением к хранилищу пользователей."""
        self.storage = storage or UsersStorage()
        self._ensure_initial_user()

    def _ensure_initial_user(self) -> None:
        """Инициализирует первичного пользователя по умолчанию (davidka), если база пуста."""
        try:
            users = self.storage.list_users()
            if not users:
                default_user = UserModel(
                    username="davidka",
                    email="e.cat.co.il@gmail.com",
                    full_name="David",
                    picture=compute_gravatar_url("e.cat.co.il@gmail.com"),
                    role="admin",
                    auth_provider="google",
                    is_active=True,
                )
                self.storage.upsert_user(default_user)
                logger.info("[UserService] Создан первичный администратор в data/users.db: davidka")
        except Exception as exc:
            logger.warning(f"[UserService] Ошибка первичной инициализации пользователя: {exc}")

    def get_or_sync_active_user(
        self,
        username: str,
        email: str = "",
        picture: str = "",
        full_name: str = "",
        has_google: bool = True,
    ) -> UserModel:
        """Получает или синхронизирует профиль текущего активного пользователя."""
        clean_name = (username or "davidka").strip()
        user = self.storage.get_user_by_username(clean_name)

        if not user:
            user_pic = picture or (compute_gravatar_url(email) if email else "")
            user = UserModel(
                username=clean_name,
                email=email,
                full_name=full_name or clean_name,
                picture=user_pic,
                role="admin",
                auth_provider="google" if has_google else "local",
                is_active=True,
                last_login_at=get_current_iso_time(),
            )
            return self.storage.upsert_user(user)

        # Если пользователь уже есть, актуализируем данные
        updates: Dict[str, Any] = {"last_login_at": get_current_iso_time()}
        if email and not user.email:
            updates["email"] = email
        if picture and (not user.picture or user.picture != picture):
            updates["picture"] = picture
        elif not user.picture and (email or user.email):
            updates["picture"] = compute_gravatar_url(email or user.email)
        if full_name and not user.full_name:
            updates["full_name"] = full_name

        if len(updates) > 1:
            updated_user = self.storage.update_user_fields(clean_name, **updates)
            if updated_user:
                return updated_user

        return user

    def update_profile(
        self,
        username: str,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        picture: Optional[str] = None,
        role: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserModel]:
        """Обновляет поля профиля пользователя."""
        fields: Dict[str, Any] = {}
        if full_name is not None:
            fields["full_name"] = full_name.strip()
        if email is not None:
            fields["email"] = email.strip()
            if picture is None:
                # Если сменился email и не задано фото, пересчитываем Gravatar
                fields["picture"] = compute_gravatar_url(fields["email"])
        if picture is not None:
            fields["picture"] = picture.strip()
        if role is not None:
            fields["role"] = role.strip()
        if preferences is not None:
            fields["preferences"] = preferences

        return self.storage.update_user_fields(username, **fields)

    def sync_google_profile(
        self,
        username: str,
        email: str,
        full_name: str,
        picture: str,
    ) -> UserModel:
        """Синхронизирует профиль пользователя с полученными данными Google OAuth."""
        user = self.get_or_sync_active_user(
            username=username,
            email=email,
            picture=picture,
            full_name=full_name,
            has_google=True,
        )
        return user

    def list_users(self) -> List[UserModel]:
        """Возвращает список всех пользователей."""
        return self.storage.list_users()

    def get_user(self, username: str) -> Optional[UserModel]:
        """Возвращает пользователя по имени."""
        return self.storage.get_user_by_username(username)


user_service = UserService()
