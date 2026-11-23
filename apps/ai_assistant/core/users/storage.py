# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Users SQLite Storage
# =============================================================================
# Description:
#   Хранилище профилей пользователей в базе данных data/users.db (SQLite)
#   в режиме WAL с поддержкой потокобезопасности и транзакций.
#
# File: storage.py
# Package: apps.ai_assistant.core.users
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 02:15:00
# =============================================================================

from __future__ import annotations

"""Модуль хранения пользователей в SQLite базе data/users.db."""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, Generator, List, Optional

from header import __root__
from logger import logger
from .models import UserModel, get_current_iso_time


class UsersStorage:
    """Управление хранением профилей пользователей в SQLite."""

    def __init__(self, db_path: str | Path = "data/users.db") -> None:
        """Инициализирует менеджер хранилища пользователей."""
        self._lock = threading.RLock()
        self.db_path = (__root__ / Path(db_path)).resolve() if not Path(db_path).is_absolute() else Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_sqlite_db()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Потокобезопасный контекстный менеджер соединения SQLite в режиме WAL."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=15.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=15000;")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_sqlite_db(self) -> None:
        """Создает таблицы и индексы базы данных пользователей."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT NOT NULL DEFAULT '',
                    full_name TEXT NOT NULL DEFAULT '',
                    picture TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT 'admin',
                    auth_provider TEXT NOT NULL DEFAULT 'google',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    preferences_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);")

    def get_user_by_username(self, username: str) -> Optional[UserModel]:
        """Получает пользователя по его уникальному логину."""
        if not username:
            return None
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM users WHERE username = ? LIMIT 1;", (username.strip(),))
            row = cur.fetchone()
            if row:
                return UserModel.from_row(row)
        return None

    def get_user_by_id(self, user_id: str) -> Optional[UserModel]:
        """Получает пользователя по его уникальному идентификатору ID."""
        if not user_id:
            return None
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM users WHERE id = ? LIMIT 1;", (user_id.strip(),))
            row = cur.fetchone()
            if row:
                return UserModel.from_row(row)
        return None

    def upsert_user(self, user: UserModel) -> UserModel:
        """Создает или обновляет запись пользователя в базе данных."""
        now = get_current_iso_time()
        user.updated_at = now
        prefs_str = json.dumps(user.preferences, ensure_ascii=False)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    id, username, email, full_name, picture,
                    role, auth_provider, is_active, preferences_json,
                    created_at, updated_at, last_login_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    email = excluded.email,
                    full_name = CASE WHEN excluded.full_name <> '' THEN excluded.full_name ELSE users.full_name END,
                    picture = CASE WHEN excluded.picture <> '' THEN excluded.picture ELSE users.picture END,
                    role = excluded.role,
                    auth_provider = excluded.auth_provider,
                    is_active = excluded.is_active,
                    preferences_json = excluded.preferences_json,
                    updated_at = excluded.updated_at,
                    last_login_at = excluded.last_login_at;
                """,
                (
                    user.id,
                    user.username,
                    user.email,
                    user.full_name,
                    user.picture,
                    user.role,
                    user.auth_provider,
                    1 if user.is_active else 0,
                    prefs_str,
                    user.created_at,
                    user.updated_at,
                    user.last_login_at,
                ),
            )
        return user

    def update_user_fields(self, username: str, **fields: Any) -> Optional[UserModel]:
        """Обновляет отдельные поля пользователя по логину."""
        user = self.get_user_by_username(username)
        if not user:
            return None

        allowed = {
            "email",
            "full_name",
            "picture",
            "role",
            "auth_provider",
            "is_active",
            "preferences",
            "last_login_at",
        }
        updates = []
        params = []
        now = get_current_iso_time()

        for key, val in fields.items():
            if key not in allowed:
                continue
            if key == "preferences":
                updates.append("preferences_json = ?")
                params.append(json.dumps(val or {}, ensure_ascii=False))
            elif key == "is_active":
                updates.append("is_active = ?")
                params.append(1 if val else 0)
            else:
                updates.append(f"{key} = ?")
                params.append(val)

        if not updates:
            return user

        updates.append("updated_at = ?")
        params.append(now)
        params.append(username)

        with self._connect() as conn:
            sql = f"UPDATE users SET {', '.join(updates)} WHERE username = ?;"
            conn.execute(sql, tuple(params))

        return self.get_user_by_username(username)

    def list_users(self) -> List[UserModel]:
        """Возвращает список всех зарегистрированных пользователей."""
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM users ORDER BY created_at ASC;")
            return [UserModel.from_row(r) for r in cur.fetchall()]

    def delete_user(self, username: str) -> bool:
        """Удаляет пользователя по его имени."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM users WHERE username = ?;", (username,))
            return cur.rowcount > 0
