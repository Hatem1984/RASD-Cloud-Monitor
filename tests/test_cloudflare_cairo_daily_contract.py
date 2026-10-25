"""Cloudflare daily release guard: no manual mail-sending backdoor or cron identity drift."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CloudflareCairoDailyContract(unittest.TestCase):
    def test_source_and_cloudflare_cron_both_seasons(self):
        config = json.loads((ROOT / "cloudflare-rasd-clock/wrangler.jsonc").read_text("utf-8"))
        self.assertEqual(config["triggers"]["crons"],
                         ["7,37 * * * *", "0 19,20 * * *"])
        self.assertIs(config["workers_dev"], False)
        source = (ROOT / "cloudflare-rasd-clock/src/index.js").read_text("utf-8")
        self.assertIn('timeZone: "Africa/Cairo"', source)
        self.assertIn('localHour !== "22"', source)
        self.assertIn('return null;', source)
        self.assertIn('githubToken(env)', source)
        self.assertIn('cloudflare-rasd-daily-v1', source)
        self.assertIn('RASD_CLOUDFLARE_DAILY_INACTIVE_CANDIDATE_SKIPPED', source)

    def test_github_protected_daily_shares_cas_lock(self):
        workflow = (ROOT / ".github/workflows/rasd-cloudflare-dispatch.yml").read_text("utf-8")
        self.assertIn('group: rasd-scheduled-monitor-private-ledger', workflow)
        self.assertIn("protected-cloudflare-cairo-daily:", workflow)
        self.assertIn("inputs.origin == 'cloudflare-rasd-daily-v1'", workflow)
        self.assertIn("github.actor == 'Hatem1984'", workflow)
        self.assertIn("vars.RASD_AUTOMATION_PAUSED != 'true'", workflow)
        self.assertIn("RASD_JOB_CRON: '0 19,20 * * *'", workflow)
        self.assertIn("python scheduled_rasd.py --mode rollup", workflow)
        self.assertNotIn("schedule:", workflow)  # External relay is ONLY workflow_dispatch.
        self.assertNotIn("pull_request:", workflow)

    def test_worker_is_not_open_http_endpoint(self):
        worker = (ROOT / "cloudflare-rasd-clock/src/index.js").read_text("utf-8")
        self.assertIn('return new Response("Not Found", { status: 404 });', worker)
        self.assertNotIn("SMTP", worker)
        self.assertNotIn("RASD_PRIVATE_LEDGER_TOKEN", worker)


if __name__ == "__main__":
    unittest.main()
