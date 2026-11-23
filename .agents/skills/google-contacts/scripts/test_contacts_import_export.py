# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Contacts Skill - Unit Tests
# =============================================================================
# Description:
#   Модульные тесты для утилит импорта и экспорта контактов (CSV / JSON).
#
# File: test_contacts_import_export.py
# Package: .agents.skills.google-contacts.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 21:05:00
# =============================================================================

from __future__ import annotations

import csv
import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from export_contacts import export_to_csv, export_to_json, CSV_HEADERS
from import_contacts import parse_csv_contacts, parse_json_contacts


@pytest.fixture
def sample_contacts():
    return [
        {
            "resource_name": "people/c111",
            "display_name": "דּוֹד משה",
            "given_name": "דּוֹד משה",
            "family_name": "",
            "phones": [{"value": "+972-50-1234567", "type": "mobile"}],
            "emails": [{"value": "dod.moshe@farm-israel.co.il", "type": "home"}],
            "organizations": [{"name": "חווה חקלאית נהלל", "title": "חקלאי ומגדל בקר"}],
            "notes": "דוד משה מהחווה בנהלל",
        },
        {
            "resource_name": "people/c222",
            "display_name": "שמוליק קיפוד",
            "given_name": "שמוליק",
            "family_name": "קיפוד",
            "phones": [{"value": "+972-52-9876543", "type": "mobile"}],
            "emails": [],
            "organizations": [],
            "notes": "מחפש תותים",
        },
    ]


def test_export_and_parse_csv(sample_contacts, tmp_path):
    csv_file = tmp_path / "test_contacts.csv"
    export_to_csv(sample_contacts, csv_file)

    assert csv_file.exists()
    parsed = parse_csv_contacts(csv_file)

    assert len(parsed) == 2
    assert parsed[0]["given_name"] == "דּוֹד משה"
    assert parsed[0]["phone"] == "+972-50-1234567"
    assert parsed[0]["email"] == "dod.moshe@farm-israel.co.il"
    assert parsed[0]["organization"] == "חווה חקלאית נהלל"
    assert parsed[0]["title"] == "חקלאי ומגדל בקר"
    assert parsed[0]["notes"] == "דוד משה מהחווה בנהלל"

    assert parsed[1]["given_name"] == "שמוליק"
    assert parsed[1]["family_name"] == "קיפוד"
    assert parsed[1]["phone"] == "+972-52-9876543"


def test_export_and_parse_json(sample_contacts, tmp_path):
    json_file = tmp_path / "test_contacts.json"
    export_to_json(sample_contacts, json_file)

    assert json_file.exists()
    parsed = parse_json_contacts(json_file)

    assert len(parsed) == 2
    assert parsed[0]["given_name"] == "דּוֹד משה"
    assert parsed[0]["phone"] == "+972-50-1234567"
    assert parsed[1]["given_name"] == "שמוליק"
