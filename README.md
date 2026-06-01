# Telegram Voice Summary Bot MVP

MVP Telegram-бота на Python 3.12 и aiogram 3: принимает voice messages, скачивает аудио из Telegram, расшифровывает через OpenAI, делает краткое содержание, выделяет задачи и важные пункты, хранит историю и тарифные лимиты в SQLite.

## Что уже есть

- `/start`
- `/profile` с тарифом, дневным лимитом и остатком
- `/history` с последними обработками
- `/settings` для выбора формата ответа
- `/health` для быстрой проверки бота, SQLite, ffmpeg и API key
- `/admin_add_unlimited <telegram_id>` для ручного тарифа `По-братски от Тоши`
- `/admin_stats` и быстрые периоды `/admin_stats_today`, `/admin_stats_7d`, `/admin_stats_30d`
- постоянное нижнее меню Telegram через Reply Keyboard
- прием Telegram `voice` messages
- скачивание аудио во временный файл
- конвертация Telegram OGG/Opus в MP3 через `ffmpeg`
- transcription через OpenAI Audio Transcriptions
- summary/action items/important points через OpenAI Responses API
- SQLite + SQLAlchemy
- тарифная система: Owner, По-братски от Тоши, Free, Standard, Premium
- дневные, месячные и trial-лимиты по минутам
- кэш результатов обработки: кнопки не делают повторный OpenAI-запрос
- история обработок с заголовками и быстрым открытием записей
- кнопка `📤 Поделиться` для создания пересылаемого блока
- компактный ответ по умолчанию: кратко + задачи, полный текст открывается кнопкой
- локальная аналитика использования в SQLite без внешних сервисов
- простое место расширения под монетизацию через Telegram Stars: сейчас при превышении лимита показывается сообщение, позже здесь можно проверять платежи и увеличивать квоту
- Docker и `docker-compose.yml`

## Структура

```text
app/
  access.py          # низкоуровневая логика доступа и списания лимитов
  access_service.py  # единая точка проверки доступа
  config.py          # env-настройки
  db.py              # SQLAlchemy engine/session
  analytics_service.py # локальная аналитика и admin stats
  formatters.py      # форматирование Telegram-сообщений
  handlers/          # aiogram handlers по модулям
  tariffs.py         # правила тарифов
  tasks.py           # нормализация задач и priority
  main.py            # точка входа
  models.py          # таблицы SQLite
  openai_service.py  # OpenAI transcription + analysis
data/                # SQLite база при локальном/Docker запуске
tests/               # минимальные unit-тесты
```

## Документация проекта

Для быстрой навигации и дальнейшей разработки сначала смотрите внутреннюю документацию:

- [`AGENTS.md`](AGENTS.md) — короткое корневое правило для Codex и других AI-агентов
- [`docs/PROJECT_MAP.md`](docs/PROJECT_MAP.md) — карта файлов, функций, классов и связей
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — архитектурные потоки voice, history, callbacks, тарифов, SQLite и OpenAI
- [`docs/FEATURES.md`](docs/FEATURES.md) — каталог реализованных функций
- [`docs/AGENTS.md`](docs/AGENTS.md) — инструкция для AI-агентов: что читать перед изменениями
- [`docs/DATABASE_MIGRATIONS.md`](docs/DATABASE_MIGRATIONS.md) — текущая SQLite-схема, ручные ALTER TABLE и план будущего Alembic
- [`docs/DEPLOY_GUIDE.md`](docs/DEPLOY_GUIDE.md) — простая инструкция: GitHub → удалённый Mac → перезапуск бота

## Быстрый запуск локально

1. Создайте бота у [@BotFather](https://t.me/BotFather) и получите `TELEGRAM_BOT_TOKEN`.
2. Создайте `.env`:

```bash
cp .env.example .env
```

3. Заполните в `.env`:

```env
TELEGRAM_BOT_TOKEN=...
OPENAI_API_KEY=...
```

4. Установите зависимости и запустите:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

Локально должен быть установлен `ffmpeg`:

```bash
brew install ffmpeg
```

После запуска отправьте боту `/start`, затем голосовое сообщение.

## Локальная тестовая среда

Для разработки на рабочем MacBook используйте отдельного тестового Telegram-бота. Так локальный polling не конфликтует с production-ботом на серверном Mac.

Env-файлы:

- `.env.production` — production-секреты и production SQLite URL; не коммитится.
- `.env.local` — тестовый Telegram Bot Token, тот же OpenAI API key и отдельная база; не коммитится.
- `.env.example` — шаблон без секретов, хранится в Git.

Создать тестового бота можно через [@BotFather](https://t.me/BotFather): `/newbot`, имя, username, затем вставить test token в `.env.local`.

Пример `.env.local`:

```env
APP_ENV=local
TELEGRAM_BOT_TOKEN=123456:test_bot_token
OPENAI_API_KEY=sk-your-key
DATABASE_URL=sqlite+aiosqlite:///./bot_local_test.db
DEFAULT_RESPONSE_MODE=short
OWNER_TELEGRAM_ID=
UNLIMITED_USER_IDS=
```

Локальный тестовый бот запускается только через `.env.local`:

```bash
./start_local.sh
./status_local.sh
./stop_local.sh
```

`start_local.sh` специально проверяет, что:

- используется `.env.local`;
- Telegram token отличается от `.env`;
- база называется `bot_local_test.db`;
- в лог выводятся только последние 4 символа токена.

Локальная тестовая база создается отдельно: `./bot_local_test.db`. Production `data/bot.db` и серверный бот не трогаются.

Важно: Telegram polling допускает только один активный процесс на один Telegram Bot Token. Поэтому локально используйте test token, а production token оставляйте только на сервере.

## Проверки

```bash
.venv/bin/python -m compileall app tests
.venv/bin/python -m unittest discover -s tests
```

## Запуск через Docker

```bash
cp .env.example .env
# заполните .env
docker compose up --build
```

SQLite база будет лежать в `./data/bot.db`.

## Настройки

Приложение поддерживает `ENV_FILE`:

```bash
ENV_FILE=.env.local python -m app.main
ENV_FILE=.env.production python -m app.main
```

Если `ENV_FILE` не указан, по умолчанию читается `.env`.

```env
APP_ENV=production
OPENAI_TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
OPENAI_TEXT_MODEL=gpt-5-mini
DATABASE_URL=sqlite:///data/bot.db
DAILY_VOICE_LIMIT=5
MAX_VOICE_SECONDS=600
DEFAULT_RESPONSE_MODE=short
OWNER_TELEGRAM_ID=
UNLIMITED_USER_IDS=
```

`MAX_VOICE_SECONDS=600` означает 10 минут. Telegram voice messages обычно приходят как OGG/Opus, поэтому бот перед отправкой в OpenAI конвертирует файл в MP3 через `ffmpeg`.

`DEFAULT_RESPONSE_MODE` задаёт формат ответа для пользователей без личной настройки:

- `short` — кратко + задачи
- `full` — подробный ответ + полный текст отдельными сообщениями
- `tasks` — только задачи

Пользователь может изменить режим командой `/settings`.

## Тарифы

Правила тарифов описаны в `app/tariffs.py`, а состояние пользователя хранится в SQLite в таблице `user_settings`.

| Тариф | Голосовых в день | Макс. одно voice | Минут в месяц | Общий trial-лимит |
| --- | ---: | ---: | ---: | ---: |
| Owner | ∞ | ∞ | ∞ | ∞ |
| По-братски от Тоши | 10 | 10 мин | 67 | ∞ |
| Free | 3 | 5 мин | 15 | 15 мин / 3 дня |
| Standard | 30 | 10 мин | 300 | ∞ |
| Premium | 100 | 15 мин | 1500 | ∞ |

Free заканчивается, если прошло больше 3 дней с момента регистрации или использовано 15 минут. После окончания trial бот предлагает оформить подписку. `tariff_type` подготовлен для будущей оплаты через Telegram Stars: после оплаты достаточно поменять тариф пользователя на `standard` или `premium`.

## Owner и доступ для друзей

### OWNER_TELEGRAM_ID

`OWNER_TELEGRAM_ID` задаёт владельца бота. Owner всегда имеет безлимит и может использовать админ-команду:

```bash
OWNER_TELEGRAM_ID=123456789
```

`OWNER_TELEGRAM_ID` нужен только во внутренней настройке владельца. В пользовательском `/profile` Telegram ID больше не показывается.

### UNLIMITED_USER_IDS

`UNLIMITED_USER_IDS` — список друзей или тестовых пользователей с тарифом `По-братски от Тоши`:

```bash
UNLIMITED_USER_IDS=123456789,987654321,555555555
```

Для таких пользователей `/profile` покажет:

```text
Тариф: По-братски от Тоши
Осталось сегодня: 10
```

### Админ-команда

Owner может добавить пользователя в тариф `По-братски от Тоши` без правки `.env`:

```text
/admin_add_unlimited 123456789
```

Команда сохраняет доступ в SQLite.

## Free Limit

Free-пользователю доступно 3 голосовых сообщения в день, максимум 5 минут на одно voice, 15 минут за весь пробный период и 3 дня trial. Лимит проверяется сразу после получения voice message, до скачивания аудио, `ffmpeg` и OpenAI-запросов.

Если лимит закончился, бот сразу отвечает:

```text
❌ Ваш лимит закончился.

Чтобы продолжить пользоваться ботом, оформите подписку.

Скоро здесь появится оплата через Telegram Stars ⭐
```

Owner не имеет ограничений. Пользователи из `UNLIMITED_USER_IDS` и пользователи, добавленные через `/admin_add_unlimited`, получают тариф `По-братски от Тоши`.

## Поддерживаемые типы сообщений

Сейчас бот обрабатывает только обычные Telegram `voice messages`.

Не обрабатываются и не отправляются в OpenAI:

- текст
- фото
- документы
- видео
- video note / кружки
- audio files

Для неподдерживаемых типов бот сразу отвечает коротким сообщением и ничего не обрабатывает.

## Формат ответа

По умолчанию после голосового бот отправляет компактный ответ:

```text
🧠 Кратко:
1-2 предложения

✅ Задачи:
1. ...
2. ...
```

Расшифровка целиком не отправляется сразу. Под ответом есть inline-кнопки:

- `📄 Показать полный текст`
- `🧠 Подробнее`
- `✅ Только задачи`

Если полный текст длиннее лимита Telegram, бот разбивает его на несколько сообщений.

## Reply Keyboard

После `/start`, `/help` и основных действий бот показывает постоянное нижнее меню:

- `🎙 Новое голосовое`
- `👤 Профиль`
- `📚 История`
- `⚙️ Настройки`
- `❓ Помощь`

Это Reply Keyboard, отдельная от inline-кнопок под результатом обработки. Inline-кнопки `📄 Полный текст`, `🧠 Подробнее`, `✅ Только задачи`, `📤 Поделиться` остаются под конкретной расшифровкой.

## Profile

Команда `/profile` и кнопка `👤 Профиль` показывают:

- имя пользователя
- username
- тариф
- использовано сегодня
- осталось сегодня
- дневной лимит
- использованные и оставшиеся минуты
- дни пробного периода для Free
- дату/время сброса лимита

Telegram ID хранится в базе и используется для лимитов, админских функций и авторского доступа, но больше не показывается пользователю в интерфейсе.

## История

Команда `/history` и кнопка `📚 История` показывают последние 5 обработанных голосовых пользователя:

- заголовок
- дата: сегодня / вчера / дата
- короткое summary

Под списком есть inline-кнопки `1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣`. Нажатие открывает сохранённую запись из базы и показывает:

- title
- дату
- summary
- tasks с флагом priority
- кнопки `📄 Полный текст`, `✅ Только задачи`, `🧠 Подробнее`, `📤 Поделиться`

Открытие истории не делает OpenAI-запросов. Все данные берутся из SQLite.

Если истории нет:

```text
История пока пуста. Отправьте первое голосовое сообщение.
```

## Что хранится в базе

В SQLite сохраняются результаты обработки:

- Telegram user id
- Telegram voice file id
- title
- full text / transcript
- summary
- tasks
- details
- important points
- created_at
- ids отправленных сообщений для защиты от дублей

В `user_settings` также хранятся тарифные поля:

- `tariff_type`
- `registration_date`
- `trial_expires_at`
- `minutes_used_total`
- `minutes_limit_total`
- `minutes_used_this_month`
- `minutes_limit_month`
- `voices_used_today`
- `daily_voice_limit`

Аудиофайлы постоянно не хранятся. Бот скачивает voice message во временный файл, конвертирует через `ffmpeg`, отправляет в OpenAI и удаляет временные файлы после обработки.

## Аналитика

Бот пишет локальные события в SQLite таблицу `analytics_events`. Данные не отправляются во внешние сервисы.

Собираются события:

- `user_started`
- `voice_received`
- `voice_limit_blocked`
- `voice_processing_started`
- `voice_transcribed`
- `voice_processed_success`
- `voice_processing_failed`
- `history_opened`
- `history_item_opened`
- `profile_opened`
- `settings_opened`
- `share_clicked`
- `paywall_shown`

В аналитике хранится только служебная информация: Telegram ID, тариф, имя события, дата и короткий JSON payload. Полные тексты расшифровок, summary, задачи, OpenAI API key и Telegram token туда не пишутся.

Owner может открыть статистику:

```text
/admin_stats
/admin_stats_today
/admin_stats_7d
/admin_stats_30d
```

Команда показывает активных пользователей, пользователей с голосовыми, полученные и успешно обработанные voice, ошибки, блокировки лимитом, минуты аудио с одной цифрой после запятой, среднее время обработки, открытия истории/профиля, share clicks, paywall views и русскоязычные конверсии:

- активация новых;
- голосовые от активных;
- успешная обработка;
- блокировки лимитом;
- доля “Поделиться”.

Если за период есть ошибки или блокировки, `/admin_stats` дополнительно показывает причины из analytics payload: `error_type` и `reason`.

Старые события можно удалить owner-командой:

```text
/admin_cleanup_analytics
```

Команда сначала спрашивает подтверждение и удаляет события старше 90 дней.

## Поделиться

Кнопка `📤 Поделиться` создаёт отдельное сообщение, которое удобно переслать вручную:

```text
📝 Расшифровка голосового

🧠 Кратко:
...

✅ Задачи:
1. ...

🎙Создано через: @voitext_bot
```

Telegram Bot API не открывает системное меню “поделиться”, поэтому бот отправляет готовый блок. Если блок уже был отправлен раньше, повторное нажатие не создаёт дубль.

## Приоритетные задачи

Если пользователь явно выделяет задачу словами вроде “важно”, “срочно”, “самое главное”, “обязательно”, “не забудь”, бот помечает её как приоритетную. В SQLite новые задачи сохраняются JSON-массивом:

```json
[
  {"text": "Оплатить сервер", "priority": true},
  {"text": "Купить молоко", "priority": false}
]
```

Старые записи со строковым списком задач продолжают открываться: для них `priority=false`. При выводе приоритетные задачи идут первыми, внутри групп сохраняется исходный порядок.

## Кэш и кнопки

После обработки voice message бот сохраняет в SQLite:

- полный текст / transcript
- title
- summary
- tasks с priority-флагами
- details
- important points

Кнопки `📄 Полный текст`, `🧠 Подробнее`, `✅ Только задачи`, `📤 Поделиться` читают уже сохранённый результат из базы по `note_id` в callback data. Они не делают повторный запрос к OpenAI.

Если пользователь быстро нажимает одну и ту же кнопку несколько раз, in-memory debounce отвечает:

```text
Уже показываю, секунду.
```

Если блок уже был отправлен раньше, бот не дублирует его и отвечает:

```text
Этот блок уже был отправлен выше 👆
```

Если сохранённый результат не найден:

```text
Не нашёл сохранённый результат. Попробуйте отправить голосовое ещё раз.
```

## Куда добавить Telegram Stars позже

Минимальная точка расширения находится в `app/tariffs.py`, `app/access_service.py`, `app/access.py` и новом модуле внутри `app/handlers/`:

- сейчас доступ проверяется через `check_user_access()`
- позже можно добавить таблицу платежей/подписок
- при успешной оплате Stars менять `UserSettings.tariff_type` на `standard` или `premium`
- обработчики `pre_checkout_query` и `successful_payment` лучше добавить отдельным файлом, когда дойдете до монетизации

## Примечания по OpenAI

В MVP используются:

- Audio Transcriptions API для речи в текст
- Responses API для генерации JSON с summary/action items

Модели вынесены в `.env`, чтобы их можно было менять без правки кода.

## Troubleshooting

### Conflict: terminated by other getUpdates request

Telegram разрешает только один активный long polling процесс для одного бота. Если видите ошибку:

```text
Conflict: terminated by other getUpdates request
```

значит этот же бот уже запущен в другом терминале, Docker-контейнере или процессе. Остановите лишний экземпляр и оставьте только один `python -m app.main`.

### ffmpeg not found

Voice messages из Telegram приходят как OGG/Opus, поэтому перед отправкой в OpenAI бот конвертирует аудио в MP3 через `ffmpeg`.

Установите:

```bash
brew install ffmpeg
```

Проверьте:

```bash
ffmpeg -version
```

На macOS с Homebrew в `/opt/homebrew` бот также пробует найти `/opt/homebrew/bin/ffmpeg`, даже если `PATH` настроен не полностью.

### 429 insufficient_quota

Если OpenAI возвращает:

```text
429 insufficient_quota
```

значит в аккаунте OpenAI закончилась API-квота или не настроен billing. Бот не ретраит эту ошибку бесконечно и показывает пользователю:

```text
Сейчас обработка временно недоступна: закончилась API-квота. Попробуйте позже.
```

Проверьте billing и usage в аккаунте OpenAI, затем повторите запрос.

### Telegram message is too long

Telegram ограничивает длину одного сообщения. Первый ответ теперь компактный, а полный текст отправляется только по кнопке `📄 Показать полный текст`. Если расшифровка длинная, бот разбивает её на несколько сообщений. Если всё равно появится ошибка про длину сообщения, уменьшите `TELEGRAM_TEXT_LIMIT` в `app/formatters.py` или лимиты форматирования там же.

### invalid JSON from OpenAI

Иногда модель может вернуть не чистый JSON, а текст или JSON внутри markdown-блока. Бот пробует извлечь JSON из ответа. Если JSON всё равно невалидный, бот использует сырой ответ как summary, оставляет списки пустыми и пишет предупреждение в логи:

```text
OpenAI returned invalid JSON
```

Для более строгого поведения следующим шагом можно подключить structured outputs / JSON schema.

### Долгая обработка

Обработка voice message состоит из нескольких этапов: проверка лимита, скачивание, конвертация через `ffmpeg`, transcription, summary/tasks. Бот редактирует одно статусное сообщение:

```text
🎧 Голосовое получил. Проверяю лимиты...
📥 Скачиваю аудио...
🎙 Расшифровываю речь...
🧠 Делаю краткое содержание и задачи...
✅ Готово, сейчас появится.
```

Если статус не меняется долго, смотрите:

- не исчерпан ли OpenAI billing/quota
- нет ли сетевой ошибки до Telegram/OpenAI
- установлен ли `ffmpeg`
- не слишком ли длинное голосовое для текущего `MAX_VOICE_SECONDS`
