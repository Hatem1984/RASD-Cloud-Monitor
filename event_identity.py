"""High-confidence Arabic event deduplication; conservative by design."""
from __future__ import annotations
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from monitor import _matchable_arabic

_STOP = set("وزارة وزير وزيرة التخطيط تنمية التنمية الاقتصاد الاقتصادى الاقتصادية في من على عن الى إلى مصر المصري المصرية مع خلال حول بشأن ان أن هذا هذه الذي التي".split())
_ALIAS = {"يستهدف":"هدف","تستهدف":"هدف","يهدف":"هدف",
          "تخفيض":"خفض","تقليص":"خفض","يخفض":"خفض",
          "تشريعية":"تشريع","التشريعية":"تشريع","تشريعات":"تشريع",
          "زيادة":"رفع","يزيد":"رفع"}
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩","0123456789")


def terms(title):
    if not isinstance(title,str) or len(title)>450:
        return set()
    clean=_matchable_arabic(title).translate(_DIGITS)
    words=re.findall(r"[ء-ي0-9]+",clean)
    found=set()
    for word in words:
        if word.startswith("ال") and len(word)>=6:
            word=word[2:]
        word=_ALIAS.get(word,word)
        if len(word)>2 and word not in _STOP:
            found.add(word)
    return found


def timestamp(item):
    try:
        return datetime.strptime(item["published_at_cairo"][:16],"%Y-%m-%d %H:%M")
    except (KeyError,TypeError,ValueError):
        return None


def same_event(a,b):
    if a.get("id") and a.get("id")==b.get("id"):
        return True
    t1,t2=timestamp(a),timestamp(b)
    if t1 is None or t2 is None or abs(t1-t2)>timedelta(hours=36):
        return False
    x,y=terms(a.get("headline")),terms(b.get("headline"))
    if min(len(x),len(y))<4 or len(x&y)<4:
        return False
    if {k for k in x if k.isdigit()}!={k for k in y if k.isdigit()}:
        return False
    dice=2*len(x&y)/(len(x)+len(y))
    coverage=len(x&y)/min(len(x),len(y))
    similarity=SequenceMatcher(None," ".join(sorted(x))," ".join(sorted(y))).ratio()
    return dice>=0.84 and coverage>=0.80 and (similarity>=0.77 or dice>=0.93)


def distinct_events(incoming,history=()):
    """Keep one event and retain other ORIGINAL publishers as source citations.

    Historical already-delivered events must never be resent. New same-event
    articles from different publishers are cited inside the one chosen Word
    rather than disappearing or becoming two emails.
    """
    chosen, duplicates = [], []
    for original in incoming:
        item = dict(original)
        if any(same_event(item, prev) for prev in history):
            duplicates.append(item)
            continue
        first = next((row for row in chosen if same_event(item, row)), None)
        if first is None:
            item.setdefault("supporting_sources", [])
            chosen.append(item)
            continue
        duplicates.append(item)
        # Display only publisher-native URLs and metadata already validated
        # by the discovery feed. Never substitute these for primary JPEG.
        if (item.get("source") != first.get("source")
                and item.get("url") != first.get("url")
                and not any(s.get("url") == item.get("url")
                            for s in first["supporting_sources"])
                and len(first["supporting_sources"]) < 8):
            first["supporting_sources"].append({
                "source": item["source"],
                "headline": item["headline"],
                "url": item["url"],
                "published_display_cairo": item.get("published_display_cairo", ""),
            })
    return chosen, duplicates
