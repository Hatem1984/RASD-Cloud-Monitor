"""Bounded original Alborsa latest-news supplement. QA only until activation review.

Never sends or touches private state. Original listing supplies discovery;
each relevant article's own canonical URL, headline and zoned publication
time supply identity. URL path dates are only a bounded pagination hint.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, date
from email.utils import format_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo
import re
from monitor import RejectRedirect, _ministry_term_present, article_id

HOST = "alborsaanews.com"
ROOT = "https://alborsaanews.com/latestnews"
MAX_PAGES = 8
MAX_CANDIDATES = 25
MAX_BYTES = 3_000_000
CAIRO = ZoneInfo("Africa/Cairo")
ARTICLE = re.compile(r"/(20[0-9]{2})/([0-9]{2})/([0-9]{2})/([0-9]+)")


def identity(url):
    p = urlsplit(url)
    if (p.scheme != "https" or p.hostname != HOST or p.port is not None
            or p.username or p.password or p.query or p.fragment):
        raise ValueError("alborsa_original_identity_hold")
    match = ARTICLE.fullmatch(p.path)
    if not match:
        raise ValueError("alborsa_original_identity_hold")
    return date(*map(int, match.groups()[:3])), match.group(4)


def read_original(url):
    if url != ROOT and not re.fullmatch(re.escape(ROOT) + r"/page/[2-8]", url):
        identity(url)
    with build_opener(RejectRedirect()).open(
        Request(url, headers={"User-Agent":"RASD-Cloud-Public-Monitor/0.1"}),
        timeout=12,
    ) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("alborsa_original_http_hold")
        if response.headers.get_content_type() != "text/html":
            raise ValueError("alborsa_original_type_hold")
        raw = response.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES:
            raise ValueError("alborsa_original_size_hold")
        return raw


def clean(parts):
    return " ".join(" ".join(parts).split())


class Listing(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url = url
        self.cards = []
        self.current = None
        self.in_title = False
        self.excerpt_depth = 0
        self.pages = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        if tag == "article" and {"jeg_post", "jeg_pl_md_3"} <= classes:
            if self.current is not None:
                raise ValueError("alborsa_listing_nested_card_hold")
            self.current = {"urls":set(), "title":[], "excerpt":[]}
        if tag == "a" and a.get("href"):
            u = urljoin(self.url, a["href"])
            if re.fullmatch(re.escape(ROOT) + r"/page/[2-8]", u):
                self.pages.add(u)
            if self.current is not None and self.in_title:
                identity(u)
                self.current["urls"].add(u)
        if self.current is None:
            return
        if tag in {"h2","h3","h4"} and "jeg_post_title" in classes:
            self.in_title = True
        if tag == "div":
            if self.excerpt_depth:
                self.excerpt_depth += 1
            elif "jeg_post_excerpt" in classes:
                self.excerpt_depth = 1

    def handle_data(self, data):
        if self.current is not None:
            if self.in_title:
                self.current["title"].append(data)
            if self.excerpt_depth:
                self.current["excerpt"].append(data)

    def handle_endtag(self, tag):
        if self.current is None:
            return
        if tag in {"h2","h3","h4"}:
            self.in_title = False
        if tag == "div" and self.excerpt_depth:
            self.excerpt_depth -= 1
        if tag == "article":
            row = self.current
            self.current = None
            title, excerpt = clean(row["title"]), clean(row["excerpt"])
            if len(row["urls"]) != 1 or not title or not excerpt:
                raise ValueError("alborsa_listing_card_incomplete")
            url = next(iter(row["urls"]))
            self.cards.append({"url":url,"headline":title,"excerpt":excerpt})
            self.in_title = False
            self.excerpt_depth = 0


def parse_listing(raw, url):
    if len(raw) > MAX_BYTES:
        raise ValueError("alborsa_original_size_hold")
    p = Listing(url)
    p.feed(raw.decode("utf-8","strict"))
    p.close()
    if p.current is not None or not 1 <= len(p.cards) <= 50:
        raise ValueError("alborsa_listing_structure_hold")
    urls = [r["url"] for r in p.cards]
    if len(set(urls)) != len(urls):
        raise ValueError("alborsa_listing_duplicate_hold")
    days = [identity(u)[0] for u in urls]
    if days != sorted(days,reverse=True):
        raise ValueError("alborsa_listing_date_order_hold")
    return p.cards,p.pages


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = {}
        self.h1 = []
        self.in_h1 = False
        self.h1_count = 0
        self.lead_depth = 0
        self.lead_containers = 0
        self.in_paragraph = False
        self.paragraph = []
        self.lead = []

    def handle_starttag(self,tag,attrs):
        a = dict(attrs)
        key = a.get("property")
        if tag == "meta" and key in {"og:url","og:title","og:description","article:published_time"}:
            self.values.setdefault(key,set()).add(a.get("content") or "")
        if tag == "h1":
            self.h1_count += 1
            self.in_h1 = True
        classes=set((a.get("class") or "").split())
        if tag == "div":
            if self.lead_depth:
                self.lead_depth+=1
            elif classes == {"entry-content","no-share"}:
                self.lead_depth=1
                self.lead_containers+=1
        if tag=="p" and self.lead_depth and len(self.lead)<2:
            self.in_paragraph=True
            self.paragraph=[]

    def handle_data(self,data):
        if self.in_h1:
            self.h1.append(data)
        if self.in_paragraph:
            self.paragraph.append(data)

    def handle_endtag(self,tag):
        if tag == "h1":
            self.in_h1 = False
        if tag=="p" and self.in_paragraph:
            self.lead.append(clean(self.paragraph))
            self.in_paragraph=False
        if tag=="div" and self.lead_depth:
            self.lead_depth-=1
            if not self.lead_depth:
                self.in_paragraph=False


def original_article(raw,row,keywords,now):
    if len(raw)>MAX_BYTES:
        raise ValueError("alborsa_original_size_hold")
    p = Metadata()
    p.feed(raw.decode("utf-8","strict"))
    p.close()
    def one(key):
        values=p.values.get(key,set())
        if len(values)!=1 or not next(iter(values)):
            raise ValueError("alborsa_original_metadata_hold")
        return next(iter(values))
    url=one("og:url")
    if url!=row["url"]:
        raise ValueError("alborsa_original_identity_hold")
    headline=clean(p.h1)
    if p.h1_count!=1 or headline!=row["headline"] or not 1<=len(headline)<=300:
        raise ValueError("alborsa_original_headline_hold")
    stamp=datetime.fromisoformat(one("article:published_time").replace("Z","+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None or stamp>now:
        raise ValueError("alborsa_original_date_hold")
    if stamp.astimezone(CAIRO).date()!=identity(url)[0]:
        raise ValueError("alborsa_original_date_hold")
    excerpt=one("og:description")[:850]
    if _ministry_term_present(headline,keywords):
        origin="title"
    elif _ministry_term_present(excerpt,keywords):
        origin="publisher_description"
    else:
        # Real publisher template verified in QA. Only the first two original
        # content paragraphs, never sidebar, related news, navigation or footer.
        lead=clean(p.lead)[:850]
        if p.lead_containers!=1 or not _ministry_term_present(lead,keywords):
            raise ValueError("alborsa_original_relevance_hold")
        excerpt,origin=lead,"publisher_original_lead"
    return {"id":article_id(url),"url":url,"headline":headline,
            "published":format_datetime(stamp),"publisher_excerpt":excerpt,
            "match_origin":origin}


def audit_listing(keywords, now, *, fetch=read_original, hours=72):
    """Read-only audit; no delivery even for historical candidates."""
    if now.tzinfo is None or now.utcoffset() is None or hours not in {24,72}:
        raise ValueError("alborsa_invalid_window")
    lower=now-timedelta(hours=hours)
    low_day=lower.astimezone(CAIRO).date()
    cards=[]
    seen={}
    pages=[]
    snapshots=[]
    holds=[]
    repeats=0
    previous_last=None
    boundary=False
    for page in range(1,MAX_PAGES+1):
        url=ROOT if page==1 else ROOT+"/page/"+str(page)
        if page>1 and url not in next_pages:
            raise ValueError("alborsa_listing_navigation_hold")
        batch,next_pages=parse_listing(fetch(url),url)
        if previous_last is not None and identity(batch[0]["url"])[0]>previous_last:
            raise ValueError("alborsa_listing_date_order_hold")
        previous_last=identity(batch[-1]["url"])[0]
        snapshots.append((url,batch,next_pages))
        pages.append(len(batch))
        for row in batch:
            key=row["url"]
            if key in seen:
                if seen[key]!=row:
                    raise ValueError("alborsa_listing_overlap_conflict_hold")
                repeats+=1
            else:
                seen[key]=row
                cards.append(row)
        if identity(batch[-1]["url"])[0]<low_day:
            boundary=True
            break
    # The original publisher repeated identical cards across pages.
    # A second bounded sweep must reproduce the complete listing and navigation;
    # never suppress conflicting duplicates or accept a drifting snapshot.
    for url,batch,nav in snapshots:
        if parse_listing(fetch(url),url)!=(batch,nav):
            raise ValueError("alborsa_listing_changed_hold")
    if not boundary:
        holds.append("alborsa_listing_window_cap_hold")
    matched=[r for r in cards if identity(r["url"])[0]>=low_day and
             (_ministry_term_present(r["headline"],keywords) or
              _ministry_term_present(r["excerpt"],keywords))]
    if len(matched)>MAX_CANDIDATES:
        raise ValueError("alborsa_listing_candidate_cap_hold")
    verified=[]
    for row in matched:
        try:
            a=original_article(fetch(row["url"]),row,keywords,now)
            stamp=datetime.strptime(a["published"],"%a, %d %b %Y %H:%M:%S %z")
            if lower<=stamp<=now:
                verified.append(a)
        except Exception as exc:
            # Safe QA diagnostics; no content or private state.
            code=str(exc) if type(exc) is ValueError and str(exc).startswith("alborsa_") else "alborsa_original_read_hold"
            holds.append(code)
    return {"pages":pages,"links":len(cards),"repeated_cards":repeats,"boundary":boundary,
            "matched":len(matched),"matched_urls":[r["url"] for r in matched],
            "verified":verified,"holds":holds,"email_sent":False}


def forward_only(verified, activation, now):
    """Explicit future activation boundary. Not called by production."""
    from email.utils import parsedate_to_datetime
    if any(x.tzinfo is None or x.utcoffset() is None for x in (activation,now)):
        raise ValueError("alborsa_invalid_activation")
    return [a for a in verified if activation<=parsedate_to_datetime(a["published"])<=now]


def apply_to_inspection(config, observed, now, *, auditor=audit_listing):
    """Opt-in only; activation UTC must be set separately by the owner.
    Preserve native RSS candidates; any unverified supplemental coverage is
    explicit PARTIAL, with no supplemental candidates admitted on HOLD.
    Never create a separate publisher, send, or touch private state.
    """
    from copy import deepcopy
    from email.utils import parsedate_to_datetime
    activation_raw=config.get("alborsa_listing_activation_utc")
    if activation_raw is None:
        return observed
    if not isinstance(activation_raw,str) or not activation_raw.endswith("Z"):
        raise ValueError("alborsa_invalid_activation")
    activation=datetime.fromisoformat(activation_raw.replace("Z","+00:00"))
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("alborsa_invalid_activation")
    if now<activation:
        return observed
    out=deepcopy(observed)
    feeds=[f for f in config["feeds"] if f["id"]=="alborsa"]
    records=[s for s in out["sources"] if s["feed_id"]=="alborsa"]
    if len(feeds)!=1 or len(records)!=1:
        raise ValueError("alborsa_listing_scope_hold")
    feed,record=feeds[0],records[0]
    # Native feed continues its existing safety rules; do not make failed
    # native RSS appear healthy just because the supplementary listing works.
    if record["status"]!="ok" or out.get("matched_article_pool_truncated"):
        return out
    try:
        a=auditor(config["keywords"],now)
        if a["holds"] or not a["boundary"] or a.get("email_sent") is not False:
            raise ValueError("alborsa_listing_coverage_hold")
        existing={}
        for row in out["matched_public_articles"]:
            if row["source"]==feed["name"]:
                p=urlsplit(row["url"])
                if p.hostname in {"alborsaanews.com","www.alborsaanews.com"} and ARTICLE.fullmatch(p.path.rstrip("/")):
                    existing[p.path.rstrip("/")]=row
        added=[]
        for row in forward_only(a["verified"],activation,now):
            key=urlsplit(row["url"]).path
            identity(row["url"])
            if row["id"]!=article_id(row["url"]):
                raise ValueError("alborsa_listing_identity_hold")
            if key in existing:
                if parsedate_to_datetime(existing[key]["published"])!=parsedate_to_datetime(row["published"]):
                    raise ValueError("alborsa_listing_date_conflict_hold")
                continue
            existing[key]=row
            added.append({**row,"source":feed["name"]})
        pool=out["matched_public_articles"]+added
        out["matched_article_pool_truncated"]=len(pool)>200
        out["matched_public_articles"]=pool[:200]
        out["planning_headline_matches"]=len(pool)
        record["supplement_verified_links"]=len(a["verified"])
        record["supplement_new_candidates"]=len(added)
    except Exception:
        record.update(status="failed",error_code="alborsa_listing_coverage_hold")
        record["supplement_new_candidates"]=0
    return out
