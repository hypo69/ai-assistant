# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Google Contacts Agent Module
# =============================================================================
# Description:
#   Автономный агент управления контактами Google People API.
#   Обеспечивает интеллектуальный поиск, создание, обновление, удаление,
#   пакетный импорт и нормализацию телефонной книги пользователя.
#
# Usage Examples:
#   from src.ai.agents.contacts_agent import ContactsAgent
#
#   agent = ContactsAgent()
#   contacts = agent.search_contacts("דוד")
#   created = agent.create_contact(given_name="Сергей", phone="+972500000000")
#
# File: contacts_agent.py
# Project: ai-windows-admin
# Package: src.ai.agents
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 20:25:00
# =============================================================================

from __future__ import annotations

"""Модуль автономного агента управления контактами Google People API."""

import json
from typing import Any, Dict, List, Optional

from apps.ai_assistant.core.skills_bridge import get_contacts_client
from logger import logger


class ContactsAgent:
    """Автономный агент для операций с телефонной книгой Google Contacts."""

    def __init__(self, account_name: Optional[str] = None, ai_model: Any = None) -> None:
        """Инициализация агента контактов.

        Args:
            account_name: Имя аккаунта Google OAuth.
            ai_model: Опциональный инстанс AI-модели.
        """
        self.account_name = account_name
        self.ai_model = ai_model

    def _get_client(self):
        """Возвращает инициализированный клиент GoogleContactsClient."""
        return get_contacts_client(account_name=self.account_name)

    def list_contacts(self, query: Optional[str] = None, max_results: int = 50) -> List[Dict[str, Any]]:
        """Получение списка контактов с возможностью фильтрации.

        Args:
            query: Строка поиска по имени, телефону или email.
            max_results: Максимальное количество контактов.

        Returns:
            Список словарей контактов.
        """
        client = self._get_client()
        return client.list_contacts(query=query, max_results=max_results)

    def search_contacts(self, query: str) -> List[Dict[str, Any]]:
        """Быстрый поиск контактов по запросу.

        Args:
            query: Запрос для поиска.

        Returns:
            Список найденных контактов.
        """
        return self.list_contacts(query=query)

    def get_contact(self, resource_name: str) -> Dict[str, Any]:
        """Получение подробных данных контакта по resourceName.

        Args:
            resource_name: Идентификатор контакта вида 'people/c...'.

        Returns:
            Словарь контакта.
        """
        client = self._get_client()
        return client.get_contact(resource_name=resource_name)

    def create_contact(
        self,
        given_name: str,
        family_name: str = "",
        phone: Optional[str] = None,
        email: Optional[str] = None,
        organization: Optional[str] = None,
        title: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Создание нового контакта в адресной книге.

        Args:
            given_name: Имя контакта.
            family_name: Фамилия контакта.
            phone: Номер телефона.
            email: Электронный адрес.
            organization: Организация.
            title: Должность.
            notes: Заметки.

        Returns:
            Словарь с результатом создания.
        """
        client = self._get_client()
        res = client.create_contact(
            given_name=given_name,
            family_name=family_name,
            phone=phone,
            email=email,
            organization=organization,
            title=title,
            notes=notes,
        )
        logger.info(f"[ContactsAgent] Создан контакт: {given_name} {family_name}")
        return res

    def update_contact(
        self,
        resource_name: str,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        organization: Optional[str] = None,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        etag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Обновление существующего контакта.

        Args:
            resource_name: Идентификатор контакта вида 'people/c...'.
            given_name: Новое имя.
            family_name: Новая фамилия.
            phone: Новый телефон.
            email: Новый email.
            organization: Новая организация.
            title: Новая должность.
            notes: Новые заметки.
            etag: etag контакта.

        Returns:
            Словарь с результатом обновления.
        """
        client = self._get_client()
        res = client.update_contact(
            resource_name=resource_name,
            given_name=given_name,
            family_name=family_name,
            phone=phone,
            email=email,
            organization=organization,
            title=title,
            notes=notes,
            etag=etag,
        )
        logger.info(f"[ContactsAgent] Обновлен контакт: {resource_name}")
        return res

    def delete_contact(self, resource_name: str) -> Dict[str, Any]:
        """Удаление контакта из адресной книги.

        Args:
            resource_name: Идентификатор контакта вида 'people/c...'.

        Returns:
            Словарь со статусом удаления.
        """
        client = self._get_client()
        res = client.delete_contact(resource_name=resource_name)
        logger.info(f"[ContactsAgent] Удален контакт: {resource_name}")
        return res

    def import_contacts_batch(self, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Пакетный импорт списка контактов.

        Args:
            contacts: Список словарей контактов для создания.

        Returns:
            Словарь со статистикой импорта.
        """
        created = []
        errors = []
        for c in contacts:
            try:
                res = self.create_contact(
                    given_name=c.get("given_name", ""),
                    family_name=c.get("family_name", ""),
                    phone=c.get("phone"),
                    email=c.get("email"),
                    organization=c.get("organization"),
                    title=c.get("title"),
                    notes=c.get("notes"),
                )
                created.append(res)
            except Exception as exc:
                logger.error(f"[ContactsAgent] Ошибка импорта контакта {c}: {exc}")
                errors.append({"contact": c, "error": str(exc)})

        return {
            "status": "success" if not errors else "partial",
            "imported_count": len(created),
            "errors_count": len(errors),
            "created": created,
            "errors": errors,
        }
