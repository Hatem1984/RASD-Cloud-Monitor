"""Facebook-only RASD read-only access preflight: never emails or screenshots.

An API success verifies only the tested Page endpoint / first sample at one
moment; it does NOT authorize Meta access, prove broad public social listening,
verify screenshot integrity, or certify the final ministry reports.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from rasd_social_official_intake import (
    CONFIG_PATH, GRAPH, _fb_page_profile, _fb_url_ok, platform_json_get,
)
MAX_CHECK_POSTS = 3
_POST_ID = re.compile(r"[0-9]{5,25}_[0-9]{5,30}\Z")


def _approved_mode(fb: dict) -> str:
    if not isinstance(fb, dict):
        raise ValueError("facebook_preflight_config_hold")
    mode = fb.get("access_mode", "managed_page")
    if mode not in {"managed_page", "public_ppca"}:
        raise ValueError("facebook_preflight_mode_hold")
    return mode


def _page_samples(page_id: str, expected_name: str,
                  token: str, getter) -> dict:
    """Exactly two endpoints; never follow opaque paging.next URLs."""
    profile_url = GRAPH + "/" + page_id + "?" + urlencode(
        {"fields": "id,name"})
    info = getter(profile_url, token, expected_host="graph.facebook.com")
    if (not isinstance(info, dict)
            or str(info.get("id")) != page_id
            or not isinstance(info.get("name"), str)
            or not info["name"].strip()
            or " ".join(info["name"].split()).casefold() !=
               " ".join(expected_name.split()).casefold()):
        raise RuntimeError("facebook_preflight_page_identity_hold")
    feed_url = GRAPH + "/" + page_id + "/published_posts?" + urlencode({
        "fields": "id,message,created_time,permalink_url",
        "limit": MAX_CHECK_POSTS,
    })
    result = getter(feed_url, token, expected_host="graph.facebook.com")
    posts = result.get("data")
    if not isinstance(posts, list) or len(posts) > MAX_CHECK_POSTS:
        raise RuntimeError("facebook_preflight_feed_shape_hold")
    # Verify a sample is an actual Page-owned timestamped post, not arbitrary
    # text or a different Page's permalink. Never store its body in the audit.
    for row in posts:
        if not isinstance(row, dict):
            raise RuntimeError("facebook_preflight_post_shape_hold")
        identifier = row.get("id")
        if (not isinstance(identifier, str)
                or not _POST_ID.fullmatch(identifier)
                or identifier.split("_", 1)[0] != page_id):
            raise RuntimeError("facebook_preflight_post_owner_hold")
        raw_time = row.get("created_time")
        try:
            published = datetime.fromisoformat(raw_time.replace(
                "Z", "+00:00"))
            if (published.utcoffset() is None or
                    published.astimezone(timezone.utc) >
                    datetime.now(timezone.utc)):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise RuntimeError("facebook_preflight_post_date_hold") from None
        permalink = row.get("permalink_url")
        if not _fb_url_ok(permalink):
            raise RuntimeError("facebook_preflight_original_link_hold")
        path = urlsplit(permalink).path.strip("/").split("/")
        if (len(path) < 3 or path[-2] != "posts"
                or path[-3] != page_id
                or path[-1] != identifier.split("_", 1)[1]):
            raise RuntimeError("facebook_preflight_link_owner_hold")
    paging = result.get("paging", {})
    if not isinstance(paging, dict):
        raise RuntimeError("facebook_preflight_paging_hold")
    return {
        "status": "API_METADATA_READABLE_NOT_IMAGE_PROOF",
        "page_id": page_id, "sample_posts_checked": len(posts),
        "more_pages_advertised": bool(paging.get("next")),
        "original_images_verified": 0,
    }


def preflight(*, config: dict | None = None,
              env: dict | None = None, live: bool = False,
              getter=platform_json_get) -> dict:
    """Never issue API reads without explicit owner, grant and token gates."""
    conf = config if config is not None else json.loads(
        CONFIG_PATH.read_text(encoding="utf-8"))
    fb = conf.get("facebook") if isinstance(conf, dict) else None
    mode = _approved_mode(fb)
    pages = fb.get("pages")
    if not isinstance(pages, list):
        raise ValueError("facebook_preflight_pages_shape_hold")
    output = {
        "status": "HOLD_NOT_APPROVED",
        "mode": mode,
        "pages_configured": len(pages),
        "pages_readable": 0, "pages_held": len(pages),
        "original_images_verified": 0,
        "smtp_sent": False, "schedule_changed": False,
        "production_activated": False, "read_only": True,
        "page_results": [],
    }
    if not live or fb.get("approved") is not True:
        return output
    if not 0 < len(pages) <= 10:
        raise ValueError("facebook_preflight_pages_required_hold")
    checked = [_fb_page_profile(page) for page in pages]
    if len({p["id"] for p in checked}) != len(checked):
        raise ValueError("facebook_preflight_duplicate_page_hold")
    if (fb.get("access_confirmed") is not True
            or (mode == "public_ppca" and fb.get("ppca_granted") is not True)):
        output["status"] = "HOLD_META_ACCESS_GRANT_REQUIRED"
        return output
    environment = env if env is not None else os.environ
    token_name = ("RASD_META_PPCA_ACCESS_TOKEN" if mode == "public_ppca"
                  else "RASD_META_PAGE_ACCESS_TOKEN")
    token = environment.get(token_name)
    if not token or len(token.strip()) < 10:
        output["status"] = "HOLD_META_TOKEN_NOT_CONFIGURED"
        return output
    statuses = []
    for page in checked:
        try:
            result = _page_samples(page["id"], page["name"], token, getter)
            statuses.append(result)
        except (RuntimeError, ValueError, TypeError):
            # Meta error detail and credentials must NEVER enter the audit.
            statuses.append({
                "status": "HOLD_META_ENDPOINT_OR_IDENTITY",
                "page_id": page["id"], "sample_posts_checked": 0,
                "original_images_verified": 0,
            })
    passed = sum(x["status"] == "API_METADATA_READABLE_NOT_IMAGE_PROOF"
                 for x in statuses)
    output.update({
        "status": ("API_METADATA_READABLE_NOT_IMAGE_PROOF"
                   if passed == len(checked)
                   else "PARTIAL_META_ACCESS_HOLD"),
        "pages_readable": passed, "pages_held": len(checked) - passed,
        "page_results": statuses,
    })
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RASD Facebook Page/PPCA access check (NO SEND)")
    parser.add_argument("--live-readonly", action="store_true",
                        help="Requires owner-approved Page IDs, Meta grant and env token")
    parser.add_argument("--out", type=Path,
                        default=Path("report-output/facebook/facebook-preflight.json"))
    args = parser.parse_args()
    protected = (Path(__file__).resolve().parent / "report-output").resolve()
    if not args.out.resolve().is_relative_to(protected):
        parser.error("audit output must stay in ignored report-output")
    result = preflight(live=args.live_readonly)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
