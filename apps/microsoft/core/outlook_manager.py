# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Microsoft Office & 365 App - Outlook Manager
# =============================================================================
# Description:
#   Сервис управления почтой Outlook (Microsoft 365, Exchange и IMAP/SMTP).
#   Обеспечивает чтение списка писем, отправку сообщений и статус подключения
#   на основе настроек из mailboxes.json или .agents/skills/smtp-mail-agent.
#
# File: outlook_manager.py
# Package: apps.microsoft.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:00:00
# =============================================================================

from __future__ import annotations

"""Сервис работы с почтой Outlook в экосистеме Microsoft 365."""

import email
from email.header import decode_header
import imaplib
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional

from header import __root__
from logger import logger


def _decode_mime_words(raw_header: Optional[str]) -> str:
    """Декодирует MIME заголовки темы и отправителя в читаемый текст."""
    if not raw_header:
        return ""
    decoded_fragments = []
    for fragment, charset in decode_header(raw_header):
        if isinstance(fragment, bytes):
            try:
                decoded_fragments.append(fragment.decode(charset or "utf-8", errors="replace"))
            except Exception:
                decoded_fragments.append(fragment.decode("utf-8", errors="replace"))
        else:
            decoded_fragments.append(str(fragment))
    return " ".join(decoded_fragments)


class OutlookManager:
    """Менеджер для выполнения операций с ящиками Outlook / Microsoft 365."""

    def __init__(self) -> None:
        """Инициализация менеджера Outlook."""
        self._lock = threading.RLock()
        self._config_cache: Optional[Dict[str, Any]] = None

    def get_config(self) -> Dict[str, Any]:
        """Загружает реквизиты Outlook из mailboxes.json или secrets.json."""
        with self._lock:
            # 1. Проверяем src/secrets/mailboxes.json
            mailboxes_file = __root__ / "src" / "secrets" / "mailboxes.json"
            if mailboxes_file.is_file():
                try:
                    data = json.loads(mailboxes_file.read_text(encoding="utf-8"))
                    # Ищем ящик с ключом outlook или алиасом
                    for key, box in data.items():
                        if key.lower() in ("outlook", "work", "office365", "microsoft"):
                            return box
                        aliases = box.get("aliases", [])
                        if any(a in ("outlook", "аутлук", "работа") for a in aliases):
                            return box
                except Exception as exc:
                    logger.warning(f"[OutlookManager] Ошибка чтения mailboxes.json: {exc}")

            # 2. Проверяем secrets.json навыка smtp-mail-agent
            smtp_secrets = __root__ / ".agents" / "skills" / "smtp-mail-agent" / "secrets.json"
            if smtp_secrets.is_file():
                try:
                    data = json.loads(smtp_secrets.read_text(encoding="utf-8"))
                    smtp = data.get("smtp", data)
                    return {
                        "imap_host": "outlook.office365.com",
                        "imap_port": 993,
                        "smtp_host": smtp.get("host", "smtp.office365.com"),
                        "smtp_port": int(smtp.get("port", 587)),
                        "username": smtp.get("username", ""),
                        "password": smtp.get("password", ""),
                        "from_name": smtp.get("from_name", "AI Assistant"),
                    }
                except Exception as exc:
                    logger.warning(f"[OutlookManager] Ошибка чтения secrets.json навыка: {exc}")

            return {
                "imap_host": "outlook.office365.com",
                "imap_port": 993,
                "smtp_host": "smtp.office365.com",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "configured": False,
            }

    def get_status(self) -> Dict[str, Any]:
        """Возвращает текущий статус настройки и подключения Outlook."""
        cfg = self.get_config()
        configured = bool(cfg.get("username") and cfg.get("password"))
        return {
            "configured": configured,
            "provider": "Microsoft Outlook / Office 365",
            "account": cfg.get("username", ""),
            "imap_host": cfg.get("imap_host", "outlook.office365.com"),
            "smtp_host": cfg.get("smtp_host", "smtp.office365.com"),
        }

    def list_messages(self, limit: int = 10, folder: str = "INBOX") -> List[Dict[str, Any]]:
        """Получает список последних писем по IMAP."""
        cfg = self.get_config()
        if not cfg.get("username") or not cfg.get("password"):
            return []

        messages: List[Dict[str, Any]] = []
        try:
            with imaplib.IMAP4_SSL(cfg.get("imap_host", "outlook.office365.com"), int(cfg.get("imap_port", 993))) as client:
                client.login(cfg["username"], cfg["password"])
                client.select(folder, readonly=True)

                status, data = client.search(None, "ALL")
                if status != "OK" or not data or not data[0]:
                    return []

                id_list = data[0].split()
                selected_ids = id_list[-limit:]
                selected_ids.reverse()

                for msg_id in selected_ids:
                    res, msg_data = client.fetch(msg_id, "(RFC822.HEADER)")
                    if res != "OK":
                        continue
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    messages.append({
                        "id": msg_id.decode("utf-8", errors="ignore"),
                        "subject": _decode_mime_words(msg.get("Subject")),
                        "from": _decode_mime_words(msg.get("From")),
                        "date": msg.get("Date", ""),
                    })
        except Exception as exc:
            logger.error(f"[OutlookManager] Ошибка выборки писем Outlook: {exc}")
        return messages

    def send_message(self, to: str, subject: str, body: str, is_html: bool = False) -> Dict[str, Any]:
        """Отправляет письмо через SMTP сервер Outlook."""
        cfg = self.get_config()
        if not cfg.get("username") or not cfg.get("password"):
            raise ValueError("Учетная запись Outlook не настроена. Укажите логин и пароль в настройках.")

        msg = MIMEMultipart("alternative")
        msg["From"] = cfg.get("username")
        msg["To"] = to
        msg["Subject"] = subject

        mime_part = MIMEText(body, "html" if is_html else "plain", "utf-8")
        msg.attach(mime_part)

        try:
            with smtplib.SMTP(cfg.get("smtp_host", "smtp.office365.com"), int(cfg.get("smtp_port", 587)), timeout=30) as server:
                server.starttls()
                server.login(cfg["username"], cfg["password"])
                server.sendmail(cfg["username"], [to], msg.as_string())
            return {"status": "ok", "message": f"Письмо успешно отправлено на {to}"}
        except Exception as exc:
            logger.error(f"[OutlookManager] Ошибка отправки письма через Outlook: {exc}")
            raise RuntimeError(f"Ошибка SMTP Outlook: {exc}")


outlook_manager = OutlookManager()
