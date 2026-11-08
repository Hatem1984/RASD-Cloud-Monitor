"""Bounded article HTML identity check. Metadata proof is NOT a screenshot."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser


class PageMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        value = dict(attrs)
        name = (value.get("property") or value.get("name") or "").lower()
        if name in ("og:title", "article:published_time", "datepublished",
                    "date", "pubdate") and value.get("content"):
            self.fields[name] = value["content"]


def aware_time(raw: str) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        try:
            dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            dt = parsedate_to_datetime(raw.strip())
        if dt.utcoffset() is not None:
            return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def assess_article_page(raw: bytes, *, rss_title: str,
                        rss_published_utc: str) -> dict:
    """Compare title and UTC publication minute; no content claims implied."""
    try:
        info = PageMetadata()
        info.feed(raw.decode("utf-8", "replace"))
        headline = info.fields.get("og:title", "")
        normalize = lambda s: " ".join(re.findall(r"\w+", s.casefold()))
        words = normalize(rss_title).split()
        target = " ".join(words[:6])
        if len(words) < 3 or target not in normalize(headline):
            return {"status": "HOLD_ORIGINAL_HEADLINE"}
        raw_published = next(
            (info.fields[k] for k in ("article:published_time", "datepublished",
                                      "pubdate", "date") if k in info.fields), "")
        actual = aware_time(raw_published)
        feed = aware_time(rss_published_utc)
        if actual is None or feed is None:
            return {"status": "HOLD_ORIGINAL_DATE_MISSING"}
        if abs((actual - feed).total_seconds()) > 90:
            return {"status": "HOLD_ORIGINAL_DATE_MISMATCH"}
        return {"status": "ORIGINAL_TITLE_DATE_MATCH_NO_SCREENSHOT",
                "published_utc": actual.isoformat()}
    except (ValueError, TypeError, UnicodeError):
        return {"status": "HOLD_ORIGINAL_METADATA"}
