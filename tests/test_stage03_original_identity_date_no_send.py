"""No-send regression of exact heading, corroborated native date and review hints."""
import unittest
from capture_public import original_headline_h1_index, original_headline_matches, alborsa_original_heading_index
from cloud_proof_report import original_headline_in_page_title, proof_capture
from elbalad_date_evidence import publication_evidence, CONFLICT, AGREEMENT
from event_identity import distinct_publisher_coverages, related_event_pairs
from monitor import article_id
from pathlib import Path
from tempfile import TemporaryDirectory

TITLE="Ministry of Planning announces details of three projects"
WRONG="Ministry of Planning announces details of nine projects"
URL="https://www.elbalad.news/7195179"
FEED={"id":"elbalad","name":"Elbalad QA","allowed_article_hosts":["www.elbalad.news"]}
ARTICLE={"id":article_id(URL),"url":URL,"source":FEED["name"],"headline":TITLE,
         "published_at_cairo":"2026-11-26 11:30 EET",
         "published":"Thu, 26 Nov 2026 09:30:00 GMT"}
VISIBLE={"canonical":[URL],"visible":["الخميس 26/نوفمبر/2026 - 11:30 ص"]}
GOOD={**VISIBLE,"meta":["2026-11-26T09:30:00Z"],"ld":["2026-11-26T11:30:00+02:00"]}
OBSERVED={**VISIBLE,"meta":["2026-11-26T11:30:00Z"],"ld":["2026-11-26T11:30:00Z"]}

class Stage03Evidence(unittest.TestCase):
    def test_shared_six_words_no_longer_prove_title(self):
        self.assertFalse(original_headline_in_page_title(TITLE,WRONG+" | Publisher"))
        self.assertIsNone(original_headline_h1_index(TITLE,TITLE+" "+WRONG,[WRONG]))
        self.assertFalse(original_headline_matches(TITLE,WRONG))
    def test_full_original_title_and_suffix(self):
        self.assertTrue(original_headline_in_page_title(TITLE,TITLE+" | Publisher"))
        self.assertEqual(original_headline_h1_index(TITLE+" | Publisher",TITLE+" extra",[TITLE]),0)
    def test_explicit_metadata_and_visible_agree(self):
        self.assertEqual(publication_evidence(ARTICLE,GOOD),AGREEMENT)
    def test_observed_utc_wall_clock_conflict_disclosed(self):
        self.assertEqual(publication_evidence(ARTICLE,OBSERVED),CONFLICT)
    def test_unresolved_metadata_or_visible_conflict_holds(self):
        for value in (None,{**OBSERVED,"visible":[]},{**OBSERVED,"canonical":["https://www.elbalad.news/other"]},
            {**OBSERVED,"visible":["الخميس 26/نوفمبر/2026 - 01:30 م"]},
            {**OBSERVED,"ld":["2026-11-26T12:30:00Z"]},
            {**OBSERVED,"meta":["2026-11-26T11:30:00"]},
            {**OBSERVED,"visible":VISIBLE["visible"]*2}):
            self.assertIsNone(publication_evidence(ARTICLE,value))
    def test_missing_native_date_or_wrong_display_zone_holds(self):
        for article in ({**ARTICLE,"published":""},{**ARTICLE,"published":"Thu, 26 Nov 2026 09:30:00"},
                        {**ARTICLE,"published_at_cairo":"2026-11-26 11:30 EEST"}):
            self.assertIsNone(publication_evidence(article,OBSERVED))
    def test_proof_rejects_unresolved_date(self):
        def capture(*args):
            return {"ok":True,"actual_url":URL,"title":TITLE,"original_headline":TITLE,
                    "publication_date_evidence":{**OBSERVED,"visible":[]}}
        with TemporaryDirectory() as d:
            self.assertEqual(proof_capture(ARTICLE,[FEED],Path(d)/"x.jpg",capture=capture)["reason"],"original_publication_date_conflict_hold")
    def test_proof_rejects_different_h1(self):
        def capture(*args):
            return {"ok":True,"actual_url":URL,"title":TITLE,"original_headline":WRONG,"publication_date_evidence":GOOD}
        with TemporaryDirectory() as d:
            self.assertEqual(proof_capture(ARTICLE,[FEED],Path(d)/"x.jpg",capture=capture)["reason"],"title_mismatch")
    def test_alborsa_structured_heading_requires_identity(self):
        url="https://www.alborsaanews.com/2026/11/26/2009038"
        evidence={"og_urls":[url],"headlines":[TITLE]}
        self.assertEqual(alborsa_original_heading_index(url,TITLE+" extra",[TITLE],evidence),0)
        for bad in ({**evidence,"og_urls":["https://www.alborsaanews.com/other"]},
                    {**evidence,"headlines":[WRONG]}, {**evidence,"headlines":[TITLE,TITLE]}):
            self.assertIsNone(alborsa_original_heading_index(url,TITLE,[TITLE],bad))
        self.assertIsNone(alborsa_original_heading_index(url,TITLE,[TITLE,TITLE],evidence))
    def test_related_intro_is_hint_not_deletion(self):
        intro="أكد الدكتور أحمد رستم، وزير التخطيط والتنمية الاقتصادية، أن ملف التوظيف وسوق العمل يمثل إحدى الغايات الرئيسية للتنمية الاقتصادية، نظرًا لتأثيره المباشر على تحسين جودة حياة المواطني..."
        a={"id":"a","source":"publisher","headline":"وزير التخطيط يستهدف توفير 3 ملايين فرصة عمل","published_at_cairo":"2026-11-24 11:32 EET","publisher_excerpt":intro}
        b={**a,"id":"b","headline":"التحول الاقتصادي يستهدف توفير ٣ ملايين فرصة عمل","published_at_cairo":"2026-11-25 08:01 EET"}
        self.assertEqual(related_event_pairs([a,b]),[("a","b")])
        self.assertEqual(distinct_publisher_coverages([a,b,a]),([a,b],[a]))
        self.assertEqual(related_event_pairs([{**b,"headline":"التحول الاقتصادي يستهدف توفير ٥ ملايين فرصة عمل"}],[a]),[])
        self.assertEqual(related_event_pairs([{**b,"source":"another"}],[a]),[])
        self.assertEqual(related_event_pairs([{**b,"published_at_cairo":"2026-11-27 08:01 EET"}],[a]),[])
    def test_distinct_update_with_same_headline_retained(self):
        a={"id":"a","source":"publisher","headline":TITLE,"published_at_cairo":"2026-11-26 11:30 EET","publisher_excerpt":"original details"}
        b={**a,"id":"b","publisher_excerpt":"updated government figures"}
        self.assertEqual(distinct_publisher_coverages([b],[a]),([b],[]))
