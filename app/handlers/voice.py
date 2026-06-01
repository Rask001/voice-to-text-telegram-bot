import asyncio
import time
from datetime import date
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.types import Message
from openai import OpenAIError, RateLimitError
from sqlalchemy.orm import Session, sessionmaker

from app.access import LIMIT_EXPIRED_MESSAGE, record_voice_usage
from app.access_service import check_user_access
from app.analytics_service import track_event
from app.config import Settings
from app.formatters import analysis_list, format_response
from app.handlers.keyboards import note_keyboard
from app.handlers.utils import (
    clean_title,
    convert_to_mp3,
    download_voice,
    join_message_ids,
    logger,
    safe_edit,
    send_html_chunks,
    send_text_chunks,
)
from app.models import VoiceNote
from app.openai_service import OpenAIInsufficientQuotaError, OpenAIService
from app.preferences import get_response_mode
from app.tasks import normalize_tasks, serialize_tasks


router = Router()


@router.message(F.voice)
async def handle_voice(
    message: Message,
    bot: Bot,
    settings: Settings,
    session_factory: sessionmaker[Session],
    openai_service: OpenAIService,
) -> None:
    if message.from_user is None or message.voice is None:
        return

    user_id = message.from_user.id
    duration_seconds = message.voice.duration
    processing_started_at = time.monotonic()
    current_tariff_type = ""
    status = await message.answer("🎧 Голосовое получил. Проверяю лимиты...")
    track_event(
        session_factory,
        "voice_received",
        message.from_user,
        {"duration_seconds": duration_seconds},
        settings=settings,
    )

    with session_factory() as session:
        access_status = check_user_access(
            session,
            user_id,
            message.from_user.username,
            settings,
            duration_seconds,
        )
        current_tariff_type = access_status.tariff_type
        if not access_status.can_process:
            denial_reason = access_status.denial_reason or LIMIT_EXPIRED_MESSAGE
            limit_payload = {
                "duration_seconds": duration_seconds,
                "reason": access_status.denial_code or "limit_exceeded",
                "remaining_minutes": (
                    access_status.minutes_remaining_month
                    if access_status.minutes_remaining_month is not None
                    else access_status.minutes_remaining_total
                ),
                "remaining_daily_messages": access_status.remaining_today,
            }
            session.commit()
            track_event(
                session_factory,
                "voice_limit_blocked",
                message.from_user,
                limit_payload,
                settings=settings,
                tariff_type=current_tariff_type,
            )
            track_event(
                session_factory,
                "paywall_shown",
                message.from_user,
                {**limit_payload, "source": "voice_limit"},
                settings=settings,
                tariff_type=current_tariff_type,
            )
            await safe_edit(
                status,
                denial_reason,
            )
            return
        session.commit()

    raw_audio_path: Path | None = None
    mp3_audio_path: Path | None = None

    try:
        track_event(
            session_factory,
            "voice_processing_started",
            message.from_user,
            {"duration_seconds": duration_seconds},
            settings=settings,
            tariff_type=current_tariff_type,
        )
        status = await safe_edit(status, "📥 Скачиваю аудио...")
        raw_audio_path = await download_voice(bot, message.voice.file_id)
        mp3_audio_path = await asyncio.to_thread(convert_to_mp3, raw_audio_path)
        status = await safe_edit(status, "🎙 Расшифровываю речь...")

        transcript = await asyncio.to_thread(openai_service.transcribe, mp3_audio_path)
        if not transcript:
            track_event(
                session_factory,
                "voice_processing_failed",
                message.from_user,
                {
                    "duration_seconds": duration_seconds,
                    "error_type": "empty_transcript",
                    "error_message_short": "Empty transcript",
                },
                settings=settings,
                tariff_type=current_tariff_type,
            )
            await safe_edit(status, "Не получилось получить текст из голосового.")
            return
        track_event(
            session_factory,
            "voice_transcribed",
            message.from_user,
            {"duration_seconds": duration_seconds},
            settings=settings,
            tariff_type=current_tariff_type,
        )

        status = await safe_edit(status, "🧠 Делаю краткое содержание и задачи...")
        analysis = await asyncio.to_thread(openai_service.analyze, transcript)

        with session_factory() as session:
            record_voice_usage(
                session,
                user_id,
                message.from_user.username,
                settings,
                duration_seconds,
            )
            response_mode = get_response_mode(
                session,
                user_id,
                settings.default_response_mode,
            )
            note = VoiceNote(
                telegram_user_id=user_id,
                telegram_file_id=message.voice.file_id,
                title=clean_title(str(analysis.get("title", "")), note_date=date.today()),
                duration_seconds=duration_seconds,
                transcript=transcript,
                summary=str(analysis["summary"]),
                action_items=serialize_tasks(normalize_tasks(analysis["action_items"])),
                details=str(analysis.get("details", "")),
                important_points="\n".join(analysis_list(analysis["important_points"])),
            )
            session.add(note)
            session.flush()
            note_id = note.id
            session.commit()

        status = await safe_edit(status, "✅ Готово, сейчас появится.")
        track_event(
            session_factory,
            "voice_processed_success",
            message.from_user,
            {
                "duration_seconds": duration_seconds,
                "transcription_id": note_id,
                "processing_time_seconds": round(time.monotonic() - processing_started_at, 2),
            },
            settings=settings,
            tariff_type=current_tariff_type,
        )
        result_messages = await send_html_chunks(
            message,
            format_response(response_mode, transcript, analysis),
            reply_markup=note_keyboard(note_id, source="fresh"),
        )
        result_message = result_messages[0]
        with session_factory() as session:
            note = session.get(VoiceNote, note_id)
            if note is not None:
                note.result_message_id = result_message.message_id
                session.commit()
        if response_mode == "full":
            sent_messages = await send_text_chunks(
                result_message,
                transcript,
                title="📄 Полный текст",
            )
            with session_factory() as session:
                note = session.get(VoiceNote, note_id)
                if note is not None:
                    note.full_text_message_ids = join_message_ids(sent_messages)
                    session.commit()

    except OpenAIInsufficientQuotaError:
        _track_voice_failure(
            session_factory,
            message,
            settings,
            current_tariff_type,
            duration_seconds,
            "insufficient_quota",
            "OpenAI insufficient quota",
        )
        await safe_edit(
            status,
            "Сейчас обработка временно недоступна: закончилась API-квота. "
            "Попробуйте позже."
        )
        logger.exception("OpenAI insufficient quota")
    except RateLimitError:
        _track_voice_failure(
            session_factory,
            message,
            settings,
            current_tariff_type,
            duration_seconds,
            "rate_limit",
            "OpenAI rate limit after retries",
        )
        await safe_edit(
            status,
            "OpenAI временно ограничил запросы. Попробуйте ещё раз чуть позже."
        )
        logger.exception("OpenAI rate limit after retries")
    except OpenAIError:
        _track_voice_failure(
            session_factory,
            message,
            settings,
            current_tariff_type,
            duration_seconds,
            "openai_error",
            "OpenAI API error",
        )
        await safe_edit(
            status,
            "OpenAI не смог обработать запрос. Проверь API key, модель и логи приложения."
        )
        logger.exception("OpenAI API error")
    except RuntimeError as exc:
        _track_voice_failure(
            session_factory,
            message,
            settings,
            current_tariff_type,
            duration_seconds,
            "runtime_error",
            str(exc),
        )
        await safe_edit(status, str(exc))
        logger.exception("Runtime error while processing voice")
    except Exception as exc:
        _track_voice_failure(
            session_factory,
            message,
            settings,
            current_tariff_type,
            duration_seconds,
            type(exc).__name__,
            str(exc),
        )
        await safe_edit(status, "Не удалось обработать голосовое. Проверь логи приложения.")
        logger.exception("Voice processing failed")
    finally:
        for path in (raw_audio_path, mp3_audio_path):
            if path and path.exists():
                path.unlink(missing_ok=True)


def _track_voice_failure(
    session_factory: sessionmaker[Session],
    message: Message,
    settings: Settings,
    tariff_type: str,
    duration_seconds: int,
    error_type: str,
    error_message_short: str,
) -> None:
    if message.from_user is None:
        return
    track_event(
        session_factory,
        "voice_processing_failed",
        message.from_user,
        {
            "duration_seconds": duration_seconds,
            "error_type": error_type,
            "error_message_short": error_message_short,
        },
        settings=settings,
        tariff_type=tariff_type or None,
    )
