# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Contacts Skill - Update Contact CLI
# =============================================================================
# Description:
#   Консольная утилита для редактирования существующего контакта в Google Contacts.
#
# File: update_contact.py
# Package: .agents.skills.google-contacts.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 20:21:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт редактирования контакта в Google People API."""

import argparse
import json
import sys
from pathlib import Path

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from contacts_client import GoogleContactsClient  # noqa: E402
from logger import logger  # noqa: E402


def main() -> None:
    """Точка входа CLI для обновления контакта."""
    parser = argparse.ArgumentParser(description="Редактирование контакта в Google Contacts.")
    parser.add_argument("-r", "--resource-name", type=str, required=True, help="Идентификатор контакта вида people/c...")
    parser.add_argument("-n", "--name", type=str, default=None, help="Новое имя контакта")
    parser.add_argument("--family-name", type=str, default=None, help="Новая фамилия контакта")
    parser.add_argument("-p", "--phone", type=str, default=None, help="Новый номер телефона")
    parser.add_argument("-e", "--email", type=str, default=None, help="Новый email адрес")
    parser.add_argument("--org", type=str, default=None, help="Новая компания / организация")
    parser.add_argument("--title", type=str, default=None, help="Новая должность")
    parser.add_argument("--notes", type=str, default=None, help="Новые заметки")
    parser.add_argument("--etag", type=str, default=None, help="etag контакта (опционально)")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleContactsClient(account_name=args.account)
        res = client.update_contact(
            resource_name=args.resource_name,
            given_name=args.name,
            family_name=args.family_name,
            phone=args.phone,
            email=args.email,
            organization=args.org,
            title=args.title,
            notes=args.notes,
            etag=args.etag,
        )

        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            c = res.get("contact", {})
            logger.console(f"✅ Контакт успешно обновлен: {c.get('display_name')} ({args.resource_name})")
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            logger.error(f"❌ Ошибка обновления контакта: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
