import json
import tempfile
import unittest
from pathlib import Path

from autopilot.pipeline import Autopilot


def valid_brief():
    # 1,350 words gives an 9-minute estimate at 150 words per minute.
    script = " ".join(["Carefully researched narration."] * 450)
    return {"topic": "Testing", "title": "A Test Video", "description": "Sources to be added.",
            "script": script, "narration": "media/narration.wav",
            "assets": ["media/still.jpg"]}


class AutopilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Autopilot(Path(self.temp.name) / "jobs.sqlite3")

    def test_valid_brief_targets_long_form(self):
        report = self.app.validate_brief(valid_brief(), strict_runtime=True)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["estimated_minutes"], 9.0)

    def test_short_script_is_warning_then_strict_error(self):
        brief = valid_brief()
        brief["script"] = "Only a short script."
        self.assertTrue(self.app.validate_brief(brief)["ok"])
        self.assertFalse(self.app.validate_brief(brief, strict_runtime=True)["ok"])

    def test_job_persists_and_idempotent_id_does_not_duplicate(self):
        brief = valid_brief()
        self.assertEqual(self.app.create_job(brief, "stable-job"), "stable-job")
        self.assertEqual(self.app.create_job(brief, "stable-job"), "stable-job")
        self.assertEqual(len(self.app.status()), 1)
        self.assertEqual(self.app.status("stable-job")[0]["status"], "planned")

    def test_missing_required_fields_block_job(self):
        report = self.app.validate_brief({"topic": "Missing fields"})
        self.assertFalse(report["ok"])
        self.assertIn("'title' is required and must be a non-empty string", report["errors"])

    def test_upload_is_off_by_default(self):
        brief = valid_brief()
        self.app.create_job(brief, "upload-job")
        with self.assertRaisesRegex(RuntimeError, "Upload is disabled"):
            self.app.upload_private("upload-job")


if __name__ == "__main__":
    unittest.main()
