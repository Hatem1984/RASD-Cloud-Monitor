"""Only offline/mocked tests. No network or real SMTP/private ledger calls."""
import hashlib
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import scheduled_rasd as subject
from monitor import article_id


class ScheduledRASDSecurity(unittest.TestCase):
    def test_dst_summer_and_winter_daily_scheduler(self):
        summer = datetime(2026, 7, 5, 19, 1, tzinfo=timezone.utc)
        winter = datetime(2026, 12, 5, 20, 1, tzinfo=timezone.utc)
        self.assertEqual(subject.scheduled_phase(subject.DAILY_CRON, summer), 'rollup')
        self.assertEqual(subject.scheduled_phase(subject.DAILY_CRON, winter), 'rollup')
        self.assertEqual(subject.scheduled_phase(subject.DAILY_CRON,
                         datetime(2026, 7, 5, 20, 1, tzinfo=timezone.utc)), 'skip')

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

    def test_production_credential_normalization_matches_cloud_preflight(self):
        """Google grouped app-password and copied PAT must normalize in memory."""
        recipient = "approved-recipient@example.com"
        digest = hashlib.sha256(recipient.encode()).hexdigest()
        mock_ledger = MagicMock()
        mock_ledger.read.return_value = ({"approved_recipient_sha256": digest}, "sha")
        env = {
            "RASD_GMAIL_SENDER": "sender@gmail.com",
            "RASD_REPORT_TO": recipient,
            "RASD_GMAIL_APP_PASSWORD": " abcd efgh ijkl mnop \n",
            "RASD_PRIVATE_LEDGER_TOKEN": "  github_pat_mock_credential_123456  \n",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(subject, "PrivateGitHubLedger",
                              return_value=mock_ledger) as factory:
                sender, to, password, ledger = subject.protected_credentials()
        self.assertEqual((sender, to), ("sender@gmail.com", recipient))
        self.assertEqual(password, "abcdefghijklmnop")
        self.assertIs(ledger, mock_ledger)
        factory.assert_called_once_with("github_pat_mock_credential_123456")

    def test_whitespace_only_credentials_hold_before_private_network(self):
        env = {
            "RASD_GMAIL_SENDER": "sender@gmail.com",
            "RASD_REPORT_TO": "approved-recipient@example.com",
            "RASD_GMAIL_APP_PASSWORD": "  \n    ",
            "RASD_PRIVATE_LEDGER_TOKEN": "  \n    ",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(subject, "PrivateGitHubLedger") as factory:
                with self.assertRaisesRegex(RuntimeError,
                                            "missing_protected_credentials"):
                    subject.protected_credentials()
        factory.assert_not_called()

    def test_sender_must_not_be_recipient(self):
        variables = {'RASD_GMAIL_SENDER': 'owner@gmail.com',
                     'RASD_REPORT_TO': 'owner@gmail.com',
                     'RASD_GMAIL_APP_PASSWORD': 'test_only_012345678901',
                     'RASD_PRIVATE_LEDGER_TOKEN': 'fake_read_only_012345'}
        with patch.dict(os.environ, variables, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'sender_and_recipient_must_differ'):
                subject.protected_credentials()

    def test_rollup_is_22_to_22_window_without_loss_of_late_alerts(self):
        story = {'id': article_id('https://hapijournal.com/planning-news'),
                 'headline': 'وزارة التخطيط تناقش مؤشرات الاستثمار',
                 'publisher_excerpt': '', 'source': 'Hapi native news RSS',
                 'url': 'https://hapijournal.com/planning-news',
                 'published_at_cairo': '2026-10-21 12:05 EEST',
                 'published_display_cairo': '21 أكتوبر 2026'}
        second = dict(story)
        second['url'] = 'https://hapijournal.com/second-news'
        second['id'] = article_id(second['url'])
        second['headline'] = 'وزير التخطيط يوقع اتفاقًا لتمويل المشروعات الصناعية'
        third = dict(story)
        third['url'] = 'https://hapijournal.com/third-news'
        third['id'] = article_id(third['url'])
        third['headline'] = 'وزارة التخطيط تعلن ضوابط الإنفاق الاستثماري'
        state = {'entries': {
            story['id']: {'status': 'smtp_accepted',
                          'accepted_at': '2026-10-20T20:30:00+00:00',
                          'kind': 'interval_item', 'news': story},
            second['id']: {'status': 'smtp_accepted',
                           'accepted_at': '2026-10-21T16:00:00+00:00',
                           'kind': 'interval_item', 'news': second},
            third['id']: {'status': 'smtp_accepted',
                          'accepted_at': '2026-10-21T19:30:00+00:00',
                          'kind': 'interval_item', 'news': third},
            'ab'*12: {'status': 'reserved', 'kind': 'interval_item',
                      'news': story},
        }}
        config = {'feeds': [{'name': 'Hapi native news RSS',
                            'allowed_article_hosts': ['hapijournal.com']}]}
        today = subject.news_for_rollup(state, '2026-10-21', config)
        self.assertEqual({s['id'] for s in today}, {story['id'], second['id']})
        tomorrow = subject.news_for_rollup(state, '2026-10-22', config)
        self.assertEqual({s['id'] for s in tomorrow}, {third['id']})

    def test_rollup_2200_dst_and_interval_collision_guard(self):
        for today_utc, prior_utc, following_utc in (
            (datetime(2026, 7, 5, 19, 0, tzinfo=timezone.utc),
             datetime(2026, 7, 5, 18, 0, tzinfo=timezone.utc),
             datetime(2026, 7, 5, 20, 0, tzinfo=timezone.utc)),
            (datetime(2026, 12, 5, 20, 0, tzinfo=timezone.utc),
             datetime(2026, 12, 5, 19, 0, tzinfo=timezone.utc),
             datetime(2026, 12, 5, 21, 0, tzinfo=timezone.utc)),
        ):
            self.assertEqual(subject.scheduled_phase(subject.DAILY_CRON,
                             today_utc), 'rollup')
            self.assertEqual(subject.scheduled_phase(subject.DAILY_CRON,
                             prior_utc), 'skip')
            self.assertEqual(subject.scheduled_phase(subject.DAILY_CRON,
                             following_utc), 'skip')
            self.assertEqual(subject.scheduled_phase(subject.HALF_HOUR_CRON,
                             today_utc), 'skip')
            self.assertEqual(subject.scheduled_phase(subject.HALF_HOUR_CRON,
                             today_utc.replace(minute=30)), 'interval')

    def test_rollup_missing_or_naive_acceptance_timestamp_holds(self):
        url = 'https://hapijournal.com/missing-date'
        article = {'id': article_id(url), 'headline': 'وزارة التخطيط',
                   'url': url, 'source': 'Hapi native news RSS',
                   'published_at_cairo': '2026-10-21 10:00 EEST'}
        config = {'feeds': [{'name': 'Hapi native news RSS',
                            'allowed_article_hosts': ['hapijournal.com']}]}
        for invalid in [None, '2026-10-21T16:00:00']:
            entry = {'kind': 'interval_item', 'status': 'smtp_accepted',
                     'news': article, 'accepted_at': invalid}
            with self.assertRaises(RuntimeError):
                subject.news_for_rollup(
                    {'entries': {article['id']: entry}}, '2026-10-21', config)

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

    def test_manual_one_shot_skips_only_capture_hold_to_next_verified_story(self):
        config = {'feeds': [{'name': 'Hapi native news RSS',
                            'allowed_article_hosts': ['hapijournal.com']}]}
        one = {'id': article_id('https://hapijournal.com/one'),
               'url': 'https://hapijournal.com/one', 'source': 'Hapi native news RSS',
               'headline': 'وزارة التخطيط - أول خبر', 'published_at_cairo': '2026-10-22 17:00'}
        two = dict(one, id=article_id('https://hapijournal.com/two'),
                   url='https://hapijournal.com/two', headline='وزارة التخطيط - ثاني خبر')
        expected_word = Path('/tmp/mock-second-original.docx')
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(subject, 'prepare_word', side_effect=[
                    RuntimeError('publisher_screenshot_hold'),
                    (expected_word, [{'id': two['id'], 'status': 'verified'}])]) as build:
                with patch.object(subject, 'reserve_stories', side_effect=AssertionError('reserved')):
                    with patch.object(subject, 'send_one_word', side_effect=AssertionError('emailed')):
                        chosen, path, proof = subject.prepare_first_verified_word(
                            [one, two], config, Path(tmp),
                            title='Manual one genuine screenshot', start='s', end='e')
        self.assertEqual(chosen['id'], two['id'])
        self.assertEqual(path, expected_word)
        self.assertEqual(proof[0]['id'], two['id'])
        self.assertEqual(build.call_count, 2)
        self.assertEqual(build.call_args_list[0].args[0], [one])
        self.assertEqual(build.call_args_list[1].args[0], [two])
        self.assertNotEqual(build.call_args_list[0].args[2],
                            build.call_args_list[1].args[2])

    def test_manual_one_shot_mock_capture_builds_real_verified_word_package(self):
        # This is purely offline and uses artificial JPEG bytes as a fixture,
        # NOT an authorization or claim of actual publisher access.
        from PIL import Image
        first_url = 'https://hapijournal.com/blocked-fixture'
        second_url = 'https://hapijournal.com/working-fixture'
        first = {'id': article_id(first_url), 'url': first_url,
                 'source': 'Hapi native news RSS', 'headline': 'وزارة التخطيط مثال أول',
                 'published_at_cairo': '2026-10-22 17:00 EEST',
                 'published_display_cairo': '22 أكتوبر 2026'}
        second = dict(first, id=article_id(second_url), url=second_url,
                      headline='وزارة التخطيط مثال ثان')
        config = {'feeds': [{'id': 'hapi', 'name': 'Hapi native news RSS',
                            'allowed_article_hosts': ['hapijournal.com']}]}
        def capture_fixture(article, _feeds, destination):
            if article['id'] == first['id']:
                return {'status': 'hold', 'reason': 'publisher_access_refused'}
            Image.new('RGB', (1100, 800), (245, 245, 245)).save(destination, 'JPEG')
            return {'status': 'verified',
                    'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            chosen, word, evidence = subject.prepare_first_verified_word(
                [first, second], config, Path(tmp), title='Offline acceptance only',
                start='2026-10-22 17:00', end='2026-10-22 17:30',
                capture=capture_fixture)
            self.assertEqual(chosen['id'], second['id'])
            self.assertTrue(word.is_file())
            self.assertTrue(subject.word_images_match_capture_digests(word, evidence))

    def test_manual_one_shot_all_unavailable_stays_hold_without_mail(self):
        rows = [{'id': str(n)} for n in range(2)]
        with patch.object(subject, 'prepare_word',
                          side_effect=RuntimeError('publisher_screenshot_hold')) as build:
            with patch.object(subject, 'send_one_word', side_effect=AssertionError('emailed')):
                with self.assertRaisesRegex(RuntimeError,
                                            'first_live_no_verified_original_publisher_story'):
                    subject.prepare_first_verified_word(
                        rows, {}, Path('mock-only'), title='x', start='s', end='e')
        self.assertEqual(build.call_count, 2)

    def test_manual_one_shot_limit_and_empty_hold_without_network(self):
        with patch.object(subject, 'prepare_word', side_effect=AssertionError('called')) as build:
            for rows, code in (
                    ([], 'first_live_no_new_approved_story'),
                    ([{}] * 16, 'first_live_excessive_unsent_news')):
                with self.assertRaisesRegex(RuntimeError, code):
                    subject.prepare_first_verified_word(
                        rows, {}, Path('mock-only'), title='x', start='s', end='e')
        build.assert_not_called()

    def test_manual_one_shot_must_not_skip_word_integrity_errors(self):
        with patch.object(subject, 'prepare_word',
                          side_effect=RuntimeError('word_screenshot_identity_hold')) as build:
            with self.assertRaisesRegex(RuntimeError, 'word_screenshot_identity_hold'):
                subject.prepare_first_verified_word(
                    [{'id': 'one'}, {'id': 'two'}], {}, Path('mock-only'),
                    title='x', start='s', end='e')
        build.assert_called_once()

    def test_manual_one_shot_rejects_misbound_article_evidence(self):
        with patch.object(subject, 'prepare_word',
                          return_value=(Path('fake.docx'), [
                              {'id': 'other', 'status': 'verified'}])):
            with self.assertRaisesRegex(RuntimeError, 'first_live_word_evidence_identity_hold'):
                subject.prepare_first_verified_word(
                    [{'id': 'article'}], {}, Path('mock-only'),
                    title='x', start='s', end='e')

    def test_manual_one_shot_unapproved_publisher_not_skipped(self):
        invalid = {'id': article_id('https://untrusted.invalid/story'),
                   'url': 'https://untrusted.invalid/story',
                   'source': 'Hapi native news RSS',
                   'headline': 'وزارة التخطيط', 'published_at_cairo': '2026-10-22 17:00'}
        config = {'feeds': [{'name': 'Hapi native news RSS',
                            'allowed_article_hosts': ['hapijournal.com']}]}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(subject, 'proof_capture',
                              side_effect=AssertionError('capture untrusted')) as capture:
                with self.assertRaisesRegex(ValueError, 'unapproved_news_publisher'):
                    subject.prepare_first_verified_word(
                        [invalid], config, Path(tmp), title='x', start='s', end='e')
        capture.assert_not_called()

    def test_dry_run_never_connects_to_sender_or_ledger(self):
        with patch.object(subject, 'protected_credentials', side_effect=AssertionError('secrets called')):
            with patch.object(subject, 'run_scheduled', side_effect=AssertionError('send called')):
                with patch('sys.argv', ['scheduled_rasd.py', '--mode', 'dry_run']):
                    subject.main()

if __name__ == '__main__':
    unittest.main()