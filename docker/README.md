<!-- Updated: 2026-11-19 23:22:00 -->
# Docker-инфраструктура AI-Assistant

Единый Docker Compose проект `ai-assistant`, объединяющий основной сервис **AI-Assistant** (WebGUI, REST API, RAG, WikiLLM, плагины) и полный стек **Paperless-ngx** (DMS) с проверками готовности (`healthcheck`), ротацией логов и общей сетью `ai-assistant-net`.

Каталог `paperless-ngx/` (локальная разработка) не изменяется и используется только как контекст сборки при подключении `docker-compose.build.yml`.

## Состав стека

| Сервис | Образ / Сборка | Порт на хосте | Назначение |
|---|---|---|---|
| `app` | `docker/Dockerfile` (`python:3.14-slim` + `git`, `ffmpeg`, `curl`, `sqlite3`) | `http://127.0.0.1:8090` (`APP_PORT`) | WebGUI и REST API ассистента (внутри `8002`, `/health`) |
| `webserver` | `ghcr.io/paperless-ngx/paperless-ngx:latest` | `http://127.0.0.1:8010` (`PAPERLESS_PORT`) | Система управления документами Paperless-ngx (внутри `8000`) |
| `db` | `postgres:18` | только внутри сети | База данных PostgreSQL для Paperless-ngx |
| `broker` | `valkey/valkey:9-alpine` | только внутри сети | Redis-совместимый брокер фоновых задач |
| `gotenberg` | `gotenberg/gotenberg:8.38` | только внутри сети | Конвертация офисных документов и HTML в PDF |
| `tika` | `apache/tika:3.3.1.0` | только внутри сети | Извлечение текста и метаданных из документов |

Внутри сети `ai-assistant-net` сервис `app` обращается к Paperless-ngx по `http://webserver:8000` (переменная `PAPERLESS_BASE_URL`). Для обращения к локальным LLM на хосте Windows (Ollama, Microsoft Foundry Local) проброшен хост `host.docker.internal`.

## Быстрый запуск

В корне репозитория расположен файл `docker-compose.yml` (подключающий `docker/docker-compose.yml`), поэтому команды можно выполнять **напрямую из корня проекта**:

```powershell
# 1. Стандартный запуск всего стека (режим разработки: код монтируется в /app)
docker compose up -d --build

# 2. Статус и состояние healthcheck всех контейнеров
docker compose ps

# 3. Просмотр логов ассистента или всего стека
docker compose logs -f app
docker compose logs -f --tail 50

# 4. Остановка стека (данные в томах сохраняются)
docker compose down
```

### Дополнительные режимы сборки

```powershell
# Автономный production-образ (код копируется внутрь образа, монтируются только data/, config.json и src/secrets/)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d --build

# Сборка Paperless-ngx из локальных исходников (../paperless-ngx)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.build.yml up -d --build

# Запуск только стека Paperless-ngx (так делает assist.ps1 при локальном запуске GUI)
docker compose -f docker/docker-compose.yml up -d webserver
```

## Файлы

| Файл | Назначение |
|---|---|
| `../docker-compose.yml` | Корневая точка входа (`include: docker/docker-compose.yml`) |
| `../.dockerignore` | Исключения контекста сборки (venv, `.git`, кэши, секреты, `~*`) |
| `docker/Dockerfile` | Многоэтапный образ `app` (`base`, `dev`, `prod`) |
| `docker/docker-compose.yml` | Основное описание всех сервисов, сетей, healthcheck и томов |
| `docker/docker-compose.prod.yml` | Продакшен-оверрайд с автономным образом (`target: prod`) |
| `docker/docker-compose.build.yml` | Оверрайд сборки Paperless-ngx из `../paperless-ngx` |
| `docker/requirements.txt` | Зависимости Python для Linux-контейнера (без Windows-специфичных и dev-пакетов) |
| `docker/.env.paperless` | Секреты и настройки Paperless-ngx (не коммитится; шаблон — `.env.paperless.example`) |

## Важные замечания

- **Сохранность данных:** Имена Docker-томов (`paperless_data`, `paperless_media`, `paperless_pgdata`, `paperless_redisdata`) сохранены для бесшовной работы с ранее накопленной базой Paperless-ngx.
- **Telegram-бот:** Если плагин `telegram_bot` включён в `config.json`, не запускайте одновременно локальный экземпляр на хосте и контейнер `app` — Telegram API допускает только один активный `getUpdates`-поллинг на токен.
- **Ограничения Linux-контейнера:** Windows-специфичные функции (`pywin32`, WMI, Electron/WebView2 GUI) внутри контейнера недоступны — контейнер работает в режиме `--no-gui` (WebGUI доступен в браузере по адресу `http://127.0.0.1:8090`).
