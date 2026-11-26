"""Corroborate native RSS publication date against original Elbalad page."""
from datetime import datetime
from email.utils import parsedate_to_datetime
import re
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")
MONTHS = "يناير فبراير مارس أبريل مايو يونيو يوليو أغسطس سبتمبر أكتوبر نوفمبر ديسمبر".split()
WEEKDAYS = "الاثنين الثلاثاء الأربعاء الخميس الجمعة السبت الأحد".split()
DISCLOSURE = (" توقيت صدى البلد مثبت من RSS الصريح والوقت الظاهر في صفحة الخبر؛"
              " بيانات UTC المهيكلة للناشر متعارضة.")
CONFLICT = "rss_visible_agree_structured_utc_conflict"
AGREEMENT = "all_original_dates_agree"


def publication_evidence(article, evidence):
    """No timezone guessing: native RSS is the clock, visible text corroborates.
    Only the observed exact UTC wall-clock mislabel pattern is admitted with
    an explicit disclosure. Other ambiguity/missing evidence is HOLD.
    """
    try:
        raw = article["published"]
        if not isinstance(raw, str) or len(raw) > 100 or not re.search(
                r"(?:GMT|UTC|[+-][0-9]{4})$", raw.strip()):
            return None
        stamp = parsedate_to_datetime(raw)
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return None
        local = stamp.astimezone(CAIRO)
        if ("published_at_cairo" in article and article["published_at_cairo"] !=
                local.strftime("%Y-%m-%d %H:%M %Z")):
            return None
        if not isinstance(evidence, dict) or evidence.get("canonical") != [article["url"]]:
            return None
        visible = evidence.get("visible")
        if not isinstance(visible, list) or len(visible) != 1 or not isinstance(visible[0], str):
            return None
        text = " ".join(visible[0].split()).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩","0123456789"))
        m = re.fullmatch(r"(\S+) ([0-9]{1,2})/(\S+)/([0-9]{4}) - ([0-9]{1,2}):([0-9]{2}) ([صم])", text)
        if not m:
            return None
        weekday, day, month, year, hour, minute, period = m.groups()
        if month not in MONTHS or weekday not in WEEKDAYS or not 1 <= int(hour) <= 12:
            return None
        wall = datetime(int(year), MONTHS.index(month)+1, int(day),
                        int(hour)%12+(12 if period=="م" else 0), int(minute))
        if wall.weekday() != WEEKDAYS.index(weekday) or wall != local.replace(
                tzinfo=None, second=0, microsecond=0):
            return None
        dates = []
        for key in ("meta", "ld"):
            values = evidence.get(key)
            if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str) or len(values[0]) > 64:
                return None
            dt = datetime.fromisoformat(values[0].replace("Z", "+00:00"))
            if dt.tzinfo is None or dt.utcoffset() is None:
                return None
            dates.append(dt)
        if all(d.astimezone(CAIRO).replace(tzinfo=None,second=0,microsecond=0)==wall for d in dates):
            return AGREEMENT
        if dates[0] == dates[1] and all(d.utcoffset().total_seconds()==0 and
                d.replace(tzinfo=None)==local.replace(tzinfo=None) for d in dates):
            return CONFLICT
        return None
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError, IndexError):
        return None
