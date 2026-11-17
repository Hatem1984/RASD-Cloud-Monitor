"""No-bypass public homepage sample tests. No networking or mail."""
import unittest
from rasd_candidate_homepage_qa import SAMPLE_IDS, probe_homepage


class FakeResponse:
    def __init__(self,url,status=200):
        self.url=url
        self.status=status
    def __enter__(self):
        return self
    def __exit__(self,*_):
        return False
    def geturl(self):
        return self.url


class FakeOpener:
    def __init__(self,reply):
        self.reply=reply
    def open(self,req,timeout):
        assert timeout==8
        return self.reply


class CandidateHomepagesNoSend(unittest.TestCase):
    def test_bounded_twelve_cannot_activate_any_source(self):
        self.assertEqual(len(SAMPLE_IDS),12)
        self.assertEqual(len(set(SAMPLE_IDS)),12)

    def test_direct_homepage_does_not_count_as_rss_or_verified_screenshot(self):
        url="https://news.example/"
        result=probe_homepage({
            "id":"fixture","publisher_host":"news.example",
            "homepage_url":url},opener=FakeOpener(FakeResponse(url)))
        self.assertEqual(result["status"],"HOMEPAGE_REACHABLE_ONLY")
        self.assertEqual(result["detail"],"RSS_DATE_SCREENSHOT_STILL_UNVERIFIED")

    def test_redirect_does_not_auto_follow_or_admit(self):
        url="https://news.example/"
        result=probe_homepage({
            "id":"fixture","publisher_host":"news.example",
            "homepage_url":url},
            opener=FakeOpener(FakeResponse("https://other.example/",302)))
        self.assertEqual(result["status"],"HOLD")

    def test_url_with_credentials_fails_before_open(self):
        class NoOpen:
            def open(self,*_args,**_kwargs):
                raise AssertionError("must never make request")
        result=probe_homepage({
            "id":"fixture","publisher_host":"news.example",
            "homepage_url":"https://alice:pw@news.example/"
        },opener=NoOpen())
        self.assertEqual(result["detail"],"CANDIDATE_URL_INVALID")


if __name__=="__main__":
    unittest.main()
