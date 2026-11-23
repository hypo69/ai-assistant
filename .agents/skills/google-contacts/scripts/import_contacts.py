# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Contacts Skill - Import Contacts CLI
# =============================================================================
# Description:
#   Консольная утилита для импорта контактов из CSV или JSON файлов
#   в Google Contacts (People API).
#
# File: import_contacts.py
# Package: .agents.skills.google-contacts.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:05:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт для пакетного импорта контактов из CSV или JSON."""

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


def parse_csv_contacts(file_path: Path) -> List[Dict[str, Any]]:
    """Считывает контакты из CSV-файла (с поддержкой utf-8-sig)."""
    contacts = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            given = (row.get("given_name") or row.get("name") or row.get("display_name") or "").strip()
            family = (row.get("family_name") or "").strip()
            phone = (row.get("phone") or "").strip()
            email = (row.get("email") or "").strip()
            org = (row.get("organization") or row.get("org") or "").strip()
            title = (row.get("title") or "").strip()
            notes = (row.get("notes") or "").strip()

            if not given and not family:
                # Если имя не разделено, пробуем извлечь из display_name
                dname = (row.get("display_name") or "").strip()
                if dname:
                    parts = dname.split(maxsplit=1)
                    given = parts[0]
                    family = parts[1] if len(parts) > 1 else ""

            if not given and not family and not phone and not email:
                continue

            contacts.append(
                {
                    "given_name": given or "(Без имени)",
                    "family_name": family,
                    "phone": phone or None,
                    "email": email or None,
                    "organization": org or None,
                    "title": title or None,
                    "notes": notes or None,
                }
            )
    return contacts


def parse_json_contacts(file_path: Path) -> List[Dict[str, Any]]:
    """Считывает контакты из JSON-файла."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        raw_list = data.get("contacts") or data.get("items") or [data]
    elif isinstance(data, list):
        raw_list = data
    else:
        raw_list = []

    contacts = []
    for item in raw_list:
        given = (item.get("given_name") or item.get("name") or item.get("display_name") or "").strip()
        family = (item.get("family_name") or "").strip()

        # Извлечение телефона
        phone = None
        if "phones" in item and isinstance(item["phones"], list) and item["phones"]:
            phone = item["phones"][0].get("value")
        elif "phone" in item:
            phone = str(item["phone"])

        # Извлечение email
        email = None
        if "emails" in item and isinstance(item["emails"], list) and item["emails"]:
            email = item["emails"][0].get("value")
        elif "email" in item:
            email = str(item["email"])

        # Извлечение организации
        org = None
        title = None
        if "organizations" in item and isinstance(item["organizations"], list) and item["organizations"]:
            org = item["organizations"][0].get("name")
            title = item["organizations"][0].get("title")
        else:
            org = item.get("organization") or item.get("org")
            title = item.get("title")

        notes = item.get("notes")

        if not given and not family:
            dname = (item.get("display_name") or "").strip()
            if dname:
                parts = dname.split(maxsplit=1)
                given = parts[0]
                family = parts[1] if len(parts) > 1 else ""

        if not given and not family and not phone and not email:
            continue

        contacts.append(
            {
                "given_name": given or "(Без имени)",
                "family_name": family,
                "phone": phone,
                "email": email,
                "organization": org,
                "title": title,
                "notes": notes,
            }
        )
    return contacts


def main() -> None:
    """Точка входа CLI для импорта контактов."""
    parser = argparse.ArgumentParser(description="Импорт контактов в Google People API из CSV или JSON.")
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=str(_PROJECT_ROOT / "assets" / "contacts.csv"),
        help="Путь к входному файлу CSV/JSON (по умолчанию assets/contacts.csv)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["csv", "json"],
        default=None,
        help="Формат входного файла (по умолчанию определяется по расширению)",
    )
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--dry-run", action="store_true", help="Режим симуляции (только парсинг без отправки в API)")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в JSON")

    args = parser.parse_args()
    in_path = Path(args.input).resolve()
    if not in_path.exists():
        err_msg = f"Файл не найден: {in_path}"
        if args.json:
            print(json.dumps({"status": "error", "message": err_msg}, ensure_ascii=False))
        else:
            logger.console(f"Ошибка: {err_msg}")
        sys.exit(1)

    fmt = args.format or (in_path.suffix.lstrip(".").lower() if in_path.suffix else "csv")
    if fmt == "json":
        parsed = parse_json_contacts(in_path)
    else:
        parsed = parse_csv_contacts(in_path)

    if args.dry_run:
        res = {
            "status": "dry_run",
            "count": len(parsed),
            "input_file": str(in_path),
            "preview": parsed[:5],
        }
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            logger.console(f"[Dry Run] Распознано контактов: {len(parsed)}. Превью первых 5 записей: {parsed[:5]}")
        return

    client = GoogleContactsClient(account_name=args.account)
    created = []
    errors = []

    for item in parsed:
        try:
            c = client.create_contact(
                given_name=item["given_name"],
                family_name=item["family_name"],
                phone=item["phone"],
                email=item["email"],
                organization=item["organization"],
                title=item["title"],
                notes=item["notes"],
            )
            created.append(c)
        except Exception as ex:
            errors.append({"contact": item, "error": str(ex)})

    res = {
        "status": "success" if not errors else ("partial" if created else "error"),
        "total_parsed": len(parsed),
        "imported_count": len(created),
        "errors_count": len(errors),
        "errors": errors if errors else None,
    }

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        logger.console(
            f"Импорт завершён: успешно импортировано {len(created)} из {len(parsed)} контактов."
            + (f" Ошибок: {len(errors)}" if errors else "")
        )


if __name__ == "__main__":
    main()
