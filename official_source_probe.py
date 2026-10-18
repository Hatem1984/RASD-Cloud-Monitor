"""One-time, read-only official Ministry discovery channel probe (no mail/Word).

Tests the original publisher's news listing and home frontpage as potential
*listing* sources. A hand-picked original article does not count as discovery.
Nothing here registers a production feed or follows arbitrary hosts/links.
"""
from __future__ import annotations

import json
from collections import Counter
from urllib.parse import urlsplit, parse_qsl

from official_ministry_source import (
    INDEX, allowed_official_resource, index_articles,
)

LISTINGS = (INDEX,)
MAX_LINKS = 35


def probe() -> dict:
    from playwright.sync_api import sync_playwright
    out = {
        "mode": "gate39_ministry_owned_listing_probe",
        "production_sources_changed": False,
        "ministry_keywords_changed": False,
        "email_sent": False, "scheduler_enabled": False,
        "report_published": False,
        "listings": [],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            context = browser.new_context(
                viewport={"width": 1200, "height": 900}, locale="ar-EG",
                accept_downloads=False, service_workers="block",
                ignore_https_errors=False)
            blocked_hosts = Counter()
            first_party_ajax_paths = Counter()
            official_xhr_requests = []
            official_xhr_responses = []
            def collect_response(response):
                if urlsplit(response.url).path.casefold() == "/news/newslist":
                    official_xhr_responses.append(response)
            context.on("response", collect_response)
            def audit_request(req):
                if (allowed_official_resource(req.url)
                        and req.resource_type in ("fetch", "xhr")):
                    first_party_ajax_paths[urlsplit(req.url).path] += 1
                    if urlsplit(req.url).path.casefold() == "/news/newslist":
                        raw = req.post_data or ""
                        try:
                            names = sorted(set(k for k, _ in parse_qsl(raw)))
                        except Exception:
                            names = []
                        official_xhr_requests.append({
                            "method": req.method, "body_field_names": names[:25],
                            "content_type": (req.headers.get("content-type", "")
                                             .split(";", 1)[0]),
                            "query_field_names": sorted(
                                set(k for k, _ in parse_qsl(
                                    urlsplit(req.url).query)))[:25],
                        })
            context.on("request", audit_request)
            def route_check(route):
                url = route.request.url
                if allowed_official_resource(url):
                    route.continue_()
                else:
                    blocked_hosts[urlsplit(url).hostname or "unknown"] += 1
                    route.abort()
            context.route("**/*", route_check)
            page = context.new_page()
            for url in LISTINGS:
                row = {
                    "listing": LISTINGS.index(url),
                    "http_success": False, "original_article_links": 0,
                    "index_legacy": url == INDEX,
                    "render_result": "unavailable",
                }
                try:
                    response = page.goto(
                        url, wait_until="domcontentloaded", timeout=22000)
                    if (response is not None and response.status == 200
                            and allowed_official_resource(page.url)):
                        row["http_success"] = True
                        page.wait_for_timeout(1400)
                        document = page.content()
                        links = index_articles(document)
                        row["original_article_links"] = len(links)
                        row["render_result"] = "links" if links else "empty"
                        # Report only safe script/endpoint topology, not URLs,
                        # article text, body, image or private data.
                        row["site_script_count"] = page.locator("script[src]").count()
                        row["document_bytes"] = len(document.encode("utf-8"))
                except Exception:
                    row["render_result"] = "page_error"
                out["listings"].append(row)
            out["official_newslist_requests"] = official_xhr_requests[:4]
            out["official_newslist_responses"] = []
            for response in official_xhr_responses[:4]:
                record = {"status": response.status,
                          "content_type": response.headers.get("content-type", "").split(";", 1)[0]}
                try:
                    body = response.body()
                    record["bytes"] = len(body)
                    record["article_link_indicators"] = body.lower().count(b"singlenews")
                    if len(body) < 700_000 and "json" in record["content_type"]:
                        d = json.loads(body)
                        record["json_root_type"] = type(d).__name__
                        record["json_keys"] = sorted(d.keys())[:25] if isinstance(d, dict) else []
                        record["json_array_size"] = len(d) if isinstance(d, list) else 0
                    else:
                        record["looks_like_no_results"] = "لا يوجد نتائج" in body.decode("utf-8", "replace")
                except Exception:
                    record["inspect_status"] = "unavailable"
                out["official_newslist_responses"].append(record)
            out["third_party_requests_blocked"] = sum(blocked_hosts.values())
            out["third_party_host_counts"] = dict(blocked_hosts.most_common(12))
            out["first_party_ajax_paths"] = dict(first_party_ajax_paths.most_common(12))
            out["discovered_original_links"] = max(
                (x["original_article_links"] for x in out["listings"]),
                default=0)
            out["status"] = "CANDIDATE_FOUND" if out[
                "discovered_original_links"] else "HOLD"
        finally:
            browser.close()
    return out


if __name__ == "__main__":
    try:
        print(json.dumps(probe(), sort_keys=True), flush=True)
    except Exception:
        print("gate39_publisher_index_probing_held", flush=True)
        raise SystemExit(2) from None
