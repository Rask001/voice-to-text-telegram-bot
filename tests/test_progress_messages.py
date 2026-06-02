import unittest
from unittest.mock import patch

from app import progress_messages


class ProgressMessagesTests(unittest.TestCase):
    def test_all_ordinary_progress_packs_have_eight_messages(self) -> None:
        self.assertGreaterEqual(progress_messages.PROGRESS_UPDATE_INTERVAL_SECONDS, 1.5)
        self.assertLessEqual(progress_messages.PROGRESS_UPDATE_INTERVAL_SECONDS, 2.0)
        self.assertEqual(len(progress_messages.ORDINARY_PROGRESS_PACKS), 24)
        for pack in progress_messages.ORDINARY_PROGRESS_PACKS:
            self.assertEqual(len(pack), 8)
            self.assertEqual(pack[0], "🎧 Голосовое получил")
            self.assertTrue(all(message.strip() for message in pack))

    def test_all_legendary_progress_packs_have_eight_messages(self) -> None:
        self.assertEqual(len(progress_messages.LEGENDARY_PROGRESS_PACKS), 5)
        for pack in progress_messages.LEGENDARY_PROGRESS_PACKS:
            self.assertEqual(len(pack), 8)
            self.assertEqual(pack[0], "🎧 Голосовое получил")
            self.assertTrue(all(message.strip() for message in pack))

    def test_random_progress_pack_returns_ordinary_pack_by_default(self) -> None:
        first_pack = progress_messages.ORDINARY_PROGRESS_PACKS[0]
        with patch("app.progress_messages.random.choice", return_value=first_pack):
            self.assertEqual(progress_messages.get_random_progress_pack(), first_pack)

    def test_random_progress_pack_supports_legendary_packs(self) -> None:
        legendary_pack = (
            "🎧 Голосовое получил",
            "🌟 Легендарный этап 1",
            "🌟 Легендарный этап 2",
            "🌟 Легендарный этап 3",
            "🌟 Легендарный этап 4",
            "🌟 Легендарный этап 5",
            "🌟 Легендарный этап 6",
            "🌟 Легендарный этап 7",
        )
        with (
            patch("app.progress_messages.LEGENDARY_PROGRESS_PACKS", (legendary_pack,)),
            patch("app.progress_messages.random.random", return_value=0.01),
            patch("app.progress_messages.random.choice", return_value=legendary_pack),
        ):
            self.assertEqual(progress_messages.get_random_progress_pack(), legendary_pack)

    def test_validate_progress_packs_rejects_wrong_size(self) -> None:
        with self.assertRaises(ValueError):
            progress_messages.validate_progress_packs([("too short",)])


if __name__ == "__main__":
    unittest.main()
