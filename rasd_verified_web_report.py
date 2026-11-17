"""Owner-reference web media clipping report built ONLY from verified JPEGs.

Every original publisher coverage gets its OWN picture/card even when several
publishers cover the same event. Descriptive analysis counts coverages, not
distinct events. No network requests, OCR, article invention or email.
"""
from __future__ import annotations

import base64
import hashlib
import html
import io
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from monitor import article_id
from rasd_ministry_visual_layout import descriptive_topic_counts


def escaped(value) -> str:
    return html.escape(str(value), quote=True)


def render_verified_web_report(report: dict, proofs: list[dict],
                               approved_feeds: list[dict], destination: Path) -> None:
    """Write a self-contained, private-preview HTML from original verified JPEGs.

    Fail closed on missing/changed evidence, unapproved URL or altered story ID.
    This does NOT certify coverage of all published news on a calendar day.
    """
    if report.get("coverage") != "CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS":
        raise ValueError("rasd_web_requires_previously_verified_deliveries")
    articles = report.get("articles")
    if (not isinstance(articles, list) or not 1 <= len(articles) <= 60 or
            not isinstance(proofs, list) or len(proofs) != len(articles)):
        raise ValueError("rasd_web_missing_original_evidence")
    by_source = {f["name"]: f for f in approved_feeds}
    if len(by_source) != len(approved_feeds):
        raise ValueError("rasd_web_ambiguous_sources")
    cards = []
    distribution = Counter()
    for pos, (item, proof) in enumerate(zip(articles, proofs), 1):
        if not isinstance(item, dict) or not isinstance(proof, dict):
            raise ValueError("rasd_web_invalid_article_or_proof")
        url = item.get("url")
        source = item.get("source")
        if (not isinstance(url, str) or
                not isinstance(source, str) or source not in by_source or
                not isinstance(item.get("headline"), str) or
                not item["headline"].strip() or
                item.get("id") != article_id(url)):
            raise ValueError("rasd_web_untrusted_article_identity")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or
                parsed.hostname not in by_source[source]["allowed_article_hosts"] or
                parsed.port not in (None, 443) or parsed.username or parsed.password or
                parsed.fragment):
            raise ValueError("rasd_web_unapproved_original_article_url")
        image_path = item.get("evidence_image_path")
        digest = proof.get("sha256")
        if (not isinstance(image_path, str) or
                not isinstance(digest, str) or
                not re.fullmatch(r"[a-f0-9]{64}", digest) or
                proof.get("status") != "verified"):
            raise ValueError("rasd_web_unverified_image")
        photo = Path(image_path).read_bytes()
        if (not photo.startswith(b"\xff\xd8") or
                hashlib.sha256(photo).hexdigest() != digest):
            raise ValueError("rasd_web_image_digest_mismatch")
        with Image.open(io.BytesIO(photo)) as pic:
            if pic.format != "JPEG" or pic.width < 900 or pic.height < 700:
                raise ValueError("rasd_web_image_size_invalid")
            pic.verify()
        encoded = base64.b64encode(photo).decode("ascii")
        headline = escaped(item["headline"])
        site = escaped(source)
        date = escaped(item.get("published_display_cairo") or
                       item.get("published_at_cairo") or "التاريخ غير متاح")
        img = "data:image/jpeg;base64," + encoded
        distribution[source] += 1
        cards.append(
            f'<article class="clip"><div class="clip-title"><span class="index">{pos:02d}</span>'
            f'<div><h3>{site}</h3><p>{headline}</p><small>النشر: {date}</small></div></div>'
            f'<a class="photo" href="#zoom-{pos:02d}" aria-label="تكبير الصورة الأصلية">'
            f'<img src="{img}" alt="صورة الصفحة الأصلية: {headline}" loading="lazy"></a>'
            f'<a class="source-link" href="{escaped(url)}" target="_blank" '
            f'rel="noopener noreferrer">رابط الخبر الأصلي</a></article>'
            f'<div class="zoom" id="zoom-{pos:02d}"><a href="#reports" '
            f'class="close" aria-label="إغلاق">إغلاق ×</a>'
            f'<img src="{img}" alt="تكبير لقطة الخبر: {headline}"></div>'
        )
    topics = descriptive_topic_counts(articles)
    summary = ''.join(
        f'<tr><td>{escaped(name)}</td><td>{count}</td>'
        f'<td>{count / len(articles) * 100:.1f}%</td></tr>'
        for name, count in sorted(distribution.items(), key=lambda x: (-x[1], x[0]))
    )
    topic_rows = ''.join(
        f'<li><span>{escaped(name)}</span><b>{count}</b></li>'
        for name, count in sorted(topics.items(), key=lambda x: (-x[1], x[0]))
    )
    page = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>رصد | تقرير المواقع الإلكترونية — معاينة موثقة</title>
<style>
:root{--navy:#172c46;--gold:#bd974c;--paper:#faf8f2;--ink:#142235}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Tahoma,Arial,sans-serif}
header{background:var(--navy);color:white;padding:36px max(18px,calc((100% - 1050px)/2));border-bottom:6px solid var(--gold)}
header .brand{color:#efd69b;letter-spacing:.12em;font-size:14px}
h1{font-size:clamp(24px,4vw,40px);margin:12px 0 8px}header p{color:#ebecf1;line-height:1.8}
main{max-width:1050px;margin:auto;padding:24px 16px 50px}
.notice{border-right:4px solid var(--gold);background:#fff;padding:14px 18px;line-height:1.8;margin:22px 0}
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.stat{background:white;padding:22px;border:1px solid #ece6da}.stat b{font-size:36px;color:var(--navy)}
h2{border-bottom:2px solid #d9c6a4;padding-bottom:10px;margin-top:34px}
table{width:100%;border-collapse:collapse;background:white}th{background:var(--navy);color:white}
td,th{text-align:right;padding:10px;border:1px solid #e2e0dc}
.topics{padding:0;list-style:none;display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:9px}
.topics li{background:white;display:flex;justify-content:space-between;padding:14px;border:1px solid #e9e1d3}
.clippings{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.clip{min-width:0;background:#fff;border:1px solid #e9dfcf;padding:14px;box-shadow:0 3px 10px #1422350a}
.clip-title{display:flex;align-items:flex-start;gap:12px;min-height:92px}.clip-title h3{margin:0;color:var(--navy)}.clip-title p{margin:4px 0;line-height:1.6}
.clip-title small{color:#606975}.index{background:var(--navy);color:#edcf86;padding:8px}
.photo{display:block;height:350px;overflow:hidden;background:#eae7df}
.photo img{display:block;width:100%;height:100%;object-fit:contain}
.source-link{display:inline-block;margin:12px 0 4px;color:#114b78}
.zoom{display:none;position:fixed;inset:0;background:#111e2ef5;z-index:8;padding:60px 20px 20px;overflow:auto;text-align:center}
.zoom:target{display:block}.zoom img{max-width:min(100%,1080px);height:auto;box-shadow:0 0 15px #000}
.close{position:fixed;top:10px;left:20px;color:white;background:#314c68;padding:10px 18px;text-decoration:none}
footer{padding:25px;text-align:center;color:#64707c}
@media(max-width:670px){.clippings{grid-template-columns:1fr}.photo{height:430px}h1{font-size:28px}}
</style></head><body>
<header><div class="brand">وزارة التخطيط | رصد RASD</div><h1>تقرير رصد المواقع الإلكترونية</h1>
<p>الفترة التي يغطيها سجل التسليم: __PERIOD__</p></header>
<main><p class="notice"><b>حدود التقرير:</b> تغطيات مصوّرة سبق قبول تسليمها بعد التحقق من الصور الأصلية.
هذا التقرير لا يثبت رصد جميع الأخبار المنشورة ولا يعني أن المصادر المرشحة للبحث تعمل آليًا.
لا تُضاف أي تغطية دون صفحة الناشر وصورتها وتاريخها ورابطها.</p>
<div class="stats"><div class="stat">التغطيات الموثقة<br><b>__STORIES__</b></div>
<div class="stat">المواقع الممثلة<br><b>__SITES__</b></div></div>
<h2>تحليل الرصد — توزيع التغطيات حسب الموقع</h2>
<table><thead><tr><th>الموقع الناشر</th><th>عدد التغطيات</th><th>النسبة</th></tr></thead>
<tbody>__DISTRIBUTION__</tbody></table>
<h2>المحاور الموضوعية — تحليل وصفي</h2><ul class="topics">__TOPICS__</ul>
<p class="notice">يُصنف الخبر من كلمات عنوانه وموجزه الأصلي. قد يُحتسب في أكثر من محور؛
الأرقام ليست تقييمًا إيجابيًا/سلبيًا، ولا تعني عدد الأحداث المستقلة.</p>
<section id="reports"><h2>المواقع الإلكترونية — كل تغطية بصورة أصلية مستقلة</h2>
<div class="clippings">__CARDS__</div></section></main>
<footer>رصد — هذا العرض من صور JPEG الموثقة ومراجع الناشرين الأصليين فقط.</footer>
</body></html>"""
    replacements = {
        "__PERIOD__": escaped(report.get("display_window_start", "غير محدد")) +
                      " — " + escaped(report.get("display_window_end", "غير محدد")),
        "__STORIES__": str(len(articles)),
        "__SITES__": str(len(distribution)),
        "__DISTRIBUTION__": summary,
        "__TOPICS__": topic_rows,
        "__CARDS__": "\n".join(cards),
    }
    for old, new in replacements.items():
        page = page.replace(old, new)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(page, encoding="utf-8")
