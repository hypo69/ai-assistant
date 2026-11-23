# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Common Models - Data Schemas
# =============================================================================
# Description:
#   Pydantic схемы данных для управления моделями ИИ, провайдерами
#   и интерактивным тестированием генерации на уровне приложений.
#
# File: models.py
# Package: apps.common.models
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 00:09:00
# =============================================================================

from __future__ import annotations

"""Pydantic-схемы запросов и ответов для подсистемы моделей ИИ."""

from typing import Optional
from pydantic import BaseModel, Field


class SetModelRequest(BaseModel):
    """Полезная нагрузка установки активной модели."""

    model: str = Field(..., description="Название модели")
    provider: Optional[str] = Field(default=None, description="Провайдер модели")
    save_to_config: Optional[bool] = Field(default=True, description="Сохранить в config.json")


class TestModelPayload(BaseModel):
    """Полезная нагрузка тестового запроса к модели."""

    __test__ = False

    model: str = Field(default="", description="Название модели")
    provider: str = Field(default="", description="Провайдер")
    message: str = Field(default="", description="Текст тестового сообщения")
    system_instruction: Optional[str] = Field(default=None, description="Системная инструкция")


class SetEmbeddingModelRequest(BaseModel):
    """Полезная нагрузка установки активной модели эмбеддингов."""

    model: str = Field(..., description="Идентификатор модели эмбеддингов")
    provider: Optional[str] = Field(default=None, description="Провайдер эмбеддингов")
    dimension: Optional[int] = Field(default=None, ge=32, le=8192, description="Размерность вектора")
    save_to_config: bool = Field(default=True, description="Сохранить в config.json")


class TestEmbeddingPayload(BaseModel):
    """Полезная нагрузка тестового запроса векторизации текста."""

    __test__ = False

    model: str = Field(default="", description="Идентификатор модели эмбеддингов")
    provider: str = Field(default="", description="Провайдер эмбеддингов")
    text: str = Field(default="", description="Тестовый текст для векторизации")
