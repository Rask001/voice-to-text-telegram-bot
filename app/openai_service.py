from app.ai_clients.openai_client import (
    OpenAIInsufficientQuotaError,
    OpenAITranscriptionClient,
)
from app.config import Settings
from app.transcription_service import TranscriptionService


class OpenAIService(TranscriptionService):
    """Backward-compatible alias for OpenAI transcription only."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(OpenAITranscriptionClient(settings))
