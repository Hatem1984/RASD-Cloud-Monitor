"""Strict acceptance for proposed RASD hourly reports: 10 real news / 10 publishers.

Research and preflight ONLY. Does not send email, change scheduling, or
manufacture article pictures. Publication time must be a verified, explicitly
timezone-aware ORIGINAL-PUBLISHER timestamp, within the last COMPLETED
UTC hour. Updated time or crawler fetch time is never a substitute.

A shortfall is a transparent HOLD, not permission to include older news.
Caller MUST run original screenshot + Word JPEG digest gates before any
report can be considered complete and must verify the minimum AFTER capture.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from event_identity import same_event
from monitor import article_id, canonical_url

TARGET_MIN_ARTICLES = 10
TARGET_MIN_PUBLISHERS = 10
MAX_HOURLY_ARTICLES = 15


def last_completed_hour(now: datetime) -> tuple[datetime, datetime]:
    if (not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None):
        raise ValueError("strict_hourly_clock_requires_timezone")
    end = now.astimezone(timezone.utc).replace(
        minute=0, second=0, microsecond=0)
    return end - timedelta(hours=1), end


def _published_utc(article: dict) -> datetime | None:
    # Only original RSS's unmodified RFC822 datetime or an independently
    # verified publisher timestamp passed as timezone-aware ISO 8601.
    value = article.get("published")
    iso = article.get("published_utc")
    try:
        if isinstance(value, str) and value:
            date = parsedate_to_datetime(value)
        elif isinstance(iso, str) and iso:
            date = datetime.fromisoformat(iso)
        else:
            return None
        if date.tzinfo is None or date.utcoffset() is None:
            return None
        return date.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, IndexError):
        return None


def audit_fresh_distinct_sources(
    articles: list[dict], feeds: list[dict], now: datetime,
    *, required: int = TARGET_MIN_ARTICLES,
    max_items: int = MAX_HOURLY_ARTICLES,
) -> dict:
    """Read-only count; ready means CANDIDATES, not original photos proved.

    Rejects untrusted URL/source identity and cross-publisher syndicated
    versions of the same event. On shortfall, selected is empty: no
    partial bulletin can accidentally be sent by the caller.
    """
    if (not isinstance(articles, list) or not isinstance(feeds, list)
            or type(required) is not int
            or type(max_items) is not int
            or not 1 <= required <= max_items <= MAX_HOURLY_ARTICLES):
        raise ValueError("strict_hourly_inputs_invalid")
    start, end = last_completed_hour(now)
    by_name = {}
    for feed in feeds:
        if not isinstance(feed, dict):
            raise ValueError("strict_hourly_feed_profile_invalid")
        name = feed.get("name")
        hosts = feed.get("allowed_article_hosts")
        if (not isinstance(name, str) or not name
                or name in by_name
                or not isinstance(hosts, list) or not hosts
                or any(not isinstance(host, str) or not host for host in hosts)):
            raise ValueError("strict_hourly_feed_profile_invalid")
        by_name[name] = set(hosts)

    rejected = {
        "unverified_source": 0,
        "wrong_original_date": 0,
        "not_in_last_completed_hour": 0,
        "duplicate_article": 0,
        "same_publisher": 0,
        "repeated_event": 0,
    }
    prepared=[]
    seen_article_ids=set()
    for item in articles:
        if not isinstance(item,dict):
            rejected["unverified_source"] += 1
            continue
        source=item.get("source")
        url=item.get("url")
        item_id=item.get("id")
        if (source not in by_name or not isinstance(url,str)
                or not isinstance(item_id,str)
                or not isinstance(item.get("headline"),str)):
            rejected["unverified_source"] += 1
            continue
        try:
            host=urlsplit(url).hostname
            safe=(urlsplit(url).scheme=="https"
                  and urlsplit(url).port in (None,443)
                  and not urlsplit(url).username
                  and not urlsplit(url).password
                  and host in by_name[source]
                  and article_id(url)==item_id
                  and canonical_url(url)==url)
        except (ValueError,TypeError):
            safe=False
        if not safe:
            rejected["unverified_source"] += 1
            continue
        if item_id in seen_article_ids:
            rejected["duplicate_article"] += 1
            continue
        seen_article_ids.add(item_id)
        stamp=_published_utc(item)
        if stamp is None:
            rejected["wrong_original_date"] += 1
            continue
        if not start <= stamp < end:
            rejected["not_in_last_completed_hour"] += 1
            continue
        prepared.append((stamp, source, item))
    # Use NEWEST first and one publisher only. Without this, five stories
    # from one website could masquerade as five independent news sources.
    prepared.sort(key=lambda row:(row[0],row[1]),reverse=True)
    accepted=[]
    publisher_set=set()
    for stamp, source, original in prepared:
        if source in publisher_set:
            rejected["same_publisher"] += 1
            continue
        normalized={
            **original,
            "published_at_cairo": stamp.strftime("%Y-%m-%d %H:%M"),
        }
        if any(same_event(normalized, prev) for prev in accepted):
            rejected["repeated_event"] += 1
            continue
        accepted.append(normalized)
        publisher_set.add(source)
        if len(accepted)==max_items:
            break
    ready=len(accepted)>=required and len(publisher_set)>=required
    return {
        "status":"CANDIDATES_NEED_ORIGINAL_IMAGES" if ready else
                 "HOLD_NOT_ENOUGH_FRESH_INDEPENDENT_SOURCES",
        "required_articles":required,
        "required_publishers":required,
        "fresh_distinct_candidates":len(accepted),
        "different_sources":len(publisher_set),
        "window_start_utc":start.isoformat(),
        "window_end_utc":end.isoformat(),
        "rejection_counts":rejected,
        "selected":accepted if ready else [],
        "smtp_sent":False,
        "original_images_verified":False,
    }


def originals_report_ready(candidate_audit: dict, delivered: list[dict]) -> bool:
    """Post-picture check. Caller still must verify Word JPEGs with digests."""
    if candidate_audit.get("status")!="CANDIDATES_NEED_ORIGINAL_IMAGES":
        return False
    if not isinstance(delivered,list):
        return False
    desired=candidate_audit["selected"]
    delivered_ids=[item.get("id") for item in delivered if isinstance(item,dict)]
    if len(delivered_ids)!=len(delivered):
        return False
    if len(delivered)<TARGET_MIN_ARTICLES:
        return False
    desired_by_id={row["id"]:row for row in desired}
    if len(set(delivered_ids))!=len(delivered_ids):
        return False
    if any(id not in desired_by_id for id in delivered_ids):
        return False
    sources=set()
    for item in delivered:
        original=desired_by_id[item["id"]]
        if item.get("source")!=original["source"]:
            return False
        if (not isinstance(item.get("evidence_image_path"),str)
                or not item["evidence_image_path"]):
            return False
        sources.add(original["source"])
    return len(sources)>=TARGET_MIN_PUBLISHERS
