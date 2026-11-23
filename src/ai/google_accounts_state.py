# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Google Accounts State Module
# =============================================================================
# Description:
#   Ensure secrets and tokens directories exist.
#
# Usage Examples:
#   Python API:
#     from src.ai.google_accounts_state import list_google_accounts
#
#     res = list_google_accounts()
#     print(res)
#
# File: google_accounts_state.py
# Project: ai-windows-admin
# Package: src.ai
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 02:16:00
# =============================================================================

from __future__ import annotations
"""Управление пулом аккаунтов Google OAuth / Service Account и состоянием квот."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
from header import __root__
from logger import logger
_SECRETS_DIR: Path = __root__ / 'src' / 'secrets'
_OAUTH_FILES_DIR: Path = _SECRETS_DIR / 'google_ouath_files'
_TOKENS_DIR: Path = _SECRETS_DIR / 'google_oauth_tokens'
_ACCOUNTS_FILE: Path = _SECRETS_DIR / 'google_accounts.json'
_DAY_SECONDS: float = 86400.0
_STATE_LOCK = threading.RLock()
DEFAULT_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/contacts',
    'https://www.googleapis.com/auth/contacts.readonly',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/documents',
]

def resolve_project_path(raw_path: Any) -> Path:
    """Нормализует путь с Windows/POSIX-разделителями и разрешает его относительно корня проекта.

    Args:
        raw_path (Any): Относительный или абсолютный путь строкой или объектом Path.

    Returns:
        Path: Кроссплатформенный объект Path, корректно работающий на Windows и в Linux/Docker.
    """
    normalized = str(raw_path or "").strip().replace("\\", "/")
    p = Path(normalized)
    if p.is_absolute():
        return p
    return __root__ / p


def _to_rel_posix(path: Path) -> str:
    """Преобразует путь в относительный POSIX-формат с прямыми слешами '/'."""
    try:
        return path.resolve().relative_to(__root__.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _ensure_dirs() -> None:
    """Ensure secrets and tokens directories exist."""
    try:
        _SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        _OAUTH_FILES_DIR.mkdir(parents=True, exist_ok=True)
        _TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as ex:
        logger.error(f'Failed to create Google accounts directories: {ex}')

def _now_iso() -> str:
    """Get current UTC ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()

def _now_ts() -> float:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc).timestamp()

def _iso_to_ts(iso_str: str) -> float:
    """Convert ISO string to timestamp."""
    if not iso_str:
        return 0.0
    try:
        cleaned = iso_str.replace('Z', '+00:00')
        return datetime.fromisoformat(cleaned).timestamp()
    except Exception:
        return 0.0

def _load_accounts_data() -> Dict[str, Any]:
    """Load accounts metadata from google_accounts.json.

    Returns:
        Dict[str, Any]: Structure with 'default_account' and 'accounts' mapping.
    """
    _ensure_dirs()
    if _ACCOUNTS_FILE.exists():
        try:
            content = _ACCOUNTS_FILE.read_text(encoding='utf-8').strip()
            if content:
                data = json.loads(content)
                if isinstance(data, dict):
                    if 'accounts' not in data:
                        data = {'default_account': '', 'accounts': data}
                    return data
        except Exception as ex:
            logger.warning(f'Error reading {_ACCOUNTS_FILE}: {ex}')
    bootstrapped = _bootstrap_from_existing_files()
    if bootstrapped.get('accounts'):
        _save_accounts_data(bootstrapped)
        return bootstrapped
    return {'default_account': '', 'accounts': {}}

def _bootstrap_from_existing_files() -> Dict[str, Any]:
    """Discover existing credentials in google_ouath_files, google_oauth_tokens, src/secrets, or root."""
    accounts: Dict[str, Any] = {}
    if _OAUTH_FILES_DIR.exists():
        for f in _OAUTH_FILES_DIR.glob('*.json'):
            if f.name == 'gemini_keys.json':
                continue
            acc_name = f.stem.removesuffix('_secret').removesuffix('_credentials')
            if not acc_name:
                acc_name = f.stem
            token_cand = _TOKENS_DIR / f'{acc_name}_token.json'
            accounts[acc_name] = {'name': acc_name, 'email': '', 'type': 'oauth2', 'credentials_file': _to_rel_posix(f), 'token_file': _to_rel_posix(token_cand), 'status': 'active', 'last_run': '', 'exhausted_at': ''}
    if _TOKENS_DIR.exists():
        for f in _TOKENS_DIR.glob('*_token.json'):
            acc_name = f.stem.removesuffix('_token')
            if acc_name not in accounts:
                secret_cand = _OAUTH_FILES_DIR / f'{acc_name}_secret.json'
                accounts[acc_name] = {'name': acc_name, 'email': '', 'type': 'oauth2', 'credentials_file': _to_rel_posix(secret_cand), 'token_file': _to_rel_posix(f), 'status': 'active', 'last_run': '', 'exhausted_at': ''}
    candidates = [(_SECRETS_DIR / 'credentials.json', 'oauth2'), (_SECRETS_DIR / 'service_account.json', 'service_account'), (__root__ / 'credentials.json', 'oauth2'), (__root__ / 'service_account.json', 'service_account')]
    for cand_path, acc_type in candidates:
        if cand_path.exists():
            acc_name = 'default' if 'default' not in accounts else cand_path.stem
            if acc_name not in accounts:
                accounts[acc_name] = {'name': acc_name, 'email': '', 'type': acc_type, 'credentials_file': _to_rel_posix(cand_path), 'token_file': _to_rel_posix(_TOKENS_DIR / f'{acc_name}_token.json'), 'status': 'active', 'last_run': '', 'exhausted_at': ''}
    default_name = next(iter(accounts.keys()), '')
    return {'default_account': default_name, 'accounts': accounts}

def _save_accounts_data(data: Dict[str, Any]) -> bool:
    """Атомарно сохраняет словарь аккаунтов Google в JSON-файл."""
    with _STATE_LOCK:
        try:
            _ensure_dirs()
            tmp_path = _ACCOUNTS_FILE.with_suffix('.json.tmp')
            tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
            os.replace(tmp_path, _ACCOUNTS_FILE)
            return True
        except Exception as ex:
            logger.error(f'Failed to save Google accounts data to {_ACCOUNTS_FILE}: {ex}')
            return False

def list_google_accounts(skip_exhausted: bool=False) -> List[Dict[str, Any]]:
    """List all configured Google Workspace accounts in pool.

    Args:
        skip_exhausted: Whether to filter out accounts with active quota exhaustion.

    Returns:
        List[Dict[str, Any]]: Account descriptor list.
    """
    data = _load_accounts_data()
    accounts = data.get('accounts', {})
    default_acc = data.get('default_account', '')
    now = _now_ts()
    result = []
    updates_needed = False
    for acc_name, acc_info in accounts.items():
        status = acc_info.get('status', 'active')
        exhausted_at = acc_info.get('exhausted_at', '')
        if status == 'exhausted' or exhausted_at:
            ref_ts = _iso_to_ts(exhausted_at)
            if ref_ts > 0 and now - ref_ts >= _DAY_SECONDS:
                acc_info['status'] = 'active'
                acc_info['exhausted_at'] = ''
                status = 'active'
                updates_needed = True
        if skip_exhausted and status == 'exhausted':
            continue
        item = dict(acc_info)
        item['name'] = acc_name
        item['is_default'] = acc_name == default_acc
        result.append(item)
    if updates_needed:
        _save_accounts_data(data)
    return result

def get_account_info(account_name: Optional[str]=None) -> Optional[Dict[str, Any]]:
    """Get metadata for a specific or default Google account."""
    data = _load_accounts_data()
    accounts = data.get('accounts', {})
    target = account_name or data.get('default_account', '')
    if target and target in accounts:
        info = dict(accounts[target])
        info['name'] = target
        return info
    if accounts:
        first_k = next(iter(accounts.keys()))
        info = dict(accounts[first_k])
        info['name'] = first_k
        return info
    '# TODO: вернуть корректное значение'
    logger.error('Функция get_account_info вернула пустой результат')
    return None

def save_google_account(account_name: str, credentials_path_or_dict: Any, account_type: str='oauth2', email: str='', set_as_default: bool=False) -> bool:
    """Add or update a Google Workspace account in pool.

    Args:
        account_name: Unique identifier for account (e.g. 'work', 'personal').
        credentials_path_or_dict: Path to client_secrets / service_account file, or dict.
        account_type: 'oauth2' or 'service_account'.
        email: Associated email address.
        set_as_default: Whether to mark this account as the default.

    Returns:
        bool: True on success.
    """
    _ensure_dirs()
    clean_name = Path(account_name.strip()).name
    if not clean_name or clean_name in ('.', '..'):
        return False
    with _STATE_LOCK:
        data = _load_accounts_data()
        accounts = data.setdefault('accounts', {})
        creds_filename = f'{clean_name}_secret.json'
        dest_file = (_OAUTH_FILES_DIR / creds_filename).resolve()
        dest_file.relative_to(_OAUTH_FILES_DIR.resolve())
        if isinstance(credentials_path_or_dict, dict):
            tmp_dest = dest_file.with_suffix('.json.tmp')
            tmp_dest.write_text(json.dumps(credentials_path_or_dict, indent=2, ensure_ascii=False), encoding='utf-8')
            os.replace(tmp_dest, dest_file)
        elif isinstance(credentials_path_or_dict, (str, Path)):
            src_path = resolve_project_path(credentials_path_or_dict)
            if src_path.exists() and src_path.resolve() != dest_file:
                tmp_dest = dest_file.with_suffix('.json.tmp')
                tmp_dest.write_bytes(src_path.read_bytes())
                os.replace(tmp_dest, dest_file)
            elif not src_path.exists():
                logger.error(f'Credentials source file does not exist: {src_path}')
                return False
        token_filename = f'{clean_name}_token.json'
        token_file = _TOKENS_DIR / token_filename
        creds_rel_path = _to_rel_posix(dest_file)
        token_rel_path = _to_rel_posix(token_file)
        accounts[clean_name] = {'name': clean_name, 'email': email or accounts.get(clean_name, {}).get('email', ''), 'type': account_type, 'credentials_file': creds_rel_path, 'token_file': token_rel_path, 'status': 'active', 'last_run': '', 'exhausted_at': ''}
        if set_as_default or not data.get('default_account'):
            data['default_account'] = clean_name
        return _save_accounts_data(data)

def delete_google_account(account_name: str) -> bool:
    """Remove a Google account from the pool."""
    data = _load_accounts_data()
    accounts = data.get('accounts', {})
    if account_name not in accounts:
        return False
    deleted = accounts.pop(account_name)
    if data.get('default_account') == account_name:
        data['default_account'] = next(iter(accounts.keys()), '')
    token_str = deleted.get('token_file', '')
    if token_str:
        token_file = resolve_project_path(token_str)
        if token_file.exists():
            try:
                token_file.unlink()
            except Exception as e:
                logger.warning(f'Could not delete token file {token_file}: {e}')
    return _save_accounts_data(data)

def set_default_account(account_name: str) -> bool:
    """Set specified account as default for pool."""
    data = _load_accounts_data()
    accounts = data.get('accounts', {})
    if account_name not in accounts:
        return False
    data['default_account'] = account_name
    return _save_accounts_data(data)

def mark_account_exhausted(account_name: str) -> None:
    """Mark an account as quota-exhausted and rotate."""
    data = _load_accounts_data()
    accounts = data.get('accounts', {})
    if account_name in accounts:
        accounts[account_name]['status'] = 'exhausted'
        accounts[account_name]['exhausted_at'] = _now_iso()
        _save_accounts_data(data)
        logger.warning(f'Google account "{account_name}" marked as quota-exhausted.')

def reset_account_status(account_name: str) -> bool:
    """Reset quota status for an account."""
    data = _load_accounts_data()
    accounts = data.get('accounts', {})
    if account_name in accounts:
        accounts[account_name]['status'] = 'active'
        accounts[account_name]['exhausted_at'] = ''
        return _save_accounts_data(data)
    return False

def save_account_credentials(account_name: str, creds: Any) -> Dict[str, Any]:
    """Атомарно сохраняет OAuth-токен на диск и синхронизирует профиль пользователя в google_accounts.json и users.db.

    Args:
        account_name (str): Имя аккаунта в пуле Google.
        creds (Any): Объект учетных данных Google OAuth 2.0 (Credentials).

    Returns:
        Dict[str, Any]: Извлеченный профиль пользователя (email, name, picture).
    """
    acc_info = get_account_info(account_name)
    name = (acc_info or {}).get("name") or account_name or "default"
    token_rel = (acc_info or {}).get("token_file", "")
    token_path = resolve_project_path(token_rel) if token_rel else (_TOKENS_DIR / f"{name}_token.json")

    try:
        token_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_tok = token_path.with_suffix(".json.tmp")
        tmp_tok.write_text(creds.to_json(), encoding="utf-8")
        os.replace(tmp_tok, token_path)
        logger.info(f"Сохранен OAuth токен для аккаунта '{name}' в {token_path}")
    except Exception as exc:
        logger.error(f"Ошибка сохранения файла токена для '{name}': {exc}")
        raise

    prof = fetch_user_profile_from_google(creds)
    with _STATE_LOCK:
        data = _load_accounts_data()
        if name in data.get("accounts", {}):
            acc_entry = data["accounts"][name]
            acc_entry["last_run"] = _now_iso()
            acc_entry["token_file"] = _to_rel_posix(token_path)
            if acc_entry.get("credentials_file"):
                acc_entry["credentials_file"] = _to_rel_posix(resolve_project_path(acc_entry["credentials_file"]))
            if prof.get("email"):
                acc_entry["email"] = prof["email"]
            _save_accounts_data(data)

    try:
        from apps.ai_assistant.core.users import user_service
        user_service.get_or_sync_active_user(
            username=name,
            email=prof.get("email") or (acc_info or {}).get("email", ""),
            picture=prof.get("picture", ""),
            full_name=prof.get("name", ""),
            has_google=True,
        )
    except Exception as exc:
        logger.warning(f"Не удалось синхронизировать профиль пользователя в users.db: {exc}")

    return prof


def load_account_credentials(account_name: Optional[str]=None, scopes: Optional[List[str]]=None):
    """Загружает и при необходимости обновляет Google Credentials для выбранного аккаунта.

    Args:
        account_name: Явное имя аккаунта в пуле (или аккаунт по умолчанию).
        scopes: Запрашиваемые OAuth-разрешения (scopes).

    Returns:
        Объект Google Credentials или None.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google.oauth2 import service_account
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        logger.error('Библиотеки Google Auth не установлены.')
        return None
    active_scopes = scopes or DEFAULT_SCOPES
    acc_info = get_account_info(account_name)
    if not acc_info:
        return None
    creds_rel = acc_info.get('credentials_file', '')
    token_rel = acc_info.get('token_file', '')
    acc_type = acc_info.get('type', 'oauth2')
    name = acc_info.get('name', 'default')
    creds_path = resolve_project_path(creds_rel) if creds_rel else None
    token_path = resolve_project_path(token_rel) if token_rel else (_TOKENS_DIR / f'{name}_token.json')
    if acc_type == 'service_account' and creds_path and creds_path.exists():
        try:
            return service_account.Credentials.from_service_account_file(str(creds_path), scopes=active_scopes)
        except Exception as e:
            logger.error(f'Не удалось загрузить Service Account для {name}: {e}')
            return None
    creds = None
    if token_path and token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), active_scopes)
        except Exception as e:
            logger.warning(f'Не удалось загрузить кешированный OAuth токен для {name}: {e}')
            creds = None
    refreshed_or_new = False
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info(f"Обновление истекшего OAuth токена для Google аккаунта '{name}'...")
                creds.refresh(Request())
                refreshed_or_new = True
            except Exception as e:
                logger.warning(f'Не удалось обновить токен для {name}: {e}')
                creds = None
        if not creds:
            if not creds_path or not creds_path.exists():
                logger.error(f"Файл credentials не найден для Google аккаунта '{name}' по пути {creds_path}.")
                return None
            if os.environ.get("AI_ASSISTANT_IN_DOCKER") == "1":
                logger.error(
                    f"Запуск локального браузера OAuth невозможен внутри Docker для '{name}'. "
                    "Пройдите авторизацию через WebGUI (/auth/google)."
                )
                return None
            try:
                logger.info(f"Запуск локального OAuth consent flow для аккаунта '{name}' ({creds_path})...")
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), active_scopes)
                creds = flow.run_local_server(port=0, timeout_seconds=180)
                refreshed_or_new = True
            except Exception as e:
                logger.error(f'Ошибка OAuth flow для {name}: {e}')
                return None
    if creds and refreshed_or_new:
        save_account_credentials(name, creds)
    return creds


def fetch_user_profile_from_google(creds: Any) -> Dict[str, Any]:
    """Извлекает информацию о профиле (email, name, picture) из Google учетных данных."""
    info: Dict[str, Any] = {"email": "", "name": "", "picture": ""}
    if not creds:
        return info

    id_token_jwt = getattr(creds, "id_token", None)
    if id_token_jwt and isinstance(id_token_jwt, str):
        try:
            import base64
            parts = id_token_jwt.split(".")
            if len(parts) >= 2:
                payload = parts[1]
                payload += "=" * ((4 - len(payload) % 4) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
                info["email"] = decoded.get("email") or info["email"]
                info["name"] = decoded.get("name") or info["name"]
                info["picture"] = decoded.get("picture") or info["picture"]
        except Exception:
            pass

    token = getattr(creds, "token", None)
    if token and not info.get("picture"):
        try:
            import requests
            resp = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
            if resp.status_code == 200:
                uinfo = resp.json()
                info["email"] = uinfo.get("email") or info["email"]
                info["name"] = uinfo.get("name") or info["name"]
                info["picture"] = uinfo.get("picture") or info["picture"]
        except Exception:
            pass

    return info
