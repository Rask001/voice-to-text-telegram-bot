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
start.sh or python -m app.main
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

- `🎙 Новое голосовое`;
- `👤 Профиль`;
- `📚 История`;
- `⚙️ Настройки`;
- `❓ Помощь`.

`app/handlers/menu.py:reply_keyboard_handler()` маршрутизирует текст кнопки в ту же логику, что команды. Обычный текст, который не совпал с кнопкой, попадает в `app/handlers/fallbacks.py:text_fallback()`.

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
