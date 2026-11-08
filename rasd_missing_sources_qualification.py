"""Read-only qualification of five missing RASD web reference publishers.

Explicit URLs only. Do NOT insert into active newsroom feeds or bypass
publisher blocks. Homepage access is not evidence of a working RSS endpoint.
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from rasd_publisher_metadata_qa import assess_article_page
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
from xml.etree import ElementTree

# These are candidates for a read-only check, NOT approved production feeds.
CANDIDATES = (
    {"id": "youm7", "publisher": "اليوم السابع",
     "home": "https://www.youm7.com/",
     "hosts": ("www.youm7.com", "youm7.com"),
     "rss": ("https://www.youm7.com/rss/SectionRss?SectionID=97",)},
    {"id": "daralmaref", "publisher": "بوابة دار المعارف",
     "home": "https://daralmaref.com/",
     "hosts": ("daralmaref.com", "www.daralmaref.com"),
     "rss": ("https://daralmaref.com/feed/",)},
    {"id": "soutalomma", "publisher": "صوت الأمة",
     "home": "https://www.soutalomma.com/",
     "hosts": ("www.soutalomma.com", "soutalomma.com"),
     "rss": ("https://www.soutalomma.com/rss",)},
    {"id": "forbesmiddleeast", "publisher": "فوربس الشرق الأوسط",
     "home": "https://www.forbesmiddleeast.com/",
     "hosts": ("www.forbesmiddleeast.com", "forbesmiddleeast.com"),
     "rss": ("https://www.forbesmiddleeast.com/feed",)},
    {"id": "dostor", "publisher": "الدستور",
     "home": "https://www.dostor.org/",
     "hosts": ("www.dostor.org", "dostor.org"),
     "rss": ("https://www.dostor.org/rss",)},
)
MAX_BYTES = 900_000
USER_AGENT = "RASD-Source-Qualification-ReadOnly/1"
_CAIRO = "Africa/Cairo"


class RefuseRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("HOLD_REDIRECT")


def _url_allowed(url: str, approved_hosts: tuple[str, ...]) -> bool:
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.hostname in approved_hosts
                and p.port in (None, 443) and not p.username
                and not p.password and not p.fragment)
    except ValueError:
        return False


def _fetch(url: str, hosts: tuple[str, ...], *, timeout: int = 10,
           opener=None) -> tuple[bytes, str]:
    if not _url_allowed(url, hosts):
        raise ValueError("HOLD_HOST")
    opener = opener or build_opener(
        RefuseRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.8, text/html;q=0.5",
    })
    try:
        with opener.open(request, timeout=timeout) as response:
            effective = response.geturl()
            if effective != url:
                raise ValueError("HOLD_FINAL_URL")
            ctype = response.headers.get("Content-Type", "")
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("HOLD_SIZE")
            return raw, ctype
    except HTTPError:
        raise RuntimeError("HOLD_HTTP") from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("HOLD_NETWORK") from None


def _date(value: str) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        try:
            x = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            x = parsedate_to_datetime(value.strip())
        return x.astimezone(timezone.utc) if x.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def assess_rss(raw: bytes, hosts: tuple[str, ...]) -> dict:
    """Strict native feed test: XML, source links, timezone-aware item dates."""
    if len(raw) > MAX_BYTES or len(raw) < 15:
        return {"status": "HOLD_EMPTY_OR_OVERSIZE"}
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return {"status": "HOLD_INVALID_XML"}
    if root.tag == "rss":
        entries = root.findall("./channel/item")
        rows = [(e.findtext("link"), e.findtext("pubDate"), e.findtext("title"))
                for e in entries]
    elif root.tag == "{http://www.w3.org/2005/Atom}feed":
        ns = "{http://www.w3.org/2005/Atom}"
        entries = root.findall(ns + "entry")
        rows = []
        for e in entries:
            links = [link.get("href", "") for link in e.findall(ns + "link")
                     if link.get("rel", "alternate") == "alternate"]
            rows.append((links[0] if links else "",
                         e.findtext(ns + "published") or e.findtext(ns + "updated"),
                         e.findtext(ns + "title")))
    else:
        return {"status": "HOLD_NOT_FEED"}
    if not rows:
        return {"status": "HOLD_NO_ITEMS"}
    verified = []
    for link, when, title in rows:
        if not _url_allowed(str(link or ""), hosts):
            return {"status": "HOLD_CROSS_HOST_ITEM", "items_seen": len(rows)}
        if not isinstance(title, str) or not title.strip():
            return {"status": "HOLD_MISSING_TITLE", "items_seen": len(rows)}
        date = _date(str(when or ""))
        if date is None:
            return {"status": "HOLD_AMBIGUOUS_ITEM_DATE", "items_seen": len(rows)}
        verified.append((str(link), date.isoformat()))
    # RSS parse alone is not source-image/headline equivalence QA.
    return {"status": "RSS_STRICT_READABLE_NOT_APPROVED",
            "items_seen": len(rows), "sample_url": verified[0][0],
            "sample_published_utc": verified[0][1],
            "sample_title": rows[0][2].strip()}


def _one_source(item: dict, *, fetcher=_fetch) -> dict:
    hosts = tuple(item["hosts"])
    result = {"id": item["id"], "publisher": item["publisher"],
              "activation": "HOLD_NOT_APPROVED", "rss": []}
    try:
        fetcher(item["home"], hosts)
        result["homepage"] = "READABLE"
    except (RuntimeError, ValueError):
        result["homepage"] = "UNAVAILABLE"
    for url in item["rss"]:
        entry = {"endpoint": url}
        try:
            raw, ctype = fetcher(url, hosts)
            entry.update(assess_rss(raw, hosts))
            entry["content_type"] = ctype.split(";", 1)[0].strip()[:60]
            if entry["status"] == "RSS_STRICT_READABLE_NOT_APPROVED":
                try:
                    page, _page_type = fetcher(entry["sample_url"], hosts)
                    entry["original_article"] = assess_article_page(
                        page, rss_title=entry["sample_title"],
                        rss_published_utc=entry["sample_published_utc"])
                except (RuntimeError, ValueError) as exc:
                    entry["original_article"] = {
                        "status": (str(exc) if str(exc).startswith("HOLD_")
                                   else "HOLD_ORIGINAL_PAGE")}
        except (RuntimeError, ValueError) as exc:
            error = str(exc)
            entry["status"] = (error if error.startswith("HOLD_")
                               else "HOLD_FETCH")
        result["rss"].append(entry)
    return result


def qualify(*, live: bool, fetcher=_fetch) -> dict:
    if not live:
        return {"status": "DRY_RUN_NO_NETWORK",
                "candidates": [x["id"] for x in CANDIDATES],
                "activated": 0, "email_sent": False}
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows = list(pool.map(lambda item: _one_source(item, fetcher=fetcher),
                             CANDIDATES))
    return {"status": "READ_ONLY_CANDIDATE_QA",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "candidates": rows, "activated": 0,
            "email_sent": False, "schedule_changed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="RASD missing publisher QA, no send")
    parser.add_argument("--live-readonly", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(
        "report-output/web-qualification/missing-five.json"))
    args = parser.parse_args()
    result = qualify(live=args.live_readonly)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(
        result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
