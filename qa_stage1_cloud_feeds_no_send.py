"""NO SEND, NO SECRETS. Public publisher RSS reachability from hosted QA Runner.

One bounded GET, do not follow redirects, no retries, 10sec/URL. Only first-party
authoritative domains currently approved for Ministry monitoring are checked.
Never claim 13/13 production coverage based on this one-shot probe.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from xml.etree import ElementTree as ET
from monitor import parse_rss

class DenyRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        return None

BASE=Path(__file__).parent
CONFIG=json.loads((BASE/"sources_owner_daily_qa.json").read_text(encoding="utf-8"))
ROOT="https://alborsaanews.com/"
URLS=[
    ("alborsa_category",ROOT+"category/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%89/feed"),
    ("alborsa_home",ROOT+"feed/"),
    ("dailynewsegypt", "https://dailynewsegypt.com/feed/"),
]
def probe(alias,url):
    hostname=urlsplit(url).hostname
    if hostname not in {"alborsaanews.com","dailynewsegypt.com"}:
        raise RuntimeError("unapproved_probe_host")
    o={"source":alias,"host":hostname,"sent":False}
    req=Request(url,headers={"User-Agent":"RASD-Cloud-Public-Monitor/0.1"})
    try:
        with build_opener(DenyRedirect()).open(req,timeout=10) as response:
            data=response.read(CONFIG["max_feed_bytes"]+1)
            o["status"]=response.status
            if len(data)>CONFIG["max_feed_bytes"]:
                return {**o,"result":"HOLD_TOO_LARGE"}
            publisher_id="alborsa" if alias.startswith("alborsa") else "dailynewsegypt"
            feed=dict(next(x for x in CONFIG["feeds"] if x["id"]==publisher_id))
            feed["allowed_article_hosts"]=sorted(set(feed["allowed_article_hosts"])|{hostname})
            try:
                n,_=parse_rss(data,feed,CONFIG["keywords"],datetime.now(timezone.utc),
                              CONFIG["recent_hours"],require_complete_items=True)
                o["result"]="RSS_NATIVE_VALID"
                o["verified_link_count"]=n
            except (ValueError,ET.ParseError):
                o["result"]="HOLD_RSS_IDENTITY_DATE_OR_XML"
    except HTTPError as error:
        o.update(status=error.code,result="HOLD_REDIRECT_OR_HTTP")
    except URLError:
        o["result"]="HOLD_TRANSPORT"
    except Exception as error:
        o["result"]="HOLD_"+type(error).__name__
    return o

if __name__=="__main__":
    for name,url in URLS:
        print("RASD_CLOUD_SOURCE_PROBE="+json.dumps(probe(name,url),sort_keys=True),flush=True)
    print("RASD_NO_SMTP_TRUE",flush=True)
