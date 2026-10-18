"""Gate 39: first-party Ministry NewsList AJAX discovery strict offline regressions."""
from __future__ import annotations

import unittest

from official_ministry_source import (
    NEWSLIST, SAMPLE, discover_official_newslist, index_articles,
)

FAKE_HTML = """<html><body>
<div class="media-items row">
  <div id="div_7269" class="newsDiv">
    <span onclick="newsDetails('7269','True','published-ministry-text')">
      وزير التخطيط يستعرض مؤشرات الاقتصاد
    </span>
  </div>
  <div id="div_7267" class="newsDiv">
    <div onclick="newsDetails('7267','True','other-ministry-publisher-story')">
       وزارة التخطيط
    </div>
  </div>
  <div id="div_7269" class="newsDiv">
    <a onclick="newsDetails('7269','True','repeat')">Repeated card</a>
  </div>
  <div id="div_9999">
    <p>no corresponding official click handler: 9999</p>
  </div>
  <p onclick="newsDetails('8888','True','no matching original div')">
    no actual card
  </p>
</div></body></html>"""


class MockResponse:
    def __init__(self, payload=FAKE_HTML.encode(), *,
                 status=200, url=NEWSLIST, content_type="text/html"):
        self.status = status
        self.url = url
        self.headers = {"content-type": content_type}
        self._payload = payload

    def body(self):
        return self._payload


class MockHTTP:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


class OfficialNewsListDiscoveryTests(unittest.TestCase):
    def test_click_handler_and_real_card_id_required_no_guessing(self):
        self.assertEqual(index_articles(FAKE_HTML), [
            SAMPLE, "https://mped.gov.eg/singlenews?id=7267&lang=ar",
        ])

    def test_escaped_onclick_entities_remain_supported(self):
        snippet = """<div id="div_7269">
          <div onclick="newsDetails(&#39;7269&#39;,&#39;True&#39;,&#39;خبر الوزارة&#39;)"></div>
        </div>"""
        self.assertEqual(index_articles(snippet), [SAMPLE])

    def test_unlinked_numbers_and_impostor_actions_cannot_be_selected(self):
        for html in (
            "<div id='div_7269'>7269</div>",
            """<a onclick="evilNewsDetails('7269','True','x')">X</a>""",
            """<div id="div_7269"></div><div onclick="newsDetails('7269','False')">X</div>""",
            """<div id="div_1"></div><div onclick="newsDetails('7269','True','x')">X</div>""",
        ):
            with self.subTest(html=html[:60]):
                self.assertEqual(index_articles(html), [])

    def test_exact_first_party_ajax_get_with_strict_no_redirects(self):
        transport = MockHTTP(MockResponse())
        found = discover_official_newslist(transport)
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0], SAMPLE)
        self.assertEqual(len(transport.calls), 1)
        args, kwargs = transport.calls[0]
        self.assertEqual(args, (NEWSLIST,))
        self.assertEqual(kwargs["max_redirects"], 0)
        self.assertEqual(kwargs["headers"]["Referer"],
                         "https://mped.gov.eg/News?id=57&lang=ar")

    def test_page_two_uses_only_bounded_real_publisher_page_parameter(self):
        url = "https://mped.gov.eg/News/NewsList?lang=ar&pageNum=2&typeId=0"
        transport = MockHTTP(MockResponse(url=url))
        discovered = discover_official_newslist(
            transport, page_number=2)
        self.assertEqual(discovered[0], SAMPLE)
        self.assertEqual(transport.calls[0][0], (url,))
        self.assertEqual(transport.calls[0][1]["max_redirects"], 0)
        for page in (0, -1, 5, 500, True, "2"):
            with self.subTest(page=page):
                with self.assertRaisesRegex(ValueError, "official_page_number_invalid"):
                    discover_official_newslist(transport, page_number=page)

    def test_failed_or_foreign_response_fails_closed(self):
        for response in (
            MockResponse(status=403),
            MockResponse(status=302),
            MockResponse(url="https://unapproved.example/list"),
            MockResponse(content_type="application/json"),
            MockResponse(payload=b""),
            MockResponse(payload=b"x" * 1_500_001),
            MockResponse(payload=b"\xff\xfe"),
        ):
            with self.subTest(status=response.status, length=len(response._payload)):
                with self.assertRaises(ValueError):
                    discover_official_newslist(MockHTTP(response))

    def test_bounded_page_count_no_external_query_or_credential(self):
        for x in (0, -1, 36, True, "35"):
            with self.assertRaises(ValueError):
                discover_official_newslist(MockHTTP(MockResponse()), max_articles=x)
        many = "".join(
            f"""<div id="div_{i}"><p onclick="newsDetails('{i}','True','post')"></p></div>"""
            for i in range(1, 70)
        )
        found = discover_official_newslist(
            MockHTTP(MockResponse(payload=many.encode())))
        self.assertLessEqual(len(found), 35)


if __name__ == "__main__":
    unittest.main()
