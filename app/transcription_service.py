from pathlib import Path
from typing import Protocol

from app.ai_clients.openai_client import OpenAIInsufficientQuotaError


class TranscriptionClient(Protocol):
    def transcribe(self, audio_path: Path) -> str:
        ...


class TranscriptionService:
    """Domain service for audio-to-text only."""

    def __init__(self, client: TranscriptionClient) -> None:
        self._client = client

    def transcribe(self, audio_path: Path) -> str:
        return self._client.transcribe(audio_path)


__all__ = ["OpenAIInsufficientQuotaError", "TranscriptionService"]
