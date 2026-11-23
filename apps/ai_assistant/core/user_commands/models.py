# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant User Commands - Data Models
# =============================================================================
# Description:
#   Pydantic-модели данных для пользовательской базы знаний команд, шпаргалок
#   и сниппетов. Содержит схемы создания, редактирования, фильтрации и запуска.
#
# File: models.py
# Package: apps.ai_assistant.core.user_commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 01:20:00
# =============================================================================

from __future__ import annotations

"""Pydantic-модели данных базы знаний команд пользователя."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def get_current_iso_time() -> str:
    """Возвращает текущую метку времени в строгом UTC ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


class UserCommandBase(BaseModel):
    """Базовые поля пользовательской команды."""

    title: str = Field(..., min_length=1, max_length=200, description="Понятное название команды")
    command: str = Field(..., min_length=1, description="Текст исполняемой команды или сценария")
    shell: str = Field(default="powershell", description="Тип оболочки: powershell, cmd, bash, python")
    category: str = Field(default="Общее", description="Категория (Git, Сеть, Docker, Система, Windows и др.)")
    description: str = Field(default="", description="Описание назначения команды и сценариев использования")
    tags: List[str] = Field(default_factory=list, description="Теги для быстрого поиска и фильтрации")
    placeholders: Dict[str, str] = Field(default_factory=dict, description="Переменные/плейсхолдеры команды вида <PARAM>: описание")
    risk_level: str = Field(default="safe", description="Уровень риска: safe (безопасно), warn (внимание), danger (деструктивно)")
    favorite: bool = Field(default=False, description="Признак добавления команды в избранное")


class UserCommandCreate(UserCommandBase):
    """Схема создания новой команды."""

    command_id: Optional[str] = Field(default=None, description="Уникальный идентификатор команды (генерируется при отсутствии)")


class UserCommandUpdate(BaseModel):
    """Схема обновления существующей команды."""

    title: Optional[str] = Field(default=None, max_length=200)
    command: Optional[str] = None
    shell: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    placeholders: Optional[Dict[str, str]] = None
    risk_level: Optional[str] = None
    favorite: Optional[bool] = None


class UserCommand(UserCommandBase):
    """Полная модель команды в базе данных."""

    command_id: str = Field(..., description="Уникальный идентификатор команды")
    execution_count: int = Field(default=0, description="Количество выполнений")
    last_executed_at: Optional[str] = Field(default="", description="Время последнего запуска в UTC ISO")
    created_at: str = Field(default_factory=get_current_iso_time, description="Время создания")
    updated_at: str = Field(default_factory=get_current_iso_time, description="Время изменения")


class UserCommandExecuteRequest(BaseModel):
    """Схема запроса на интерактивное выполнение команды."""

    command_id: str = Field(..., description="Идентификатор выполняемой команды")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Значения плейсхолдеров/переменных")
    timeout_sec: int = Field(default=30, ge=1, le=300, description="Таймаут выполнения команды в секундах")
    as_admin: bool = Field(default=False, description="Выполнять ли от имени администратора Windows")


class UserCommandExecuteResult(BaseModel):
    """Результат выполнения команды."""

    command_id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    executed_at: str
    status: str
