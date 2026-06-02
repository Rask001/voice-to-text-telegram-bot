import logging
from pathlib import Path
import time
from typing import Callable, TypeVar

from openai import OpenAI, RateLimitError

from app.config import Settings


logger = logging.getLogger(__name__)
T = TypeVar("T")


TRANSCRIPTION_PROMPT = (
    "Дословно расшифруй текст. Не исправляй смысл, не добавляй выводы, "
    "не структурируй, не сокращай, не интерпретируй."
)


class OpenAIInsufficientQuotaError(RuntimeError):
    """Raised when OpenAI reports that API quota or billing is exhausted."""


class OpenAITranscriptionClient:
    """OpenAI client used only for speech-to-text transcription."""

    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_transcription_model
        self._max_rate_limit_attempts = 3

    def transcribe(self, audio_path: Path) -> str:
        def request() -> object:
            with audio_path.open("rb") as audio_file:
                return self._client.audio.transcriptions.create(
                    model=self._model,
                    file=audio_file,
                    prompt=TRANSCRIPTION_PROMPT,
                )

        transcript = self._with_rate_limit_retry(request, "audio transcription")
        text = getattr(transcript, "text", "")
        return text.strip()

    def _with_rate_limit_retry(self, request: Callable[[], T], label: str) -> T:
        for attempt in range(1, self._max_rate_limit_attempts + 1):
            try:
                return request()
            except RateLimitError as exc:
                if _is_insufficient_quota(exc):
                    raise OpenAIInsufficientQuotaError(
                        "OpenAI API quota is exhausted"
                    ) from exc

                if attempt >= self._max_rate_limit_attempts:
                    raise

                delay_seconds = 2 ** (attempt - 1)
                logger.warning(
                    "OpenAI rate limit during %s, retrying in %s seconds "
                    "(attempt %s/%s)",
                    label,
                    delay_seconds,
                    attempt,
                    self._max_rate_limit_attempts,
                    exc_info=True,
                )
                time.sleep(delay_seconds)

        raise RuntimeError("OpenAI retry loop exited unexpectedly")


def _is_insufficient_quota(exc: RateLimitError) -> bool:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        code = body.get("code")
        if code == "insufficient_quota":
            return True

        error = body.get("error")
        if isinstance(error, dict) and error.get("code") == "insufficient_quota":
            return True

    return "insufficient_quota" in str(exc)
