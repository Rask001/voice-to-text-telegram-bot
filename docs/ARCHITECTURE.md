# Architecture

Проект — polling Telegram bot на aiogram 3. Telegram orchestration разделен на пакет `app/handlers/`, где каждый модуль отвечает за свою область: start/help/profile/history/voice/callbacks/menu/admin/settings/system/fallbacks. Доменные правила вынесены в `app/access_service.py`, `app/access.py`, `app/tariffs.py`, `app/tasks.py`, `app/formatters.py`, `app/analytics_service.py`, `app/transcription_service.py`, `app/text_analysis_service.py`, `app/voice_metrics_service.py`, `app/models.py`.

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
TranscriptionService(OpenAITranscriptionClient)
↓
TextAnalysisService(DeepSeekClient)
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

На старте `app/main.py` логирует `APP_ENV`, `ENV_FILE`, безопасный `DATABASE_URL` и только последние 4 символа Telegram token. OpenAI key, DeepSeek key и полный Telegram token не логируются.

Текущий SQLAlchemy engine синхронный. Для удобства локального `.env.local` `app/db.py` принимает `sqlite+aiosqlite:///...` и внутри приводит его к `sqlite:///...`.

## Поток Voice Message

```text
Voice Message
↓
handle_voice()
↓
get_random_progress_pack()
↓
status: progress_pack[0]
↓
check_user_access(duration_seconds)
↓
download Telegram file
↓
ffmpeg OGG/Opus -> MP3
↓
OpenAI transcription only
↓
plain text transcript
↓
local pre_metrics
↓
DeepSeek structured JSON
↓
local final voice metrics calculation
↓
consistency validation for verdict/meme
↓
record_voice_usage()
↓
save VoiceNote to SQLite
↓
send compact/default response
↓
send voice analysis block
↓
attach fresh_* inline buttons
```

Подробности:

- лимиты проверяются до скачивания аудио, ffmpeg, OpenAI и DeepSeek;
- тексты прогресса выбираются один раз на voice из `app/progress_messages.py`; отдельный progress updater редактирует одно статусное сообщение каждые 1.7 секунды, на успехе бот дожидается завершения набора, а при ошибке останавливает updater и показывает ошибку;
- аудиофайлы сохраняются только во временных файлах и удаляются в `finally`;
- `TranscriptionService.transcribe()` через OpenAI возвращает только полный plain text;
- `voice_metrics_service.calculate_pre_metrics()` до DeepSeek считает `duration_seconds`, `word_count`, `words_per_minute`, rough `wordiness_score`;
- `TextAnalysisService.analyze()` передает DeepSeek transcript + pre_metrics и возвращает `title`, `summary`, `tasks`, `details`, `important_points`, текстовые `voice_analysis` поля;
- `voice_metrics_service.build_voice_analysis()` локально считает численные метрики анализа;
- задачи сохраняются в `VoiceNote.action_items` как JSON-массив `{text, priority}`;
- мемный анализ сохраняется в `VoiceNote.voice_analysis_json`;
- `saved_seconds` прибавляется к `UserSettings.total_saved_seconds` и показывается в `/profile`;
- старые newline-задачи читаются как `priority=false`;
- ответ по умолчанию строит `format_short()`: summary + tasks.

## AI Pipeline

```text
MP3 file
↓
OpenAITranscriptionClient
↓
transcript text
↓
calculate_pre_metrics()
↓
DeepSeekClient
↓
JSON extraction
↓
normalize_tasks()
↓
build_voice_analysis()
↓
handlers save normalized data
```

OpenAI используется только как speech-to-text. Он получает MP3 и простой prompt: дословно расшифровать текст без структурирования, сокращения, выводов или интерпретации. OpenAI не получает prompt для summary, tasks, details, meme или численных метрик.

DeepSeek используется только для анализа готового текста. Он получает plain text transcript и возвращает JSON с `title`, `summary`, `tasks`, `details`, `important_points`, `voice_analysis.memorable_quote`, `voice_analysis.verdict`, `voice_analysis.meme`.

Локальный сервер считает технические и мемные числа без AI: `duration_seconds`, `word_count`, `words_per_minute`, `useful_word_count`, `compression_ratio`, `meaningful_duration_seconds`, `water_percent`, `wordiness_score`, `quality_score`, `voice_type_level`, `water_level`, `verdict_level`, `rare_title`, `saved_seconds` и общий `total_saved_seconds`.

`voice_metrics_service.calculate_pre_metrics()` передает DeepSeek локальный контекст, чтобы creative text не спорил с цифрами. Prompt прямо говорит: локальные метрики — источник истины; если duration маленький, нельзя шутить про сериал/подкаст/аудиокнигу; если `wordiness_score` низкий, нельзя шутить про многословность; если воды мало или она неизвестна, нельзя утверждать, что воды много.

`voice_metrics_service.calculate_final_metrics()` после DeepSeek считает:

- `wordiness_score` через длительность, word count и speech rate;
- `useful_word_count` из `summary + tasks + important_points + details * 0.25`;
- `compression_ratio = useful_word_count / word_count`;
- `water_percent = (1 - compression_ratio) * 100` с защитными ограничениями для коротких сообщений;
- `meaningful_duration_seconds = duration_seconds * compression_ratio`;
- `quality_score` из воды, многословности и наличия задач.

Вода и многословность не равны друг другу. Многословность — сколько человек занял эфир словами. Вода — сколько сказанного можно сжать без потери смысла. Поэтому длинная медленная речь с малым количеством слов не становится автоматически “аудиокнигой”, а короткое сообщение не может получить тип выше `Деловой человек`.

`voice_metrics_service.sanitize_ai_meme_by_metrics()` выполняет consistency validation: если AI-текст противоречит метрикам, например при `water_percent <= 20` пишет про “много воды”, “подкаст” или “аудиокнигу”, verdict/meme заменяются локальным fallback. Для короткого сухого сообщения fallback: `Редкий случай: коротко, по делу и без экспедиции к смыслу.`

`normalize_voice_analysis()` остается совместимым слоем: он приводит локально рассчитанные метрики к безопасной структуре, пересчитывает `water_level` из `water_percent`, `voice_type_level` из `wordiness_score` с учетом длительности и word count, выбирает редкие титулы и санитизирует токсичный meme.

DeepSeek prompt требует жёсткий сарказм, циничный короткий мемный verdict/meme без канцелярита и без мягкой “бережной” подачи. Мем шутит про формат, длину, воду, драматургию, фразы вроде `короче`/`я быстро` или контекст, но бьёт по формату сообщения, а не по человеку. Запрещены мат, травля, угрозы, личностные оскорбления и чувствительные признаки.

OpenAI transcription ошибки:

- `insufficient_quota` превращается в `OpenAIInsufficientQuotaError` и не ретраится бесконечно;
- обычный `RateLimitError` получает exponential backoff с ограниченным числом попыток;
- техническая ошибка логируется и показывает пользователю понятное сообщение.

DeepSeek ошибки:

- если DeepSeek недоступен или возвращает invalid JSON, уже полученная расшифровка сохраняется в `VoiceNote.transcript`;
- пользователь получает `Текст расшифрован, но анализ временно недоступен. Попробуйте позже.`;
- история и кнопка полного текста продолжают работать с сохраненным transcript.

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
- `payments` — Telegram Stars invoices и successful payments;
- `analytics_events` — локальные события использования и admin stats;
- `reminders` — ручные и будущие task/history/AI напоминания;
- `app_config` — небольшие настройки бота, включая owner-managed start text;
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
fresh_analysis:<id>
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
history_analysis:<id>
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

`reminder_parser.py` не использует OpenAI. Основная точка входа — `parse_reminder_text()`, которая возвращает `success`, `task_text`, `remind_at`, `timezone`, `matched_pattern`, `error`, `needs_task`, `needs_tomorrow_clarification`, `clarification_today_at`, `clarification_nextday_at`. Parser понимает разговорные русские форматы: `через минуту`, `через 10`, `через пол часа`, `через полчаса`, `минут через 15`, `через пару минут`, `через несколько часов`, `через 1 час 30 минут`, `через полтора часа`, `сегодня 18:00`, `завтра 14:30`, `завтра утром/днём/вечером/ночью`, `послезавтра`, `через день`, `через два дня`, дни недели и формат `задача в HH:MM`, например `позвонить Соне в 21:21`. Для ввода только времени: если время уже прошло сегодня, ставится завтра. `через 10` без единиц считается 10 минутами. `DEFAULT_TIMEZONE` задает часовой пояс, `DEFAULT_REMINDER_TIME` — дефолтное время для коротких сценариев вроде `завтра` или `в пятницу`.

Ночной режим для неоднозначного `завтра`:

```text
00:00-05:59 + "завтра в 11:00" без явной даты
↓
parse_reminder_text(needs_tomorrow_clarification=True)
↓
FSM stores task_text + today/nextday candidates
↓
reminder_tomorrow_today: or reminder_tomorrow_nextday:
↓
reminder_service.create_reminder()
```

Порог хранится в `app/reminder_parser.py:AMBIGUOUS_TOMORROW_HOUR`. Уточнение не показывается для явных дат (`03.06`, `3 июня`, `2026-06-03`), `послезавтра`, `через день`, дней недели и времени после 06:00.

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

## Поток Админских Команд

Все расширенные админские команды живут в `app/handlers/admin.py`, а бизнес-логика вынесена в `app/admin_service.py`.

```text
Owner command
↓
app/handlers/admin.py
↓
is_owner(user.id, username, settings)
↓
admin_service function
↓
SQLite / filesystem / Telegram response
```

Non-owner получает единый ответ:

```text
Команда доступна только владельцу бота.
```

Стартовый текст:

```text
/set_start_text
↓
AdminStates.waiting_for_start_text
↓
validate length
↓
UPSERT app_config(key='start_text')
↓
/start reads get_start_text()
```

Если записи `start_text` нет, `/start` использует дефолтный текст из `app/admin_service.py`.

Тарифы:

```text
/set_tariff <telegram_id> <tariff>
↓
normalize free/standard/premium/friend/owner
↓
update user_settings.tariff_type and compatibility flags
↓
access.py resolves plan through tariffs.py
```

`friend` — внешний alias для внутреннего тарифа `brother` / `По-братски от Тоши`. `/bro` и `/unbro` — короткие alias-команды.

Service actions:

- `/admin_users` читает `user_settings` и последнюю активность из `analytics_events`/`voice_notes`;
- `/admin_health` проверяет SQLite, ffmpeg, OpenAI key, DeepSeek key, scheduler flag, pending/failed reminders, uptime, Python и диск;
- `/admin_backup` копирует SQLite в `backups/bot_backup_YYYY-MM-DD_HH-MM-SS.db`;
- `/admin_broadcast` проходит FSM: текст → подтверждение inline-кнопкой → отправка всем `user_settings.telegram_user_id` с небольшой паузой.

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
INSERT analytics_events with local created_at
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
- активных пользователей по тарифам: каждый пользователь считается один раз, по последнему `tariff_type` за период;
- русскоязычные конверсии;
- причины ошибок из `error_type`;
- причины блокировок из стабильного `reason` code: `daily_voice_limit`, `monthly_minutes_limit`, `trial_expired`, `trial_minutes_limit`, `voice_too_long`.

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

```text
/profile
↓
⭐ Купить тариф
↓
pay:show
↓
Standard/Premium options
↓
send_invoice(currency=XTR)
↓
pre_checkout_query validates payload + tariff + amount
↓
successful_payment
↓
process_successful_payment()
↓
payments row paid
↓
UserSettings.tariff_type + tariff_expires_at
```

MVP оплаты живёт в:

- `app/payment_service.py` — цены, payload, validation, pending/paid/duplicate, выдача тарифа;
- `app/handlers/payments.py` — inline callbacks, invoice, `pre_checkout_query`, `successful_payment`;
- `app/models.py:Payment` — таблица `payments`;
- `app/models.py:UserSettings.tariff_expires_at` — срок paid-тарифа.

Telegram Stars использует `currency=XTR` и пустой `provider_token`. Реальных payment-секретов в `.env` нет.

Тариф выдаётся только после `successful_payment`, не после `pre_checkout_query`. Дубликат по `telegram_payment_charge_id` не продлевает тариф повторно.

Owner и `brother` не затираются оплатой: если такой пользователь пытается купить тариф, бот показывает, что текущий доступ уже особый.
