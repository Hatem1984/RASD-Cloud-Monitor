"""Build bounded, lossless Ministry daily Word volumes from ALREADY-SENT photos.

STAGING ONLY. No SMTP, private ledger, IMAP, recipients or automatic changes
to delivery policy. Must not be wired into production sends until owner approval
of multiple attachment/message delivery and manual reconciliation policy.

The input is the verified nightly archive after exact Gmail Sent extraction.
All article identities/order and original JPEG digests are preserved. Any
overflow is a HARD HOLD before any delivery; never truncate or downsample.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from docx import Document

from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx

MAX_STORIES = 360
DEFAULT_MAX_WORD_BYTES = 7_500_000
MAX_DAILY_VOLUMES = 32
DOCUMENT_OVERHEAD_RESERVE = 750_000


def create_verified_daily_volumes(
    articles: list[dict],
    digests: list[dict],
    output: Path,
    *,
    title: str,
    start: str,
    end: str,
    max_word_bytes: int = DEFAULT_MAX_WORD_BYTES,
    max_volumes: int = MAX_DAILY_VOLUMES,
) -> list[dict]:
    """Return ordered verified volume records or raise before any mail.

    Every record contains its local Word path, source IDs, image SHA-256 and
    verified count. The caller MUST separately decide what to send and must
    obtain the owner's production distribution approval first.

    Tight size limits deliberately HOLD, even if full-sized originals would
    otherwise fit in other envelopes. Never silently drop an original.
    """
    if (not isinstance(articles, list) or not 1 <= len(articles) <= MAX_STORIES
            or not isinstance(digests, list) or len(digests) != len(articles)):
        raise ValueError("daily_volume_items_invalid")
    if (type(max_word_bytes) is not int
            or not 1_200_000 <= max_word_bytes <= 15_000_000
            or type(max_volumes) is not int or not 1 <= max_volumes <= MAX_DAILY_VOLUMES):
        raise ValueError("daily_volume_limits_invalid")
    if not all(isinstance(s, str) and s for s in (title, start, end)):
        raise ValueError("daily_volume_window_missing")
    article_ids = [item.get("id") for item in articles]
    if (len(set(article_ids)) != len(articles)
            or any(not isinstance(s, str) or
                   re.fullmatch(r"[a-z0-9]{24,64}", s) is None
                   for s in article_ids)):
        raise ValueError("daily_volume_article_ids_invalid")

    safe = []
    for item, evidence in zip(articles, digests):
        if (not isinstance(evidence, dict) or evidence.get("status") != "verified"
                or not isinstance(evidence.get("sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", evidence["sha256"]) is None):
            raise RuntimeError("daily_volume_original_proof_missing")
        path = Path(item["evidence_image_path"])
        if not path.is_file() or path.stat().st_size < 8000:
            raise RuntimeError("daily_volume_original_image_missing")
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence["sha256"]:
            raise RuntimeError("daily_volume_original_image_digest_hold")
        safe.append((item, evidence, path.stat().st_size))

    # Deterministic first pass, leaving room for Word XML, relationships and
    # cover. Actual file size and every embedded photo are checked separately.
    budget = max_word_bytes - DOCUMENT_OVERHEAD_RESERVE
    groups = []
    current = []
    size = 0
    for item in safe:
        predicted = item[2] + 12_000
        if predicted > budget:
            raise RuntimeError("daily_volume_single_original_too_large_hold")
        if current and size + predicted > budget:
            groups.append(current)
            current = []
            size = 0
        current.append(item)
        size += predicted
    if current:
        groups.append(current)

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Prove every document BEFORE exposing any final-volume name. Renders
    # that exceed a limit are split, never compressed or dropped.
    while True:
        if len(groups) > max_volumes:
            raise RuntimeError("daily_volume_count_capacity_hold")
        too_large = -1
        with tempfile.TemporaryDirectory(prefix="rasd-volume-check-", dir=output) as tmp:
            probe = Path(tmp)
            for index, group in enumerate(groups, start=1):
                report = _report(group, title, start, end, index, len(groups))
                filename = probe / ("probe-" + str(index) + ".docx")
                render_docx(report, filename)
                if filename.stat().st_size > max_word_bytes:
                    too_large = index - 1
                    break
                if len(Document(filename).inline_shapes) != len(group):
                    raise RuntimeError("daily_volume_missing_originals_hold")
                if not word_images_match_capture_digests(
                        filename, [row[1] for row in group]):
                    raise RuntimeError("daily_volume_mismatched_originals_hold")
            if too_large == -1:
                staged = []
                for index, group in enumerate(groups, start=1):
                    source = probe / ("probe-" + str(index) + ".docx")
                    dest = output / (
                        "RASD-Daily-Originals-Part-" + f"{index:02d}" +
                        "-of-" + f"{len(groups):02d}" + ".docx")
                    if dest.exists():
                        raise RuntimeError("daily_volume_destination_exists_hold")
                    staged.append((source, dest, group))
                committed = []
                try:
                    for source, dest, group in staged:
                        # Same filesystem: atomic rename after all validation.
                        os.replace(source, dest)
                        committed.append(dest)
                except OSError:
                    for path in committed:
                        path.unlink(missing_ok=True)
                    raise RuntimeError("daily_volume_atomic_publish_hold") from None
                result = [
                    {"path": dest, "part": i, "parts": len(groups),
                     "article_ids": [x[0]["id"] for x in group],
                     "sha256": [x[1]["sha256"] for x in group],
                     "count": len(group),
                     "bytes": dest.stat().st_size}
                    for i, (src, dest, group) in enumerate(staged, start=1)]
                if ([key for vol in result for key in vol["article_ids"]]
                        != article_ids):
                    for vol in result:
                        vol["path"].unlink(missing_ok=True)
                    raise RuntimeError("daily_volume_incomplete_coverage_hold")
                return result
        oversized = groups[too_large]
        if len(oversized) < 2:
            raise RuntimeError("daily_volume_single_rendered_original_too_large_hold")
        middle = len(oversized) // 2
        groups[too_large:too_large + 1] = [
            oversized[:middle], oversized[middle:]]


def _report(group: list, title: str, start: str, end: str,
            part: int, parts: int) -> dict:
    return {
        "title": title + f" | الجزء {part} من {parts}",
        "volume_label": f"الجزء {part} من {parts}",
        "display_window_start": start,
        "display_window_end": end,
        "ministry_media_grid": True,
        "coverage": "CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS",
        "verified_links": len(group),
        "articles": [row[0] for row in group],
        "sources": [],
        "limitations": (
            f"هذا الجزء {part} من {parts} من التقرير اليومي المجمع. "
            "الصور مأخوذة من ملفات Word المرسلة سابقًا، دون تعديل أو استبدال. "
            "لا يدل عدد الأخبار المرسلة على اكتمال كل أخبار السوق."
        ),
    }
