"""Verify and extract exact publisher JPEGs from SENT hourly Ministry grid Word.

Read-only and fail-closed: every image must be in the correct numbered
publisher card with its original headline, publication date, and exact URL.
No screenshot or replacement image is created by this parser.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from capture_public import image_quality
from rasd_ministry_visual_layout import SOURCE_NAMES

REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
COVER_TYPES = ("تقرير المتابعة الساعية", "تقرير المتابعة النصف ساعية")


def is_interval_ministry_grid(document) -> bool:
    if not document.tables:
        return False
    cover = document.tables[0].cell(0, 0).text
    return any(label in cover for label in COVER_TYPES)


def extract_sent_grid_originals(document, expected: list[dict],
                                output: Path) -> list[tuple[dict, str, str]]:
    if not expected or len(expected) > 15 or not is_interval_ministry_grid(document):
        raise RuntimeError("daily_sent_grid_cover_identity_hold")
    if len(document.tables) < 3 or len(document.inline_shapes) != len(expected):
        raise RuntimeError("daily_sent_grid_image_count_hold")
    recorded = []
    seen_cells = set()
    for table in document.tables[2:]:
        for row in table.rows:
            for cell in row.cells:
                if id(cell._tc) in seen_cells:
                    continue
                seen_cells.add(id(cell._tc))
                paragraphs = cell.paragraphs
                if not paragraphs:
                    continue
                original_title = paragraphs[0].text.strip()
                # An intentionally empty 2-column grid cell is allowed.
                # A numbered publisher card WITHOUT a picture must HOLD.
                match = re.fullmatch(r"(\d{2,3})\s+\|\s+(.+)", original_title)
                images = cell._tc.xpath(".//a:blip")
                if not match and not images:
                    continue
                if not match or len(images) != 1 or len(paragraphs) < 4:
                    raise RuntimeError("daily_sent_grid_card_identity_hold")
                index = int(match.group(1))
                if index != len(recorded) + 1 or index > len(expected):
                    raise RuntimeError("daily_sent_grid_card_order_hold")
                item = expected[index - 1]
                outlet = SOURCE_NAMES.get(item["source"], item["source"])
                if (match.group(2) != outlet
                        or paragraphs[1].text.strip() != item["headline"]):
                    raise RuntimeError("daily_sent_grid_article_identity_hold")
                dated = item.get("published_display_cairo") or item.get("published_at_cairo")
                if not isinstance(dated, str) or not dated or not any(
                        p.text.strip() == "النشر: " + dated for p in paragraphs):
                    raise RuntimeError("daily_sent_grid_publication_date_hold")
                hyperlinks = cell._tc.xpath(".//w:hyperlink")
                if len(hyperlinks) != 1:
                    raise RuntimeError("daily_sent_grid_original_url_hold")
                rel_id = hyperlinks[0].get(REL + "id")
                relation = document.part.rels.get(rel_id)
                if (relation is None
                        or not relation.reltype.endswith("/hyperlink")
                        or not relation.is_external
                        or relation.target_ref != item["url"]):
                    raise RuntimeError("daily_sent_grid_original_url_hold")
                image_id = images[0].get(REL + "embed")
                if image_id not in document.part.related_parts:
                    raise RuntimeError("daily_sent_grid_image_relationship_hold")
                blob = document.part.related_parts[image_id].blob
                if len(blob) < 8000 or not blob.startswith(b"\xff\xd8"):
                    raise RuntimeError("daily_sent_grid_original_jpeg_hold")
                destination = output / ("daily-original-" + item["id"] + ".jpg")
                destination.write_bytes(blob)
                if not image_quality(destination)["accepted"]:
                    raise RuntimeError("daily_sent_grid_original_visual_hold")
                recorded.append((
                    item, str(destination), hashlib.sha256(blob).hexdigest()))
    if len(recorded) != len(expected):
        raise RuntimeError("daily_sent_grid_missing_originals_hold")
    return recorded
