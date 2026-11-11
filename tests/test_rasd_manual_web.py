"""Manual web button reuses RSS preview; never sends or claims photo proof."""
import json
import tempfile
import unittest
from pathlib import Path

from docx import Document
from rasd_manual_web import run_manual_web


class SeparateWebPreviewTest(unittest.TestCase):
    def test_web_preview_has_rasd_brand_and_never_uses_facebook(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "sources.json"
            config.write_text(json.dumps({"feeds": []}), encoding="utf-8")
            def fake_gather(value, *, now=None):
                self.assertEqual(value["feeds"], [])
                return {
                    "title": "OLD", "display_window_start": "أمس",
                    "display_window_end": "اليوم", "coverage": "HEALTHY",
                    "verified_links": 0, "window_article_count": 0,
                    "truncated": False, "article_limit": 15,
                    "articles": [], "sources": [],
                    "limitations": "نتائج RSS فقط",
                }
            result = run_manual_web(
                Path(directory) / "web",
                gather_fn=fake_gather, config_file=config)
            self.assertEqual(result["status"], "MANUAL_WEB_PREVIEW_ONLY")
            self.assertFalse(result["email_sent"])
            doc = Document(result["word"])
            text = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("رصد | مسودة بحث الويب", text)
            self.assertIn("بروفة / مسودة", text)
            self.assertIn("معاينة RSS غير موثقة بالصور", text)
            self.assertNotIn("أخبار موثقة بالصور", text)
            self.assertNotIn("فيسبوك", text)
            self.assertNotIn("مآل", text)


if __name__ == "__main__":
    unittest.main()
