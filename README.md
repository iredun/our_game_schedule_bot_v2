# our_game_schedule_bot

Проект с отдельными слоями:

- `db` — SQLAlchemy модели, session/engine
- `repositories` — доступ к данным
- `services` — доменная логика
- `platforms/telegram` — Telegram адаптер
- `platforms/vk` — VK адаптер
- `web` — FastAPI сервер и iCal endpoint
- `web/templates` — HTML-шаблоны
- `web/static` — CSS и JavaScript Mini App
- `web/api` — JSON API роуты
- `web/routes` — HTML-страницы
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

## Создание игры из консоли или cron

Команда `scripts.create_game` публикует игру в Telegram и сохраняет её в БД. Нужны `TELEGRAM_BOT_TOKEN`, `DATABASE_URL` и применённые миграции. Бот должен быть добавлен в чат и иметь право отправлять сообщения. `--chat-id` — ID группы, `--author-id` — Telegram ID пользователя, который будет считаться автором игры.

```bash
python -m scripts.create_game --chat-id -1001234567890 --author-id 123456789 \
  --date next:saturday --time 19:00 --title '#игра' --description 'Настольный футбол' \
  --duration 120 --price 2000 --max-players 14
```

В `--date` можно передать дату `YYYY-MM-DD`, `today`, `tomorrow`, `this:<день>` или `next:<день>`. Дни недели: `monday`…`sunday` или `пн`…`вс`. Например, `next:saturday` всегда означает ближайшую субботу строго после текущего дня; если команда запускается в воскресенье, это будет через шесть дней. `this:saturday` выбирает субботу текущей недели (в саму субботу — сегодня). Часовой пояс берётся из `TIMEZONE`.

Cron на хосте, каждое воскресенье в 09:00 (серверное время cron):

```cron
0 9 * * 0 cd /path/to/our_game_schedule_bot && /path/to/venv/bin/python -m scripts.create_game --chat-id -1001234567890 --author-id 123456789 --date next:saturday --time 19:00 --title '#игра' --description 'Настольный футбол' >> /var/log/game-schedule.log 2>&1
```

Если приложение запущено через Docker Compose, cron тоже настраивается на хосте. Из каталога с `docker-compose.yml` команда `docker compose run --rm` создаст одноразовый контейнер на основе `tgbot`, подключит его к БД и загрузит настройки из `.env`:

```cron
0 9 * * 0 cd /path/to/our_game_schedule_bot && /usr/bin/docker compose run --rm tgbot python -m scripts.create_game --chat-id -1001234567890 --author-id 123456789 --date next:saturday --time 19:00 --title '#игра' --description 'Настольный футбол' >> /var/log/game-schedule.log 2>&1
```

Укажите фактический путь к проекту и к исполняемому файлу Docker (`command -v docker`). Каталог проекта важен: Compose берёт из него конфигурацию и `.env`. `run --rm` удаляет контейнер после выполнения команды; сервис `tgbot` при этом не останавливается.

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

## Telegram Mini App

Mini App для создания игр доступен по `https://<TRAEFIK_DOMAIN>/app`. В личном чате выполните `/start` и нажмите «Создать игру». Для Telegram Web App требуется публичный HTTPS URL; `APP_BASE_URL` должен указывать на этот же домен.

Список активных и ещё не завершившихся игр доступен по кнопке «Список игр» в `/start` или по адресу `/games`. Автор игры и администраторы/владелец чата могут менять дату, описание, длительность, цену и лимит игроков, а также удалять игру. Изменения сразу обновляют исходное сообщение игры в Telegram; участники и список записи управляются кнопками этого сообщения.

Доступные чаты берутся из таблицы `chat_memberships`. Бот добавляет туда пользователя, когда тот использует поддерживаемую команду в группе или нажимает игровую кнопку. При загрузке списка и перед публикацией членство дополнительно проверяется через Telegram. Чтобы чат появился у пользователя, ему нужно хотя бы раз взаимодействовать с ботом в этом чате. После изменения модели примените миграции: `alembic -c alembic.ini upgrade head` (Docker Compose запускает их сервисом `migrate`).
