# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Calendar Skill - Core Client Module
# =============================================================================
# Description:
#   Базовый клиент для взаимодействия с Google Calendar API v3 через OAuth 2.0.
#   Предоставляет методы для получения расписания, событий, создания встреч
#   и удаления записей из календаря.
#
# File: calendar_client.py
# Package: .agents.skills.google-calendar.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 21:06:00
# =============================================================================

from __future__ import annotations

"""Модуль клиента Google Calendar API для навыка google-calendar."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import header  # noqa: F401
from googleapiclient.discovery import build
from logger import logger
from src.ai.google_accounts_state import get_account_info, load_account_credentials


class GoogleCalendarClient:
    """Клиент для выполнения операций с Google Calendar API."""

    def __init__(self, account_name: Optional[str] = None) -> None:
        """Инициализирует клиент Календаря.

        Args:
            account_name: Имя аккаунта Google из настроенного пула.
        """
        self._account_name = account_name or self._resolve_default_account()
        self._service: Optional[Any] = None

    def _resolve_default_account(self) -> str:
        """Определяет активный аккаунт по умолчанию."""
        info = get_account_info()
        return info.get("name", "davidka") if info else "davidka"

    def get_service(self) -> Any:
        """Возвращает экземпляр сервиса Google Calendar API.

        Raises:
            RuntimeError: При отсутствии авторизационных данных.
        """
        if self._service is not None:
            return self._service

        creds = load_account_credentials(self._account_name)
        if not creds:
            raise RuntimeError(
                f"Не удалось получить авторизационные данные для аккаунта '{self._account_name}'. "
                "Проверьте наличие токена или выполните авторизацию через /auth/google."
            )

        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def list_calendars(self) -> List[Dict[str, Any]]:
        """Возвращает список доступных пользователю календарей.

        Returns:
            Список словарей с данными календарей (id, summary, timeZone, primary).
        """
        service = self.get_service()
        res = service.calendarList().list().execute()
        items = res.get("items", [])
        return [
            {
                "id": c.get("id"),
                "summary": c.get("summary", ""),
                "time_zone": c.get("timeZone", ""),
                "primary": c.get("primary", False),
                "access_role": c.get("accessRole", ""),
            }
            for c in items
        ]

    def list_events(
        self,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        query: Optional[str] = None,
        max_results: int = 15,
    ) -> List[Dict[str, Any]]:
        """Возвращает список предстоящих событий календаря.

        Args:
            calendar_id: Идентификатор календаря (по умолчанию 'primary').
            time_min: Нижняя граница времени в ISO формате (по умолчанию текущий момент UTC).
            time_max: Верхняя граница времени в ISO формате.
            query: Текстовый поисковый фильтр по названию/описанию события.
            max_results: Максимальное количество возвращаемых событий.

        Returns:
            Список словарей с атрибутами событий (id, summary, start, end, location, link).
        """
        service = self.get_service()
        if not time_min:
            time_min = datetime.now(timezone.utc).isoformat()

        params: Dict[str, Any] = {
            "calendarId": calendar_id,
            "timeMin": time_min,
            "maxResults": min(max(1, max_results), 100),
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if time_max:
            params["timeMax"] = time_max
        if query:
            params["q"] = query

        res = service.events().list(**params).execute()
        items = res.get("items", [])

        events: List[Dict[str, Any]] = []
        for ev in items:
            start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
            end = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
            events.append({
                "id": ev.get("id"),
                "summary": ev.get("summary") or "—",
                "description": ev.get("description", ""),
                "start": start,
                "end": end,
                "location": ev.get("location", ""),
                "html_link": ev.get("htmlLink", ""),
                "attendees": [a.get("email") for a in ev.get("attendees", []) if a.get("email")],
            })
        return events

    def get_event(self, event_id: str, calendar_id: str = "primary") -> Dict[str, Any]:
        """Возвращает подробности события по ID.

        Args:
            event_id: Уникальный ID события.
            calendar_id: Идентификатор календаря.

        Returns:
            Словарь с полными данными события.
        """
        service = self.get_service()
        return service.events().get(calendarId=calendar_id, eventId=event_id).execute()

    def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
        attendees: Optional[List[str]] = None,
        calendar_id: str = "primary",
        send_updates: str = "all",
        reminders: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Создает новое событие в календаре с отправкой приглашений и настройкой напоминаний.

        Args:
            summary: Название / тема события.
            start_time: Время начала в ISO формате (например: '2026-11-20T06:00:00+02:00') или дата YYYY-MM-DD.
            end_time: Время окончания в ISO формате или дата YYYY-MM-DD.
            description: Описание события.
            location: Место проведения встречи.
            attendees: Список email участников.
            calendar_id: Идентификатор календаря (по умолчанию 'primary').
            send_updates: Кому отправлять email-приглашения ('all', 'externalOnly', 'none').
            reminders: Список напоминаний вида [{'method': 'email'|'popup', 'minutes': int}].

        Returns:
            Словарь созданного события с id и ссылкой html_link.
        """
        service = self.get_service()
        event_body: Dict[str, Any] = {
            "summary": summary,
            "description": description,
            "location": location,
        }

        # Определение типа даты (дата или дата-время)
        if "T" in start_time:
            event_body["start"] = {"dateTime": start_time}
            event_body["end"] = {"dateTime": end_time}
        else:
            event_body["start"] = {"date": start_time}
            event_body["end"] = {"date": end_time}

        if attendees:
            event_body["attendees"] = [{"email": email.strip()} for email in attendees if email.strip()]

        if reminders:
            event_body["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {"method": str(r.get("method") or "popup"), "minutes": int(r.get("minutes", 60))}
                    for r in reminders
                ],
            }

        created = (
            service.events()
            .insert(
                calendarId=calendar_id,
                body=event_body,
                sendUpdates=send_updates if attendees else "none",
            )
            .execute()
        )
        return {
            "status": "success",
            "id": created.get("id"),
            "summary": created.get("summary"),
            "html_link": created.get("htmlLink"),
            "start": created.get("start"),
            "end": created.get("end"),
            "attendees": [a.get("email") for a in created.get("attendees", []) if a.get("email")],
        }

    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        calendar_id: str = "primary",
        send_updates: str = "none",
    ) -> Dict[str, Any]:
        """Обновляет существующее событие в календаре (PATCH)."""
        service = self.get_service()
        patch_body: Dict[str, Any] = {}
        if summary is not None:
            patch_body["summary"] = summary
        if description is not None:
            patch_body["description"] = description
        if location is not None:
            patch_body["location"] = location
        updated = (
            service.events()
            .patch(calendarId=calendar_id, eventId=event_id, body=patch_body, sendUpdates=send_updates)
            .execute()
        )
        return {
            "status": "success",
            "id": updated.get("id"),
            "summary": updated.get("summary"),
            "description": updated.get("description"),
            "html_link": updated.get("htmlLink"),
        }

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> Dict[str, Any]:
        """Удаляет событие из календаря.

        Args:
            event_id: Идентификатор удаляемого события.
            calendar_id: Идентификатор календаря.

        Returns:
            Словарь со статусом выполнения.
        """
        service = self.get_service()
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return {"status": "success", "id": event_id, "deleted": True}
