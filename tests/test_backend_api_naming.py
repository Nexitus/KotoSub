"""Output naming contract: sanitized original upload basename + C3 suffix fields.

The temp upload filename must never reach an exported file name.
"""
import asyncio
import json
import unittest
from unittest import mock

import httpx

from app import gpu_guard, main
from app.core import _output_filename


def call(method, url, **kwargs):
    """Routes through the real ASGI app (TestClient breaks on httpx 0.28)."""
    async def go():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, url, **kwargs)
    return asyncio.run(go())


class TestSanitizeBasename(unittest.TestCase):
    def test_plain_name(self):
        self.assertEqual(main._sanitize_basename("My Clip.mp4"), "My_Clip")
        self.assertEqual(main._sanitize_basename("holiday-2024_final.mkv"), "holiday-2024_final")

    def test_windows_path_and_unsafe_chars(self):
        self.assertEqual(
            main._sanitize_basename("C:\\Users\\me\\My Video #2!.mp4"),
            "My_Video_2",
        )

    def test_traversal_cannot_survive(self):
        self.assertEqual(main._sanitize_basename("../../.env"), "env")
        self.assertNotIn("/", main._sanitize_basename("../../etc/passwd"))

    def test_non_ascii_falls_back(self):
        self.assertEqual(main._sanitize_basename("日本語動画.mp4"), "video")

    def test_empty_or_unusable_falls_back(self):
        self.assertEqual(main._sanitize_basename(""), "video")
        self.assertEqual(main._sanitize_basename("   "), "video")
        self.assertEqual(main._sanitize_basename(None), "video")


class TestOutputFilename(unittest.TestCase):
    def test_default_suffix_and_language(self):
        self.assertEqual(_output_filename("clip", "_translated", True, "en", "srt"),
                         "clip_translated_en.srt")

    def test_empty_suffix_keeps_language(self):
        self.assertEqual(_output_filename("clip", "", True, "en", "srt"), "clip_en.srt")

    def test_empty_suffix_without_language(self):
        self.assertEqual(_output_filename("clip", "", False, "en", "srt"), "clip.srt")

    def test_suffix_without_language(self):
        self.assertEqual(_output_filename("clip", "_translated", False, "en", "srt"),
                         "clip_translated.srt")

    def test_language_only(self):
        self.assertEqual(_output_filename("clip", "", True, "ja", "ass"), "clip_ja.ass")


class TestTranslateStreamForwarding(unittest.TestCase):
    def setUp(self):
        gpu_guard._held = None

    def tearDown(self):
        gpu_guard._held = None

    def _capture(self, config):
        captured = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return {"output_file": "out.srt", "video_output": None}

        with mock.patch.object(main.translator, "process", side_effect=fake):
            r = call("POST", "/api/translate_stream",
                     files={"video": ("My Clip.mp4", b"data", "video/mp4")},
                     data={"config": json.dumps(config)})
        self.assertEqual(r.status_code, 200)
        return captured

    def test_sanitized_basename_reaches_pipeline(self):
        captured = self._capture({"outputSuffix": "_subs", "includeLanguageInName": False})
        self.assertEqual(captured["output_basename"], "My_Clip")
        self.assertEqual(captured["output_suffix"], "_subs")
        self.assertFalse(captured["include_language_in_name"])

    def test_empty_suffix_is_honored(self):
        captured = self._capture({"outputSuffix": "", "includeLanguageInName": True})
        self.assertEqual(captured["output_suffix"], "")


if __name__ == "__main__":
    unittest.main()
