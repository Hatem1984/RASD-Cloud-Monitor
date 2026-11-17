"""One proven publisher article capture probe. NO SEND, no artifact output.

Public original URL was in the genuine 17-Nov RASD received Word's clickable
publisher reference. It is public newsroom data; neither the private Word,
email, sender/recipient, ledger nor stored screenshot is uploaded.
"""
import json
import tempfile
from pathlib import Path

from capture_public import capture_publisher

PUBLIC_ORIGINAL = "https://almessa.gomhuriaonline.com/770296/"


def main():
    with tempfile.TemporaryDirectory(prefix="rasd-massa-real-no-send-") as folder:
        destination = Path(folder) / "original.jpg"
        outcome = capture_publisher(
            PUBLIC_ORIGINAL, "gomhuriaonline.com", destination)
        safe_reasons = {
            "visual_qa_unloaded_massa_article_lead_media",
            "visual_qa_suspicious_flat_original_lead_media",
            "original_article_image_not_loaded",
            "original_headline_not_in_article", "missing_original_headline",
            "publisher_access_refused", "publisher_article_unavailable",
            "page_content_unavailable", "original_headline_out_of_frame",
            "not_a_planning_article", "TimeoutError", "Error",
        }
        code = outcome.get("reason")
        accepted = outcome.get("ok") is True and destination.is_file()
        print(json.dumps({
            "mode": "RASD_REAL_MASSA_ORIGINAL_PAGE_PHOTO_NO_SEND",
            "capture_verified": accepted,
            "capture_hold": not accepted,
            "hold_reason": None if accepted else (
                code if code in safe_reasons else "other"),
            "screenshot_ever_published_as_artifact": False,
            "source_activated": False,
            "emails_sent": 0, "private_ledger_accessed": False,
        }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
