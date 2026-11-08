"""Authorized, read-only RASD social API discovery. NEVER sends or publishes.

Official Meta Page-published-posts and X recent-search APIs only. No cookies,
personal accounts, scraping, third-party search, tokens in URLs/logs, or implicit
paid X requests. Data are CANDIDATES, never screenshot-verified news.
"""
from __future__ import annotations

import json
import os
import re
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from monitor import _ministry_term_present
from rasd_four_reports_review import hourly_window

CONFIG_PATH = Path(__file__).with_name("rasd_social_sources_review.json")
NEWS_PATH = Path(__file__).with_name("sources_newsroom_active.json")
MAX_BODY = 1_200_000
MAX_QUERY = 512
GRAPH = "https://graph.facebook.com/v26.0"
X_RECENT = "https://api.x.com/2/tweets/search/recent"
_SNOWFLAKE = re.compile(r"[0-9]{8,25}\Z")
_PAGE = re.compile(r"[0-9]{5,25}\Z")
_FB_ID = re.compile(r"[0-9]{5,25}_[0-9]{5,30}\Z")
_USER = re.compile(r"[A-Za-z0-9_]{1,15}\Z")
_CURSOR = re.compile(r"[A-Za-z0-9_\-=]{1,500}\Z")
_ALLOWED_STATUS = {"ok", "hold", "unauthorized", "not_configured"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("social_api_redirect_hold")


def platform_json_get(url: str, token: str, *,
                      expected_host: str, requester=None) -> dict:
    """No redirects, host override, bearer leaks, or unsafe HTTP responses."""
    p = urlsplit(url)
    if (p.scheme != "https" or p.hostname != expected_host
            or p.port not in (None, 443) or p.username or p.password
            or p.fragment or not p.path.strip("/")):
        raise RuntimeError("social_api_host_hold")
    if not isinstance(token, str) or not token.strip():
        raise RuntimeError("social_missing_authorization_hold")
    if "access_token" in p.query.lower() or "token=" in p.query.lower():
        raise RuntimeError("social_api_token_in_url_hold")
    request = Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "RASD-Official-Social-ReadOnly/1",
    })
    try:
        opener = requester or build_opener(
            NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
        with opener.open(request, timeout=15) as response:
            if response.geturl() != url:
                raise RuntimeError("social_api_final_url_hold")
            body = response.read(MAX_BODY + 1)
            if len(body) > MAX_BODY:
                raise RuntimeError("social_api_body_limit_hold")
            data = json.loads(body.decode("utf-8"))
        if (not isinstance(data, dict) or "errors" in data
                or "error" in data):
            raise RuntimeError("social_api_error_or_partial_hold")
        return data
    except (HTTPError, URLError, OSError, TimeoutError,
            ValueError, UnicodeError, json.JSONDecodeError):
        # Error replies may contain tokens, account names, and billing data.
        raise RuntimeError("social_api_unavailable_or_denied_hold") from None


def _when(value: str, *, start: datetime, end: datetime) -> datetime | None:
    if not isinstance(value, str) or len(value) > 45:
        raise ValueError("social_post_time_hold")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError
        utc = dt.astimezone(timezone.utc)
        return utc if start <= utc < end else None
    except ValueError:
        raise ValueError("social_post_time_hold") from None


def _fb_url_ok(raw: str) -> bool:
    if not isinstance(raw, str) or len(raw) > 1600:
        return False
    try:
        p = urlsplit(raw)
        return (p.scheme == "https" and p.hostname in {
                "facebook.com", "www.facebook.com", "m.facebook.com"}
                and p.port in (None, 443) and not p.username
                and not p.password and not p.query and not p.fragment
                and ("/posts/" in p.path or p.path.rstrip("/").endswith("/story.php")
                     or "/reel/" in p.path))
    except ValueError:
        return False


def _keywords() -> list[str]:
    doc = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    keys = doc.get("keywords")
    if (not isinstance(keys, list) or not keys
            or any(not isinstance(x, str) or not x.strip() for x in keys)):
        raise ValueError("social_ministry_scope_missing_hold")
    return keys


def _fb_page_profile(row: dict) -> dict:
    if (not isinstance(row, dict)
            or not _PAGE.fullmatch(str(row.get("id", "")))
            or not isinstance(row.get("name"), str)
            or not 1 <= len(row["name"].strip()) <= 140):
        raise ValueError("facebook_page_approval_invalid_hold")
    handle = row.get("handle", "")
    if (not isinstance(handle, str) or
            handle and not re.fullmatch(r"[A-Za-z0-9.]{5,80}", handle)):
        raise ValueError("facebook_page_handle_approval_invalid_hold")
    return {"id": row["id"], "name": row["name"].strip(),
            "handle": handle}


def _fb_post(row: dict, page: dict, *, start: datetime, end: datetime,
             keywords: list[str]) -> dict | None:
    if not isinstance(row, dict):
        raise ValueError("facebook_post_shape_hold")
    text = row.get("message", "")
    if not isinstance(text, str):
        raise ValueError("facebook_post_text_hold")
    if not text.strip() or not _ministry_term_present(text, keywords):
        return None
    ident = row.get("id")
    if not isinstance(ident, str) or not _FB_ID.fullmatch(ident):
        raise ValueError("facebook_post_identity_hold")
    if ident.split("_", 1)[0] != page["id"]:
        raise ValueError("facebook_post_other_page_hold")
    stamp = _when(row.get("created_time"), start=start, end=end)
    if stamp is None:
        return None
    url = row.get("permalink_url")
    if not _fb_url_ok(url):
        raise ValueError("facebook_post_permalink_hold")
    parts = urlsplit(url).path.strip("/").split("/")
    if len(parts) >= 3 and parts[-2] == "posts":
        owner = parts[-3]
        approved_handle = page.get("handle", "")
        if not (owner == page["id"] or
                approved_handle and owner.casefold() == approved_handle.casefold()):
            raise ValueError("facebook_permalink_other_owner_hold")
        suffix = ident.split("_", 1)[1]
        if parts[-1].isdigit() and parts[-1] != suffix:
            raise ValueError("facebook_permalink_other_post_hold")
    else:
        # Other opaque Graph aliases require separate original-page proof.
        raise ValueError("facebook_noncanonical_post_link_hold")
    return {
        "channel": "social", "platform": "facebook",
        "platform_post_id": ident, "source": page["name"],
        "url": url, "published_at": stamp.isoformat(),
        "title": text.strip()[:250], "text": text.strip()[:2000],
        "evidence_status": "HOLD_ORIGINAL_POST_SCREENSHOT",
    }


def _x_post(row: dict, user_map: dict, *, start: datetime, end: datetime,
            keywords: list[str]) -> dict | None:
    if not isinstance(row, dict):
        raise ValueError("x_post_shape_hold")
    ident, author = row.get("id"), row.get("author_id")
    text = row.get("text", "")
    if not isinstance(text, str):
        raise ValueError("x_post_text_hold")
    if not text.strip() or not _ministry_term_present(text, keywords):
        return None
    if (not isinstance(ident, str) or not _SNOWFLAKE.fullmatch(ident)
            or not isinstance(author, str) or not _SNOWFLAKE.fullmatch(author)):
        raise ValueError("x_post_identity_hold")
    account = user_map.get(author)
    if (not isinstance(account, dict)
            or account.get("id") != author
            or not _USER.fullmatch(str(account.get("username", "")))):
        raise ValueError("x_post_user_identity_hold")
    stamp = _when(row.get("created_at"), start=start, end=end)
    if stamp is None:
        return None
    username = account["username"]
    return {
        "channel": "social", "platform": "x",
        "platform_post_id": ident, "source": "@" + username,
        "url": f"https://x.com/{username}/status/{ident}",
        "published_at": stamp.isoformat(),
        "title": text.strip()[:250], "text": text.strip()[:2000],
        "evidence_status": "HOLD_ORIGINAL_POST_SCREENSHOT",
    }


def _batch_outcome(rows: list[dict], next_cursor: str | None, *,
                   platform: str, failed: bool) -> dict:
    return {"platform": platform,
            "status": "hold" if failed or next_cursor else "ok",
            "posts": rows,
            "matched_count": len(rows),
            "coverage": ("PARTIAL_API_OR_PAGINATION_HOLD" if failed or next_cursor
                         else "API_METADATA_ONLY_SCREENSHOT_HOLD")}



def collect_approved_facebook(config: dict, *, token: str,
                              start: datetime, end: datetime,
                              keywords: list[str], getter=platform_json_get) -> dict:
    pages = config.get("pages")
    max_pages = config.get("max_pages_per_page")
    page_size = config.get("max_posts_per_page")
    if (not isinstance(pages, list) or not 0 < len(pages) <= 10
            or type(max_pages) is not int or not 1 <= max_pages <= 5
            or type(page_size) is not int or not 1 <= page_size <= 100):
        raise ValueError("facebook_approved_scope_invalid_hold")
    profiles = [_fb_page_profile(p) for p in pages]
    if len({p["id"] for p in profiles}) != len(profiles):
        raise ValueError("facebook_duplicate_page_scope_hold")
    seen, posts, failures = set(), [], []
    for page in profiles:
        after = None
        exhausted = False
        try:
            for _ in range(max_pages):
                params = {
                    "fields": "id,message,created_time,permalink_url",
                    "limit": page_size,
                    "since": int(start.timestamp()),
                    "until": int(end.timestamp()),
                }
                if after:
                    params["after"] = after
                uri = GRAPH + "/" + page["id"] + "/published_posts?" + urlencode(params)
                payload = getter(uri, token, expected_host="graph.facebook.com")
                data = payload.get("data")
                if not isinstance(data, list) or len(data) > page_size:
                    raise RuntimeError("facebook_api_page_shape_hold")
                for row in data:
                    post = _fb_post(row, page, start=start, end=end,
                                    keywords=keywords)
                    if post and post["platform_post_id"] not in seen:
                        posts.append(post)
                        seen.add(post["platform_post_id"])
                paging = payload.get("paging", {})
                if not isinstance(paging, dict):
                    raise RuntimeError("facebook_api_paging_hold")
                cursors = paging.get("cursors", {})
                if not isinstance(cursors, dict):
                    raise RuntimeError("facebook_api_paging_hold")
                upcoming = cursors.get("after") if paging.get("next") else None
                if paging.get("next") and not upcoming:
                    raise RuntimeError("facebook_api_missing_cursor_hold")
                if not upcoming:
                    after = None
                    exhausted = True
                    break
                if (not isinstance(upcoming, str)
                        or not _CURSOR.fullmatch(upcoming)
                        or upcoming == after):
                    raise RuntimeError("facebook_api_cursor_hold")
                after = upcoming
            if not exhausted:
                failures.append("HOLD_FACEBOOK_PAGINATION_LIMIT")
        except (RuntimeError, ValueError, TypeError):
            failures.append("HOLD_FACEBOOK_ORIGINAL_API")
    result = _batch_outcome(
        posts, "limited" if failures else None,
        platform="facebook", failed=bool(failures))
    result["pages_requested"] = len(profiles)
    result["pages_with_hold"] = len(failures)
    return result


def collect_approved_x(config: dict, *, token: str,
                       start: datetime, end: datetime,
                       keywords: list[str], getter=platform_json_get) -> dict:
    queries = config.get("queries")
    pages = config.get("max_pages_per_query")
    size = config.get("page_size")
    cap = config.get("max_posts_per_run")
    if (not isinstance(queries, list) or not 0 < len(queries) <= 4
            or any(not isinstance(q, str) or
                   not 3 <= len(q.strip()) <= MAX_QUERY for q in queries)
            or len(set(queries)) != len(queries)
            or type(pages) is not int or not 1 <= pages <= 5
            or type(size) is not int or not 10 <= size <= 100
            or type(cap) is not int or not 1 <= cap <= 100
            or len(queries) * pages * size > cap):
        raise ValueError("x_cost_and_scope_limit_hold")
    seen, posts, failures = set(), [], []
    for query in queries:
        cursor = None
        exhausted = False
        try:
            for _ in range(pages):
                params = {
                    "query": query,
                    "tweet.fields": "created_at,author_id",
                    "expansions": "author_id",
                    "user.fields": "username,name",
                    "start_time": start.isoformat().replace("+00:00", "Z"),
                    "end_time": end.isoformat().replace("+00:00", "Z"),
                    "max_results": size,
                }
                if cursor:
                    params["next_token"] = cursor
                uri = X_RECENT + "?" + urlencode(params)
                payload = getter(uri, token, expected_host="api.x.com")
                data = payload.get("data", [])
                meta = payload.get("meta")
                includes = payload.get("includes", {})
                if (not isinstance(data, list) or len(data) > size
                        or not isinstance(meta, dict)
                        or not isinstance(includes, dict)):
                    raise RuntimeError("x_api_page_shape_hold")
                users = includes.get("users", [])
                if not isinstance(users, list):
                    raise RuntimeError("x_api_users_hold")
                mapped = {
                    u["id"]: u for u in users
                    if isinstance(u, dict) and isinstance(u.get("id"), str)}
                if len(mapped) != len(users):
                    raise RuntimeError("x_api_users_ambiguous_hold")
                for row in data:
                    post = _x_post(row, mapped, start=start, end=end,
                                   keywords=keywords)
                    if post and post["platform_post_id"] not in seen:
                        seen.add(post["platform_post_id"])
                        posts.append(post)
                upcoming = meta.get("next_token")
                if not upcoming:
                    cursor = None
                    exhausted = True
                    break
                if (not isinstance(upcoming, str)
                        or not _CURSOR.fullmatch(upcoming)
                        or upcoming == cursor):
                    raise RuntimeError("x_api_cursor_hold")
                cursor = upcoming
            if not exhausted:
                failures.append("HOLD_X_PAGINATION_LIMIT")
        except (ValueError, RuntimeError, TypeError):
            failures.append("HOLD_X_ORIGINAL_API")
    result = _batch_outcome(
        posts, "limited" if failures else None,
        platform="x", failed=bool(failures))
    result["queries_requested"] = len(queries)
    result["queries_with_hold"] = len(failures)
    result["max_billable_posts_configured"] = cap
    return result


def _ig_post(row: dict, account: dict, *, start: datetime,
             end: datetime, keywords: list[str]) -> dict | None:
    if not isinstance(row, dict):
        raise ValueError("instagram_media_shape_hold")
    text = row.get("caption", "")
    if not isinstance(text, str):
        raise ValueError("instagram_media_caption_hold")
    if not text.strip() or not _ministry_term_present(text, keywords):
        return None
    ident = row.get("id")
    if not isinstance(ident, str) or not _SNOWFLAKE.fullmatch(ident):
        raise ValueError("instagram_media_id_hold")
    if row.get("username", "").casefold() != account["username"].casefold():
        raise ValueError("instagram_owner_identity_hold")
    stamp = _when(row.get("timestamp"), start=start, end=end)
    if stamp is None:
        return None
    raw = row.get("permalink")
    if not isinstance(raw, str) or len(raw) > 1000:
        raise ValueError("instagram_original_link_hold")
    try:
        parsed = urlsplit(raw)
        if (parsed.scheme != "https" or parsed.hostname not in
                {"www.instagram.com", "instagram.com"} or
                parsed.port not in (None, 443) or parsed.username or
                parsed.password or parsed.query or parsed.fragment or
                not any(parsed.path.startswith(prefix) for prefix in
                        ("/p/", "/reel/"))):
            raise ValueError
    except ValueError:
        raise ValueError("instagram_original_link_hold") from None
    return {
        "channel": "social", "platform": "instagram",
        "platform_post_id": ident, "source": "@" + account["username"],
        "url": raw, "published_at": stamp.isoformat(),
        "title": text.strip()[:250], "text": text.strip()[:2000],
        "evidence_status": "HOLD_ORIGINAL_POST_SCREENSHOT",
    }


def collect_approved_instagram(config: dict, *, token: str,
                               start: datetime, end: datetime,
                               keywords: list[str],
                               getter=platform_json_get) -> dict:
    """Read only *managed, approved professional* account media.

    Meta's IG media edge lacks time-based pagination: page caps are labelled
    HOLD, never mistaken for full public listening or third-party coverage.
    """
    accounts = config.get("accounts")
    pages = config.get("max_pages_per_account")
    size = config.get("page_size")
    if (not isinstance(accounts, list) or not 0 < len(accounts) <= 5
            or type(pages) is not int or not 1 <= pages <= 4
            or type(size) is not int or not 1 <= size <= 100):
        raise ValueError("instagram_approved_scope_invalid_hold")
    checked = []
    for item in accounts:
        if (not isinstance(item, dict)
                or not _SNOWFLAKE.fullmatch(str(item.get("id", "")))
                or not re.fullmatch(
                    r"[A-Za-z0-9_.]{1,30}", str(item.get("username", "")))):
            raise ValueError("instagram_business_account_invalid_hold")
        checked.append({"id": item["id"], "username": item["username"]})
    if len({i["id"] for i in checked}) != len(checked):
        raise ValueError("instagram_duplicate_owner_hold")
    seen, posts, failures = set(), [], []
    for account in checked:
        cursor, exhausted = None, False
        try:
            for _ in range(pages):
                params = {
                    "fields": "id,caption,timestamp,permalink,username",
                    "limit": size,
                }
                if cursor:
                    params["after"] = cursor
                url = GRAPH + "/" + account["id"] + "/media?" + urlencode(params)
                payload = getter(url, token, expected_host="graph.facebook.com")
                data = payload.get("data")
                if not isinstance(data, list) or len(data) > size:
                    raise RuntimeError("instagram_api_media_shape_hold")
                for row in data:
                    post = _ig_post(row, account, start=start, end=end,
                                    keywords=keywords)
                    if post and post["platform_post_id"] not in seen:
                        posts.append(post)
                        seen.add(post["platform_post_id"])
                paging = payload.get("paging", {})
                if not isinstance(paging, dict):
                    raise RuntimeError("instagram_api_cursor_hold")
                cursors = paging.get("cursors", {})
                if not isinstance(cursors, dict):
                    raise RuntimeError("instagram_api_cursor_hold")
                next_cursor = cursors.get("after") if paging.get("next") else None
                if paging.get("next") and not next_cursor:
                    raise RuntimeError("instagram_api_missing_cursor_hold")
                if not next_cursor:
                    exhausted = True
                    cursor = None
                    break
                if (not isinstance(next_cursor, str) or
                        not _CURSOR.fullmatch(next_cursor) or
                        next_cursor == cursor):
                    raise RuntimeError("instagram_api_cursor_hold")
                cursor = next_cursor
            if not exhausted:
                failures.append("HOLD_INSTAGRAM_PAGINATION_LIMIT")
        except (RuntimeError, ValueError, TypeError):
            failures.append("HOLD_INSTAGRAM_ORIGINAL_API")
    result = _batch_outcome(
        posts, "limited" if failures else None,
        platform="instagram", failed=bool(failures))
    result["accounts_requested"] = len(checked)
    result["accounts_with_hold"] = len(failures)
    return result


def collect_social(*, live: bool = False,
                   config: dict | None = None,
                   now: datetime | None = None,
                   getter=platform_json_get,
                   environment: dict | None = None) -> dict:
    """No live traffic without dual explicit source and credential gates."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("social_clock_timezone_hold")
    start, end = hourly_window(current)
    config = config if config is not None else json.loads(
        CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise ValueError("social_source_manifest_invalid_hold")
    env = environment if environment is not None else os.environ
    keywords = _keywords()
    results = {}
    for platform in ("facebook", "x", "instagram"):
        scope = config.get(platform)
        if not isinstance(scope, dict):
            raise ValueError("social_scope_missing_hold")
        results[platform] = {
            "platform": platform,
            "status": "not_configured" if not scope.get("approved") else "unauthorized",
            "posts": [], "matched_count": 0, "coverage": "HOLD_NOT_ACCESSED",
        }
        if not live or scope.get("approved") is not True:
            continue
        if platform == "facebook":
            mode = scope.get("access_mode", "managed_page")
            if mode not in ("managed_page", "public_ppca"):
                raise ValueError("facebook_access_mode_invalid_hold")
            if mode == "public_ppca":
                token = env.get("RASD_META_PPCA_ACCESS_TOKEN", "")
                if scope.get("ppca_granted") is not True:
                    continue
            else:
                token = env.get("RASD_META_PAGE_ACCESS_TOKEN", "")
            if (scope.get("access_confirmed") is not True or not token):
                continue
            results[platform] = collect_approved_facebook(
                scope, token=token, start=start, end=end,
                keywords=keywords, getter=getter)
        elif platform == "x":
            token = env.get("RASD_X_BEARER_TOKEN", "")
            if (scope.get("paid_api_cost_approved") is not True
                    or env.get("RASD_X_PAID_READ_APPROVED") != "yes"
                    or not token):
                continue
            results[platform] = collect_approved_x(
                scope, token=token, start=start, end=end,
                keywords=keywords, getter=getter)
        else:
            token = env.get("RASD_INSTAGRAM_PAGE_ACCESS_TOKEN", "")
            if scope.get("access_confirmed") is not True or not token:
                continue
            results[platform] = collect_approved_instagram(
                scope, token=token, start=start, end=end,
                keywords=keywords, getter=getter)
    results["linkedin"] = {
        "platform": "linkedin", "status": "not_configured" if
        config.get("linkedin", {}).get("approved") is not True else "hold",
        "posts": [], "matched_count": 0,
        "coverage": "HOLD_NO_VERIFIED_OFFICIAL_READ_CONNECTOR",
    }
    seen, posts = set(), []
    for platform in ("facebook", "x", "instagram"):
        for row in results[platform]["posts"]:
            key = (platform, row["platform_post_id"])
            if key not in seen:
                posts.append(row)
                seen.add(key)
    return {
        "status": "REVIEW_METADATA_ONLY_NO_SEND",
        "window_utc": [start.isoformat(), end.isoformat()],
        "sources": results,
        "post_candidates": posts,
        "original_screenshots_verified": 0,
        "smtp_sent": False, "scheduler_changed": False,
        "platform_api_access_proven": bool(live and
            any(results[x]["status"] == "ok" for x in
                ("facebook", "x", "instagram"))),
    }
