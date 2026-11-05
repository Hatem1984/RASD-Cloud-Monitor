"""Owner-requested RASD hourly and 100-publisher expansion *quality gates*.

Candidate listing is NOT permission to fetch arbitrary URLs or to use
unverified sources. Exact first-party native RSS links must still be approved
in monitor.APPROVED_FEED_URLS. Source type NEWS/REPORT/ANALYSIS only
describes reviewed publisher metadata; it is not generated interpretation.

Cross-source near-duplicates go to review, never silently discarded.
No mail, secrets, production edits, scraping bypass or social API here.
"""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

CAIRO=ZoneInfo("Africa/Cairo")
ALLOWED_KINDS=frozenset({"news","report","analysis"})
MAX_REQUESTED_SOURCES=100
_WINDOW_START=0
_WINDOW_END=22
_ARABIC_MARKS=re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]")
_PUNCTUATION=re.compile(r"[^\w\s]",re.U)
_SPACE=re.compile(r"\s+")

def hourly_slots():
    """Existing owner window remains 00:00..22:00 Cairo (22 observations)."""
    return [f"{hour:02d}:00" for hour in range(_WINDOW_START,_WINDOW_END)]

def hourly_schedule():
    """Deliberately 07 minutes past the hour to avoid top-of-hour load."""
    return "7 0-21 * * *"

def _title_key(value):
    if not isinstance(value,str):raise ValueError("article_title_invalid")
    normalized=unicodedata.normalize("NFKC",html.unescape(value))
    normalized=_ARABIC_MARKS.sub("",normalized).casefold()
    normalized=_PUNCTUATION.sub(" ",normalized)
    return _SPACE.sub(" ",normalized).strip()

def _published_day(story):
    text=story.get("published_at_utc") or story.get("published_at_cairo")
    if not isinstance(text,str) or not text:raise ValueError("publication_day_missing")
    try:
        stamped=datetime.fromisoformat(text.replace("Z","+00:00"))
        if stamped.tzinfo is None or stamped.utcoffset() is None:
            raise ValueError("publication_day_unverified")
        return stamped.astimezone(CAIRO).date().isoformat()
    except (TypeError,ValueError):
        # Owner RSS parser also provides a RFC 2822 publisher timestamp.
        raw=story.get("published")
        try:
            stamp=parsedate_to_datetime(raw)
        except (TypeError,ValueError):
            raise ValueError("publication_day_unverified") from None
        if stamp is None or stamp.tzinfo is None:
            raise ValueError("publication_day_unverified")
        return stamp.astimezone(CAIRO).date().isoformat()

def _story_origin(story):
    url=story.get("url")
    if not isinstance(url,str):raise ValueError("unapproved_story_url")
    host=urlsplit(url).hostname
    if not host or not url.startswith("https://"):
        raise ValueError("unapproved_story_url")
    return host

def deduplicate_publisher_stories(stories):
    """Only exact normalized headlines ON SAME DAY auto-cluster.

    Different originals under one cluster preserve all credited publisher
    links; near-matches are flagged for human review, NOT suppressed.
    Each included original story remains screenshot-mandatory downstream.
    """
    if not isinstance(stories,list):raise ValueError("stories_must_be_list")
    clusters={}
    seen_original={}
    for s in stories:
        if not isinstance(s,dict):raise ValueError("story_invalid")
        day=_published_day(s)
        title=_title_key(s.get("headline"))
        if len(title)<12:raise ValueError("title_too_short_for_dedup")
        url=s.get("url")
        publisher=_story_origin(s)
        from monitor import canonical_url
        identity=canonical_url(url)
        if identity in seen_original:
            if seen_original[identity]!=(day,title):
                raise ValueError("duplicate_original_conflicting_identity")
            continue
        seen_original[identity]=(day,title)
        kind=s.get("content_kind","news")
        if kind not in ALLOWED_KINDS:raise ValueError("unapproved_article_content_kind")
        # A report or analysis may contain distinct evidence despite the
        # same headline as a breaking news item. Never merge across genres.
        key=(day,title,kind)
        cluster=clusters.setdefault(key,{"day_cairo":day,"headline":s["headline"],
              "content_kind":kind,
              "originals":[],"must_capture_original_each":True})
        cluster["originals"].append({"url":url,
             "publisher_host":publisher,"source":s.get("source"),
             "content_kind":s.get("content_kind","news")})
        if cluster["originals"][-1]["content_kind"] not in ALLOWED_KINDS:
            raise ValueError("unapproved_article_content_kind")
    # Exact duplicate publisher editions are grouped while retaining every
    # original source. Similar but nonidentical titles are never removed:
    # mark them HOLD for human comparison, especially ahead of social inputs.
    output=list(clusters.values())
    for cluster in output:
        cluster["story_key"]=hashlib.sha256((
            cluster["day_cairo"]+"|"+cluster["content_kind"]+"|"+
            _title_key(cluster["headline"])).encode("utf-8")).hexdigest()[:20]
        cluster["possible_duplicate_story_keys"]=[]
    for i,left in enumerate(output):
        lt=set(_title_key(left["headline"]).split())
        for right in output[i+1:]:
            if (left["day_cairo"]!=right["day_cairo"] or
                    left["content_kind"]!=right["content_kind"]):
                continue
            rt=set(_title_key(right["headline"]).split())
            if (len(lt)<5 or len(rt)<5 or
                    len(lt & rt)<5 or len(lt & rt)/len(lt | rt)<0.76):
                continue
            left["possible_duplicate_story_keys"].append(right["story_key"])
            right["possible_duplicate_story_keys"].append(left["story_key"])
    return output

def require_crosspublisher_review_closed(clusters):
    """Fail closed when near-duplicate stories still require editorial review."""
    if any(x.get("possible_duplicate_story_keys") for x in clusters):
        raise ValueError("possible_crosspublisher_duplicate_requires_review")
    return True

def proposed_catalog_status(validated_feeds, researched_sources, target=100):
    if target!=MAX_REQUESTED_SOURCES:
        raise ValueError("source_target_change_requires_owner_review")
    if not isinstance(validated_feeds,list) or not isinstance(researched_sources,list):
        raise ValueError("catalog_shape_invalid")
    active={f["id"] for f in validated_feeds}
    if len(active)!=len(validated_feeds):
        raise ValueError("duplicate_active_source_id")
    catalog={}
    for source in researched_sources:
        if not isinstance(source,dict) or not source.get("id"):
            raise ValueError("candidate_source_identity_missing")
        if source["id"] in catalog:raise ValueError("duplicate_research_candidate")
        catalog[source["id"]]=source
    missing_active=sorted(active-set(catalog))
    # Unlisted active sources are not removed. A catalog is NOT an
    # authorization list nor an assertion that 100 feeds are healthy.
    return {"requested_sources":target,
       "active_approved_native_rss":len(active),
       "already_researched_distinct_sources":len(catalog),
       "unresearched_to_target":max(0,target-len(catalog)),
       "researched_not_active":len(set(catalog)-active),
       "active_not_on_research_catalog":missing_active,
       "activation_state":"HOLD_CANDIDATE_ENDPOINTS_NOT_VALIDATED" if len(active)<target else "ELIGIBLE_FOR_REAL_DAY_QA_ONLY"}
