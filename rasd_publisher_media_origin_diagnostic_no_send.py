"""Read-only CDN diagnostics for reviewed exact original publisher article URLs.

Diagnostic does not fetch denied assets, record request URLs, log article text,
alter DOM, bypass challenges, persist screenshots or touch mail. Browser logs
only sanitised public hostnames and counts, which allow explicit per-publisher
CDN review. Existing source QA is not changed automatically.
"""
from __future__ import annotations

import json
from collections import Counter
from urllib.parse import urlsplit

from capture_public import allowed_url

SAMPLES=(
    ("alnaharegypt.com",
     "https://www.alnaharegypt.com/1205331"),
    ("almalnews.com",
     "https://almalnews.com/2148532/"
     "%D8%AA%D8%AD%D9%88%D9%8A%D9%84%D9%87%D8%A7-%D8%A5%D9%84%D9%89-%D9%85%D8%AF%D9%8A%D9%86%D8%A9-%D9%85%D8%B3%D8%AA%D8%AF%D8%A7%D9%85%D8%A9-%D9%88%D8%B2%D9%8A%D8%B1-%D8%A7%D9%84%D8%AA%D8%AE%D8%B7%D9%8A%D8%B7-%D8%A8%D9%88%D8%B1%D8%B3%D8%B9%D9%8A%D8%AF/"),
    ("youm7.com",
     "https://www.youm7.com/story/2026/11/20/"
     "%D9%88%D8%B2%D9%8A%D8%B1-%D8%A7%D9%84%D8%AA%D8%AE%D8%B7%D9%8A%D8%B7-%D9%86%D8%AC%D8%A7%D8%AD-%D8%A7%D9%84%D8%AF%D9%88%D8%B1%D8%A9-%D8%A7%D9%84%D8%B1%D8%A7%D8%A8%D8%B9%D8%A9-%D9%8A%D8%B9%D9%83%D8%B3-%D8%AA%D8%B7%D9%88%D8%B1-%D8%A7%D9%84%D9%85%D8%A8%D8%A7%D8%AF%D8%B1%D8%A9-%D9%88%D9%82%D8%AF%D8%B1%D8%AA%D9%87%D8%A7-%D8%B9%D9%84%D9%89/7625874"),
)
ASSET_TYPES={"image","stylesheet","font","media"}
MAX_PRINT_HOSTS=7


def inspect(browser,publisher,url):
    context=browser.new_context(
        viewport={"width":1200,"height":900},locale="ar-EG",
        service_workers="block",ignore_https_errors=False)
    blocked=Counter()
    allowed_assets=Counter()

    def router(route):
        request=route.request
        if allowed_url(request.url,publisher,asset=True):
            if request.resource_type in ASSET_TYPES:
                allowed_assets[request.resource_type]+=1
            route.continue_()
        else:
            if request.resource_type in ASSET_TYPES:
                p=urlsplit(request.url)
                hostname=(p.hostname or "").lower()
                # No IPs/ports/URLs; generic hostname diagnostics only.
                if p.scheme=="https" and hostname and not any(
                    c in hostname for c in ("localhost","127.0.0.1")):
                    blocked[(request.resource_type,hostname)]+=1
            route.abort()
    context.route("**/*",router)
    page=context.new_page()
    result={"publisher":publisher,"status":"HOLD",
            "http_status":None,"original_h1_count":0}
    try:
        response=page.goto(url,wait_until="domcontentloaded",timeout=18000)
        result["http_status"]=response.status if response else None
        if response and response.status==200 and page.url==url:
            page.wait_for_timeout(1500)
            result["original_h1_count"]=page.locator("h1").count()
            result["status"]="ORIGINAL_LOADED"
    except Exception as error:
        result["status"]="BROWSER_"+type(error).__name__
    finally:
        result["allowed_asset_counts"]=dict(allowed_assets)
        result["blocked_asset_hosts"]=[
            {"type":kind,"host":host,"count":value}
            for (kind,host),value in blocked.most_common(MAX_PRINT_HOSTS)]
        context.close()
    return result


def main():
    from playwright.sync_api import sync_playwright
    from capture_public import APPROVED_PUBLISHERS
    # Research-only known hosts. Production hosts remain unmodified until
    # reviewed, explicit source acceptance.
    APPROVED_PUBLISHERS.update({
        "alnaharegypt.com":frozenset({"www.alnaharegypt.com"}),
        "almalnews.com":frozenset({"almalnews.com"}),
        "youm7.com":frozenset({"www.youm7.com"}),
    })
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox",
                                                      "--disable-dev-shm-usage"])
        try:
            for publisher,url in SAMPLES:
                result=inspect(browser,publisher,url)
                print("RASD_MEDIA_ORIGIN_DIAGNOSTIC="+json.dumps(
                    result,ensure_ascii=True),flush=True)
        finally:
            browser.close()
    print("RASD_MEDIA_PROBE_NO_SEND_NO_ARTIFACTS=1")


if __name__=="__main__":
    main()
