import asyncio
import time
from contextlib import suppress
from datetime import date
from pathlib import Path
from typing import TypedDict

from aiogram import Bot, F, Router
from aiogram.types import Message
from openai import OpenAIError, RateLimitError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.access import LIMIT_EXPIRED_MESSAGE, record_voice_usage
from app.access_service import check_user_access
from app.analytics_service import track_event
from app.config import Settings
from app.formatters import analysis_list, format_response, format_voice_analysis
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
from app.models import UserSettings, VoiceNote
from app.preferences import get_response_mode
from app.progress_messages import (
    PROGRESS_UPDATE_INTERVAL_SECONDS,
    ProgressPack,
    get_random_progress_pack,
)
from app.tasks import normalize_tasks, serialize_tasks
from app.text_analysis_service import TextAnalysisError, TextAnalysisService
from app.transcription_service import OpenAIInsufficientQuotaError, TranscriptionService
from app.voice_analysis import fallback_voice_analysis, serialize_voice_analysis
from app.voice_metrics_service import build_voice_analysis


router = Router()


class _StatusRef(TypedDict):
    message: Message


@router.message(F.voice)
async def handle_voice(
    message: Message,
    bot: Bot,
    settings: Settings,
    session_factory: sessionmaker[Session],
    transcription_service: TranscriptionService,
    text_analysis_service: TextAnalysisService,
) -> None:
    if message.from_user is None or message.voice is None:
        return

    user_id = message.from_user.id
    duration_seconds = message.voice.duration
    processing_started_at = time.monotonic()
    current_tariff_type = ""
    progress_pack = get_random_progress_pack()
    status = await message.answer(progress_pack[0])
    status_ref = _StatusRef(message=status)
    progress_task: asyncio.Task[None] | None = None
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
            status_ref["message"] = await safe_edit(
                status_ref["message"],
                denial_reason,
            )
            return
        session.commit()

    raw_audio_path: Path | None = None
    mp3_audio_path: Path | None = None

    try:
        progress_task = asyncio.create_task(
            _run_progress_updates(status_ref, progress_pack)
        )
        track_event(
            session_factory,
            "voice_processing_started",
            message.from_user,
            {"duration_seconds": duration_seconds},
            settings=settings,
            tariff_type=current_tariff_type,
        )
        raw_audio_path = await download_voice(bot, message.voice.file_id)
        mp3_audio_path = await asyncio.to_thread(convert_to_mp3, raw_audio_path)

        transcript = await asyncio.to_thread(
            transcription_service.transcribe,
            mp3_audio_path,
        )
        if not transcript:
            await _stop_progress_updates(progress_task)
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
            status_ref["message"] = await safe_edit(
                status_ref["message"],
                "Не получилось получить текст из голосового.",
            )
            return
        track_event(
            session_factory,
            "voice_transcribed",
            message.from_user,
            {"duration_seconds": duration_seconds},
            settings=settings,
            tariff_type=current_tariff_type,
        )

        try:
            analysis = await asyncio.to_thread(text_analysis_service.analyze, transcript)
        except TextAnalysisError as exc:
            await _stop_progress_updates(progress_task)
            note_id = _save_transcription_without_analysis(
                session_factory=session_factory,
                user_id=user_id,
                username=message.from_user.username,
                settings=settings,
                telegram_file_id=message.voice.file_id,
                duration_seconds=duration_seconds,
                transcript=transcript,
            )
            _track_voice_failure(
                session_factory,
                message,
                settings,
                current_tariff_type,
                duration_seconds,
                "deepseek_analysis_error",
                str(exc),
            )
            status_ref["message"] = await safe_edit(
                status_ref["message"],
                "Текст расшифрован, но анализ временно недоступен. "
                "Попробуйте позже.",
                reply_markup=note_keyboard(note_id, source="fresh"),
            )
            logger.exception("DeepSeek text analysis failed")
            return

        try:
            voice_analysis = build_voice_analysis(
                transcript=transcript,
                duration_seconds=duration_seconds,
                summary=str(analysis["summary"]),
                tasks=analysis["action_items"],
                details=str(analysis.get("details", "")),
                important_points=analysis["important_points"],
                voice_analysis_text=analysis.get("voice_analysis_text"),
            )
        except Exception:
            logger.exception("Local voice metrics calculation failed")
            voice_analysis = fallback_voice_analysis(duration_seconds)
        analysis["voice_analysis"] = voice_analysis

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
            user_settings = session.scalar(
                select(UserSettings).where(UserSettings.telegram_user_id == user_id)
            )
            total_saved_seconds = 0
            if user_settings is not None:
                user_settings.total_saved_seconds = (
                    user_settings.total_saved_seconds or 0
                ) + int(voice_analysis["saved_seconds"])
                total_saved_seconds = user_settings.total_saved_seconds
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
                voice_analysis_json=serialize_voice_analysis(voice_analysis),
            )
            session.add(note)
            session.flush()
            note_id = note.id
            session.commit()

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
        if progress_task is not None:
            await progress_task
        result_messages = await send_html_chunks(
            message,
            format_response(response_mode, transcript, analysis),
            reply_markup=note_keyboard(note_id, source="fresh"),
        )
        result_message = result_messages[0]
        analysis_messages = await send_html_chunks(
            message,
            format_voice_analysis(voice_analysis, total_saved_seconds),
        )
        with session_factory() as session:
            note = session.get(VoiceNote, note_id)
            if note is not None:
                note.result_message_id = result_message.message_id
                note.analysis_message_ids = join_message_ids(analysis_messages)
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
        await _stop_progress_updates(progress_task)
        _track_voice_failure(
            session_factory,
            message,
            settings,
            current_tariff_type,
            duration_seconds,
            "insufficient_quota",
            "OpenAI insufficient quota",
        )
        status_ref["message"] = await safe_edit(
            status_ref["message"],
            "Сейчас обработка временно недоступна: закончилась API-квота. "
            "Попробуйте позже."
        )
        logger.exception("OpenAI insufficient quota")
    except RateLimitError:
        await _stop_progress_updates(progress_task)
        _track_voice_failure(
            session_factory,
            message,
            settings,
            current_tariff_type,
            duration_seconds,
            "rate_limit",
            "OpenAI rate limit after retries",
        )
        status_ref["message"] = await safe_edit(
            status_ref["message"],
            "OpenAI временно ограничил запросы. Попробуйте ещё раз чуть позже."
        )
        logger.exception("OpenAI rate limit after retries")
    except OpenAIError:
        await _stop_progress_updates(progress_task)
        _track_voice_failure(
            session_factory,
            message,
            settings,
            current_tariff_type,
            duration_seconds,
            "openai_error",
            "OpenAI API error",
        )
        status_ref["message"] = await safe_edit(
            status_ref["message"],
            "OpenAI не смог обработать запрос. Проверь API key, модель и логи приложения."
        )
        logger.exception("OpenAI API error")
    except RuntimeError as exc:
        await _stop_progress_updates(progress_task)
        _track_voice_failure(
            session_factory,
            message,
            settings,
            current_tariff_type,
            duration_seconds,
            "runtime_error",
            str(exc),
        )
        status_ref["message"] = await safe_edit(status_ref["message"], str(exc))
        logger.exception("Runtime error while processing voice")
    except Exception as exc:
        await _stop_progress_updates(progress_task)
        _track_voice_failure(
            session_factory,
            message,
            settings,
            current_tariff_type,
            duration_seconds,
            type(exc).__name__,
            str(exc),
        )
        status_ref["message"] = await safe_edit(
            status_ref["message"],
            "Не удалось обработать голосовое. Проверь логи приложения.",
        )
        logger.exception("Voice processing failed")
    finally:
        for path in (raw_audio_path, mp3_audio_path):
            if path and path.exists():
                path.unlink(missing_ok=True)


async def _run_progress_updates(
    status_ref: _StatusRef,
    progress_pack: ProgressPack,
) -> None:
    for progress_text in progress_pack[1:]:
        await asyncio.sleep(PROGRESS_UPDATE_INTERVAL_SECONDS)
        status_ref["message"] = await safe_edit(status_ref["message"], progress_text)


async def _stop_progress_updates(progress_task: asyncio.Task[None] | None) -> None:
    if progress_task is None:
        return
    if not progress_task.done():
        progress_task.cancel()
    with suppress(asyncio.CancelledError):
        await progress_task


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


def _save_transcription_without_analysis(
    *,
    session_factory: sessionmaker[Session],
    user_id: int,
    username: str | None,
    settings: Settings,
    telegram_file_id: str,
    duration_seconds: int,
    transcript: str,
) -> int:
    with session_factory() as session:
        record_voice_usage(
            session,
            user_id,
            username,
            settings,
            duration_seconds,
        )
        note = VoiceNote(
            telegram_user_id=user_id,
            telegram_file_id=telegram_file_id,
            title=clean_title("", note_date=date.today()),
            duration_seconds=duration_seconds,
            transcript=transcript,
            summary="Анализ временно недоступен.",
            action_items=serialize_tasks([]),
            details="",
            important_points="",
            voice_analysis_json=serialize_voice_analysis(
                fallback_voice_analysis(duration_seconds)
            ),
        )
        session.add(note)
        session.flush()
        note_id = note.id
        session.commit()
        return note_id
