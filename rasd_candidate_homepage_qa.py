"""Batched limited research-only first-party homepage reachability checks.

Never claim a reachable homepage is a qualified RSS feed, news item, reliable
date or publisher screenshot. Never follow redirects, inspect internal URLs,
include credentials, send email, or mutate active 13 source definitions.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from research_source_queries_100 import load_100_sources

SAMPLE_IDS = (
    "soutalomma", "daralmaref", "forbesmiddleeast", "arabfinance",
    "cbe_official", "mof_official", "gafi_official", "fra_official",
    "eces_research", "erf_research", "worldbank_egypt", "undp_egypt",
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("candidate_redirect_no_follow")


def probe_homepage(row: dict, *, opener=None) -> dict:
    # URL is selected ONLY from a previously strictly validated registry.
    url = row["homepage_url"]
    result = {"id": row["id"], "status": "HOLD",
              "detail": "NOT_VERIFIED_ORIGINAL_RSS"}
    try:
        p = urlsplit(url)
        if (p.scheme != "https" or p.hostname !=
                row["publisher_host"] and p.hostname !=
                "www." + row["publisher_host"] or
                p.port not in (None, 443) or p.username or p.password):
            result["detail"] = "CANDIDATE_URL_INVALID"
            return result
        if opener is None:
            opener = build_opener(NoRedirect())
        with opener.open(
            Request(url, headers={"User-Agent": "RASD-public-source-research/1.0"}),
            timeout=8,
        ) as response:
            if response.status == 200 and response.geturl() == url:
                result.update(status="HOMEPAGE_REACHABLE_ONLY",
                              detail="RSS_DATE_SCREENSHOT_STILL_UNVERIFIED")
            else:
                result["detail"] = "HOMEPAGE_RESPONSE_NOT_DIRECT"
    except RuntimeError:
        result["detail"] = "HOMEPAGE_REDIRECT_NOT_FOLLOWED"
    except HTTPError:
        result["detail"] = "HOMEPAGE_HTTP_FAILURE"
    except (URLError, OSError, TimeoutError):
        result["detail"] = "HOMEPAGE_NETWORK_FAILURE"
    except Exception:
        result["detail"] = "OTHER_HOMEPAGE_HOLD"
    return result


def main():
    data = load_100_sources()
    sources = {x["id"]: x for x in data["sources"][50:]}
    if any(sid not in sources for sid in SAMPLE_IDS):
        raise RuntimeError("rasd_research_candidate_subset_missing")
    with ThreadPoolExecutor(max_workers=3) as executor:
        outcomes = list(executor.map(
            probe_homepage, [sources[sid] for sid in SAMPLE_IDS]))
    print(json.dumps({
        "mode": "RASD_HOMEPAGE_RESEARCH_ONLY_NO_SEND",
        "total_research_origins": 100,
        "approved_automated_rss_feeds": 13,
        "sampled_homepages": len(outcomes),
        "reachable_landing_pages": sum(
            x["status"] == "HOMEPAGE_REACHABLE_ONLY" for x in outcomes),
        "outcomes": outcomes,
        "rss_sources_approved_by_test": 0,
        "article_dates_verified_by_test": 0,
        "original_screenshots_verified_by_test": 0,
        "private_ledger_changed": False,
        "emails_sent": False,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
