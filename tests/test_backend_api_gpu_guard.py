"""GPU admission contract: one job at a time across batch and live modes.

Covers C1 (app/gpu_guard.py) and the 409/202 behavior of the routes that
acquire and release the single GPU slot.
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


class TestGuard(unittest.TestCase):
    def setUp(self):
        gpu_guard._held = None

    def tearDown(self):
        gpu_guard._held = None

    def test_acquire_is_exclusive_across_kinds(self):
        self.assertTrue(gpu_guard.try_acquire("batch"))
        self.assertFalse(gpu_guard.try_acquire("batch"))
        self.assertFalse(gpu_guard.try_acquire("live"))
        self.assertEqual(gpu_guard.held_kind(), "batch")
        gpu_guard.release("batch")
        self.assertIsNone(gpu_guard.held_kind())
        self.assertTrue(gpu_guard.try_acquire("live"))

    def test_release_by_wrong_owner_raises(self):
        gpu_guard.try_acquire("live")
        with self.assertRaises(RuntimeError):
            gpu_guard.release("batch")
        self.assertEqual(gpu_guard.held_kind(), "live")

    def test_release_when_free_raises(self):
        with self.assertRaises(RuntimeError):
            gpu_guard.release("batch")

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            gpu_guard.try_acquire("nope")
        gpu_guard.try_acquire("batch")
        with self.assertRaises(ValueError):
            gpu_guard.release("nope")


class _FakeEngine:
    def __init__(self, stopped):
        self._stopped = stopped
        self.hls_dir = None

    def stop(self):
        return self._stopped


class TestBatchRouteAdmission(unittest.TestCase):
    def setUp(self):
        gpu_guard._held = None
        main.live_sessions.clear()

    def tearDown(self):
        gpu_guard._held = None
        main.live_sessions.clear()

    def _post(self):
        return call("POST", "/api/translate_stream",
                    files={"video": ("clip.mp4", b"data", "video/mp4")},
                    data={"config": json.dumps({})})

    def test_busy_with_batch_returns_409_before_touching_disk(self):
        gpu_guard.try_acquire("batch")
        # NamedTemporaryFile is called as main.tempfile.NamedTemporaryFile; the
        # module object is shared, so patch it at that attribute.
        with mock.patch.object(main.tempfile, "NamedTemporaryFile") as ntf:
            r = self._post()
        self.assertEqual(r.status_code, 409)
        self.assertIn("full-video", r.json()["detail"])
        self.assertFalse(ntf.called)

    def test_busy_with_live_returns_409(self):
        gpu_guard.try_acquire("live")
        r = self._post()
        self.assertEqual(r.status_code, 409)
        self.assertIn("live", r.json()["detail"])

    def test_live_start_busy_with_batch_returns_409(self):
        gpu_guard.try_acquire("batch")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            video_path = tmp.name
        try:
            r = call("POST", "/api/live/start", json={"video_path": video_path})
        finally:
            os.remove(video_path)
        self.assertEqual(r.status_code, 409)
        self.assertIn("full-video", r.json()["detail"])
        self.assertEqual(gpu_guard.held_kind(), "batch")

    def test_failed_batch_releases_slot_and_emits_error_event(self):
        with mock.patch.object(main.translator, "process", side_effect=RuntimeError("boom")):
            r = self._post()
        events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
        errors = [e for e in events if e["step"] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["status"], "error")
        self.assertEqual(errors[0]["progress"], 0)
        self.assertEqual(errors[0]["message"], "boom")
        self.assertIsNone(gpu_guard.held_kind())


class TestLiveStopAdmission(unittest.TestCase):
    def setUp(self):
        gpu_guard._held = None
        main.live_sessions.clear()

    def tearDown(self):
        gpu_guard._held = None
        main.live_sessions.clear()

    def _session(self, stopped):
        sid = "s1"
        main.live_sessions[sid] = {
            "engine": _FakeEngine(stopped),
            "remuxed_path": None,
            "temp_upload_path": None,
            "last_segment_count": 0,
            "srt_download_token": "tok",
        }
        return sid

    def test_worker_still_alive_returns_202_and_keeps_slot(self):
        sid = self._session(stopped=False)
        gpu_guard.try_acquire("live")
        r = call("POST", f"/api/live/stop/{sid}")
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json(), {"status": "stopping"})
        self.assertIn(sid, main.live_sessions)
        self.assertEqual(gpu_guard.held_kind(), "live")

    def test_stopped_worker_returns_200_frees_slot_and_forgets_session(self):
        sid = self._session(stopped=True)
        gpu_guard.try_acquire("live")
        r = call("POST", f"/api/live/stop/{sid}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "stopped", "srt_download_token": "tok"})
        self.assertNotIn(sid, main.live_sessions)
        self.assertIsNone(gpu_guard.held_kind())

    def test_retry_after_stopping_cleans_up(self):
        sid = self._session(stopped=False)
        gpu_guard.try_acquire("live")
        self.assertEqual(call("POST", f"/api/live/stop/{sid}").status_code, 202)
        main.live_sessions[sid]["engine"] = _FakeEngine(stopped=True)
        r = call("POST", f"/api/live/stop/{sid}")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(sid, main.live_sessions)
        self.assertIsNone(gpu_guard.held_kind())

    def test_unknown_session_is_404(self):
        self.assertEqual(call("POST", "/api/live/stop/nope").status_code, 404)


if __name__ == "__main__":
    unittest.main()
