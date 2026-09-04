# CRM-бот отдела продаж

Telegram-бот для учёта депозитов, рейтинга менеджеров и статистики из партнёрской программы. Полное ТЗ — [sales-crm-bot-spec.md](./sales-crm-bot-spec.md).

Статус: Этап 1 (MVP) + каркас интеграции с партнёркой (без конкретного провайдера, см. §9 ТЗ).

## Стек

Python 3.12 · uv (workspace) · aiogram 3 · FastAPI · SQLAlchemy 2 (async) · PostgreSQL · Alembic

## Структура

```
shared/    — общие ORM-модели, enum'ы, Pydantic-схемы (используются и bot, и backend)
backend/   — FastAPI: REST для депозитов/статистики/пользователей, приём вебхуков партнёрки
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
3. Скопировать `.env.example` → `.env` в `backend/` и `bot/`, заполнить значения (в частности `BOT_TOKEN` — токен от @BotFather).
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

См. раздел 10 ТЗ. Ключевая ручная проверка: менеджер вносит депозит → видит его в «Моей статистике» и в топе команды; повторная отправка того же вебхук-события с `external_id` не создаёт второй депозит; правка/удаление депозита оставляет запись в аудит-логе.
