import tempfile
import unittest
from pathlib import Path

from autopilot.captions import _chunks, _stamp
from autopilot.pipeline import Autopilot
from autopilot.thumbnail import _wrap, generate_thumbnail

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Autopilot(Path(self.temp.name) / "jobs.sqlite3")
        self.brief = {"topic": "Open-source AI", "title": "Five Open-Source AI Tools",
                      "script": " ".join(["This is a useful sentence."] * 450),
                      "narration": str(Path(self.temp.name) / "missing.wav"),
                      "assets": [str(Path(self.temp.name) / "still.jpg")]}
        self.app.create_job(self.brief, "production-test")

    def test_srt_timestamp_format(self):
        self.assertEqual(_stamp(65.432), "00:01:05,432")

    def test_caption_chunks_cover_script_words(self):
        script = "One two three. Four five six seven eight nine ten eleven."
        chunks = _chunks(script, max_words=5)
        self.assertEqual(" ".join(chunks).split(), script.split())
        self.assertTrue(all(len(chunk.split()) <= 5 for chunk in chunks))

    def test_thumbnail_wrap_caps_lines(self):
        lines = _wrap("A very long title for a useful open source AI video", 12, 3)
        self.assertLessEqual(len(lines), 3)
        self.assertTrue(lines[-1].endswith("…"))

    def test_thumbnail_writes_svg(self):
        target = generate_thumbnail(self.app, "production-test", str(Path(self.temp.name) / "thumb.svg"))
        data = target.read_text(encoding="utf-8")
        self.assertIn('width="1280" height="720"', data)
        self.assertIn("Five Open-Source AI", data)
        self.assertIn("Tools", data)

if __name__ == "__main__":
    unittest.main()
