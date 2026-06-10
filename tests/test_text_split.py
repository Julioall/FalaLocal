from __future__ import annotations

import unittest

from kokoro_ptbr_desktop.engine import KOKORO_VOICES, split_text_for_generation


class SplitTextForGenerationTests(unittest.TestCase):
    def test_empty_text_returns_no_chunks(self) -> None:
        self.assertEqual(split_text_for_generation("   "), [])

    def test_short_text_returns_one_chunk(self) -> None:
        self.assertEqual(split_text_for_generation("Ola do Kokoro.", 120), ["Ola do Kokoro."])

    def test_long_text_keeps_chunks_under_limit(self) -> None:
        text = " ".join(["This is a local text to speech sentence."] * 30)
        chunks = split_text_for_generation(text, 180)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 180 for chunk in chunks))

    def test_long_word_is_split(self) -> None:
        text = "a" * 250
        chunks = split_text_for_generation(text, 120)
        self.assertEqual([len(chunk) for chunk in chunks], [120, 120, 10])

    def test_kokoro_ptbr_voices_are_available(self) -> None:
        self.assertEqual(set(KOKORO_VOICES), {"pf_dora", "pm_alex", "pm_santa"})


if __name__ == "__main__":
    unittest.main()
