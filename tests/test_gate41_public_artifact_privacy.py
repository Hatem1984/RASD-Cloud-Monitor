"""Ensure public repo Actions never expose original Word or publisher JPEGs.

Encrypted owner-only ciphertext JSON is an explicitly separate gated flow.
Public metadata-only JSON manifests may continue as read-only audit artifacts.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"


class NoUnencryptedPublisherMediaArtifactsTests(unittest.TestCase):
    def test_no_action_uploads_plaintext_word_or_original_publisher_photos(self):
        for path in ROOT.glob("*.yml"):
            contents = path.read_text(encoding="utf-8")
            steps = re.findall(
                r"(?ms)^      - name: .*?(?=^      - (?:name:|uses:)|\\Z)",
                contents,
            )
            for step in steps:
                if "uses: actions/upload-artifact@" not in step:
                    continue
                with self.subTest(path=path.name):
                    path_field = re.search(r"(?m)^\s+path:\s*(.+)$", step)
                    self.assertIsNotNone(path_field)
                    uploaded = path_field.group(1).casefold()
                    self.assertFalse(any(token in uploaded for token in (
                        ".docx", ".jpg", ".jpeg", ".png", "evidence/capture",
                        "report-output", "proof-output/rasd-daily",
                    )), f"public unencrypted publisher media uploaded: {path.name}")

    def test_public_preview_and_capture_workflows_no_longer_upload_artifacts(self):
        for name in ("gate11-ci.yml", "report-manual.yml", "capture-manual.yml"):
            workflow = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("uses: actions/upload-artifact", workflow, name)


if __name__ == "__main__":
    unittest.main()
