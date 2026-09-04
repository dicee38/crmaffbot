# CRM-бот отдела продаж

Telegram-бот для учёта депозитов, рейтинга менеджеров и статистики из партнёрской программы. Полное ТЗ — [sales-crm-bot-spec.md](./sales-crm-bot-spec.md).

Статус: Этапы 1–3 (ТЗ §8) полностью реализованы — учёт депозитов, роли, статистика/топы, аудит-лог с согласованием правок, цели/KPI, экспорт в Excel, уведомления и периодические сводки. Из Этапа 4 готов Mini App-дашборд (бэкенд полностью, визуальная проверка — после деплоя). Интеграция с партнёркой (Этап 2) реализована только как каркас-адаптер — провайдер ещё не выбран (§9 ТЗ).

## Стек

Python 3.12 · uv (workspace) · aiogram 3 · FastAPI · SQLAlchemy 2 (async) · PostgreSQL · Alembic · APScheduler · openpyxl

## Структура

```
shared/    — общие ORM-модели, enum'ы, Pydantic-схемы (используются и bot, и backend)
backend/   — FastAPI: REST, вебхуки партнёрки, планировщик (сводки/idle-check), Mini App (static)
bot/       — aiogram-бот, обращается к backend по REST
```

## Локальный запуск

1. Поднять Postgres:
   ```
   docker compose up -d
   ```
2. Установить зависимости всех пакетов:
   ```
   uv sync
   ```
3. Скопировать `.env.example` → `.env` в `backend/` и `bot/`, заполнить значения:
   - `BOT_TOKEN` — токен от @BotFather (одинаковый в обоих `.env`)
   - `INTERNAL_API_SECRET` — любая случайная строка, должна совпадать в `backend/.env` и `bot/.env` (защищает API от подделки заголовка авторизации из браузера — см. `backend/deps.py`)
4. Применить миграции:
   ```
   uv run --package backend alembic -c backend/alembic.ini upgrade head
   ```
5. Создать первую организацию и админа:
   ```
   uv run --package backend python -m backend.seed "Моя компания" <ваш_telegram_id> "Имя Фамилия"
   ```
   Свой `telegram_id` можно узнать у @userinfobot в Telegram.
6. Запустить backend:
   ```
   uv run --package backend uvicorn backend.main:app --reload
   ```
7. Запустить бота (в отдельном терминале):
   ```
   uv run --package bot python -m bot.main
   ```

## Тесты приёмки MVP

См. раздел 10 ТЗ. Ключевая ручная проверка: менеджер вносит депозит → видит его в «Моей статистике» и в топе команды; повторная отправка того же вебхук-события с `external_id` не создаёт второй депозит; правка/удаление депозита требует согласования и оставляет запись в аудит-логе.

## Деплой на Railway

Монорепо — три Railway-сервиса из **одного и того же** GitHub-репозитория (uv workspace резолвит зависимость `shared` только когда виден корень репо, поэтому «Root Directory» для backend/bot-сервисов должен оставаться пустым/корневым, а не `backend/` или `bot/`).

1. **New Project → Deploy from GitHub repo** → выбрать `dicee38/crmaffbot`.
2. **Добавить Postgres**: в проекте `+ New` → `Database` → `PostgreSQL`. Railway сам создаст переменную `DATABASE_URL` (в форме `postgresql://...` — код сам приводит её к `postgresql+asyncpg://`, ничего вручную менять не нужно).
3. **Сервис backend** (можно переименовать первый задеплоенный сервис или добавить новый `+ New` → `GitHub Repo` → тот же репозиторий):
   - Settings → Build → Build Command: `pip install uv && uv sync --frozen`
   - Settings → Deploy → Start Command:
     ```
     uv run --package backend alembic -c backend/alembic.ini upgrade head && uv run --package backend uvicorn backend.main:app --host 0.0.0.0 --port $PORT
     ```
   - Settings → Networking → Generate Domain (нужен публичный HTTPS для вебхуков партнёрки и для Mini App).
   - Variables: `DATABASE_URL` (ссылкой на Postgres-сервис, `${{Postgres.DATABASE_URL}}`), `BOT_TOKEN`, `INTERNAL_API_SECRET`, `AFFILIATE_WEBHOOK_SECRET`, `LARGE_DEPOSIT_THRESHOLD`, `DIGEST_HOUR_UTC`, `IDLE_DAYS_THRESHOLD` (см. `backend/.env.example`).
4. **Сервис bot** (ещё один `+ New` → тот же репозиторий):
   - Build Command: тот же, что у backend.
   - Start Command: `uv run --package bot python -m bot.main`
   - Variables: `BOT_TOKEN` (тот же), `INTERNAL_API_SECRET` (тот же, что у backend), `BACKEND_URL` — приватный адрес backend-сервиса внутри Railway (`${{backend.RAILWAY_PRIVATE_DOMAIN}}`, порт 8080 по умолчанию у Railway для приватной сети — проверить фактический порт в Settings backend-сервиса), `MINIAPP_URL` — публичный домен backend + `/miniapp/` (например `https://<backend-domain>.up.railway.app/miniapp/`).
5. После первого успешного деплоя backend проверить `https://<backend-domain>/health` → `{"status":"ok"}`, затем прогнать сид-скрипт через `railway run` или разово через Railway Shell:
   ```
   railway run --service backend uv run --package backend python -m backend.seed "Моя компания" <telegram_id> "Имя"
   ```
