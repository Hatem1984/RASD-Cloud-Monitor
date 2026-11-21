"""Read-only live evidence: approved RSS, STRICTLY previous completed hour.

Print only aggregated counts, never news text, article URLs, private data,
SMTP secrets, attachments or original screenshots. A passing RSS candidate
is NOT an accepted photographed Word news item.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from monitor import inspect
from rasd_strict_hourly_ten_source_gate import audit_fresh_distinct_sources


def main() -> None:
    config=json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    now=datetime.now(timezone.utc)
    observed=inspect(config,now=now,article_limit=200,
                     require_complete_items=True)
    if observed.get("matched_article_pool_truncated"):
        raise RuntimeError("latest_hour_inventory_truncated_hold")
    result=audit_fresh_distinct_sources(
        observed["matched_public_articles"], config["feeds"], now)
    healthy=sum(source["status"]=="ok" for source in observed["sources"])
    print("RASD_STRICT_TEN_LIVE_HOUR="+
          json.dumps({
              "run_utc":now.isoformat(),
              "hour_start_utc":result["window_start_utc"],
              "hour_end_utc":result["window_end_utc"],
              "configured_publishers":len(config["feeds"]),
              "healthy_rss_sources":healthy,
              "rss_matches_in_72h":observed["planning_headline_matches"],
              "fresh_distinct_publisher_news_candidates":
                  result["fresh_distinct_candidates"],
              "required":result["required_articles"],
              "status":result["status"],
              "no_images_proved":True,
              "no_smtp_sent":True,
              "not_guarantee_any_future_hour":True,
          },ensure_ascii=True,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
