# our_game_schedule_bot

Проект с отдельными слоями:

- `db` — SQLAlchemy модели, session/engine
- `repositories` — доступ к данным
- `services` — доменная логика
- `platforms/telegram` — Telegram адаптер
- `platforms/vk` — VK адаптер
- `web` — FastAPI сервер и iCal endpoint
- `alembic` — миграции БД

## Переменные окружения

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_IDS=
VK_BOT_TOKEN=
VK_ALLOWED_CHAT_IDS=
TRAEFIK_DOMAIN=calendar.example.com
TRAEFIK_ACME_EMAIL=admin@example.com
DATABASE_URL=sqlite:///app.db
APP_BASE_URL=https://calendar.example.com
TIMEZONE=Europe/Moscow
```

Токен теперь задается отдельно для каждой платформы:

- `TELEGRAM_BOT_TOKEN` для Telegram
- `VK_BOT_TOKEN` для VK

Готовый шаблон для Docker лежит в `example.env`.

## Запуск миграций

```bash
alembic -c alembic.ini upgrade head
```

## Запуск Telegram

```bash
python -m platforms.telegram.app
```

## Запуск VK

```bash
python -m platforms.vk.app
```

## Запуск Web API

```bash
uvicorn web.main:app --reload
```

## Docker

Для проекта добавлены отдельные `Dockerfile` и `docker-compose.yml`.

Поднимаются сервисы:

- `traefik` — reverse proxy с Let's Encrypt
- `db` — PostgreSQL
- `migrate` — прогоняет Alembic миграции
- `web` — FastAPI с `ical`
- `tgbot` — Telegram bot
- `vkbot` — VK bot

Команда `/calendar_link` работает так:

- в группе бот отправляет пользователя в личку
- в личке бот создает или переиспользует персональный токен из БД
- пользователю возвращается приватная `ical` ссылка

Запуск:

```bash
cp example.env .env
docker compose up --build -d
```

Для Docker используется `DATABASE_URL=postgresql+psycopg://...`.
Для HTTPS через Let's Encrypt нужны:

- `TRAEFIK_DOMAIN` — реальный публичный домен с A/AAAA записью на сервер
- `TRAEFIK_ACME_EMAIL` — email для ACME регистрации

После этого `web` будет доступен через Traefik по `https://<TRAEFIK_DOMAIN>`.
