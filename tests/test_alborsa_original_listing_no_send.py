"""Synthetic-only tests for the Alborsa original listing candidate."""
import unittest
from datetime import datetime, timezone, timedelta
from alborsa_original_listing import ROOT, identity, parse_listing, original_article, audit_listing, forward_only

NOW=datetime(2026,11,26,13,35,tzinfo=timezone.utc)
KEY=["Ministry of Planning"]
U="https://alborsaanews.com/2026/11/26/1"
OLD="https://alborsaanews.com/2026/11/22/2"
def card(url=U, title="Ministry of Planning", excerpt="Official news"):
    return f'<article class="jeg_post jeg_pl_md_3"><h3 class="jeg_post_title"><a href="{url}">{title}</a></h3><div class="jeg_post_excerpt"><p>{excerpt}</p></div></article>'
def listing(*cards,next_page=False):
    return ("".join(cards)+(f'<a href="{ROOT}/page/2">Next</a>' if next_page else "")).encode()
def article(url=U,title="Ministry of Planning",stamp="2026-11-26T12:00:00Z",description="Official news"):
    return f'<meta property="og:url" content="{url}"><meta property="article:published_time" content="{stamp}"><meta property="og:description" content="{description}"><h1>{title}</h1>'.encode()
class ListingQA(unittest.TestCase):
    def test_card_extracts_title_and_excerpt(self):
        rows,pages=parse_listing(listing(card(),next_page=True),ROOT)
        self.assertEqual(rows,[{"url":U,"headline":"Ministry of Planning","excerpt":"Official news"}])
        self.assertIn(ROOT+"/page/2",pages)
    def test_sidebar_links_do_not_become_candidates(self):
        rows,_=parse_listing(b'<a href="https://alborsaanews.com/2026/11/26/999">Unrelated</a>'+listing(card()),ROOT)
        self.assertEqual(len(rows),1)
    def test_identity_rejects_external_and_query(self):
        for u in ("https://evil.com/2026/11/26/1",U+"?x=1",U+"#x"):
            with self.assertRaises(ValueError): identity(u)
    def test_incomplete_card_and_duplicate_hold(self):
        for raw in (listing(card(excerpt="")),listing(card(),card())):
            with self.assertRaises(ValueError):parse_listing(raw,ROOT)
    def test_original_timestamp_and_identity(self):
        row=parse_listing(listing(card()),ROOT)[0][0]
        a=original_article(article(),row,KEY,NOW)
        self.assertEqual(a["url"],U)
        for raw in (article(url=OLD),article(title="Different"),article(stamp="2026-11-26T12:00:00"),article(stamp="2026-11-26T15:00:00Z")):
            with self.assertRaises(ValueError): original_article(raw,row,KEY,NOW)
    def test_relevant_description(self):
        row=parse_listing(listing(card(title="Official",excerpt="Ministry of Planning")),ROOT)[0][0]
        a=original_article(article(title="Official",description="Ministry of Planning"),row,KEY,NOW)
        self.assertEqual(a["match_origin"],"publisher_description")
    def test_pagination_audit_and_forward_cutoff(self):
        data={ROOT:listing(card(),next_page=True),ROOT+"/page/2":listing(card(OLD,title="Unrelated")),U:article()}
        result=audit_listing(KEY,NOW,fetch=data.__getitem__)
        self.assertTrue(result["boundary"])
        self.assertEqual(result["links"],2)
        self.assertEqual(len(result["verified"]),1)
        self.assertFalse(result["email_sent"])
        self.assertEqual(result["holds"],[])
        self.assertEqual(forward_only(result["verified"],NOW,NOW),[])
        self.assertEqual(len(forward_only(result["verified"],NOW-timedelta(hours=2),NOW)),1)
    def test_missing_navigation_holds(self):
        with self.assertRaisesRegex(ValueError,"navigation_hold"):
            audit_listing(KEY,NOW,fetch=lambda _:listing(card()))
    def test_identical_overlap_is_deduplicated_only_in_stable_snapshot(self):
        data={ROOT:listing(card(),next_page=True),ROOT+"/page/2":listing(card(),card(OLD,title="Unrelated")),U:article()}
        result=audit_listing(KEY,NOW,fetch=data.__getitem__)
        self.assertEqual((result["links"],result["repeated_cards"],len(result["verified"])),(2,1,1))
    def test_conflicting_duplicate_holds(self):
        data={ROOT:listing(card(),next_page=True),ROOT+"/page/2":listing(card(excerpt="Changed"),card(OLD,title="Unrelated"))}
        with self.assertRaisesRegex(ValueError,"overlap_conflict_hold"):
            audit_listing(KEY,NOW,fetch=data.__getitem__)
    def test_later_page_drift_holds_even_when_top_page_unchanged(self):
        data={ROOT:listing(card(),next_page=True),ROOT+"/page/2":listing(card(OLD,title="Unrelated"))}
        count=0
        def fetch(url):
            nonlocal count
            if url.endswith("/page/2"):
                count+=1
                if count==2:
                    return listing(card(OLD,title="Updated"))
            return data[url]
        with self.assertRaisesRegex(ValueError,"changed_hold"):
            audit_listing(KEY,NOW,fetch=fetch)
