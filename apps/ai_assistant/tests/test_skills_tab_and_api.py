# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Skills API Suite
# =============================================================================
# Description:
#   Модульные и интеграционные тесты для REST API управления навыками (/api/v1/skills).
#
# File: test_skills_tab_and_api.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 20:31:00
# =============================================================================

from __future__ import annotations

"""Тестирование REST API навыков и их конфигураций."""

import json
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from header import __root__
from apps.ai_assistant.main import app


@pytest.mark.asyncio
async def test_api_list_skills() -> None:
    """Проверяет эндпоинт GET /api/v1/skills."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/skills")
        assert res.status_code == 200
        skills = res.json()
        assert isinstance(skills, list)
        assert len(skills) > 0

        skill_ids = [s.get("id") for s in skills]
        assert "smtp-mail-agent" in skill_ids
        assert "cert-installer" in skill_ids

        smtp_skill = next(s for s in skills if s.get("id") == "smtp-mail-agent")
        assert smtp_skill["has_config"] is True


@pytest.mark.asyncio
async def test_api_skill_config_lifecycle() -> None:
    """Проверяет жизненный цикл чтения и обновления конфигурации навыка."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Чтение конфигурации
        res = await client.get("/api/v1/skills/smtp-mail-agent/config")
        assert res.status_code == 200
        data = res.json()
        assert data["skill"] == "smtp-mail-agent"
        assert "config" in data

        secrets_file = __root__ / ".agents" / "skills" / "smtp-mail-agent" / "secrets.json"
        original_content = secrets_file.read_text(encoding="utf-8") if secrets_file.is_file() else None

        try:
            test_payload = {
                "config": {
                    "smtp": {
                        "host": "smtp.office365.com",
                        "port": 587,
                        "use_tls": True,
                        "use_ssl": False,
                        "username": "test@outlook.com",
                        "password": "sample-password",
                        "from_email": "test@outlook.com",
                        "from_name": "Test Outlook User",
                        "timeout": 30
                    }
                }
            }
            save_res = await client.post("/api/v1/skills/smtp-mail-agent/config", json=test_payload)
            assert save_res.status_code == 200
            assert save_res.json()["status"] == "ok"

            # Проверяем повторным GET
            verify_res = await client.get("/api/v1/skills/smtp-mail-agent/config")
            assert verify_res.status_code == 200
            saved_data = verify_res.json()
            assert saved_data["is_template"] is False
            assert saved_data["config"]["smtp"]["host"] == "smtp.office365.com"
            assert saved_data["config"]["smtp"]["username"] == "test@outlook.com"
        finally:
            if original_content is not None:
                secrets_file.write_text(original_content, encoding="utf-8")
            elif secrets_file.is_file():
                secrets_file.unlink()
