"""Read-only provenance check for publisher-owned Atom discovery feeds.

Atom is a candidate research format, never a source-approval shortcut.
Require ALL entries to have same-publisher article links and publisher-owned,
timezone-aware <published>. <updated> is NOT publication time. Browser photo
and exact original page checks remain separate production gates.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from monitor import _ministry_term_present, _native_text, article_id, is_publisher_link

ATOM = "{http://www.w3.org/2005/Atom}"


def parse_first_party_atom(data: bytes, feed: dict, keywords: list[str],
                           now: datetime, *, recent_hours: int = 72) -> tuple[int, list[dict]]:
    if not isinstance(data, bytes) or len(data) > 1_500_000 or (
            b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper()):
        raise ValueError("atom_unsafe_xml")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("atom_naive_clock")
    root = ET.fromstring(data)
    if root.tag != ATOM + "feed":
        raise ValueError("not_atom")
    entries = root.findall(ATOM + "entry")
    if not entries:
        raise ValueError("atom_no_entries")
    matched, seen = [], {}
    clock = now.astimezone(timezone.utc)
    for node in entries:
        title = " ".join((node.findtext(ATOM + "title") or "").split())[:300]
        links = [x.get("href", "").strip()
                 for x in node.findall(ATOM + "link")
                 if x.get("rel", "alternate") == "alternate"
                 and x.get("type", "text/html") in ("text/html", "")]
        links = [x for x in links if is_publisher_link(
            x, feed["allowed_article_hosts"])]
        raw_published = (node.findtext(ATOM + "published") or "").strip()
        if not title or len(links) != 1 or not raw_published:
            raise ValueError("atom_original_entry_identity_or_date_unverifiable")
        try:
            when = datetime.fromisoformat(raw_published.replace("Z", "+00:00"))
        except (ValueError, OverflowError):
            raise ValueError("atom_original_date_unverifiable") from None
        if when.tzinfo is None or when.utcoffset() is None:
            raise ValueError("atom_original_date_unverifiable")
        url = links[0]
        key = article_id(url)
        signature = (title, raw_published)
        if key in seen:
            if seen[key] != signature:
                raise ValueError("atom_conflicting_original_entries")
            continue
        seen[key] = signature
        summary = node.find(ATOM + "summary")
        excerpt = _native_text("".join(summary.itertext())[:3500])[:850] if summary is not None else ""
        match_title = _ministry_term_present(title, keywords)
        match_description = _ministry_term_present(excerpt, keywords)
        if not (match_title or match_description):
            continue
        if not clock - timedelta(hours=recent_hours) <= when.astimezone(timezone.utc) <= clock:
            continue
        # Generate an RFC-822 date with an explicit offset for the existing
        # read-only match-window counters, without ever inferring a timezone.
        from email.utils import format_datetime
        matched.append({
            "id": key, "source": feed["name"], "headline": title, "url": url,
            "published": format_datetime(when), "publisher_excerpt": excerpt,
            "match_origin": "title" if match_title else "publisher_description",
        })
    return len(seen), matched
