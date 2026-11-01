import unittest
from app.processors.translation import TranslationService


class TestNumberedParsing(unittest.TestCase):
    """Audit item 9: the response numbers decide placement, not response order."""

    def setUp(self):
        self.svc = TranslationService.__new__(TranslationService)

    def test_out_of_order_restored_to_input_order(self):
        self.assertEqual(
            self.svc._parse_numbered_lines("2. Second\n1. First", 2),
            ["First", "Second"],
        )

    def test_unnumbered_prose_rejected(self):
        self.assertIsNone(
            self.svc._parse_numbered_lines("It changed\n12:30 is the meeting time.", 1)
        )

    def test_preamble_rejected(self):
        self.assertIsNone(
            self.svc._parse_numbered_lines(
                "Here are the translations:\n1. First\n2. Second", 2
            )
        )

    def test_duplicate_number_rejected(self):
        self.assertIsNone(self.svc._parse_numbered_lines("1. First\n1. Again", 2))

    def test_out_of_range_rejected(self):
        self.assertIsNone(self.svc._parse_numbered_lines("0. First", 1))
        self.assertIsNone(self.svc._parse_numbered_lines("1. First\n3. Third", 2))

    def test_missing_number_rejected(self):
        self.assertIsNone(self.svc._parse_numbered_lines("1. First", 2))

    def test_empty_text_rejected(self):
        self.assertIsNone(self.svc._parse_numbered_lines("3. ", 3))

    def test_leading_number_in_content_preserved(self):
        self.assertEqual(
            self.svc._parse_numbered_lines("1. 12:30 is the meeting time.", 1),
            ["12:30 is the meeting time."],
        )

    def test_separator_variants_and_blank_lines(self):
        self.assertEqual(
            self.svc._parse_numbered_lines("1) First\n\n2: Second", 2),
            ["First", "Second"],
        )
        self.assertEqual(
            self.svc._parse_numbered_lines("１．First\n２：Second", 2),
            ["First", "Second"],
        )

    def test_happy_path(self):
        self.assertEqual(self.svc._parse_numbered_lines("1. Hello", 1), ["Hello"])
        self.assertEqual(
            self.svc._parse_numbered_lines("1. One\n2. Two\n3. Three", 3),
            ["One", "Two", "Three"],
        )


class TestCleanTranslation(unittest.TestCase):
    """Audit item 10: only <think> wrappers and whitespace are touched."""

    def setUp(self):
        self.svc = TranslationService.__new__(TranslationService)

    def test_legitimate_translated_by_kept(self):
        self.assertEqual(
            self.svc._clean_translation("This was translated by my mother."),
            "This was translated by my mother.",
        )

    def test_leading_time_not_mangled(self):
        self.assertEqual(
            self.svc._clean_translation("12:30 is the meeting time."),
            "12:30 is the meeting time.",
        )

    def test_think_tags_removed(self):
        self.assertEqual(
            self.svc._clean_translation("<think>draft reasoning</think>Hello there"),
            "Hello there",
        )
        self.assertEqual(
            self.svc._clean_translation("<THINK>x</THINK>\n\nHi"), "Hi"
        )

    def test_lines_joined(self):
        self.assertEqual(
            self.svc._clean_translation("line one\n\nline two"), "line one line two"
        )

    def test_label_kept(self):
        self.assertEqual(self.svc._clean_translation("Translation: hello"), "Translation: hello")


if __name__ == "__main__":
    unittest.main()
