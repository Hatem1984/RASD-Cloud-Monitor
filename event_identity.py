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
        # Numeric claims matter even for a single digit (1%, 3 projects).
        # Dropping them caused distinct same-publisher headlines to collapse.
        if (word.isdigit() or len(word)>2) and word not in _STOP:
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
    """Return chosen and suppressed; reserved items also bar duplicate attempts."""
    chosen,duplicates=[],[]
    for item in incoming:
        if any(same_event(item,prev) for prev in (*history,*chosen)):
            duplicates.append(item)
        else:
            chosen.append(item)
    return chosen,duplicates

def related_event_pairs(incoming, history=()):
    """Review hints for same-publisher retitled coverage, not event counts.
    A bounded intro cannot establish that a distinct article has no update.
    """
    def excerpt(item):
        raw=item.get("publisher_excerpt","")
        if not isinstance(raw,str): return ""
        return re.sub(r"[^\w]+"," ",_matchable_arabic(raw).translate(_DIGITS)).strip()[:240]
    prior=list(history)
    pairs=[]
    for item in incoming:
        for other in prior:
            if item.get("id")==other.get("id") or not item.get("source") or item.get("source")!=other.get("source"):
                continue
            t1,t2=timestamp(item),timestamp(other)
            if not t1 or not t2 or abs(t1-t2)>timedelta(hours=36): continue
            x,y=excerpt(item),excerpt(other)
            if min(len(x),len(y))<100: continue
            a,b=terms(item.get("headline")),terms(other.get("headline"))
            an,bn={v for v in a if v.isdigit()},{v for v in b if v.isdigit()}
            if an and bn and an!=bn: continue
            if SequenceMatcher(None,x,y,autojunk=False).ratio()>=0.90:
                pairs.append((other.get("id"),item.get("id")))
        prior.append(item)
    return pairs


def distinct_publisher_coverages(incoming, history=()):
    """Preserve each publisher's separate clipping of a shared event.

    The owner-provided web model counts and displays publisher COVERAGES,
    not just distinct events. Suppress repeated article IDs across runs;
    dedupe near-identical titles ONLY within the same publisher. If the
    publisher identity is absent/invalid, conservatively use legacy global
    event dedup rather than making an untrusted new coverage claim.
    """
    chosen, duplicates = [], []
    for item in incoming:
        def duplicate(prev):
            if not isinstance(item, dict) or not isinstance(prev, dict):
                return False
            if item.get("id") and item["id"] == prev.get("id"):
                return True
            first = item.get("source")
            second = prev.get("source")
            if not isinstance(first, str) or not first.strip() or (
                    not isinstance(second, str) or not second.strip()):
                return same_event(item, prev)
            if first != second:
                return False
            # Preserve potentially substantive updates on distinct URLs.
            # The native excerpt is bounded; similar wording is a review hint.
            if item.get("publisher_excerpt") or prev.get("publisher_excerpt"):
                return False
            return same_event(item, prev)

        if any(duplicate(other) for other in (*history, *chosen)):
            duplicates.append(item)
        else:
            chosen.append(item)
    return chosen, duplicates
