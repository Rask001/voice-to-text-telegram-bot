import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.config import Settings
from app.db import create_session_factory
from app.formatters import format_share, format_voice_analysis
from app.models import UserSettings, VoiceNote
from app.openai_service import OpenAIService
from app.tasks import normalize_tasks
from app.voice_analysis import (
    normalize_voice_analysis,
    parse_voice_analysis_json,
    serialize_voice_analysis,
    voice_type,
    water_class,
)


class VoiceAnalysisTests(unittest.TestCase):
    def test_voice_analysis_parses_openai_json(self) -> None:
        analysis = normalize_voice_analysis(
            {
                "meaningful_duration_seconds": 38,
                "water_percent": 87,
                "wordiness_score": 9.4,
                "quality_score": 3.2,
                "voice_type_level": 9,
                "water_level": 10,
                "verdict_level": 9,
                "memorable_quote": "Короче смотри",
                "verdict": "38 секунд пользы. Остальное было подготовкой к ним.",
                "meme": "Можно было написать “ок”, но автор выбрал формат аудиокниги.",
            },
            duration_seconds=402,
        )

        self.assertEqual(analysis["meaningful_duration_seconds"], 38)
        self.assertEqual(analysis["saved_seconds"], 364)
        self.assertEqual(analysis["meme"], "Можно было написать “ок”, но автор выбрал формат аудиокниги.")

    def test_old_record_without_voice_analysis_uses_fallback(self) -> None:
        analysis = parse_voice_analysis_json("", duration_seconds=60)

        self.assertEqual(analysis["duration_seconds"], 60)
        self.assertEqual(analysis["saved_seconds"], 0)
        self.assertIn("старой записи", analysis["verdict"])

    def test_saved_seconds_never_negative(self) -> None:
        analysis = normalize_voice_analysis(
            {"meaningful_duration_seconds": 120},
            duration_seconds=60,
        )

        self.assertEqual(analysis["meaningful_duration_seconds"], 60)
        self.assertEqual(analysis["saved_seconds"], 0)

    def test_voice_type_is_consistent_with_wordiness(self) -> None:
        concise = normalize_voice_analysis(
            {
                "wordiness_score": 2.0,
                "voice_type_level": 8,
                "water_percent": 90,
            },
            duration_seconds=600,
        )
        verbose = normalize_voice_analysis(
            {
                "wordiness_score": 8.0,
                "voice_type_level": 2,
                "water_percent": 80,
            },
            duration_seconds=360,
        )

        self.assertLessEqual(concise["voice_type_level"], 3)
        self.assertIn(voice_type(concise["voice_type_level"]), {"Деловой человек", "По существу"})
        self.assertGreaterEqual(verbose["voice_type_level"], 8)
        self.assertNotEqual(voice_type(verbose["voice_type_level"]), "Подкастер")

    def test_water_level_is_consistent_with_water_percent(self) -> None:
        dry = normalize_voice_analysis(
            {
                "water_percent": 12,
                "water_level": 10,
            },
            duration_seconds=60,
        )
        wet = normalize_voice_analysis(
            {
                "water_percent": 87,
                "water_level": 1,
            },
            duration_seconds=60,
        )

        self.assertEqual(dry["water_level"], 1)
        self.assertEqual(water_class(dry["water_level"])[1], "Пустыня — Сухо и эффективно.")
        self.assertEqual(wet["water_level"], 9)
        self.assertIn("Атлантический океан", water_class(wet["water_level"])[1])

    def test_rare_title_only_for_high_water_or_wordiness(self) -> None:
        low = normalize_voice_analysis(
            {"water_percent": 20, "wordiness_score": 4, "rare_title": "🏆 Не должен"},
            duration_seconds=60,
        )
        high = normalize_voice_analysis(
            {"water_percent": 93, "wordiness_score": 8, "meme": "Очень длинно"},
            duration_seconds=60,
        )

        self.assertEqual(low["rare_title"], "")
        self.assertTrue(high["rare_title"])

    def test_formatter_outputs_voice_analysis(self) -> None:
        analysis = normalize_voice_analysis(
            {
                "meaningful_duration_seconds": 38,
                "water_percent": 87,
                "wordiness_score": 9.4,
                "quality_score": 3.2,
                "voice_type_level": 9,
                "water_level": 9,
                "verdict": "38 секунд пользы.",
                "meme": "Голосовое стало подкастом.",
            },
            duration_seconds=402,
        )

        rendered = format_voice_analysis(analysis, total_saved_seconds=1000)

        self.assertIn("📊 <b>Анализ голосового</b>", rendered)
        self.assertIn("Индекс воды: <b>87%</b>", rendered)
        self.assertIn("Режиссёрская версия", rendered)
        self.assertIn("Голосовое стало подкастом.", rendered)
        self.assertIn("\n😂\nГолосовое стало подкастом.", rendered)
        self.assertNotIn("Мем:", rendered)

    def test_share_block_contains_meme(self) -> None:
        analysis = normalize_voice_analysis(
            {
                "meaningful_duration_seconds": 38,
                "water_percent": 87,
                "voice_type_level": 9,
                "meme": "Можно было написать “ок”.",
            },
            duration_seconds=402,
        )

        rendered = format_share(
            "Короткое содержание",
            normalize_tasks([]),
            analysis,
        )

        self.assertIn("\n😂\nМожно было написать", rendered)
        self.assertNotIn("Мем:", rendered)
        self.assertIn("Можно было написать", rendered)
        self.assertIn("🎙Создано через: @voitext_bot", rendered)

    def test_toxic_meme_is_replaced(self) -> None:
        analysis = normalize_voice_analysis(
            {"meme": "Автор тупой и не умеет говорить"},
            duration_seconds=60,
        )

        self.assertNotIn("тупой", analysis["meme"].lower())
        self.assertIn("подкастом", analysis["meme"])

    def test_meme_is_saved_in_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = Settings(
                telegram_bot_token="test-token",
                openai_api_key="test-key",
                database_url=f"sqlite:///{Path(tmpdir) / 'voice_analysis.db'}",
            )
            session_factory = create_session_factory(settings)
            analysis = normalize_voice_analysis(
                {"meme": "Голосовое стало подкастом."},
                duration_seconds=60,
            )
            with session_factory() as session:
                note = VoiceNote(
                    telegram_user_id=1,
                    telegram_file_id="file",
                    duration_seconds=60,
                    transcript="text",
                    summary="summary",
                    action_items="[]",
                    voice_analysis_json=serialize_voice_analysis(analysis),
                )
                session.add(note)
                session.commit()

            with session_factory() as session:
                note = session.query(VoiceNote).one()
                restored = parse_voice_analysis_json(note.voice_analysis_json, note.duration_seconds)

            self.assertEqual(restored["meme"], "Голосовое стало подкастом.")

    def test_total_saved_seconds_increases(self) -> None:
        user = UserSettings(telegram_user_id=1, total_saved_seconds=10)
        analysis = normalize_voice_analysis(
            {"meaningful_duration_seconds": 30},
            duration_seconds=100,
        )

        user.total_saved_seconds += analysis["saved_seconds"]

        self.assertEqual(user.total_saved_seconds, 80)

    def test_openai_analyze_returns_voice_analysis_and_safe_prompt(self) -> None:
        captured = {}

        class FakeResponses:
            def create(self, model, input):
                captured["prompt"] = input
                return SimpleNamespace(
                    output_text=json.dumps(
                        {
                            "title": "Тест",
                            "summary": "Кратко",
                            "tasks": [],
                            "details": "Детали",
                            "important_points": [],
                            "voice_analysis": {
                                "meaningful_duration_seconds": 10,
                                "water_percent": 80,
                                "wordiness_score": 8,
                                "quality_score": 4,
                                "voice_type_level": 8,
                                "water_level": 8,
                                "verdict_level": 8,
                                "memorable_quote": "короче",
                                "verdict": "Суть нашлась.",
                                "meme": "Голосовое начиналось как сообщение, но стало подкастом.",
                            },
                        },
                        ensure_ascii=False,
                    )
                )

        service = OpenAIService.__new__(OpenAIService)
        service._client = SimpleNamespace(responses=FakeResponses())
        service._text_model = "test-model"
        service._with_rate_limit_retry = lambda request, label: request()

        result = service.analyze("короче надо проверить бота", duration_seconds=60)

        self.assertIn("voice_analysis", result)
        self.assertEqual(result["voice_analysis"]["saved_seconds"], 50)
        self.assertIn("жёсткий сарказм", captured["prompt"])
        self.assertIn("без бережной душнины", captured["prompt"])
        self.assertIn("бей по формату сообщения, а не по человеку", captured["prompt"])
        self.assertIn("Нельзя: оскорблять человека как личность", captured["prompt"])
        self.assertIn("Запрещено: унижения, личностные оскорбления", captured["prompt"])


if __name__ == "__main__":
    unittest.main()
