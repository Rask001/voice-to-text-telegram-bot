import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.db import create_session_factory
from app.formatters import format_share, format_voice_analysis
from app.models import UserSettings, VoiceNote
from app.tasks import normalize_tasks
from app.voice_analysis import (
    normalize_voice_analysis,
    parse_voice_analysis_json,
    serialize_voice_analysis,
    voice_type,
    water_class,
)
from app.voice_metrics_service import build_voice_analysis
from app.voice_metrics_service import (
    calculate_final_metrics,
    calculate_pre_metrics,
    sanitize_ai_meme_by_metrics,
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
        self.assertEqual(verbose["voice_type_level"], 8)
        self.assertEqual(voice_type(verbose["voice_type_level"]), "Аудиокнига")

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

        self.assertEqual(dry["water_level"], 2)
        self.assertEqual(water_class(dry["water_level"])[1], "Засуха — Воды почти нет.")
        self.assertEqual(wet["water_level"], 8)
        self.assertIn("Наводнение", water_class(wet["water_level"])[1])

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
        self.assertTrue(rendered.endswith("@voitext_bot"))

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
            bind = session_factory.kw.get("bind")
            if bind is not None:
                bind.dispose()

            self.assertEqual(restored["meme"], "Голосовое стало подкастом.")

    def test_total_saved_seconds_increases(self) -> None:
        user = UserSettings(telegram_user_id=1, total_saved_seconds=10)
        analysis = normalize_voice_analysis(
            {"meaningful_duration_seconds": 30},
            duration_seconds=100,
        )

        user.total_saved_seconds += analysis["saved_seconds"]

        self.assertEqual(user.total_saved_seconds, 80)

    def test_voice_metrics_are_calculated_locally(self) -> None:
        analysis = build_voice_analysis(
            transcript="короче надо купить молоко сыр хлеб и не забыть оплатить сервер",
            duration_seconds=180,
            summary="Купить продукты и оплатить сервер.",
            tasks=[
                {"text": "Купить молоко", "priority": False},
                {"text": "Оплатить сервер", "priority": True},
            ],
            details="Есть список покупок и важная оплата.",
            important_points=["Оплата сервера важна"],
            voice_analysis_text={
                "memorable_quote": "короче",
                "verdict": "Суть выжила после вступления.",
                "meme": "Голосовое могло быть списком, но выбрало драматургию.",
            },
        )

        self.assertEqual(analysis["duration_seconds"], 180)
        self.assertGreaterEqual(analysis["water_percent"], 0)
        self.assertLessEqual(analysis["water_percent"], 95)
        self.assertEqual(
            analysis["saved_seconds"],
            analysis["duration_seconds"] - analysis["meaningful_duration_seconds"],
        )
        self.assertIn("word_count", analysis)
        self.assertIn("compression_ratio", analysis)
        self.assertEqual(analysis["memorable_quote"], "короче")
        self.assertEqual(analysis["verdict"], "Суть выжила после вступления.")
        self.assertIn("драматургию", analysis["meme"])

    def test_wordiness_for_short_dense_message_is_capped(self) -> None:
        metrics = calculate_pre_metrics(" ".join(["слово"] * 40), duration_seconds=18)

        self.assertLessEqual(metrics["wordiness_score"], 2.0)

    def test_wordiness_for_long_dense_message_is_high(self) -> None:
        metrics = calculate_pre_metrics(" ".join(["слово"] * 800), duration_seconds=300)

        self.assertGreaterEqual(metrics["wordiness_score"], 8.0)

    def test_wordiness_for_long_sparse_message_is_not_high(self) -> None:
        metrics = calculate_pre_metrics(" ".join(["слово"] * 80), duration_seconds=300)

        self.assertLessEqual(metrics["wordiness_score"], 2.5)

    def test_water_for_short_message_is_capped(self) -> None:
        metrics = calculate_final_metrics(
            transcription=" ".join(["слово"] * 40),
            duration_seconds=18,
            summary="короткая суть",
            tasks=[],
            details="",
            important_points=[],
        )

        self.assertLessEqual(metrics["water_percent"], 25)
        self.assertEqual(metrics["meaningful_duration_seconds"], 18)

    def test_water_is_based_on_compression_ratio(self) -> None:
        metrics = calculate_final_metrics(
            transcription=" ".join(["слово"] * 200),
            duration_seconds=180,
            summary=" ".join(["суть"] * 40),
            tasks=[],
            details="",
            important_points=[],
        )

        self.assertAlmostEqual(metrics["compression_ratio"], 0.2, places=2)
        self.assertEqual(metrics["water_percent"], 80)

    def test_useful_text_does_not_include_transcription_and_details_are_weighted(self) -> None:
        metrics = calculate_final_metrics(
            transcription=" ".join(["исходник"] * 100),
            duration_seconds=120,
            summary="",
            tasks=[],
            details=" ".join(["подробность"] * 100),
            important_points=[],
        )

        self.assertEqual(metrics["useful_word_count"], 25.0)
        self.assertAlmostEqual(metrics["compression_ratio"], 0.25, places=2)

    def test_meaningful_duration_and_saved_seconds_are_safe(self) -> None:
        metrics = calculate_final_metrics(
            transcription=" ".join(["слово"] * 10),
            duration_seconds=20,
            summary=" ".join(["суть"] * 100),
            tasks=[],
            details="",
            important_points=[],
        )

        self.assertLessEqual(metrics["meaningful_duration_seconds"], metrics["duration_seconds"])
        self.assertGreaterEqual(metrics["saved_seconds"], 0)

    def test_voice_type_is_capped_for_short_messages(self) -> None:
        short = calculate_final_metrics(
            transcription=" ".join(["слово"] * 40),
            duration_seconds=18,
            summary="суть",
            tasks=[],
            details="",
            important_points=[],
        )
        under_minute = calculate_final_metrics(
            transcription=" ".join(["слово"] * 120),
            duration_seconds=50,
            summary="суть",
            tasks=[],
            details="",
            important_points=[],
        )

        self.assertLessEqual(short["voice_type_level"], 2)
        self.assertLessEqual(under_minute["voice_type_level"], 3)

    def test_quality_for_short_dry_message_is_high(self) -> None:
        metrics = calculate_final_metrics(
            transcription="проверить бота",
            duration_seconds=10,
            summary="Проверить бота.",
            tasks=[{"text": "Проверить бота", "priority": False}],
            details="",
            important_points=[],
        )

        self.assertGreaterEqual(metrics["quality_score"], 8.0)

    def test_consistency_replaces_low_water_conflict(self) -> None:
        metrics = {
            "duration_seconds": 20,
            "water_percent": 10,
            "wordiness_score": 1.5,
            "quality_score": 9.0,
        }

        verdict, meme = sanitize_ai_meme_by_metrics(
            verdict="Тут много воды и почти аудиокнига.",
            meme="Голосовое стало подкастом.",
            metrics=metrics,
        )

        self.assertIn("коротко", verdict)
        self.assertNotIn("подкаст", meme.lower())

    def test_consistency_replaces_short_duration_conflict(self) -> None:
        metrics = {
            "duration_seconds": 18,
            "water_percent": 30,
            "wordiness_score": 2.5,
            "quality_score": 8.0,
        }

        _, meme = sanitize_ai_meme_by_metrics(
            verdict="Нормально.",
            meme="Это длинное голосовое внезапно стало сериалом.",
            metrics=metrics,
        )

        self.assertNotIn("сериал", meme.lower())

    def test_consistency_replaces_bad_verdict_for_high_quality(self) -> None:
        metrics = {
            "duration_seconds": 20,
            "water_percent": 10,
            "wordiness_score": 1.5,
            "quality_score": 9.0,
        }

        verdict, _ = sanitize_ai_meme_by_metrics(
            verdict="Сообщение плохое и водянистое.",
            meme="Коротко.",
            metrics=metrics,
        )

        self.assertNotIn("плох", verdict.lower())


if __name__ == "__main__":
    unittest.main()
