"""Model download failure contract: a helper returning False must surface.

Covers the audit fix: the worker used to ignore helper return values and report
"Download finished" with error: None after partial failures.
"""
import tempfile
import unittest
from unittest import mock

import download_models

from app import main


def _fresh_state():
    main.model_download_state.clear()
    main.model_download_state.update(
        {"active": True, "kind": "all", "logs": [], "error": None,
         "failed": [], "finished": False}
    )


FAKE_LLMS = [
    {"label": "Model One", "file": "one.gguf"},
    {"label": "Model Two", "file": "two.gguf"},
]


class TestRunModelDownloads(unittest.TestCase):
    def setUp(self):
        _fresh_state()
        self.models_dir = tempfile.mkdtemp()
        self._patches = [
            mock.patch.object(main.settings, "MODELS_DIR", self.models_dir),
            mock.patch.object(download_models, "LLM_MODELS", FAKE_LLMS),
            mock.patch.object(download_models, "WHISPER_MODELS", ["w1"]),
            mock.patch.object(download_models, "QWEN_ASR", {"label": "Qwen Test"}),
            mock.patch.object(main, "_whisper_installed", return_value=False),
            mock.patch.object(download_models, "qwen_asr_installed", return_value=False),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()

    def test_partial_failure_is_recorded(self):
        with mock.patch.object(download_models, "download_llm_model",
                               side_effect=lambda m: m["file"] != "one.gguf"), \
             mock.patch.object(download_models, "download_whisper_model", return_value=True), \
             mock.patch.object(download_models, "download_qwen_asr_model", return_value=True):
            main._run_model_downloads("all")

        state = main.model_download_state
        self.assertEqual(state["failed"], ["Model One"])
        self.assertEqual(state["error"], "Failed to download: Model One")
        self.assertTrue(state["finished"])
        self.assertFalse(state["active"])
        self.assertNotIn("✅ Download finished", state["logs"])
        self.assertIn("❌ Failed: Model One", state["logs"])
        self.assertTrue(any("1 failure(s)" in line for line in state["logs"]))

    def test_all_success_clears_error(self):
        with mock.patch.object(download_models, "download_llm_model", return_value=True), \
             mock.patch.object(download_models, "download_whisper_model", return_value=True), \
             mock.patch.object(download_models, "download_qwen_asr_model", return_value=True):
            main._run_model_downloads("all")

        state = main.model_download_state
        self.assertEqual(state["failed"], [])
        self.assertIsNone(state["error"])
        self.assertIn("✅ Download finished", state["logs"])

    def test_qwen_failure_names_its_label(self):
        with mock.patch.object(download_models, "download_qwen_asr_model", return_value=False):
            main._run_model_downloads("qwen")

        self.assertEqual(main.model_download_state["failed"], ["Qwen Test"])
        self.assertEqual(main.model_download_state["error"],
                         "Failed to download: Qwen Test")

    def test_helper_exception_reports_error_and_finishes(self):
        with mock.patch.object(download_models, "download_llm_model",
                               side_effect=RuntimeError("network down")):
            main._run_model_downloads("llm")

        state = main.model_download_state
        self.assertEqual(state["error"], "network down")
        self.assertTrue(state["finished"])
        self.assertFalse(state["active"])


class TestDownloadStateReset(unittest.TestCase):
    def test_start_clears_previous_error_and_failures(self):
        main.model_download_state.update(
            {"active": False, "kind": "llm", "logs": ["old"],
             "error": "old error", "failed": ["Old Model"], "finished": True}
        )
        with mock.patch.object(main, "_run_model_downloads") as runner:
            out = main.start_model_downloads(main.ModelDownloadRequest(kind="llm"))
        self.assertTrue(out["started"])
        self.assertEqual(main.model_download_state["failed"], [])
        self.assertIsNone(main.model_download_state["error"])
        self.assertTrue(main.model_download_state["active"])
        runner.assert_called_once_with("llm")


if __name__ == "__main__":
    unittest.main()
