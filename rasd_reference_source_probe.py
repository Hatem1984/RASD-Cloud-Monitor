"""Read-only strict first-party RSS qualification for sources in the owner's PDF.

This script never creates reports, visits private state or sends email.
Neither source reachability nor RSS XML alone authorizes production admission.
Public Actions prints only fixed site IDs, bounded counts and safe reason codes.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from monitor import RejectRedirect, parse_rss

# Candidate-only first-party fetch, deliberately NOT added to monitor's
# protected production RSS allowlist. Exact URLs are reviewed in the QA
# registry; no redirects, no credentials, no alternate mirror or fallback.
def read_candidate_feed(url: str, limit: int) -> bytes:
    req = Request(url, headers={"User-Agent": "RASD-original-RSS-QA/1.0"})
    with build_opener(RejectRedirect()).open(req, timeout=20) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("candidate_http_or_redirect_error")
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("candidate_rss_size_exceeded")
        return raw


SAFE_EXPLICIT_REASONS = frozenset({
    "DTD_or_entity_forbidden", "not_rss", "rss_channel_unverifiable",
    "rss_original_item_identity_unverifiable",
    "rss_original_item_date_unverifiable",
    "rss_original_duplicate_conflict",
    "candidate_http_or_redirect_error", "candidate_rss_size_exceeded",
})

ALLOWED_CODES = {
    "ValueError", "RuntimeError", "URLError", "HTTPError",
    "TimeoutError", "ParseError", "ConnectionResetError",
    "RemoteDisconnected", "OSError", "other",
}


def strict_candidate_probe(config: dict, *, fetch=None,
                           clock: datetime | None = None) -> dict:
    if fetch is None:
        fetch = read_candidate_feed
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("candidate_clock_must_have_timezone")
    checked = []
    for candidate in config["candidates"]:
        code = candidate["id"]
        if not isinstance(code, str) or not code.replace("_", "").isalnum():
            raise ValueError("candidate_id_not_safe")
        record = {
            "source_id": code, "status": "HOLD",
            "original_links": 0, "relevant_matches": 0,
            "reason": "NO_QUALIFIED_FIRST_PARTY_RSS",
        }
        url = candidate.get("rss_candidate")
        hosts = candidate.get("allowed_article_hosts", [])
        if not url:
            checked.append(record)
            continue
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.username or parts.password
                or parts.port not in (None, 443)
                or not isinstance(hosts, list) or not hosts
                or parts.hostname not in hosts
                or not all(isinstance(x, str) and x for x in hosts)):
            record["reason"] = "INVALID_HTTPS_CANDIDATE"
            checked.append(record)
            continue
        try:
            feed = {
                "id": code, "name": candidate["publisher"],
                "url": url, "allowed_article_hosts": hosts,
            }
            raw = fetch(url, 1_500_000)
            original, matches = parse_rss(
                raw, feed,
                ["وزارة التخطيط", "وزير التخطيط", "وزيرة التخطيط",
                 "التخطيط والتنمية الاقتصادية"],
                now, 72, require_complete_items=True,
            )
            if type(original) is not int or not 0 <= original <= 500:
                raise ValueError("candidate_count_untrusted")
            record.update(
                status="RSS_QA_ONLY", reason="PAGE_SCREENSHOT_PENDING",
                original_links=original, relevant_matches=len(matches),
            )
        except Exception as exc:
            # Publisher body/exception messages are untrusted. Only exact
            # internal exception labels may enter public GitHub logs.
            if type(exc) is ValueError and str(exc) in SAFE_EXPLICIT_REASONS:
                record["reason"] = str(exc)
            else:
                error = type(exc).__name__
                record["reason"] = error if error in ALLOWED_CODES else "other"
        checked.append(record)
    return {
        "mode": "strict_original_rss_admission_observation",
        "status": "ALL_CANDIDATES_REQUIRE_SEPARATE_ORIGINAL_PAGE_QA",
        "candidates": checked,
        "active_feeds_modified": False,
        "private_state_used": False,
        "email_sent": False,
        "scheduler_enabled": False,
    }


def main() -> None:
    data = json.loads(
        Path("rasd_reference_source_expansion_20261114.json").read_text(
            encoding="utf-8"))
    result = strict_candidate_probe(data)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
