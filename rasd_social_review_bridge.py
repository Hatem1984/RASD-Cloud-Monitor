"""Connect official social metadata to RASD four Word REVIEW reports.

An API post without an independently checked original-post screenshot is
HOLD, not reportable. No SMTP, CAS, schedule, platform login or cookie use.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from rasd_social_official_intake import collect_social
from rasd_social_original_capture import capture_original_post
from rasd_four_reports_review import validate_item

MAX_SOCIAL_REVIEW_ITEMS = 100
PLATFORM_NAMES = {"facebook": "Facebook", "x": "X",
                  "instagram": "Instagram", "linkedin": "LinkedIn"}


def approved_social_probe(*, now, evidence_root: Path,
                          collect=None, screenshot=None,
                          capture_originals: bool = False,
                          config: dict | None = None,
                          environment: dict | None = None) -> tuple[list[dict], list[dict], dict]:
    """Approved API discovery + original visible post capture, NO SEND.

    Screenshots run only when both owner-controlled configuration and runtime
    gates are true. A mock screenshot in tests is not source authenticity.
    """
    env = environment if environment is not None else os.environ
    gather = collect or collect_social
    original = screenshot or capture_original_post
    if config is None:
        import json
        from rasd_social_official_intake import CONFIG_PATH
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    response = gather(live=True, now=now, config=config, environment=env)
    candidates = response.get("post_candidates")
    api_sources = response.get("sources")
    if (not isinstance(candidates, list)
            or len(candidates) > MAX_SOCIAL_REVIEW_ITEMS
            or not isinstance(api_sources, dict)
            or set(api_sources) != set(PLATFORM_NAMES)):
        raise RuntimeError("social_api_review_shape_hold")
    allowed_capture = (
        capture_originals is True and
        config.get("original_post_browser_capture_approved") is True and
        env.get("RASD_SOCIAL_ORIGINAL_CAPTURE_APPROVED") == "yes")
    accepted, errors = [], {name: 0 for name in PLATFORM_NAMES}
    seen = set()
    for candidate in candidates:
        if (not isinstance(candidate, dict)
                or candidate.get("platform") not in ("facebook", "x", "instagram")
                or candidate.get("evidence_status") !=
                   "HOLD_ORIGINAL_POST_SCREENSHOT"):
            raise RuntimeError("social_candidate_provenance_hold")
        platform = candidate["platform"]
        ident = candidate.get("platform_post_id")
        if not isinstance(ident, str):
            raise RuntimeError("social_candidate_identity_hold")
        pair = (platform, ident)
        if pair in seen:
            raise RuntimeError("social_cross_page_duplicate_hold")
        seen.add(pair)
        if not allowed_capture:
            errors[platform] += 1
            continue
        output = evidence_root / ("social-" +
            hashlib.sha256((platform + ":" + ident).encode()).hexdigest() + ".png")
        try:
            proof = original(candidate, output, owner_authorized=True)
            if (not isinstance(proof, dict)
                    or proof.get("status") != "verified"
                    or proof.get("url") != candidate.get("url")
                    or proof.get("platform_post_id") != ident
                    or proof.get("method") !=
                       "authorized_platform_original_capture"
                    or not isinstance(proof.get("sha256"), str)
                    or not output.is_file()
                    or hashlib.sha256(output.read_bytes()).hexdigest()
                       != proof["sha256"]):
                errors[platform] += 1
                output.unlink(missing_ok=True)
                continue
            item = {
                **candidate,
                "image_path": str(output),
                "image_sha256": proof["sha256"],
                "capture_receipt": proof,
            }
            validate_item(item, "social", evidence_root, set(), cutoff=now)
            accepted.append(item)
        except (ValueError, RuntimeError, OSError):
            output.unlink(missing_ok=True)
            errors[platform] += 1
    statuses = []
    for platform in PLATFORM_NAMES:
        source = api_sources.get(platform)
        if (not isinstance(source, dict) or
                source.get("status") not in
                {"ok", "hold", "unauthorized", "not_configured"}):
            raise RuntimeError("social_api_source_status_hold")
        status = source["status"]
        if errors[platform] or (status == "ok" and
                                source.get("matched_count", 0) and
                                not accepted):
            status = "hold"
        statuses.append({
            "channel": "social", "name": PLATFORM_NAMES[platform],
            "status": status,
        })
    info = {
        "api_candidates": len(candidates),
        "independent_original_captures_verified": len(accepted),
        "original_capture_hold": sum(errors.values()),
        "api_source_statuses": {s["name"]: s["status"] for s in statuses},
        "capture_authorized": allowed_capture,
        "social_archive_receipts_verified": False,
        "smtp_sent": False,
    }
    return accepted, statuses, info
