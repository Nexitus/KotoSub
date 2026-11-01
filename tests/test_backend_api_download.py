"""Download route contract: token-only access to files registered by this process.

Covers the audit fix: GET /api/download must never read an arbitrary path
(?path=.env used to leak the config file through the Vite proxy).
"""
import asyncio
import json
import os
import tempfile
import unittest
from unittest import mock

import httpx

from app import gpu_guard, main


def call(method, url, **kwargs):
    """Routes through the real ASGI app (TestClient breaks on httpx 0.28)."""
    async def go():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, url, **kwargs)
    return asyncio.run(go())


def _events(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


class TestDownloadRoute(unittest.TestCase):
    def setUp(self):
        main._job_downloads.clear()
        gpu_guard._held = None
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "My_Clip_en.srt")
        with open(self.path, "wb") as f:
            f.write(b"1\n00:00:00,000 --> 00:00:01,000\nHello\n")
        self.token = main.register_job_output(self.path)

    def tearDown(self):
        main._job_downloads.clear()
        gpu_guard._held = None

    def test_registered_file_is_served_with_original_filename(self):
        with open(self.path, "rb") as f:
            expected = f.read()
        r = call("GET", "/api/download", params={"token": self.token})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, expected)
        self.assertIn('filename="My_Clip_en.srt"', r.headers["content-disposition"])

    def test_unknown_token_is_404(self):
        r = call("GET", "/api/download", params={"token": "0" * 32})
        self.assertEqual(r.status_code, 404)

    def test_registered_but_deleted_file_is_410(self):
        os.remove(self.path)
        r = call("GET", "/api/download", params={"token": self.token})
        self.assertEqual(r.status_code, 410)

    def test_missing_token_is_422(self):
        self.assertEqual(call("GET", "/api/download").status_code, 422)

    def test_legacy_path_query_never_serves_files(self):
        # The old attack shape: absolute/relative filesystem paths.
        for url in ("/api/download?path=.env", "/api/download?path=../../.env"):
            r = call("GET", url)
            self.assertEqual(r.status_code, 422)
            self.assertNotIn(b"HF_TOKEN", r.content)

    def test_token_traversal_is_just_a_miss(self):
        r = call("GET", "/api/download", params={"token": "../../.env"})
        self.assertEqual(r.status_code, 404)


class TestBatchCompletionRegistersDownloads(unittest.TestCase):
    def setUp(self):
        main._job_downloads.clear()
        gpu_guard._held = None
        self.dir = tempfile.mkdtemp()
        self.sub = os.path.join(self.dir, "out_en.srt")
        self.vid = os.path.join(self.dir, "out_en.mp4")
        with open(self.sub, "w", encoding="utf-8") as f:
            f.write("sub")
        with open(self.vid, "wb") as f:
            f.write(b"video")

    def tearDown(self):
        gpu_guard._held = None

    def _fake_process(self, **kwargs):
        return {
            "job_id": "job-1",
            "status": "completed",
            "output_file": self.sub,
            "video_output": self.vid,
            "duration": 1.0,
            "segments": 1,
            "transcription_meta": {"dropped_count": 0, "retry_regions": 0},
        }

    def test_completion_event_has_tokens_and_no_paths(self):
        with mock.patch.object(main.translator, "process", side_effect=self._fake_process):
            r = call("POST", "/api/translate_stream",
                     files={"video": ("My Clip.mp4", b"data", "video/mp4")},
                     data={"config": json.dumps({"targetLang": "en"})})
        self.assertEqual(r.status_code, 200)
        completed = [e for e in _events(r) if e["step"] == "completed"]
        self.assertEqual(len(completed), 1)
        result = completed[0]["result"]
        self.assertNotIn("output_file", result)
        self.assertNotIn("video_output", result)
        self.assertEqual(
            call("GET", "/api/download", params={"token": result["downloads"]["subtitle"]}).content,
            b"sub",
        )
        self.assertEqual(
            call("GET", "/api/download", params={"token": result["downloads"]["video"]}).content,
            b"video",
        )
        self.assertIsNone(gpu_guard.held_kind())

    def test_subtitle_only_completion_has_null_video_token(self):
        def fake(**kwargs):
            out = self._fake_process(**kwargs)
            out["video_output"] = None
            return out

        with mock.patch.object(main.translator, "process", side_effect=fake):
            r = call("POST", "/api/translate_stream",
                     files={"video": ("clip.mp4", b"data", "video/mp4")},
                     data={"config": json.dumps({})})
        result = [e for e in _events(r) if e["step"] == "completed"][0]["result"]
        self.assertIsNone(result["downloads"]["video"])
        self.assertEqual(
            call("GET", "/api/download", params={"token": result["downloads"]["subtitle"]}).status_code,
            200,
        )


if __name__ == "__main__":
    unittest.main()
