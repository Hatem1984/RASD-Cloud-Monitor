"""Al Masdar publisher page original screenshot qualification: research only.

This temporarily adds an exact publisher ARTICLE host inside this isolated
process; it DOES NOT add Al Masdar to production config or RSS allowlists.
No mail, no artifact upload, no fake pages, no challenge bypass.
"""
import json
import tempfile
from pathlib import Path

from capture_public import APPROVED_PUBLISHERS, capture_publisher

ARTICLE="https://www.almasdar.com/176237"
PUBLISHER="almasdar.com"


def main():
    if PUBLISHER in APPROVED_PUBLISHERS:
        raise RuntimeError("almasdar_research_must_not_claim_production_approved")
    APPROVED_PUBLISHERS[PUBLISHER]=frozenset({"www.almasdar.com"})
    try:
        with tempfile.TemporaryDirectory(prefix="rasd-almasdar-research-") as d:
            dest=Path(d)/"original.jpg"
            result=capture_publisher(ARTICLE,PUBLISHER,dest)
            safe={
                "status":"verified" if result.get("ok") else "HOLD",
                "reason":result.get("reason") if result.get("reason") in {
                    "publisher_access_refused",
                    "page_content_unavailable",
                    "original_headline_not_in_article",
                    "original_headline_out_of_frame",
                    "original_article_image_not_loaded",
                    "missing_original_headline",
                    "visual_qa_suspicious_flat_original_lead_media",
                    "visual_qa_unloaded_massa_article_lead_media",
                    "visual_qa_blank_or_low_content",
                    "screenshot_too_small",
                    "publisher_article_unavailable",
                } else ("ok" if result.get("ok") else "other"),
                "original_image_bytes":dest.stat().st_size if dest.exists() else 0,
                "source_approved":False,
                "smtp_sent":False,
            }
            print("RASD_ALMASDAR_UNAPPROVED_SCREENSHOT_RESEARCH="+json.dumps(safe),flush=True)
    finally:
        APPROVED_PUBLISHERS.pop(PUBLISHER,None)


if __name__=="__main__":
    main()
