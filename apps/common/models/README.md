# Общий модуль управления моделями ИИ (`apps/common/models`)

## Назначение
Модуль `apps/common/models` предоставляет общесистемную бизнес-логику и REST API маршруты для управления моделями ИИ, провайдерами (Google Gemini, Microsoft AI Foundry Local, Ollama, Google Antigravity, ONNX / DirectML, браузерный BERT), пулом API-ключей, системными инструкциями и интерактивным тестированием на уровне приложений платформы.

---

## Архитектура компонента

```
apps/common/models/
├── __init__.py          # Экспорт роутера, сервиса и ключевых функций
├── models.py            # Pydantic-схемы запросов и ответов
├── service.py           # Сервисный слой работы с конфигурацией, провайдерами и тестированием
├── router.py            # FastAPI маршрутизатор эндпоинтов /api/v1/chat/*, /auth/*, /api/*
└── README.md            # Документация модуля
```

---

## Поддерживаемые эндпоинты

- **Каталог и активная модель**:
  - `GET /api/v1/chat/models` — сгруппированный каталог доступных моделей по провайдерам.
  - `GET /api/v1/chat/active-model`, `GET /api/v1/tc/model` — текущая активная модель.
  - `POST /api/v1/chat/model`, `POST /api/v1/tc/model` — выбор и сохранение активной модели.
- **Пользовательские настройки и избранное**:
  - `GET/POST /auth/settings`, `GET/POST /api/v1/auth/settings` — настройки профиля пользователя.
  - `GET /auth/favorites` — список избранных моделей с заметками.
  - `POST /auth/favorites/{model_name}` — добавление в избранное.
  - `DELETE /auth/favorites/{model_name}` — удаление из избранного.
- **Интерактивное тестирование**:
  - `POST /api/v1/chat/test-model` — прямой проверочный запрос к модели с замером задержки.
- **Системные инструкции**:
  - `GET/POST /api/v1/tc/model-instruction`
  - `GET/POST /api/v1/chat/model-instruction`
  - `GET/POST /api/admin/system_instruction`
- **Конфигурация провайдеров**:
  - `/api/foundry/config` (Microsoft AI Foundry Local)
  - `/api/ollama/config` (Локальный сервер Ollama)
  - `/api/agy/config` (Google Antigravity)
  - `/api/onnx/config` (ONNX / DirectML)
  - `/api/local-bert/catalog`, `/api/local-bert/config` (Браузерный BERT)
  - `GET /api/v1/models/summary` — общая сводка доступности провайдеров.

---

## Разработчик
- **Автор**: hypo69
- **Обновлено**: 2026-11-16 01:15:00
