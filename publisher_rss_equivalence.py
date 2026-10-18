"""Conservative offline qualification for a same-publisher RSS shadow URL.

This is a READ-ONLY acceptance helper, not an automatic feed switch. It
never fetches a URL, edits sources.json, changes Ministry search terms,
or makes a failed original feed count as healthy.
"""
from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from monitor import APPROVED_FEED_URLS, canonical_url


def _verified_publisher_rows(blob: bytes, publisher_hosts: tuple[str, ...]) -> dict[str, tuple[str, str]]:
    """Strict complete publisher RSS. One malformed/undated/foreign item HOLDs."""
    if not isinstance(blob, bytes) or not blob or len(blob) > 1_500_000:
        raise ValueError("publisher_rss_invalid_size")
    if b"<!DOCTYPE" in blob.upper() or b"<!ENTITY" in blob.upper():
        raise ValueError("publisher_rss_dtd_forbidden")
    root = ET.fromstring(blob)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("publisher_rss_not_native")
    rows = root.findall("./channel/item")
    if not rows:
        raise ValueError("publisher_rss_missing_items")
    output: dict[str, tuple[str, str]] = {}
    for item in rows:
        url = (item.findtext("link") or "").strip()
        title = (item.findtext("title") or "").strip()
        raw_date = (item.findtext("pubDate") or "").strip()
        address = urlsplit(url)
        if (address.scheme != "https" or address.hostname not in publisher_hosts
                or address.username or address.password or address.port not in (None, 443)
                or not title or not raw_date):
            raise ValueError("publisher_rss_unsafe_article_identity")
        try:
            date = parsedate_to_datetime(raw_date)
            if date.tzinfo is None or date.utcoffset() is None:
                raise ValueError
        except (ValueError, TypeError, IndexError, OverflowError):
            raise ValueError("publisher_rss_original_date_invalid") from None
        key = canonical_url(url)
        signature = (title, date.isoformat())
        if key in output and output[key] != signature:
            raise ValueError("publisher_rss_conflicting_duplicate")
        output[key] = signature
    return output


def audit_shadow_equivalence(
    primary_blob: bytes,
    shadow_blob: bytes,
    *,
    original_url: str = "https://www.almasryalyoum.com/rss/rssfeeds",
    shadow_url: str = "https://www.almasryalyoum.com/rss/rssfeed",
    observation_run_id: str | None = None,
) -> dict:
    """Compare one simultaneous VALID snapshot. Never imply exhaustive history.

    This is a data-integrity diagnostic; production only permits the
    currently approved primary URL even if the candidate passes one sample.
    """
    if observation_run_id is not None and (
        not isinstance(observation_run_id, str)
        or not observation_run_id.isdecimal()
        or not 6 <= len(observation_run_id) <= 24
    ):
        raise ValueError("independent_run_id_invalid")
    if original_url not in APPROVED_FEED_URLS:
        raise ValueError("primary_not_approved")
    if shadow_url != "https://www.almasryalyoum.com/rss/rssfeed":
        raise ValueError("shadow_not_reviewed")
    hosts = ("www.almasryalyoum.com", "almasryalyoum.com")
    first = _verified_publisher_rows(primary_blob, hosts)
    second = _verified_publisher_rows(shadow_blob, hosts)
    missing = set(first) - set(second)
    overlap = set(first) & set(second)
    changed = {key for key in overlap if first[key] != second[key]}
    return {
        "observation_run_id": observation_run_id,
        "primary_items": len(first),
        "shadow_items": len(second),
        "intersection": len(overlap),
        "missing_primary_items": len(missing),
        "changed_titles_or_original_dates": len(changed),
        "snapshot_no_loss": not missing and not changed,
        "production_source_switch_allowed": False,
        "rss_is_exhaustive_historical_archive": False,
    }


def require_two_valid_independent_snapshots(results: list[dict]) -> bool:
    """An isolated successful snapshot is never enough to authorize swap."""
    if len(results) < 2:
        return False
    ids = [row.get("observation_run_id") for row in results]
    if (any(not isinstance(value, str) or
            not value.isdecimal() or len(value) < 6 for value in ids)
            or len(set(ids)) != len(ids)):
        return False
    return all(
        row.get("snapshot_no_loss") is True
        and row.get("missing_primary_items") == 0
        and row.get("changed_titles_or_original_dates") == 0
        and row.get("intersection", 0) > 0
        for row in results
    )
