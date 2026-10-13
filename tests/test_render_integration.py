import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from autopilot.pipeline import Autopilot
from autopilot.renderer import render_video

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/ffprobe not installed")
class RenderIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audio = self.root / "narration.wav"
        self.visual = self.root / "visual.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=2", "-c:a", "pcm_s16le", str(self.audio)],
                       check=True, timeout=60)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=blue:s=320x240:r=15:d=2", "-an", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", str(self.visual)], check=True, timeout=60)
        script = " ".join(["A careful explanation for integration testing."] * 450)
        brief = {"topic": "Renderer integration test", "title": "Local Render Test",
                 "script": script, "narration": str(self.audio), "assets": [str(self.visual)],
                 "output": str(self.root / "rendered.mp4")}
        self.app = Autopilot(self.root / "jobs.sqlite3")
        self.app.create_job(brief, "render-integration")

    def test_render_creates_valid_mp4_with_video_and_audio(self):
        output = render_video(self.app, "render-integration")
        self.assertTrue(output.is_file())
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "stream=codec_type,width,height", "-of", "csv=p=0",
                                str(output)], capture_output=True, text=True, check=True, timeout=30)
        self.assertIn("video", probe.stdout)
        self.assertIn("audio", probe.stdout)
        self.assertIn("1920", probe.stdout)
        self.assertEqual(self.app.status("render-integration")[0]["status"], "rendered")

if __name__ == "__main__":
    unittest.main()
