"""Manual, opt-in Facebook PAGE monitoring pilot; separate from production RASD.

Only Meta Graph API posts for owner-approved Page IDs. No broad Facebook search,
private-profile access, scraping, email, scheduler, private CAS or credential files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from docx import Document
from docx.shared import Pt

from daily_report import _rtl, _word_hyperlink, cairo_display_time
from monitor import _ministry_term_present

GRAPH_API_VERSION = "v26.0"
MAX_PAGES = 10
PAGE_SAMPLE_LIMIT = 25
MAX_RESPONSE_BYTES = 1_000_000
CONFIG_PATH = Path(__file__).with_name("facebook_pages_pilot.json")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("facebook_graph_redirect_hold")


def _approved_pages(config: dict) -> list[dict]:
    pages = config.get("pages")
    if not isinstance(pages, list) or not 0 < len(pages) <= MAX_PAGES:
        raise ValueError("facebook_page_configuration_hold")
    checked = []
    for page in pages:
        if (not isinstance(page, dict)
                or not isinstance(page.get("id"), str)
                or not re.fullmatch(r"[0-9]{5,25}", page["id"])
                or not isinstance(page.get("name"), str)
                or not 1 <= len(page["name"].strip()) <= 120):
            raise ValueError("facebook_page_configuration_hold")
        checked.append({"id": page["id"], "name": page["name"].strip()})
    if len({p["id"] for p in checked}) != len(checked):
        raise ValueError("facebook_duplicate_page_hold")
    return checked


def _permalink_ok(link: str) -> bool:
    if not isinstance(link, str):
        return False
    try:
        url = urlsplit(link)
        return (url.scheme == "https"
                and url.hostname in ("www.facebook.com", "facebook.com",
                                     "m.facebook.com")
                and url.port in (None, 443)
                and not url.username and not url.password
                and bool(url.path) and len(link) <= 1200
                and not re.search(r"access_token|appsecret", url.query, re.I))
    except ValueError:
        return False


def _graph_get_published_posts(page_id: str, access_token: str) -> dict:
    # No arbitrary host, supplied next-page URLs or redirects are followed.
    url = ("https://graph.facebook.com/" + GRAPH_API_VERSION + "/"
           + page_id + "/published_posts?" + urlencode({
               "fields": "id,message,created_time,permalink_url",
               "limit": PAGE_SAMPLE_LIMIT,
           }))
    request = Request(url, headers={
        "Authorization": "Bearer " + access_token, "Accept": "application/json",
        "User-Agent": "RASD-Facebook-Manual-Pilot/1",
    })
    with build_opener(_NoRedirect).open(request, timeout=15) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("facebook_response_size_hold")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        raise ValueError("facebook_graph_response_hold")
    return value


def collect(config: dict, *, token: str, page_getter=None,
            now: datetime | None = None) -> dict:
    """Scan at most 25 recent Page-owned posts per approved Page.

    Keyword match is against the SAME saved Ministry of Planning terms as
    the web newsroom. A post is documented as a platform claim, not a fact.
    """
    pages = _approved_pages(config)
    if not isinstance(token, str) or not token.strip():
        raise ValueError("facebook_meta_authorization_hold")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("facebook_clock_hold")
    current = current.astimezone(timezone.utc)
    keywords = config.get("keywords")
    if not isinstance(keywords, list) or not keywords or not all(
            isinstance(k, str) and k.strip() for k in keywords):
        raise ValueError("facebook_keywords_hold")
    fetch = page_getter or _graph_get_published_posts
    findings, held, failures, inspected = [], 0, [], 0
    seen = set()
    for page in pages:
        try:
            payload = fetch(page["id"], token)
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError("facebook_graph_response_hold")
            if len(payload["data"]) > PAGE_SAMPLE_LIMIT:
                raise ValueError("facebook_graph_over_limit_hold")
        except Exception:
            # Never expose token, Graph error payload or original HTTP headers.
            failures.append(page["name"])
            continue
        for post in payload["data"]:
            inspected += 1
            if not isinstance(post, dict):
                held += 1
                continue
            text = post.get("message")
            if not isinstance(text, str) or not text.strip():
                continue
            if not _ministry_term_present(text, keywords):
                continue
            try:
                created = datetime.strptime(
                    post["created_time"], "%Y-%m-%dT%H:%M:%S%z"
                ).astimezone(timezone.utc)
                link = post["permalink_url"]
                post_id = post["id"]
                if (not _permalink_ok(link)
                        or not isinstance(post_id, str)
                        or not re.fullmatch(r"[0-9_]{3,80}", post_id)
                        or created > current
                        or created < current - timedelta(hours=72)):
                    held += 1
                    continue
            except (ValueError, TypeError, KeyError):
                held += 1
                continue
            if post_id in seen:
                continue
            seen.add(post_id)
            findings.append({
                "id": post_id, "page": page["name"],
                "url": link, "created": cairo_display_time(created),
                "message": text.strip()[:1600],
                "evidence_status": "META_PAGE_POST_METADATA_ONLY",
            })
    coverage = "PARTIAL" if failures or held else "SAMPLED"
    findings.sort(key=lambda item: item["id"])
    return {
        "status": ("PARTIAL_SAMPLE" if coverage == "PARTIAL"
                   else "SAMPLED_MATCHES" if findings
                   else "NO_MATCHES_IN_LIMITED_SAMPLE"),
        "coverage": coverage, "posts": findings,
        "pages_checked": len(pages), "pages_failed": len(failures),
        "posts_inspected": inspected, "posts_held": held,
        "per_page_limit": PAGE_SAMPLE_LIMIT,
        "hours": 72, "email_sent": False, "private_ledger_used": False,
    }


def write_facebook_word(report: dict, destination: Path) -> Path:
    """Write a FACEBOOK-only Word. No web RSS sections or delivery claims."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.styles["Normal"].font.name = "DejaVu Sans"
    document.styles["Normal"].font.size = Pt(10)
    heading = document.add_paragraph(style="Title")
    _rtl(heading)
    heading.add_run("رصد | تقرير فيسبوك التجريبي — منشورات صفحات معتمدة")
    for line in (
        "الحالة: " + report["status"] + " | عدد المنشورات المطابقة: "
        + str(len(report["posts"])),
        "عدد الصفحات المفحوصة: " + str(report["pages_checked"])
        + " | صفحات متعذرة: " + str(report["pages_failed"])
        + " | منشورات معلقة: " + str(report["posts_held"]),
        "النطاق: أول " + str(report["per_page_limit"])
        + " منشورًا من كل صفحة خلال آخر " + str(report["hours"])
        + " ساعة. لا يعني غياب النتائج عدم وجود منشورات على فيسبوك.",
        "تنبيه: هذه منشورات من صفحات فيسبوك عبر Meta API. "
        "المنشور أو التعليقات لا يثبتان صحة الادعاءات. "
        "لا توجد صور موثقة أو مراجعة تحريرية مستقلة في هذه النسخة.",
        "هذا تقرير بحث يدوي مستقل؛ لا إرسال بريد ولا دمج مع تقرير الويب.",
    ):
        p = document.add_paragraph()
        _rtl(p)
        p.add_run(line)
    for index, post in enumerate(report["posts"], 1):
        p = document.add_paragraph()
        _rtl(p)
        p.add_run(str(index) + ". " + post["page"]).bold = True
        p = document.add_paragraph()
        _rtl(p)
        p.add_run("تاريخ النشر: " + post["created"])
        p = document.add_paragraph()
        _rtl(p)
        p.add_run(post["message"])
        p = document.add_paragraph()
        _rtl(p)
        _word_hyperlink(p, post["url"], "فتح منشور فيسبوك الأصلي")
    document.save(destination)
    return destination


def run_manual(*, live: bool, output_dir: Path,
               config_file: Path = CONFIG_PATH, page_getter=None,
               now: datetime | None = None) -> dict:
    """No Facebook request unless user explicitly selects live search."""
    if not live:
        return {"status": "DRY_RUN_NO_NETWORK", "facebook_requested": False,
                "email_sent": False}
    config = json.loads(config_file.read_text(encoding="utf-8"))
    # The operator cannot add arbitrary broad keywords to Facebook.
    approved_terms = json.loads(
        Path(__file__).with_name("sources_newsroom_active.json").read_text(
            encoding="utf-8"))["keywords"]
    config["keywords"] = approved_terms
    result = collect(config, token=os.environ.get("RASD_FB_PAGE_TOKEN", ""),
                     page_getter=page_getter, now=now)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S-%f")
    word = write_facebook_word(
        result, output_dir / ("RASD-Facebook-Manual-" + stamp + ".docx"))
    return {**{k: v for k, v in result.items() if k != "posts"},
            "word": str(word), "posts": len(result["posts"])}


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual Facebook Page report, no email")
    parser.add_argument("--live", action="store_true",
                        help="Explicitly authorize Meta Graph read-only requests")
    parser.add_argument("--output-dir", type=Path,
                        default=Path("report-output/facebook"))
    args = parser.parse_args()
    try:
        result = run_manual(live=args.live, output_dir=args.output_dir)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError):
        # All authorization, network and input failures fail closed.
        print(json.dumps({"status": "FACEBOOK_ACCESS_OR_CONFIG_HOLD",
                          "email_sent": False, "private_ledger_used": False}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
