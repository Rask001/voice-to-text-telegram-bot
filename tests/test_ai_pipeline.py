import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.db import create_session_factory
from app.handlers.voice import _save_transcription_without_analysis
from app.models import VoiceNote
from app.openai_service import OpenAIService
from app.text_analysis_service import TextAnalysisError, TextAnalysisService
from app.transcription_service import TranscriptionService
from app.voice_analysis import parse_voice_analysis_json
from app.voice_metrics_service import build_voice_analysis


class FakeTranscriptionClient:
    def __init__(self) -> None:
        self.audio_path = None

    def transcribe(self, audio_path: Path) -> str:
        self.audio_path = audio_path
        return "дословная расшифровка"


class FakeDeepSeekClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.system_prompt = ""
        self.user_prompt = ""

    def analyze_text(self, system_prompt: str, user_prompt: str) -> str:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.response


class AIPipelineTests(unittest.TestCase):
    def test_openai_transcription_service_returns_only_text(self) -> None:
        client = FakeTranscriptionClient()
        service = TranscriptionService(client)
        audio_path = Path("voice.mp3")

        text = service.transcribe(audio_path)

        self.assertEqual(text, "дословная расшифровка")
        self.assertEqual(client.audio_path, audio_path)

    def test_deepseek_analysis_service_gets_text_and_returns_json(self) -> None:
        client = FakeDeepSeekClient(
            """
            {
              "title": "Проверка бота",
              "summary": "Нужно проверить бота.",
              "tasks": [{"text": "Проверить бота", "priority": true}],
              "details": "Проверить локальный запуск.",
              "important_points": ["Без OpenAI анализа"],
              "voice_analysis": {
                "memorable_quote": "короче",
                "verdict": "Смысл найден.",
                "meme": "Голосовое притворилось задачником."
              }
            }
            """
        )
        service = TextAnalysisService(client)

        result = service.analyze("короче нужно проверить бота")

        self.assertEqual(result["title"], "Проверка бота")
        self.assertEqual(result["summary"], "Нужно проверить бота.")
        self.assertEqual(result["action_items"][0]["text"], "Проверить бота")
        self.assertTrue(result["action_items"][0]["priority"])
        self.assertIn("короче нужно проверить бота", client.user_prompt)
        prompt = client.system_prompt + "\n" + client.user_prompt
        self.assertIn("жёсткий сарказм", prompt)
        self.assertIn("бей по формату сообщения, а не по человеку", prompt)
        self.assertNotIn("water_percent", prompt)
        self.assertNotIn("wordiness_score", prompt)
        self.assertNotIn("quality_score", prompt)
        self.assertNotIn("voice_type_level", prompt)
        self.assertNotIn("saved_seconds", prompt)

    def test_openai_service_has_no_text_analysis_method(self) -> None:
        self.assertFalse(hasattr(OpenAIService, "analyze"))

    def test_deepseek_invalid_json_raises_text_analysis_error(self) -> None:
        service = TextAnalysisService(FakeDeepSeekClient("не json"))

        with self.assertLogs("app.text_analysis_service", level="WARNING"):
            with self.assertRaises(TextAnalysisError):
                service.analyze("текст")

    def test_voice_metrics_calculate_water_and_saved_seconds_locally(self) -> None:
        analysis = build_voice_analysis(
            transcript=" ".join(["слово"] * 120),
            duration_seconds=300,
            summary="Краткая суть.",
            tasks=[],
            details="Одна полезная мысль.",
            important_points=[],
            voice_analysis_text={"meme": "Голосовое выбрало длинную дорогу."},
        )

        self.assertGreater(analysis["water_percent"], 0)
        self.assertEqual(
            analysis["saved_seconds"],
            analysis["duration_seconds"] - analysis["meaningful_duration_seconds"],
        )
        self.assertGreaterEqual(analysis["wordiness_score"], 1)

    def test_deepseek_failure_can_save_full_text_without_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = Settings(
                telegram_bot_token="test-token",
                openai_api_key="test-key",
                database_url=f"sqlite:///{Path(tmpdir) / 'fallback.db'}",
            )
            session_factory = create_session_factory(settings)

            note_id = _save_transcription_without_analysis(
                session_factory=session_factory,
                user_id=123,
                username="tester",
                settings=settings,
                telegram_file_id="file-id",
                duration_seconds=60,
                transcript="полный дословный текст",
            )

            with session_factory() as session:
                note = session.get(VoiceNote, note_id)
            bind = session_factory.kw.get("bind")
            if bind is not None:
                bind.dispose()

            self.assertIsNotNone(note)
            self.assertEqual(note.transcript, "полный дословный текст")
            self.assertEqual(note.summary, "Анализ временно недоступен.")
            restored = parse_voice_analysis_json(
                note.voice_analysis_json,
                note.duration_seconds,
            )
            self.assertEqual(restored["duration_seconds"], 60)


if __name__ == "__main__":
    unittest.main()
