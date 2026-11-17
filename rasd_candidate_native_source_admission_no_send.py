"""Bounded source-admission research — six REVIEW candidates; NO SEND.

A public publisher homepage is not an approved RSS feed. Do not change active
sources, aliases, original-photo browser allowlists or daily email. Reject
redirects, malicious DTD, spoofed article hosts and naive article dates.
Log only fixed source IDs/counts/failure codes; no headlines or URLs.
"""
from __future__ import annotations

import json
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree as ET

CANDIDATES = (
    ("youm7_economy", "https://www.youm7.com/rss/SectionRss?SectionID=297",
     ("www.youm7.com",)),
    ("youm7_governorates", "https://www.youm7.com/rss/SectionRss?SectionID=296",
     ("www.youm7.com",)),
    ("daralmaref", "https://daralmaref.com/feed/",
     ("daralmaref.com", "www.daralmaref.com")),
    ("soutalomma", "https://www.soutalomma.com/rss/rss",
     ("www.soutalomma.com",)),
    ("dostor", "https://www.dostor.org/rss",
     ("www.dostor.org", "dostor.org")),
    ("forbesmiddleeast", "https://www.forbesmiddleeast.com/ar/rss",
     ("www.forbesmiddleeast.com",)),
)
MAX_BYTES = 1_000_000


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("ORIGIN_REDIRECT_HOLD")


def validate_native_feed(raw: bytes, allowed_hosts: tuple[str, ...]) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        return {"status":"HOLD","reason":"RSS_SIZE_INVALID"}
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        return {"status":"HOLD","reason":"RSS_XML_ENTITY_FORBIDDEN"}
    try:
        root=ET.fromstring(raw)
    except ET.ParseError:
        return {"status":"HOLD","reason":"RSS_XML_MALFORMED"}
    if root.tag.rsplit("}",1)[-1]!="rss" or root.find("channel") is None:
        return {"status":"HOLD","reason":"NOT_NATIVE_RSS"}
    items=root.findall("./channel/item")
    if not 1<=len(items)<=400:
        return {"status":"HOLD","reason":"RSS_INVENTORY_INVALID"}
    # Verify ALL RSS item identities and original publication clock, not
    # just the first five, before calling an origin an RSS-stage candidate.
    for item in items:
        title=(item.findtext("title") or "").strip()
        url=(item.findtext("link") or "").strip()
        raw_date=(item.findtext("pubDate") or "").strip()
        try:
            parsed=urlsplit(url)
            if (not title or len(title)>1000 or
                    parsed.scheme!="https" or parsed.hostname not in allowed_hosts or
                    parsed.port not in (None,443) or parsed.username or
                    parsed.password or parsed.fragment):
                return {"status":"HOLD","reason":"ARTICLE_ORIGIN_UNVERIFIED"}
        except (ValueError,TypeError):
            return {"status":"HOLD","reason":"ARTICLE_ORIGIN_UNVERIFIED"}
        try:
            date=parsedate_to_datetime(raw_date)
            if date is None or date.tzinfo is None or date.utcoffset() is None:
                return {"status":"HOLD","reason":"PUBLISHER_DATE_UNVERIFIABLE"}
        except (ValueError,TypeError,OverflowError,IndexError):
            return {"status":"HOLD","reason":"PUBLISHER_DATE_UNVERIFIABLE"}
    return {"status":"RSS_STAGE_QUALIFIED_ONLY",
            "reason":"ORIGINAL_JPEG_AND_OWNER_ACTIVATION_STILL_REQUIRED",
            "original_links":len(items)}


def probe(entry, *, fetch=None) -> dict:
    source_id, url, approved_hosts = entry
    result={"id":source_id,"status":"HOLD","reason":"NOT_CHECKED",
            "original_links":0,"original_screenshot_verified":False,
            "activated":False}
    try:
        parsed=urlsplit(url)
        if (parsed.scheme!="https" or parsed.hostname not in approved_hosts
                or parsed.port not in (None,443) or
                parsed.username or parsed.password or parsed.fragment):
            result["reason"]="CANDIDATE_URL_INVALID"
            return result
        if fetch is None:
            def fetch(endpoint):
                with build_opener(NoRedirect()).open(
                    Request(endpoint,headers={
                        "User-Agent":"RASD-original-source-admission-review/1.0",
                        "Accept":"application/rss+xml,application/xml,text/xml",
                    }),timeout=11) as r:
                    if r.status!=200 or r.geturl()!=endpoint:
                        raise ValueError("ORIGIN_HTTP_NOT_200")
                    return r.read(MAX_BYTES+1)
        accepted=validate_native_feed(fetch(url),approved_hosts)
        result.update(accepted)
    except (RuntimeError,ValueError) as err:
        reason=str(err)
        result["reason"] = reason if reason in (
            "ORIGIN_REDIRECT_HOLD","ORIGIN_HTTP_NOT_200") else "OTHER_HOLD"
    except HTTPError as err:
        result["reason"]=(
            "HTTP_401_403_HOLD" if err.code in (401,403) else
            "HTTP_404_HOLD" if err.code==404 else
            "HTTP_RATE_LIMIT_HOLD" if err.code==429 else "HTTP_ERROR_HOLD")
    except (URLError,OSError,TimeoutError):
        result["reason"]="ORIGIN_CONNECTION_HOLD"
    except Exception:
        result["reason"]="OTHER_HOLD"
    return result


def main():
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(probe,CANDIDATES))
    print(json.dumps({
        "mode":"RASD_SIX_CANDIDATE_FIRSTPARTY_RSS_ADMISSION_NO_SEND",
        "source_candidates_checked":len(outcomes),
        "rss_stage_qualified":sum(r["status"]=="RSS_STAGE_QUALIFIED_ONLY"
                                  for r in outcomes),
        "results":outcomes,
        "new_production_sources":0,
        "publisher_screenshots_claimed":0,
        "emails_sent":0,"private_ledger_changed":False,
    },ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    main()
