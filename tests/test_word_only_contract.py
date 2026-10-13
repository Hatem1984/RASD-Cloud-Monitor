"""Word-only output contract; does not inspect or invoke private services."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class WordOnlyContractTests(unittest.TestCase):
    def test_active_report_paths_never_create_or_attach_pdf(self):
        paths = (
            "daily_report.py", "cloud_proof_report.py", "digest_mailer.py",
            ".github/workflows/report-manual.yml",
            ".github/workflows/gate11-ci.yml",
            ".github/workflows/digest-mail-manual.yml",
            ".github/workflows/proof-report-manual.yml",
        )
        for path in paths:
            with self.subTest(path=path):
                source = (ROOT / path).read_text(encoding="utf-8").lower()
                self.assertNotIn("render_pdf(", source)
                self.assertNotIn("pdfreader", source)
                self.assertNotIn("application/pdf", source)
                # Negative guards against unwanted files are allowed.
                self.assertNotIn("pdf_created", source)
                self.assertNotIn("add_attachment(\n        pdf", source)

    def test_no_pdf_parser_runtime_dependency(self):
        packages = (ROOT / "requirements-test.txt").read_text(encoding="utf-8").lower()
        self.assertNotIn("pypdf", packages)
        self.assertIn("python-docx", packages)

    def test_screenshot_report_must_stop_on_missing_images(self):
        source = (ROOT / "cloud_proof_report.py").read_text(encoding="utf-8")
        self.assertIn('status": "READY" if ready else "HOLD"', source)
        self.assertIn('verified == len(rows)', source)
        self.assertIn('and report["coverage"] == "HEALTHY"', source)
        self.assertIn('render_docx(report, word)', source)

    def test_manual_email_requires_verified_word_not_preview(self):
        source = (ROOT / "digest_mailer.py").read_text(encoding="utf-8")
        self.assertIn("generator=build_proof_report", source)
        self.assertIn("verify_word(word, date,", source)
        self.assertIn('"screenshots_verified"', source)
        self.assertIn("digest_publisher_evidence_incomplete", source)


if __name__ == "__main__":
    unittest.main()
