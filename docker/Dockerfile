# Updated: 2026-11-19 23:22:00
# Универсальный многоэтапный Dockerfile для сервиса AI-Assistant.
# Этапы сборки:
#   - base : системные утилиты (git, ffmpeg, curl, sqlite3) + Python-зависимости.
#   - dev  : режим разработки (код монтируется с хоста в /app через docker-compose.yml).
#   - prod : автономный образ с кодом проекта внутри (см. docker-compose.prod.yml).

# =============================================================================
# Этап 1: Базовый слой (системные пакеты и Python-зависимости)
# =============================================================================
FROM python:3.14-slim AS base

LABEL org.opencontainers.image.title="AI-Assistant" \
      org.opencontainers.image.description="Универсальный сервис AI-Assistant (WebGUI, REST API, RAG, WikiLLM, Paperless)" \
      org.opencontainers.image.authors="hypo69"

ENV PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Kyiv

WORKDIR /app

# Системные зависимости:
# - git: работа с историей коммитов, diff и рабочими пространствами
# - ffmpeg: аудио-конвертация (плагин youtube_mp3, pydub, SpeechRecognition)
# - curl: встроенные healthcheck-проверки
# - sqlite3: диагностика и обслуживание локальных БД
# - ca-certificates, tzdata: корректная работа HTTPS и часовых поясов
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        git \
        sqlite3 \
        tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && git config --global --add safe.directory '*'

COPY docker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

EXPOSE 8002
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8002/health || exit 1

CMD ["python", "-m", "apps.ai_assistant", "serve", "--host", "0.0.0.0", "--port", "8002", "--no-gui"]

# =============================================================================
# Этап 2: Режим разработки (код монтируется в /app из корня проекта)
# =============================================================================
FROM base AS dev

# =============================================================================
# Этап 3: Автономный образ для деплоя (код копируется внутрь образа)
# =============================================================================
FROM base AS prod

COPY . /app
