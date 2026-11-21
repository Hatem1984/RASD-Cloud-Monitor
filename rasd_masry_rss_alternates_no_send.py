"""Read-only exact first-party Masry Alyoum RSS alternatives QA.

Original 2026-11-20 publisher RSS returned malformed XML; this checks
fixed HTTPS same-publisher alternatives without redirect or content repair.
Do not claim a healthy source until strict EVERY-item identities/dates pass.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET
from rasd_source_candidate_preflight import _fetch
from monitor import parse_rss

ENDPOINTS = {
    "CURRENT": "https://www.almasryalyoum.com/rss/rssfeeds",
    "EGYPT_SECTION": "https://www.almasryalyoum.com/rss/rssfeeds?sectionId=3",
    "RSS_INDEX": "https://www.almasryalyoum.com/rss/",
}
def main():
    cfg=json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    candidate=next(x for x in cfg["feeds"] if x["id"]=="almasryalyoum")
    for label, url in ENDPOINTS.items():
        kind="HOLD"
        links=0
        relevant=0
        try:
            data=_fetch(url, 1_500_000)
            links,found=parse_rss(
                data,candidate,cfg["keywords"],now=datetime.now(timezone.utc),
                recent_hours=72,require_complete_items=True)
            if links>0:
                kind="STRICT_NATIVE_RSS_VALID"
                relevant=len(found)
        except (HTTPError,URLError,ET.ParseError,ValueError,RuntimeError,OSError,TimeoutError) as ex:
            if isinstance(ex,ET.ParseError):kind="XML_MALFORMED_HOLD"
            elif isinstance(ex,HTTPError):kind="HTTP_HOLD"
            elif isinstance(ex,URLError):kind="NETWORK_HOLD"
            else:kind="PUBLISHER_FEED_HOLD"
        print("RASD_MASRY_FIRSTPARTY_ALTERNATE="+label+
              " STATUS="+kind+" LINKS="+str(links)+
              " MINISTRY_MATCHES="+str(relevant),flush=True)
    print("RASD_MASRY_QA_NO_ACTIVATION_NO_SEND=1")
if __name__=="__main__":
    main()
