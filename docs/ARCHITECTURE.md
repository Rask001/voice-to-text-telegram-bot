# Architecture

Проект — polling Telegram bot на aiogram 3. Telegram orchestration разделен на пакет `app/handlers/`, где каждый модуль отвечает за свою область: start/help/profile/history/voice/callbacks/menu/admin/settings/system/fallbacks. Доменные правила вынесены в `app/access_service.py`, `app/access.py`, `app/tariffs.py`, `app/tasks.py`, `app/formatters.py`, `app/analytics_service.py`, `app/openai_service.py`, `app/models.py`.

## High-Level Схема

```text
Telegram user
↓
aiogram Bot API polling
↓
app/main.py
↓
app/handlers/__init__.py aggregate router
↓
SQLite / OpenAI / ffmpeg / Telegram replies
```

## Запуск

```text
start.sh / start_local.sh / python -m app.main
↓
get_settings()
↓
create_session_factory()
↓
OpenAIService(settings)
↓
dp.include_router(router)
↓
dp.start_polling(bot)
```

`app/main.py` создает `Bot` с `ParseMode.HTML`, поэтому все сообщения форматируются HTML-тегами (`<b>...</b>`), а не Markdown.

## Окружения: Local vs Production

```text
production:
.env or .env.production
↓
production Telegram Bot Token
↓
data/bot.db or production DATABASE_URL
```

```text
local test:
start_local.sh
↓
ENV_FILE=.env.local
↓
separate Telegram test bot token
↓
sqlite+aiosqlite:///./bot_local_test.db
```

`ENV_FILE` выбирает env-файл. Если переменная не задана, читается `.env`, чтобы существующий production/deploy flow не менялся.

`start_local.sh` защищает от случайного запуска production token локально: сравнивает токен с `.env`, требует базу `bot_local_test.db`, пишет PID в `data/local_bot.pid` и логи в `logs/local.out.log` / `logs/local.err.log`.

На старте `app/main.py` логирует `APP_ENV`, `ENV_FILE`, безопасный `DATABASE_URL` и только последние 4 символа Telegram token. OpenAI key и полный Telegram token не логируются.

Текущий SQLAlchemy engine синхронный. Для удобства локального `.env.local` `app/db.py` принимает `sqlite+aiosqlite:///...` и внутри приводит его к `sqlite:///...`.

## Поток Voice Message

```text
Voice Message
↓
handle_voice()
↓
status: "Голосовое получил. Проверяю лимиты..."
↓
check_user_access(duration_seconds)
↓
download Telegram file
↓
ffmpeg OGG/Opus -> MP3
↓
OpenAI transcription
↓
OpenAI analysis JSON
↓
record_voice_usage()
↓
save VoiceNote to SQLite
↓
send compact/default response
↓
attach fresh_* inline buttons
```

Подробности:

- лимиты проверяются до скачивания аудио, ffmpeg и OpenAI;
- аудиофайлы сохраняются только во временных файлах и удаляются в `finally`;
- `OpenAIService.transcribe()` возвращает полный текст;
- `OpenAIService.analyze()` возвращает `title`, `summary`, `tasks`, `details`, `important_points`;
- задачи сохраняются в `VoiceNote.action_items` как JSON-массив `{text, priority}`;
- старые newline-задачи читаются как `priority=false`;
- ответ по умолчанию строит `format_short()`: summary + tasks.

## Поток OpenAI

```text
MP3 file
↓
OpenAIService.transcribe()
↓
transcript text
↓
OpenAIService.analyze()
↓
JSON extraction
↓
normalize_tasks()
↓
handlers save normalized data
```

OpenAI ошибки:

- `insufficient_quota` превращается в `OpenAIInsufficientQuotaError` и не ретраится бесконечно;
- обычный `RateLimitError` получает exponential backoff с ограниченным числом попыток;
- invalid JSON логируется, а raw text используется как summary fallback.

## Поток SQLite

```text
create_session_factory()
↓
Base.metadata.create_all()
↓
_ensure_sqlite_schema_updates()
↓
handlers use session_factory per operation
```

Основные таблицы:

- `voice_notes` — история обработок и кэш результатов;
- `user_settings` — тариф, response mode, counters, trial/month limits;
- `analytics_events` — локальные события использования и admin stats;
- `reminders` — ручные и будущие task/history/AI напоминания;
- `daily_usage` — legacy дневной счетчик, сейчас не участвует в активной проверке тарифов.

SQLite schema updates сделаны простыми `ALTER TABLE` в `app/db.py`. Это не полноценная миграционная система, но достаточно для текущего MVP. Текущая схема, уже поддержанные ручные миграции и план будущего Alembic описаны в `docs/DATABASE_MIGRATIONS.md`.

Полная очистка пользовательской истории выполняется через удаление строк из `voice_notes`. Таблицы, schema, `user_settings`, тарифы, лимиты и настройки сохраняются.

## Поток Тарифов и Лимитов

```text
handler receives user
↓
get_or_create_user_settings()
↓
resolve tariff
↓
reset daily/month counters if needed
↓
apply plan limits
↓
build AccessStatus
```

Для voice:

```text
duration_seconds
↓
check_user_access(duration_seconds)
↓
static checks: trial, daily voice count, month minutes
↓
dynamic checks: max voice duration, projected monthly/total minutes
↓
allow or deny before download/ffmpeg/OpenAI
```

Тарифы задаются в `app/tariffs.py`:

- Owner: без ограничений;
- По-братски от Тоши: 10 voice/day, 10 min per voice, 67 min/month;
- Free: 3 days trial, 3 voice/day, 5 min per voice, 15 min total;
- Standard: 30 voice/day, 10 min per voice, 300 min/month;
- Premium: 100 voice/day, 15 min per voice, 1500 min/month.

Публичная точка проверки для handlers — `app/access_service.py:check_user_access()`. Низкоуровневая логика остается в `app/access.py`.

## Поток Callback-Кнопок

Свежий результат:

```text
fresh_full_text:<id>
fresh_tasks:<id>
fresh_details:<id>
fresh_share:<id>
↓
fresh_note_callback()
↓
load VoiceNote owned by user
↓
if block already sent: callback.answer("...уже был отправлен...")
↓
else send cached SQLite data
↓
save sent message ids
```

История:

```text
history:<id>
↓
history_callback()
↓
load VoiceNote owned by user
↓
send history item
↓
attach history_* buttons
```

Кнопки внутри истории:

```text
history_full_text:<id>
history_tasks:<id>
history_details:<id>
history_share:<id>
↓
history_note_callback()
↓
load VoiceNote owned by user
↓
send cached SQLite block again
```

Ключевое отличие: history callbacks не применяют защиту “блок уже отправлен”, потому что пользователь явно открыл запись из истории.

## Поток Истории

```text
/history or Reply Keyboard "История"
↓
send history list from `app/handlers/history.py`
↓
SELECT last 5 VoiceNote for telegram_user_id
↓
format_history()
↓
inline buttons 1-5
```

Открытие записи:

```text
history:<note_id>
↓
check owner
↓
format_history_item()
↓
note_keyboard(source="history")
```

История не вызывает OpenAI.

## Поток Reply Keyboard

Нижнее меню создается `app/handlers/keyboards.py:main_keyboard()`:

```text
🎙 Голосовое | 🔔 Напомни
👤 Профиль  | 📚 История
⚙️ Настройки | ❓ Помощь
```

`🔔 Напомни` открывает `app/handlers/keyboards.py:reminders_menu_keyboard()`:

```text
➕ Создать | 📋 Текущие
⬅️ Назад
```

Старые тексты `🎙 Новое голосовое`, `🔔` и `🔔 Напоминания` остаются совместимыми.

`app/handlers/menu.py:reply_keyboard_handler()` маршрутизирует текст кнопки в ту же логику, что команды. Обычный текст, который не совпал с кнопкой, попадает в `app/handlers/fallbacks.py:text_fallback()`.

## Поток Напоминаний

Ручное создание:

```text
/remind
↓
handlers/reminders.py asks task text
↓
user sends text
↓
reminder_parser.py tries to parse full text
↓
if time found: create reminder immediately
↓
if no time found: ask selected button or manual text time
↓
reminder_service.create_reminder()
↓
SQLite reminders(status=pending)
```

Быстрое создание одной командой:

```text
/remind завтра 14:30 заехать в автосервис
↓
handlers/reminders.py reads command args
↓
reminder_parser.parse_reminder_request()
↓
reminder_service.create_reminder()
↓
SQLite reminders(status=pending)
```

`reminder_parser.py` не использует OpenAI. Основная точка входа — `parse_reminder_text()`, которая возвращает `success`, `task_text`, `remind_at`, `timezone`, `matched_pattern`, `error`, `needs_task`. Parser понимает разговорные русские форматы: `через минуту`, `через 10`, `через пол часа`, `через полчаса`, `минут через 15`, `через пару минут`, `через несколько часов`, `через 1 час 30 минут`, `через полтора часа`, `сегодня 18:00`, `завтра 14:30`, `завтра утром/днём/вечером/ночью`, дни недели и формат `задача в HH:MM`, например `позвонить Соне в 21:21`. Для ввода только времени: если время уже прошло сегодня, ставится завтра. `через 10` без единиц считается 10 минутами. `DEFAULT_TIMEZONE` задает часовой пояс, `DEFAULT_REMINDER_TIME` — дефолтное время для коротких сценариев вроде `завтра` или `в пятницу`.

Scheduler тоже берет текущее время через `DEFAULT_TIMEZONE`, а не через системную таймзону сервера. Это сохраняет одинаковое сравнение `remind_at <= now` на локальном и серверном Mac.

Список:

```text
/reminders or Reply Keyboard "📋 Текущие"
↓
reminder_service.get_user_reminders()
↓
format_reminders_list()
↓
inline actions: complete / snooze / cancel
```

Отправка:

```text
app/main.py
↓
run_reminder_scheduler()
↓ every 30 seconds
get_due_reminders(status=pending, remind_at <= now)
↓
mark_reminder_sending()
↓
Telegram send_message()
↓
mark_reminder_sent() or mark_reminder_failed()
```

Защита от дублей держится на статусах `pending → sending → sent`. Handlers не пишут в таблицу `reminders` напрямую: все изменения проходят через `app/reminder_service.py`.

Будущие сценарии:

- свежая расшифровка сможет дать кнопку `🔔 Напомнить по задаче`;
- история сможет дать кнопку `🔔 Напомнить по задаче`;
- будущий OpenAI `reminder_candidate` сможет предлагать готовое напоминание;
- все эти сценарии должны вызывать `create_reminder()` из `app/reminder_service.py`.

## Поток Форматирования Задач

```text
OpenAI tasks
↓
normalize_tasks()
↓
serialize_tasks()
↓
VoiceNote.action_items JSON
↓
parse_stored_tasks()
↓
sort_tasks_for_display()
↓
format_numbered_list()
```

Правила:

- приоритетные задачи сначала;
- обычные задачи после них;
- порядок внутри каждой группы сохраняется;
- приоритетные задачи выводятся жирным и с `❗`;
- если задач нет: `Задачи не найдены.`

## Telegram Message Limits

Длинные сообщения режутся:

- plain transcript: `send_text_chunks()` + `split_for_telegram()`;
- HTML blocks: `send_html_chunks()` + `split_html_for_telegram()`.

`TELEGRAM_TEXT_LIMIT = 3900`, чтобы оставаться ниже лимита Telegram.

## Централизация Форматирования

```text
handlers collect data
↓
formatters.py
↓
HTML text for Telegram
↓
handlers send chunks/reply markup
```

`app/formatters.py` отвечает за summary, tasks, details, profile, history, settings, help и share-блоки. `app/handlers/` оставляет за собой Telegram routing, отправку сообщений, chunking и inline/reply keyboards.

## Структура Handlers

```text
app/handlers/__init__.py
↓
start.py      /start and start callbacks
help.py       /help
profile.py    /profile
history.py    /history and opening history records
voice.py      voice processing pipeline
callbacks.py  fresh/history inline buttons
menu.py       Reply Keyboard actions
settings.py   /settings
admin.py      owner-only commands
system.py     /health
reminders.py  /reminders, /remind and reminder callbacks
fallbacks.py  text and unsupported media
```

`app/handlers.py` больше не существует. Внешний импорт `from app.handlers import router` сохранен за счет package-level `router` в `app/handlers/__init__.py`.

## Поток Аналитики

```text
handler action
↓
track_event(session_factory, event_name, user, payload, settings)
↓
sanitize payload
↓
resolve tariff_type
↓
INSERT analytics_events
```

События пишутся локально в SQLite и не отправляются во внешние сервисы. Ошибка записи аналитики логируется, но не прерывает пользовательский сценарий.

События:

- `user_started`;
- `voice_received`;
- `voice_limit_blocked`;
- `voice_processing_started`;
- `voice_transcribed`;
- `voice_processed_success`;
- `voice_processing_failed`;
- `history_opened`;
- `history_item_opened`;
- `profile_opened`;
- `settings_opened`;
- `share_clicked`;
- `paywall_shown`.
- `reminders_opened`;
- `reminder_created`;
- `reminder_sent`;
- `reminder_completed`;
- `reminder_cancelled`;
- `reminder_snoozed`.

Payload ограничен служебными полями: длительность voice, тип ошибки, короткая ошибка, transcription id, остатки лимитов, причина, source, processing time. Полные transcript/summary/tasks и секреты в `analytics_events` не пишутся.

Owner stats:

```text
/admin_stats
↓
is_owner()
↓
get_admin_stats(period)
↓
aggregate analytics_events
↓
format_admin_stats()
```

`get_stats_for_period()` считает:

- уникальных активных пользователей;
- уникальных пользователей с `voice_received`;
- минуты аудио как float, чтобы короткие voice не терялись при округлении;
- среднее `processing_time_seconds` по `voice_processed_success`;
- русскоязычные конверсии;
- причины ошибок из `error_type`;
- причины блокировок из `reason`.

Периоды: `today`, `7d`, `30d`. Inline-кнопки `admin_stats:*` переключают период. `/admin_cleanup_analytics` удаляет события старше 90 дней только после подтверждения.

## Тестовый Контур

```text
python -m unittest discover -s tests
↓
access_service tests
tasks tests
history tests
```

Тесты не вызывают OpenAI и используют временную SQLite базу для проверки доступа.

## Монетизация Telegram Stars

Текущая архитектура подготовлена через:

- `tariff_type` в `UserSettings`;
- тарифные планы в `app/tariffs.py`;
- единый gate `check_user_access()`;
- messages о подписке в `app/access.py`.

Для Stars достаточно добавить платежный handler, который после успешной оплаты меняет `user_settings.tariff_type` на `standard` или `premium`.
