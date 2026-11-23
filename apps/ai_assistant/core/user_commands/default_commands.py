# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant User Commands - Default Knowledge Base
# =============================================================================
# Description:
#   Предустановленная база знаний команд и сниппетов для системного администрирования,
#   разработки, работы с Git, Docker, сетью и Windows.
#
# File: default_commands.py
# Package: apps.ai_assistant.core.user_commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 01:20:00
# =============================================================================

from __future__ import annotations

"""Базовые команды для первичного наполнения базы знаний."""

from typing import Any, Dict, List

DEFAULT_USER_COMMANDS: List[Dict[str, Any]] = [
    {
        "command_id": "cmd_git_status_compact",
        "title": "Git: Краткий статус репозитория",
        "command": "git status -sb",
        "shell": "powershell",
        "category": "Git",
        "description": "Показывает компактный статус измененных и неотслеживаемых файлов в ветке.",
        "tags": ["#git", "#status", "#vcs"],
        "placeholders": {},
        "risk_level": "safe",
        "favorite": True,
    },
    {
        "command_id": "cmd_git_discard_unstaged",
        "title": "Git: Отменить все незакоммиченные изменения",
        "command": "git restore .",
        "shell": "powershell",
        "category": "Git",
        "description": "Откатывает все локальные правки в рабочей директории до состояния последнего коммита.",
        "tags": ["#git", "#restore", "#clean"],
        "placeholders": {},
        "risk_level": "warn",
        "favorite": False,
    },
    {
        "command_id": "cmd_git_log_graph",
        "title": "Git: Красивое дерево коммитов",
        "command": "git log --oneline --graph --decorate --all -n 20",
        "shell": "powershell",
        "category": "Git",
        "description": "Отображает последние 20 коммитов в виде ASCII-дерева ветвления.",
        "tags": ["#git", "#log", "#history"],
        "placeholders": {},
        "risk_level": "safe",
        "favorite": True,
    },
    {
        "command_id": "cmd_net_find_port_process",
        "title": "Сеть: Найти процесс, слушающий порт",
        "command": "Get-NetTCPConnection -LocalPort <PORT> | Select-Object LocalAddress, LocalPort, State, OwningProcess",
        "shell": "powershell",
        "category": "Сеть",
        "description": "Определяет PID процесса Windows, занимающего указанный сетевой порт.",
        "tags": ["#network", "#port", "#process", "#powershell"],
        "placeholders": {"<PORT>": "Номер порта (например, 8002 или 3000)"},
        "risk_level": "safe",
        "favorite": True,
    },
    {
        "command_id": "cmd_sys_kill_process_by_pid",
        "title": "Система: Принудительное завершение процесса по PID",
        "command": "Stop-Process -Id <PID> -Force",
        "shell": "powershell",
        "category": "Система",
        "description": "Принудительно останавливает зависший процесс по его идентификатору PID.",
        "tags": ["#process", "#kill", "#windows"],
        "placeholders": {"<PID>": "Идентификатор процесса (число)"},
        "risk_level": "warn",
        "favorite": False,
    },
    {
        "command_id": "cmd_sys_free_disk_space",
        "title": "Диск: Свободное место на всех дисках",
        "command": "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='FreeGB';E={[math]::Round($_.Free/1GB, 2)}}, @{N='UsedGB';E={[math]::Round($_.Used/1GB, 2)}}",
        "shell": "powershell",
        "category": "Система",
        "description": "Выводит таблицу дисков Windows со свободным и занятым объемом в гигабайтах.",
        "tags": ["#disk", "#storage", "#windows"],
        "placeholders": {},
        "risk_level": "safe",
        "favorite": True,
    },
    {
        "command_id": "cmd_docker_list_containers",
        "title": "Docker: Список активных контейнеров",
        "command": "docker ps --format 'table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}'",
        "shell": "powershell",
        "category": "Docker",
        "description": "Таблица всех работающих Docker-контейнеров с открытыми портами.",
        "tags": ["#docker", "#containers", "#devops"],
        "placeholders": {},
        "risk_level": "safe",
        "favorite": False,
    },
    {
        "command_id": "cmd_py_find_outdated_packages",
        "title": "Python: Проверка устаревших пакетов в venv",
        "command": "pip list --outdated --format=columns",
        "shell": "powershell",
        "category": "Python",
        "description": "Выводит список пакетов в текущем виртуальном окружении, для которых доступны обновления.",
        "tags": ["#python", "#pip", "#packages"],
        "placeholders": {},
        "risk_level": "safe",
        "favorite": True,
    },
    {
        "command_id": "cmd_win_flush_dns",
        "title": "Windows: Сброс кэша DNS",
        "command": "Clear-DnsClientCache; ipconfig /flushdns",
        "shell": "powershell",
        "category": "Сеть",
        "description": "Очищает локальный DNS-кэш операционной системы Windows.",
        "tags": ["#dns", "#network", "#cache"],
        "placeholders": {},
        "risk_level": "safe",
        "favorite": False,
    },
]
