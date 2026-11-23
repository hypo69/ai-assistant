# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Google OAuth & Auth Router Tests
# =============================================================================
# Description:
#   Модульные тесты проверки маршрутов Google OAuth 2.0 авторизации,
#   проверки профиля (/api/v1/auth/check), страницы входа (/auth/google)
#   и управления пулом аккаунтов Google Workspace.
#
# Usage Examples:
#   pytest tests/test_ai_assistant_auth.py -v
#
# File: test_ai_assistant_auth.py
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 02:18:00
# =============================================================================

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.ai_assistant.main import app
from src.ai.google_accounts_state import resolve_project_path


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Создает тестовый клиент автономного приложения AI Assistant."""
    return TestClient(app)


def test_auth_check_endpoint(client: TestClient) -> None:
    """Проверяет эндпоинт проверки статуса авторизации /api/v1/auth/check."""
    resp = client.get("/api/v1/auth/check")
    assert resp.status_code == 200
    data = resp.json()
    assert "authenticated" in data
    assert "email" in data
    assert "name" in data
    assert "has_google" in data
    assert "accounts" in data
    assert isinstance(data["accounts"], list)


def test_auth_google_page_endpoint(client: TestClient) -> None:
    """Проверяет отдачу страницы авторизации Google OAuth /auth/google."""
    resp = client.get("/auth/google?next=/ai_assistant")
    assert resp.status_code == 200
    assert "Google OAuth Авторизация" in resp.text
    assert "btn-trigger-oauth" in resp.text

    resp_v1 = client.get("/api/v1/auth/google?next=/ai_assistant")
    assert resp_v1.status_code == 200
    assert "Google OAuth Авторизация" in resp_v1.text


def test_auth_logout_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Проверяет эндпоинт завершения сессии /api/v1/auth/logout без удаления реального токена."""
    fake_token = tmp_path / "fake_token.json"
    fake_token.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "apps.ai_assistant.api.routers.router_auth.list_google_accounts",
        lambda: [{"name": "fake", "token_file": str(fake_token)}],
    )
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert not fake_token.exists()


def test_resolve_project_path_normalizes_windows_separators() -> None:
    """Проверяет нормализацию Windows-разделителей пути для совместимости с Linux/Docker."""
    resolved = resolve_project_path(r"src\secrets\google_oauth_tokens\davidka_token.json")
    assert "\\" not in resolved.as_posix()
    assert resolved.as_posix().endswith("src/secrets/google_oauth_tokens/davidka_token.json")


def test_google_login_returns_web_oauth_redirect(client: TestClient) -> None:
    """Проверяет генерацию OAuth 2.0 URL с серверным callback вместо блокирующего run_local_server."""
    resp = client.post("/api/v1/auth/google/login?next=/ai_assistant")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "redirect"
    auth_url = data.get("auth_url", "")
    assert auth_url.startswith("https://accounts.google.com/o/oauth2/auth")
    assert "auth%2Fgoogle%2Fcallback" in auth_url


def test_google_callback_handles_error_and_invalid_state(client: TestClient) -> None:
    """Проверяет безопасную обработку отмены авторизации и просроченного state на /auth/google/callback."""
    resp_err = client.get("/auth/google/callback?error=access_denied")
    assert resp_err.status_code == 400
    assert "access_denied" in resp_err.text

    resp_bad_state = client.get("/auth/google/callback?code=abc&state=invalid_state_xyz")
    assert resp_bad_state.status_code == 400
    assert "истекла" in resp_bad_state.text


def test_google_accounts_list_endpoint(client: TestClient) -> None:
    """Проверяет получение списка Google аккаунтов /api/v1/auth/google-accounts."""
    resp = client.get("/api/v1/auth/google-accounts")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert "accounts" in data
    assert isinstance(data["accounts"], list)


def test_google_account_test_endpoint(client: TestClient) -> None:
    """Проверяет эндпоинт тестирования токена Google аккаунта."""
    resp = client.post("/api/v1/auth/google-accounts/davidka/test")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "name" in data
    assert data["name"] == "davidka"
