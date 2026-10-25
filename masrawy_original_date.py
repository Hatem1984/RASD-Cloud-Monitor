"""Publisher-owned, timezone-aware publication timestamp for Masrawy RSS items.

Masrawy's native RSS pubDate omits time zone. Never infer Cairo/UTC
from that field. Accept only if publisher ORIGINAL ARTICLE includes valid
NewsArticle JSON-LD with explicit UTC offset and matching exact local wall
clock and headline. Fail closed on redirects, spoofed hosts, malformed
metadata, oversize bodies, contradictory dates, or network failures.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime
from email.utils import format_datetime
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_PAGE_BYTES = 750_000
ORIGINAL_HOSTS = frozenset({"www.masrawy.com", "masrawy.com"})
_JSONLD = re.compile(
    r"<script\b[^>]{0,500}\btype\s*=\s*[\"']application/ld\+json[\"']"
    r"[^>]{0,500}>(.*?)</script\s*>", re.I | re.S
)


class DenyRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("masrawy_original_page_redirect_forbidden")


def fetch_original_page(url: str) -> bytes:
    try:
        p = urlsplit(url)
        if (p.scheme != "https" or p.hostname not in ORIGINAL_HOSTS
                or (p.port is not None and p.port != 443)
                or p.username or p.password or not p.path.startswith("/news/")):
            raise ValueError("masrawy_original_url_not_approved")
        req = Request(url, headers={"User-Agent": "RASD-Cloud-Public-Monitor/0.1"})
        with build_opener(DenyRedirect()).open(req, timeout=12) as resp:
            if (resp.status != 200 or resp.geturl() != url
                    or "html" not in resp.headers.get("Content-Type", "").lower()):
                raise ValueError("masrawy_original_page_unavailable")
            page = resp.read(MAX_PAGE_BYTES + 1)
        if not 100 <= len(page) <= MAX_PAGE_BYTES:
            raise ValueError("masrawy_original_page_size_hold")
        return page
    except (ValueError, RuntimeError):
        raise
    except Exception:
        # Do not log response, URL, headers or upstream exception body.
        raise RuntimeError("masrawy_original_page_request_hold") from None


def _flat_text(value: str) -> str:
    return " ".join(html.unescape(value).split()).casefold()


def original_pubdate(url: str, rss_title: str, rss_pubdate: str, *,
                     fetch=fetch_original_page) -> tuple[datetime, str]:
    """Read publisher page only and return its explicit time-zoned publication.

    Exact RSS naive date must equal the publisher NewsArticle JSON-LD's
    own local wall clock. No timezone is assigned to an unzoned RSS time.
    """
    if not isinstance(rss_title, str) or not rss_title.strip():
        raise ValueError("masrawy_rss_title_invalid")
    if not isinstance(rss_pubdate, str) or len(rss_pubdate) > 40:
        raise ValueError("masrawy_rss_timestamp_invalid")
    try:
        unzoned = datetime.strptime(rss_pubdate.strip(),
                                    "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        raise ValueError("masrawy_rss_timestamp_unrecognized") from None
    data = fetch(url)
    if not isinstance(data, bytes) or len(data) > MAX_PAGE_BYTES:
        raise ValueError("masrawy_original_html_invalid")
    text = data.decode("utf-8", "replace")
    valid = []
    for match in _JSONLD.finditer(text):
        if len(match.group(1)) > 100_000:
            continue
        try:
            block = json.loads(match.group(1))
        except (ValueError, TypeError):
            continue
        blocks = block if isinstance(block, list) else [block]
        for item in blocks:
            if not isinstance(item, dict):
                continue
            kind = item.get("@type")
            if "NewsArticle" not in (kind if isinstance(kind, list) else [kind]):
                continue
            headline = item.get("headline")
            iso = item.get("datePublished")
            if (not isinstance(headline, str)
                    or _flat_text(headline) != _flat_text(rss_title)
                    or not isinstance(iso, str) or len(iso) > 50):
                continue
            try:
                dated = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            except ValueError:
                continue
            if dated.tzinfo is None or dated.utcoffset() is None:
                continue
            if dated.replace(tzinfo=None) != unzoned:
                continue
            valid.append(dated)
    if not valid or len({v.isoformat() for v in valid}) != 1:
        raise ValueError("masrawy_publisher_publication_date_unverified")
    return valid[0], format_datetime(valid[0])
