"""Explicitly gated first-party Al Mal HTML source within the RASD pipeline.

Approval of a publisher origin and sending its articles are separate:
- Original HTML source requires a fixed config identity and exact HTTPS hosts.
- Candidate is dormant unless RASD_ALMAL_ORIGINAL_HTML_ENABLED=true.
- Accepted historical articles retain verifiable source identity if disabled.
- No RSS substitution, redirect, CAPTCHA bypass, third-party snippet or AI.
"""
from __future__ import annotations

import os

ALMAL_SOURCE = {
    "id": "almal_html",
    "name": "Al Mal native publisher HTML",
    "homepage_url": "https://almalnews.com/",
    "allowed_article_hosts": ["almalnews.com", "www.almalnews.com"],
    "type": "original_publisher_html",
}

YOUM7_SOURCE = {
    "id": "youm7_html",
    "name": "Youm7 first-party Ministry tag HTML",
    "homepage_url": ("https://www.youm7.com/Tags/Index?id=33679&tag="
                     "%D9%88%D8%B2%D8%A7%D8%B1%D8%A9-%D8%A7%D9%84%D8%AA%D8%AE%D8%B7%D9%8A%D8%B7"),
    "allowed_article_hosts": ["www.youm7.com"],
    "type": "original_publisher_tag_html",
}


def all_newsroom_origins(config: dict) -> list[dict]:
    feeds=config["feeds"]
    if not isinstance(feeds,list) or not feeds:
        raise ValueError("rss_newsroom_inventory_invalid")
    optional=config.get("original_html_sources",[])
    if optional not in ([], [ALMAL_SOURCE], [ALMAL_SOURCE, YOUM7_SOURCE]):
        raise ValueError("unreviewed_html_publisher_origin")
    # Preserve validation by existing 14-RSS production functions.
    if not optional:
        return feeds
    ids={item["id"] for item in optional}
    names={item["name"] for item in optional}
    if any(x.get("id") in ids or x.get("name") in names for x in feeds):
        raise ValueError("publisher_origin_identity_conflict")
    return [*feeds,*optional]


def collection_origins(config: dict) -> list[dict]:
    all_origins=all_newsroom_origins(config)
    enabled = []
    if os.environ.get("RASD_ALMAL_ORIGINAL_HTML_ENABLED")=="true":
        enabled.append("almal_html")
    if os.environ.get("RASD_YOUM7_ORIGINAL_HTML_ENABLED")=="true":
        enabled.append("youm7_html")
    return [*config["feeds"], *(row for row in
        all_origins[len(config["feeds"]):] if row["id"] in enabled)]


def html_collection_enabled(config: dict) -> bool:
    return (os.environ.get("RASD_ALMAL_ORIGINAL_HTML_ENABLED")=="true"
            and any(x["id"]=="almal_html"
                    for x in all_newsroom_origins(config)
                    if x.get("type")=="original_publisher_html"))


def youm7_collection_enabled(config: dict) -> bool:
    return (os.environ.get("RASD_YOUM7_ORIGINAL_HTML_ENABLED")=="true"
            and any(x["id"]=="youm7_html"
                    for x in all_newsroom_origins(config)
                    if x.get("type")=="original_publisher_tag_html"))
