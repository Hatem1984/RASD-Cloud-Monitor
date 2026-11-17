"""Inspect only first-party RSS redirect targets without following redirects.

Used for qualifying replacement of the EXACT source endpoint after owner
review. An upstream 301/302 is not automatically accepted. Never send email
or fetch third-party locations, even when a publisher redirects there.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from monitor import parse_rss


class RedirectObserved(Exception):
    def __init__(self, destination: str):
        self.destination = destination


class NoFollowButRecord(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RedirectObserved(newurl)


def safe_first_party_destination(source: dict, newurl: str) -> str | None:
    original = urlsplit(source["url"])
    try:
        target = urlsplit(newurl)
        hosts = source["allowed_article_hosts"]
        # The only QA extension is the SAME site's www/apex spelling.
        # It is not a general same-eTLD, CDN or redirect allowance.
        origin_root = original.hostname.removeprefix("www.")
        target_root = (target.hostname or "").removeprefix("www.")
        if (target.scheme == "https" and original.hostname in hosts
                and target_root == origin_root
                and target.hostname in {origin_root, "www." + origin_root}
                and target.port in (None, 443) and not target.username
                and not target.password and not target.fragment
                and not target.query):
            return newurl
    except (ValueError, TypeError, KeyError):
        pass
    return None


def observe(feed: dict, *, opener=None, now=None) -> dict:
    if opener is None:
        opener = build_opener(NoFollowButRecord())
    url = feed["url"]
    result = {"id": feed["id"], "status": "HOLD", "http_status": None,
              "first_party_redirect_target": None,
              "strict_items_at_direct_target": 0,
              "reason": "NO_STABLE_FIRST_PARTY_TARGET"}
    try:
        with opener.open(Request(url, headers={
                "User-Agent": "RASD-first-party-feed-redirect-QA/1.0"}),
                timeout=15) as response:
            if response.status == 200 and response.geturl() == url:
                result["reason"] = "ORIGINAL_URL_ALREADY_DIRECT"
            else:
                result["reason"] = "ORIGINAL_URL_UNEXPECTED_RESPONSE"
            return result
    except RedirectObserved as redirect:
        target = safe_first_party_destination(feed, redirect.destination)
    except Exception as error:
        result["reason"] = (
            "NETWORK_OR_STATUS_HOLD" if type(error).__name__ in (
                "HTTPError", "URLError", "TimeoutError", "OSError")
            else "OTHER_HOLD")
        return result

    if target is None or target == url:
        result["reason"] = "REDIRECT_OUTSIDE_APPROVED_FIRST_PARTY"
        return result
    result["first_party_redirect_target"] = target

    # ONE direct request. Any new redirect or invalid original RSS stays HOLD.
    try:
        with opener.open(Request(target, headers={
                "User-Agent": "RASD-first-party-feed-redirect-QA/1.0"}),
                timeout=15) as resp:
            if resp.status != 200 or resp.geturl() != target:
                result["reason"] = "TARGET_NOT_DIRECT_HTTP200"
                return result
            data = resp.read(1_500_001)
            if len(data) > 1_500_000:
                result["reason"] = "TARGET_TOO_LARGE"
                return result
        candidate = {
            **feed, "url": target,
            "allowed_article_hosts": list(set(feed["allowed_article_hosts"]) |
                                          {urlsplit(target).hostname}),
        }
        count, _matches = parse_rss(
            data, candidate, ["وزارة التخطيط", "وزير التخطيط",
                              "التخطيط والتنمية الاقتصادية"],
            now or datetime.now(timezone.utc), 72, require_complete_items=True)
        result["status"] = "RSS_QA_ONLY"
        result["strict_items_at_direct_target"] = count
        result["reason"] = "PUBLISHER_PAGE_IMAGE_QA_STILL_REQUIRED"
    except RedirectObserved:
        result["reason"] = "TARGET_REDIRECTS_AGAIN"
    except Exception as error:
        code = type(error).__name__
        result["reason"] = ("STRICT_" + code if code in (
            "ValueError", "ParseError", "RuntimeError") else
            "TARGET_NETWORK_OR_XML_HOLD")
    return result


def main():
    cfg = json.loads(Path("sources_newsroom_active.json").read_text(
        encoding="utf-8"))
    names = {"alborsa", "dailynewsegypt"}
    sources = [f for f in cfg["feeds"] if f["id"] in names]
    if {f["id"] for f in sources} != names:
        raise RuntimeError("source_inventory_not_expected")
    print(json.dumps({
        "mode": "first_party_direct_endpoint_qa_no_send",
        "candidates": [observe(f) for f in sources],
        "production_feeds_modified": False, "email_sent": False,
        "private_state_used": False, "scheduler_enabled": False,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
