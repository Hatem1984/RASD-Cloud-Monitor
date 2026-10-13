"""Prevent GitHub Actions dependency drift from disabling secure preflight.

Pure offline repository contract checks, no GitHub account access or secrets.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = (
    "capture-manual.yml",
    "manual-probe.yml",
    "stateful-manual.yml",
    "gate11-manual.yml",
    "gate11-ci.yml",
    "report-manual.yml",
    "digest-mail-manual.yml",
    "proof-report-manual.yml",
)
TEST_REQUIREMENTS = "python -m pip install -r requirements-test.txt"


class WorkflowDependenciesContractTests(unittest.TestCase):
    def test_single_manifest_contains_all_three_current_offline_libraries(self):
        entries = (ROOT / "requirements-test.txt").read_text(encoding="utf-8").splitlines()
        packages = set()
        for line in entries:
            line = line.strip()
            if line and not line.startswith("#"):
                packages.add(re.split(r"[<>=!~]", line, maxsplit=1)[0].casefold())
        self.assertEqual(packages, {"pillow", "python-docx"})

    def test_every_workflow_uses_the_same_test_dependencies(self):
        for name in WORKFLOWS:
            with self.subTest(workflow=name):
                source = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
                self.assertIn(TEST_REQUIREMENTS, source)
                self.assertNotIn("python -m pip install \"Pillow", source)

    def test_preflight_job_installs_complete_suite_before_running_tests(self):
        source = (ROOT / ".github/workflows/gate11-manual.yml").read_text(encoding="utf-8")
        before_send = source.split("\n  preflight:", 1)[1].split("\n  send:", 1)[0]
        self.assertLess(before_send.index(TEST_REQUIREMENTS),
                        before_send.index("python -m unittest discover -s tests -v"))
        self.assertLess(before_send.index("python -m unittest discover -s tests -v"),
                        before_send.index("python gate11_preflight.py"))

    def test_gate11_approval_and_scheduled_send_remain_inactive(self):
        for name in ("gate11-manual.yml", "digest-mail-manual.yml", "report-manual.yml", "proof-report-manual.yml"):
            source = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertIn("workflow_dispatch:", source)
                self.assertNotRegex(source, r"(?m)^\s*schedule\s*:")
        gate11 = (ROOT / ".github/workflows/gate11-manual.yml").read_text(encoding="utf-8")
        self.assertIn("environment: rasd-gmail-manual-approval", gate11)
        self.assertIn("default: dry_run", gate11)

    def test_main_branch_ci_is_non_privileged_and_without_scheduled_mail(self):
        source = (ROOT / ".github/workflows/gate11-ci.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", source)
        self.assertNotRegex(source, r"(?m)^\s*schedule\s*:")
        self.assertNotIn("RASD_GMAIL_APP_PASSWORD:", source)
        self.assertNotIn("RASD_PRIVATE_LEDGER_TOKEN:", source)


if __name__ == "__main__":
    unittest.main()
