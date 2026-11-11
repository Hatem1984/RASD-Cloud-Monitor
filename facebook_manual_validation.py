"""Review-only Facebook URL identity and local cross-report duplication checks.

No network, no Meta cookies or credentials. The local registry stores only
SHA-256 identifiers; it does not establish authenticity of any Facebook post.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

INDEX_NAME = ".rasd-facebook-manual-index.json"
MAX_INDEX_BYTES = 4_000_000
_ALLOWED_HOSTS = {"facebook.com", "www.facebook.com",
                  "m.facebook.com", "web.facebook.com"}
_SENSITIVE_KEYS = ("access_token", "appsecret_proof", "token",
                   "password", "cookie", "session", "auth_token", "code")


def post_identity(raw: str) -> str | None:
    """Return same identity for m/www and equivalent direct/styled post links.

    Unresolved Facebook short-link aliases and different Page usernames may
    still refer to the same post; content-level dedup requires human review.
    """
    if not isinstance(raw, str) or len(raw) > 1600:
        return None
    try:
        uri = urlsplit(raw)
        if (uri.scheme != "https" or uri.hostname not in _ALLOWED_HOSTS
                or uri.port not in (None, 443)
                or uri.username is not None or uri.password is not None
                or uri.fragment):
            return None
        query = parse_qs(uri.query, keep_blank_values=True)
        if any(any(s in key.casefold() for s in _SENSITIVE_KEYS)
               for key in query):
            return None
        parts = [p for p in uri.path.strip("/").split("/") if p]
        if not parts:
            return None
        if parts[-1] in ("story.php", "permalink.php"):
            owner, story = query.get("id", [""])[0], query.get(
                "story_fbid", [""])[0]
            if (re.fullmatch(r"\d{3,25}", owner)
                    and re.fullmatch(r"(?:\d{3,40}|pfbid[A-Za-z0-9]+)",
                                     story)):
                return f"post:{owner}:{story}"
            return None
        if len(parts) >= 2 and parts[-2] == "posts":
            post = parts[-1]
            if not re.fullmatch(r"(?:\d{1,40}|pfbid[A-Za-z0-9]+)", post):
                return None
            owner = parts[-3].casefold() if len(parts) >= 3 else ""
            return f"post:{owner}:{post}"
        if len(parts) >= 2 and parts[-2] in ("reel", "videos"):
            return f"media:{parts[-2]}:{parts[-1]}"
        if parts == ["watch"] and re.fullmatch(
                r"\d{1,40}", query.get("v", [""])[0]):
            return "media:watch:" + query["v"][0]
        if len(parts) == 3 and parts[:2] == ["share", "p"]:
            return "share-post:" + parts[2]
        return None
    except (ValueError, TypeError):
        return None


def identity_digest(raw: str) -> str:
    identity = post_identity(raw)
    if identity is None:
        raise ValueError("facebook_permalink_hold")
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def parse_operator_post_time(value: str, *, now: datetime) -> datetime:
    """Require a timezone-aware timestamp and reject future-dated claims."""
    if (not isinstance(value, str) or len(value) > 35
            or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}",
                value)):
        raise ValueError("facebook_post_date_hold")
    try:
        stamp = datetime.fromisoformat(value)
        if (stamp.tzinfo is None or stamp.utcoffset() is None
                or abs(stamp.utcoffset().total_seconds()) > 14 * 3600
                or stamp > now.astimezone(timezone.utc)):
            raise ValueError
        return stamp
    except (ValueError, OverflowError):
        raise ValueError("facebook_post_date_hold") from None


def read_local_index(output_dir: Path) -> set[str]:
    path = output_dir / INDEX_NAME
    if not path.is_file():
        return set()
    if path.stat().st_size > MAX_INDEX_BYTES:
        raise ValueError("facebook_index_unreadable_hold")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        entries = obj["ids"]
        if (obj.get("version") != 1 or not isinstance(entries, list)
                or not all(isinstance(x, str)
                           and re.fullmatch(r"[0-9a-f]{64}", x)
                           for x in entries)
                or len(set(entries)) != len(entries)):
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError("facebook_index_unreadable_hold") from None
    return set(entries)


def write_local_index(output_dir: Path, ids: set[str]) -> None:
    """Atomic local review bookkeeping, not a production/Ministry CAS ledger."""
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(
        {"version": 1, "ids": sorted(ids)}, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_INDEX_BYTES:
        raise ValueError("facebook_index_capacity_hold")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=output_dir, prefix=".rasd-fb-index-",
                suffix=".tmp", delete=False) as stream:
            temp = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, output_dir / INDEX_NAME)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
