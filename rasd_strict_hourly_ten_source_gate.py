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
from monitor import article_id

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
    versions of the same event. Owner policy: keep 1–9 valid candidates
    available for an HONEST partial Word, with the shortfall explicit.
    A candidate is not photographed/accepted until downstream Word evidence.
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

    decisions=[]
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
        identifier = item.get("id") if isinstance(item,dict) else None
        def decide(reason):
            # Keep opaque article IDs rather than private/raw page payloads.
            decisions.append({"id": identifier if isinstance(identifier,str)
                              and len(identifier)==24 else None,
                              "outcome": reason})
        if not isinstance(item,dict):
            rejected["unverified_source"] += 1
            decide("unverified_source")
            continue
        source=item.get("source")
        url=item.get("url")
        item_id=item.get("id")
        if (source not in by_name or not isinstance(url,str)
                or not isinstance(item_id,str)
                or not isinstance(item.get("headline"),str)):
            rejected["unverified_source"] += 1
            decide("unverified_source")
            continue
        try:
            host=urlsplit(url).hostname
            safe=(urlsplit(url).scheme=="https"
                  and urlsplit(url).port in (None,443)
                  and not urlsplit(url).username
                  and not urlsplit(url).password
                  and host in by_name[source]
                  and article_id(url)==item_id)
        except (ValueError,TypeError):
            safe=False
        if not safe:
            rejected["unverified_source"] += 1
            decide("unverified_source")
            continue
        if item_id in seen_article_ids:
            rejected["duplicate_article"] += 1
            decide("duplicate_article")
            continue
        seen_article_ids.add(item_id)
        stamp=_published_utc(item)
        if stamp is None:
            rejected["wrong_original_date"] += 1
            decide("wrong_original_date")
            continue
        if not start <= stamp < end:
            rejected["not_in_last_completed_hour"] += 1
            decide("not_in_last_completed_hour")
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
            decisions.append({"id":original["id"],"outcome":"same_publisher"})
            continue
        # Keep Cairo publication time supplied by the original-source parser.
        # UTC timestamp is ONLY for exact clock boundaries; never relabel UTC
        # wall time as Cairo on an accepted item.
        normalized=dict(original)
        if any(same_event(normalized, prev) for prev in accepted):
            rejected["repeated_event"] += 1
            decisions.append({"id":original["id"],"outcome":"repeated_event"})
            continue
        accepted.append(normalized)
        publisher_set.add(source)
        decisions.append({"id":original["id"],"outcome":"accepted_candidate"})
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
        "selected":accepted,
        "candidate_decisions":decisions,
        "smtp_sent":False,
        "original_images_verified":False,
    }


def originals_selection_valid(candidate_audit: dict, delivered: list[dict]) -> bool:
    """Validate exact original publisher evidence identity for ANY 1–15 photos.

    The caller must also verify every JPEG digest inside the *actual Word*.
    Partial reports with 1–9 originals are allowed by owner's accepted
    shortfall policy, provided source and event identities are unchanged.
    """
    desired=candidate_audit.get("selected")
    if not isinstance(desired,list) or not isinstance(delivered,list):
        return False
    if not 1 <= len(delivered) <= len(desired) <= MAX_HOURLY_ARTICLES:
        return False
    desired_by_id={row.get("id"):row for row in desired}
    if len(desired_by_id)!=len(desired):
        return False
    ids=[item.get("id") for item in delivered if isinstance(item,dict)]
    if len(ids)!=len(delivered) or len(set(ids))!=len(ids):
        return False
    publishers=set()
    for item in delivered:
        original=desired_by_id.get(item["id"])
        if original is None or item.get("source")!=original["source"]:
            return False
        if (not isinstance(item.get("evidence_image_path"),str)
                or not item["evidence_image_path"]):
            return False
        publishers.add(item["source"])
    if len(publishers)!=len(delivered):
        return False
    return all(
        not same_event(delivered[i],delivered[j])
        for i in range(len(delivered))
        for j in range(i+1,len(delivered))
    )


def originals_report_ready(candidate_audit: dict, delivered: list[dict]) -> bool:
    """Full 10/10 acceptance; valid photographed shortfalls may still send."""
    return (originals_selection_valid(candidate_audit,delivered)
            and len(delivered)>=TARGET_MIN_ARTICLES)
