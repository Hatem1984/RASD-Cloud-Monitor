"""Only offline/mocked tests. No network or real SMTP/private ledger calls."""
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import scheduled_rasd as subject
from monitor import article_id


class ScheduledRASDSecurity(unittest.TestCase):
    def test_dst_summer_and_winter_daily_scheduler(self):
        summer = datetime(2026, 7, 5, 20, 51, tzinfo=timezone.utc)
        winter = datetime(2026, 12, 5, 21, 51, tzinfo=timezone.utc)
        self.assertEqual(subject.scheduled_phase(subject.DAILY_CRON, summer), 'rollup')
        self.assertEqual(subject.scheduled_phase(subject.DAILY_CRON, winter), 'rollup')
        self.assertEqual(subject.scheduled_phase(subject.DAILY_CRON,
                         datetime(2026, 7, 5, 21, 51, tzinfo=timezone.utc)), 'skip')

    def test_slot_is_utc_30_minute_floor_with_cairo_day(self):
        slot, day, _ = subject.cairo_window(
            datetime(2026, 10, 21, 20, 44, tzinfo=timezone.utc))
        self.assertEqual(slot, '2026-10-21T20:30Z')
        self.assertEqual(day, '2026-10-21')
        self.assertEqual(subject.scheduled_phase(subject.HALF_HOUR_CRON,
                         datetime(2026, 10, 21, 20, 44, tzinfo=timezone.utc)), 'interval')
        with self.assertRaises(ValueError):
            subject.cairo_window(datetime(2026, 10, 21, 12, 0))

    def test_schedule_requires_explicit_opt_in_and_github_schedule(self):
        env = {'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_REF': 'refs/heads/main',
               'GITHUB_REPOSITORY': 'Hatem1984/RASD-Cloud-Monitor',
               'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_RUN_ID': '1234',
               'GITHUB_WORKFLOW_REF': subject.EXPECTED_WORKFLOW,
               'RASD_AUTOMATION_ENABLED': 'true'}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                subject.require_github_scheduler()
            os.environ['GITHUB_EVENT_NAME'] = 'schedule'
            subject.require_github_scheduler()
            os.environ['GITHUB_RUN_ATTEMPT'] = '2'
            with self.assertRaises(RuntimeError):
                subject.require_github_scheduler()
            os.environ['GITHUB_RUN_ATTEMPT'] = '1'
            os.environ.pop('RASD_AUTOMATION_ENABLED')
            with self.assertRaises(RuntimeError):
                subject.require_github_scheduler()

    def test_source_inventory_not_cut_to_15_before_deduplication(self):
        checked = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
        config = {"feeds": [{"name": "Hapi native news RSS",
                             "allowed_article_hosts": ["hapijournal.com"]}]}
        raw = [{"sequence": n} for n in range(18)]
        fake = {"matched_public_articles": raw,
                "matched_article_pool_truncated": False,
                "sources": [{"status": "ok"}]}
        def candidate(item, *_args):
            n = item["sequence"]
            url = "https://hapijournal.com/story-" + str(n)
            return {"id": article_id(url), "url": url,
                    "headline": "وزارة التخطيط خبر " + str(n),
                    "source": "Hapi native news RSS", "published": "Wed, 21 Oct 2026 11:30:00 GMT"}
        with patch.object(subject, "candidate_from_feed", side_effect=candidate):
            result = subject.discover_interval_news(
                config, checked, inspector=lambda *_args, **_kw: fake)
        self.assertEqual(len(result), 18)
        already_sent = {a["id"]: {"status": "smtp_accepted"} for a in result[:17]}
        unsent = [a for a in result if a["id"] not in already_sent]
        self.assertEqual(len(unsent), 1)

    def test_sender_must_not_be_recipient(self):
        variables = {'RASD_GMAIL_SENDER': 'owner@gmail.com',
                     'RASD_REPORT_TO': 'owner@gmail.com',
                     'RASD_GMAIL_APP_PASSWORD': 'test_only_012345678901',
                     'RASD_PRIVATE_LEDGER_TOKEN': 'fake_read_only_012345'}
        with patch.dict(os.environ, variables, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'sender_and_recipient_must_differ'):
                subject.protected_credentials()

    def test_rollup_contains_only_prior_accepted_interval_items(self):
        story = {'id': article_id('https://hapijournal.com/planning-news'),
                 'headline': 'وزارة التخطيط تناقش مؤشرات الاستثمار',
                 'publisher_excerpt': '', 'source': 'Hapi native news RSS',
                 'url': 'https://hapijournal.com/planning-news',
                 'published_at_cairo': '2026-10-21 12:05 EEST',
                 'published_display_cairo': '21 أكتوبر 2026'}
        state = {'entries': {
            story['id']: {'status': 'smtp_accepted', 'day_cairo': '2026-10-21',
                          'kind': 'interval_item', 'news': story},
            'ab'*12: {'status': 'reserved', 'day_cairo': '2026-10-21',
                      'kind': 'interval_item', 'news': story},
            'bb'*12: {'status': 'smtp_accepted', 'day_cairo': '2026-10-20',
                      'kind': 'interval_item', 'news': story},
        }}
        config = {'feeds': [{'name': 'Hapi native news RSS',
                            'allowed_article_hosts': ['hapijournal.com']}]}
        selected = subject.news_for_rollup(state, '2026-10-21', config)
        self.assertEqual([s['id'] for s in selected], [story['id']])

    def test_negative_unapproved_external_story_and_duplicate(self):
        config = {'feeds': [{'name': 'Hapi native news RSS',
                            'allowed_article_hosts': ['hapijournal.com']}]}
        story = {'id': article_id('https://mped.gov.eg/News/unknown'),
                 'url': 'https://mped.gov.eg/News/unknown',
                 'headline': 'وزارة التخطيط',
                 'published_at_cairo': '2026-10-21 10:00 EEST',
                 'source': 'Hapi native news RSS'}
        with self.assertRaises(ValueError):
            subject.validate_story(story, config)

    def test_dry_run_never_connects_to_sender_or_ledger(self):
        with patch.object(subject, 'protected_credentials', side_effect=AssertionError('secrets called')):
            with patch.object(subject, 'run_scheduled', side_effect=AssertionError('send called')):
                with patch('sys.argv', ['scheduled_rasd.py', '--mode', 'dry_run']):
                    subject.main()

if __name__ == '__main__':
    unittest.main()