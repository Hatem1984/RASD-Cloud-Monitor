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


def all_newsroom_origins(config: dict) -> list[dict]:
    feeds=config["feeds"]
    if not isinstance(feeds,list) or not feeds:
        raise ValueError("rss_newsroom_inventory_invalid")
    optional=config.get("original_html_sources",[])
    if optional not in ([],[ALMAL_SOURCE]):
        raise ValueError("unreviewed_html_publisher_origin")
    result=[*feeds,*optional]
    ids=[x["id"] for x in result]
    names=[x["name"] for x in result]
    if len(set(ids))!=len(ids) or len(set(names))!=len(names):
        raise ValueError("publisher_origin_identity_conflict")
    return result


def collection_origins(config: dict) -> list[dict]:
    all_origins=all_newsroom_origins(config)
    html_enabled=(os.environ.get("RASD_ALMAL_ORIGINAL_HTML_ENABLED")=="true"
                  and "original_html_sources" in config)
    return all_origins if html_enabled else config["feeds"]


def html_collection_enabled(config: dict) -> bool:
    return (os.environ.get("RASD_ALMAL_ORIGINAL_HTML_ENABLED")=="true"
            and any(x["id"]=="almal_html"
                    for x in all_newsroom_origins(config)
                    if x.get("type")=="original_publisher_html"))
