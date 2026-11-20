"""Al Mal native RSS discoverability QA; read-only, not source activation."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from xml.etree.ElementTree import ParseError
from rasd_source_candidate_preflight import _fetch
from monitor import parse_rss

ENDPOINTS = {
    "RSS_SECTION_INDEX": "https://almalnews.com/rss/rss/",
    "NATIVE_TAG_18": "https://almalnews.com/rss/tagrss?TagID=18/",
    "NATIVE_TAG_21": "https://almalnews.com/rss/tagrss?TagID=21/",
    "HOMEPAGE_FEED": "https://almalnews.com/feed/",
}

def main():
    cfg = json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    feed={"id":"almal","name":"Al Mal native RSS shadow",
          "allowed_article_hosts":["almalnews.com","www.almalnews.com"]}
    now=datetime.now(timezone.utc)
    for label,url in ENDPOINTS.items():
        count=matched=0
        try:
            data=_fetch(url,1_500_000)
            count,stories=parse_rss(data,feed,cfg["keywords"],
                                    now=now,recent_hours=72,
                                    require_complete_items=True)
            matched=len(stories)
            status="STRICT_NATIVE_RSS_VALID" if count else "ZERO_HOLD"
        except (HTTPError,URLError,OSError,TimeoutError,ParseError,ValueError,RuntimeError):
            status="NATIVE_RSS_HOLD"
        print("RASD_ALMAL_FIRSTPARTY_ENDPOINT="+label+
              " STATUS="+status+" LINKS="+str(count)+
              " MINISTRY_MATCHES="+str(matched),flush=True)
    print("RASD_ALMAL_NO_SEND_NO_ACTIVATION=1")
if __name__=="__main__":
    main()
