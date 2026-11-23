# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Contacts Skill - Export Contacts CLI
# =============================================================================
# Description:
#   Консольная утилита для экспорта контактов из Google Contacts в форматы
#   CSV или JSON (по умолчанию assets/contacts.csv).
#
# File: export_contacts.py
# Package: .agents.skills.google-contacts.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:05:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт для экспорта контактов в CSV или JSON."""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from contacts_client import GoogleContactsClient  # noqa: E402
from logger import logger  # noqa: E402

CSV_HEADERS = [
    "display_name",
    "given_name",
    "family_name",
    "phone",
    "email",
    "organization",
    "title",
    "notes",
    "resource_name",
]


def export_to_csv(contacts: List[Dict[str, Any]], file_path: Path) -> None:
    """Записывает список контактов в CSV с кодировкой utf-8-sig."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for c in contacts:
        phones = c.get("phones", [])
        phone_val = phones[0].get("value", "") if phones else ""
        emails = c.get("emails", [])
        email_val = emails[0].get("value", "") if emails else ""
        orgs = c.get("organizations", [])
        org_val = orgs[0].get("name", "") if orgs else ""
        title_val = orgs[0].get("title", "") if orgs else ""

        rows.append(
            {
                "display_name": c.get("display_name", ""),
                "given_name": c.get("given_name", ""),
                "family_name": c.get("family_name", ""),
                "phone": phone_val,
                "email": email_val,
                "organization": org_val,
                "title": title_val,
                "notes": c.get("notes", ""),
                "resource_name": c.get("resource_name", ""),
            }
        )

    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def export_to_json(contacts: List[Dict[str, Any]], file_path: Path) -> None:
    """Записывает список контактов в JSON."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(contacts, f, ensure_ascii=False, indent=2)


def main() -> None:
    """Точка входа CLI для экспорта контактов."""
    parser = argparse.ArgumentParser(description="Экспорт контактов Google в CSV или JSON.")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=str(_PROJECT_ROOT / "assets" / "contacts.csv"),
        help="Путь к файлу назначения (по умолчанию assets/contacts.csv)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["csv", "json"],
        default=None,
        help="Формат экспорта (csv или json, по умолчанию определяется по расширению)",
    )
    parser.add_argument(
        "-q",
        "--query",
        type=str,
        default=None,
        help="Поисковый фильтр (по умолчанию экспортируются все)",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=500,
        help="Максимальное количество контактов (по умолчанию 500)",
    )
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод статуса строго в JSON")

    args = parser.parse_args()
    out_path = Path(args.output).resolve()
    fmt = args.format or (out_path.suffix.lstrip(".").lower() if out_path.suffix else "csv")
    if fmt not in ("csv", "json"):
        fmt = "csv"

    try:
        client = GoogleContactsClient(account_name=args.account)
        contacts = client.list_contacts(query=args.query, max_results=args.limit)

        if fmt == "json":
            export_to_json(contacts, out_path)
        else:
            export_to_csv(contacts, out_path)

        res = {
            "status": "success",
            "count": len(contacts),
            "output_path": str(out_path),
            "format": fmt,
        }

        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            logger.console(f"Успешно экспортировано контактов: {len(contacts)} в файл '{out_path}'.")

    except Exception as ex:
        err_res = {"status": "error", "message": str(ex)}
        if args.json:
            print(json.dumps(err_res, ensure_ascii=False))
        else:
            logger.console(f"Ошибка при экспорте контактов: {ex}")
        sys.exit(1)


if __name__ == "__main__":
    main()
