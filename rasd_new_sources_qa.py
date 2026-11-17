"""RASD original-publisher candidate qualification, no source activation or mail.

These are RESEARCH CANDIDATES, not approved production sources. Checks one
reviewed first-party HTTPS URL per candidate; strictly refuses redirects,
incomplete/malformed publisher RSS, unzoned original dates and unsafe links.
Outputs only source IDs/counts and fixed failure labels. No publisher article
texts/URLs/screenshots, Word, secrets or Gmail leave this process.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from monitor import RejectRedirect, parse_rss

# Candidate research. An unverified endpoint does not imply endorsement.
CANDIDATES = (
    ("amwalalghad", "أموال الغد", "https://amwalalghad.com/feed/",
     ("amwalalghad.com", "www.amwalalghad.com")),
    ("ahramonline", "Ahram Online", "https://english.ahram.org.eg/rss.aspx",
     ("english.ahram.org.eg",)),
    ("ahramgate", "بوابة الأهرام", "https://gate.ahram.org.eg/rss",
     ("gate.ahram.org.eg",)),
    ("youm7_reports", "اليوم السابع", "https://www.youm7.com/rss/SectionRss?SectionID=97",
     ("www.youm7.com",)),
    ("madamasr", "مدى مصر", "https://www.madamasr.com/ar/feed/",
     ("www.madamasr.com", "madamasr.com")),
)

SAFE_REASON = frozenset({
    "candidate_url_untrusted", "candidate_redirect_or_status",
    "candidate_size_limit", "DTD_or_entity_forbidden", "not_rss",
    "rss_channel_unverifiable", "rss_original_item_identity_unverifiable",
    "rss_original_item_date_unverifiable", "rss_original_duplicate_conflict",
})

SAFE_EXCEPTION_TYPES = frozenset({
    "HTTPError", "URLError", "TimeoutError", "ParseError",
    "ConnectionResetError", "RemoteDisconnected", "OSError",
    "RuntimeError", "ValueError",
})


def fetch_direct(url: str, hosts: tuple[str, ...], *, max_bytes: int = 1500000) -> bytes:
    p = urlsplit(url)
    if (p.scheme != "https" or p.hostname not in hosts or
            p.port not in (None, 443) or p.username or p.password
            or p.fragment):
        raise ValueError("candidate_url_untrusted")
    req = Request(url, headers={"User-Agent": "RASD-original-candidate-QA/1.0"})
    with build_opener(RejectRedirect()).open(req, timeout=17) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("candidate_redirect_or_status")
        raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("candidate_size_limit")
    return raw


def probe_candidate(row: tuple, terms: list[str], now: datetime,
                    *, fetch=fetch_direct) -> dict:
    sid, label, url, hosts = row
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", sid):
        raise ValueError("unsafe_research_candidate_id")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_required")
    result = {
        "source_id": sid, "status": "HOLD", "strict_original_links": 0,
        "keyword_matches": 0, "reason": None,
        "original_page_screenshot_verified": False,
    }
    try:
        raw = fetch(url, hosts)
        count, matches = parse_rss(
            raw, {"id": sid, "name": label, "url": url,
                  "allowed_article_hosts": list(hosts)},
            terms, now=now, recent_hours=72, require_complete_items=True)
        if type(count) is not int or not (1 <= count <= 500):
            raise ValueError("candidate_item_count_untrusted")
        result.update(
            status="RSS_ONLY_QA", strict_original_links=count,
            keyword_matches=len(matches),
            reason="PUBLISHER_SCREENSHOT_AND_SOURCE_APPROVAL_PENDING",
        )
    except Exception as exc:
        if type(exc) is ValueError and str(exc) in SAFE_REASON:
            result["reason"] = str(exc)
        elif type(exc).__name__ in SAFE_EXCEPTION_TYPES:
            result["reason"] = type(exc).__name__
        else:
            result["reason"] = "other"
    return result


def observe_all(config: dict, *, fetch=fetch_direct, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    approved_ids = {x["id"] for x in config["feeds"]}
    candidates = [probe_candidate(row, config["keywords"], now, fetch=fetch)
                  for row in CANDIDATES if row[0] not in approved_ids]
    return {
        "mode": "RASD_CANDIDATE_NATIVE_RSS_QA_NO_SEND",
        "candidate_count": len(candidates), "results": candidates,
        "new_production_sources_activated": 0,
        "emails_sent": 0, "private_ledger_used": False,
        "screenshots_and_word_created": False,
        "note": "RSS_ONLY_QA is NOT final publisher-page screenshot acceptance",
    }


def main():
    cfg = json.loads(Path("sources_newsroom_active.json").read_text(
        encoding="utf-8"))
    print(json.dumps(observe_all(cfg), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
