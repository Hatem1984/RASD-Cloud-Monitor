"""One-hop same-publisher canonical-host RSS qualification (NO SEND).

Original candidates never become active merely due to this QA. No redirects
are followed automatically. Only an exact HTTPS www<->apex swap with
unchanged original RSS path/query is tested by a new direct request.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from monitor import parse_rss
from rasd_new_sources_qa import CANDIDATES


class CanonicalRedirect(Exception):
    def __init__(self, target: str):
        self.target = target


class RejectAndRecord(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise CanonicalRedirect(newurl)


def approved_apex_swap(source_url: str, location: str,
                       hosts: tuple[str, ...]) -> str | None:
    try:
        a, b = urlsplit(source_url), urlsplit(location)
        source = a.hostname or ""
        target = b.hostname or ""
        root = source.removeprefix("www.")
        if (a.scheme != "https" or b.scheme != "https" or
                source not in hosts or target not in hosts
                or target != ("www." + root if source == root else root)
                or b.path.rstrip("/") != a.path.rstrip("/")
                or b.query != a.query or b.fragment or
                b.port not in (None, 443) or
                b.username or b.password):
            return None
        return location
    except (ValueError, AttributeError, TypeError):
        return None


def observe_one(row, keywords, *, opener=None, now=None):
    sid, name, url, hosts = row
    if opener is None:
        opener = build_opener(RejectAndRecord())
    result = {
        "source_id": sid, "status": "HOLD", "canonical_host": None,
        "original_items": 0, "matches": 0,
        "reason": "FIRST_PARTY_DIRECT_TARGET_NOT_ESTABLISHED",
    }
    try:
        with opener.open(Request(url, headers={
                "User-Agent": "RASD-canonical-native-RSS-QA/1.0"}),
                timeout=17) as response:
            # Original directly opens; canonical redirect QA is not needed.
            result["reason"] = ("ORIGINAL_ALREADY_DIRECT" if
                                response.status == 200 and response.geturl() == url
                                else "ORIGINAL_UNEXPECTED_RESPONSE")
            return result
    except CanonicalRedirect as redirect:
        target = approved_apex_swap(url, redirect.target, hosts)
        if not target:
            result["reason"] = "REJECT_REDIRECT_NOT_EXACT_WWW_APEX"
            return result
    except Exception:
        result["reason"] = "ORIGINAL_REQUEST_UNAVAILABLE"
        return result
    result["canonical_host"] = urlsplit(target).hostname
    try:
        with opener.open(Request(target, headers={
                "User-Agent": "RASD-canonical-native-RSS-QA/1.0"}),
                timeout=17) as response:
            if response.status != 200 or response.geturl() != target:
                result["reason"] = "DIRECT_TARGET_NOT_200"
                return result
            raw = response.read(1_500_001)
            if len(raw) > 1_500_000:
                result["reason"] = "DIRECT_TARGET_TOO_LARGE"
                return result
        count, matches = parse_rss(
            raw, {"id": sid, "name": name, "url": target,
                  "allowed_article_hosts": list(hosts)},
            keywords, now=now or datetime.now(timezone.utc),
            recent_hours=72, require_complete_items=True)
        if not 1 <= count <= 500:
            result["reason"] = "DIRECT_TARGET_ITEMS_INVALID"
            return result
        result.update(status="RSS_CANONICAL_QA_ONLY",
                      original_items=count, matches=len(matches),
                      reason="SCREENSHOT_AND_SOURCE_APPROVAL_PENDING")
    except CanonicalRedirect:
        result["reason"] = "DIRECT_TARGET_REDIRECTS_AGAIN"
    except Exception as exc:
        result["reason"] = (
            type(exc).__name__ if type(exc).__name__ in
            ("ValueError", "ParseError", "HTTPError", "URLError",
             "RuntimeError", "TimeoutError") else "other")
    return result


def main():
    cfg = json.loads(Path("sources_newsroom_active.json").read_text(
        encoding="utf-8"))
    originals = [x for x in CANDIDATES
                 if x[0] in {"amwalalghad", "madamasr"}]
    output = {
        "mode": "RASD_FIRST_PARTY_CANONICAL_RSS_QA_NO_SEND",
        "results": [observe_one(r, cfg["keywords"]) for r in originals],
        "email_sent": False, "production_sources_activated": 0,
        "private_state_used": False,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
