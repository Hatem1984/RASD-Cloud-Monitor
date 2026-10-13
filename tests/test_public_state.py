"""Zero-network QA of public state continuity and safe persistence."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from monitor import article_id
from public_state import (apply_observations, empty_state, load_state,
                          save_state, validate_state)
from stateful_probe import run

NOW = datetime(2026, 10, 13, 9, tzinfo=timezone.utc)
URL = "https://hapijournal.com/public-ministry-example"
IDENTITY = article_id(URL)
SAMPLE = {"sources": [{"feed_id": "hapi", "status": "ok"}],
          "matched_public_articles": [{"id": IDENTITY, "url": URL,
                                       "headline": "وزير التخطيط"}]}


class PersistentStateTests(unittest.TestCase):

    def test_successive_runs_do_not_repeat_observed_id(self):
        first, stats1 = apply_observations(empty_state(), SAMPLE, NOW)
        second, stats2 = apply_observations(first, SAMPLE, NOW + timedelta(minutes=30))
        self.assertEqual((stats1["newly_observed_public_articles"],
                          stats2["newly_observed_public_articles"]), (1, 0))
        self.assertEqual(stats2["already_observed_public_articles"], 1)
        self.assertEqual(second["run_count"], 2)
        self.assertEqual(list(second["seen_ids"]), [IDENTITY])
        self.assertNotIn("sent", second)
        self.assertNotIn("email", json.dumps(second))

    def test_persist_reload_keeps_fingerprints_only(self):
        state, _ = apply_observations(empty_state(), SAMPLE, NOW)
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "state.json"
            save_state(dest, state)
            restored = load_state(dest)
            self.assertEqual(restored, state)
            self.assertNotIn(URL, dest.read_text(encoding="utf-8"))
            self.assertNotIn("وزير التخطيط", dest.read_text(encoding="utf-8"))

    def test_zero_match_run_still_advances_counter(self):
        probe = {"sources": [{"status": "ok"}], "matched_public_articles": []}
        next_state, counts = apply_observations(empty_state(), probe, NOW)
        self.assertEqual(next_state["run_count"], 1)
        self.assertEqual(counts["total_stored_public_url_fingerprints"], 0)

    def test_all_sources_failed_cannot_persist(self):
        with self.assertRaisesRegex(ValueError, "no_verified_public_source"):
            apply_observations(empty_state(), {"sources": [{"status": "failed"}]}, NOW)

    def test_invalid_public_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_article_fingerprint"):
            apply_observations(empty_state(), {"sources": [{"status": "ok"}],
                                                "matched_public_articles": [{"id": URL}]}, NOW)

    def test_malformed_persisted_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "state.json"
            file.write_text('{"schema_version":2,"run_count":1,"seen_ids":{}}')
            with self.assertRaises(ValueError):
                load_state(file)

    def test_expire_old_fingerprints(self):
        state = empty_state()
        state["seen_ids"][IDENTITY] = (NOW - timedelta(days=95)).isoformat()
        new, counts = apply_observations(state, {"sources": [{"status": "ok"}],
                                                "matched_public_articles": []}, NOW)
        self.assertEqual(counts["total_stored_public_url_fingerprints"], 0)
        self.assertFalse(new["seen_ids"])

    def test_naive_clock_rejected(self):
        with self.assertRaisesRegex(ValueError, "utc_aware_clock_required"):
            apply_observations(empty_state(), SAMPLE, datetime(2026, 10, 13))

    def test_end_to_end_repeated_stateful_probe_no_network(self):
        xml = ('<rss><channel><item><title>وزير التخطيط يشارك في مؤتمر</title>'
               '<link>' + URL + '</link></item></channel></rss>').encode()
        config = {
            "feeds": [{"id": "hapi", "name": "Hapi",
                       "url": "https://hapijournal.com/feed/",
                       "allowed_article_hosts": ["hapijournal.com"]}],
            "keywords": ["وزير التخطيط"], "recent_hours": 72,
            "max_feed_bytes": 1500000}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cfg = root / "sources.json"
            cfg.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            prev = root / "previous.json"
            out1 = root / "next.json"
            report = root / "evidence.json"
            one = run(cfg, prev, out1, report, fetch=lambda *a: xml, clock=NOW)
            two = run(cfg, out1, prev, report, fetch=lambda *a: xml,
                      clock=NOW + timedelta(minutes=30))
            self.assertEqual(one["persistence"]["newly_observed_public_articles"], 1)
            self.assertEqual(two["persistence"]["newly_observed_public_articles"], 0)
            self.assertEqual(two["persistence"]["run_number_in_public_state"], 2)
            self.assertFalse(two["email_sent"])
            self.assertFalse(two["scheduler_enabled"])


if __name__ == "__main__":
    unittest.main()
