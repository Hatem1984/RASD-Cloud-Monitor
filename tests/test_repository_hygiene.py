"""Repository hygiene guarantees; no network, secrets or production actions."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


class RepositoryHygieneTests(unittest.TestCase):
    def test_ephemeral_outputs_and_credentials_are_ignored(self):
        rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        rules = {line.strip() for line in rules if line.strip() and not line.startswith("#")}
        for required in (".env", ".env.*", ".venv/", "__pycache__/",
                         "evidence/", "report-output/", "*.log", "*.pem", "*.key"):
            with self.subTest(pattern=required):
                self.assertIn(required, rules)

    def test_push_ci_covers_all_gate_branches_without_obsolete_gate_lists(self):
        content = (WORKFLOWS / "gate11-ci.yml").read_text(encoding="utf-8")
        self.assertIn("- 'gate*'", content)
        self.assertIn("cancel-in-progress: true", content)
        self.assertIn("contents: read", content)
        self.assertNotIn("gate11-secure-gmail-bridge", content)
        self.assertNotIn("environment: rasd-gmail-manual-approval", content)

    def test_mail_and_private_artifacts_stay_on_approved_manual_workflows(self):
        for filename in ("gate11-manual.yml", "digest-mail-manual.yml"):
            with self.subTest(filename=filename):
                source = (WORKFLOWS / filename).read_text(encoding="utf-8")
                self.assertIn("workflow_dispatch:", source)
                self.assertIn("environment: rasd-gmail-manual-approval", source)
                self.assertNotIn("cancel-in-progress: true", source)
                self.assertNotIn("schedule:", source)
        report = (WORKFLOWS / "report-manual.yml").read_text(encoding="utf-8")
        self.assertNotIn("RASD_GMAIL_APP_PASSWORD", report)
        self.assertNotIn("RASD_PRIVATE_LEDGER_TOKEN", report)


if __name__ == "__main__":
    unittest.main()
