"""Manual-only integrated RSS-discovery -> real publisher screenshot proof.

If the live RSS has zero matching headlines, render a KNOWN HISTORICAL public
article as a browser regression fixture. That fixture is NEVER a new discovery.
No Gmail, recurring schedule, personal identifiers, or persistent public media.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from capture_public import APPROVED_PUBLISHERS, capture_publisher
from monitor import inspect

REFERENCE = {
    "url": "https://www.elwatannews.com/news/details/8375816",
    "headline": "وزير التخطيط يتوجه إلى بانكوك للمشاركة في الاجتماعات السنوية للبنك وصندوق النقد الدوليين",
    "publisher": "elwatannews.com",
    "selection": "historic_publisher_reference_not_new_discovery",
}


def choose_targets(inspection: dict, limit: int = 2) -> list[dict]:
    """Prefer real RSS discoveries; only use the reference when none exist."""
    found = []
    for item in inspection.get("matched_public_articles", []):
        host = urlsplit(item["url"]).hostname or ""
        for publisher, hosts in APPROVED_PUBLISHERS.items():
            if host in hosts:
                found.append({"url": item["url"], "headline": item["headline"],
                              "publisher": publisher, "selection": "live_feed_discovery"})
                break
        if len(found) >= limit:
            break
    return found or [dict(REFERENCE)]


def run(settings_path: Path, outdir: Path) -> dict:
    settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    inspection = inspect(settings)
    targets = choose_targets(inspection)
    outdir.mkdir(parents=True, exist_ok=True)
    captures = []
    for index, article in enumerate(targets, 1):
        # No user-provided filenames; all public evidence is limited to this job.
        dest = outdir / f"publisher_{index:02d}.jpg"
        captured = capture_publisher(article["url"], article["publisher"], dest)
        captures.append({**article, **captured})
    result = {
        "kind": "manual_public_publisher_capture_acceptance",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "native_feed_links_checked": inspection["public_verified_publisher_links"],
        "live_matched_headlines": inspection["planning_headline_matches"],
        "selected_for_capture": len(targets),
        "accepted_article_screenshots": sum(x["ok"] for x in captures),
        "all_targets_reference_only": all(x["selection"] != "live_feed_discovery" for x in targets),
        "captures": captures,
        "email_sent": False,
        "automatic_schedule_enabled": False,
        "state_changed": False,
        "note": "A historical publisher regression screenshot is not newly discovered news or evidence of production news coverage.",
    }
    (outdir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    if result["accepted_article_screenshots"] == 0:
        raise RuntimeError("no_visually_accepted_publisher_screenshot")
    return result


if __name__ == "__main__":
    run(Path("sources.json"), Path("evidence/capture"))
