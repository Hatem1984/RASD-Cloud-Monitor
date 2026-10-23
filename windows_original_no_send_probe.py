"""Read-only GitHub-hosted Windows proof of genuine Hapi original-page JPEG/Word.

Zero secrets, mail, private ledger, uploads, source changes or browser bypass.
Only print allowlisted status and counts. Temporary JPEG/DOCX are discarded.
"""
from __future__ import annotations
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scheduled_rasd import discover_interval_news, prepare_word


def main() -> None:
    config = json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    now = datetime.now(timezone.utc)
    health = []
    stories = discover_interval_news(
        config, now, allow_degraded=True, source_records=health)
    candidates = [row for row in stories
                  if row["source"] == "Hapi native news RSS"
                  and row["url"].startswith("https://hapijournal.com/")]
    if not candidates:
        print(json.dumps({
            "mode": "windows_cloud_no_send",
            "status": "HOLD_NO_CURRENT_APPROVED_HAPI_MATCH",
            "eligible": 0, "verified": 0,
            "email_sent": False, "private_state_used": False,
        }), flush=True)
        return
    with tempfile.TemporaryDirectory(prefix="rasd-win-original-") as temp:
        target = Path(temp)
        try:
            word, proof = prepare_word(
                candidates[:1], config, target,
                title="RASD Windows-origin real-page experimental proof ONLY",
                start=now.isoformat(), end=now.isoformat())
        except RuntimeError as exc:
            reason = str(exc)
            status = (
                "HOLD_ORIGINAL_PUBLISHER_CAPTURE"
                if reason == "publisher_screenshot_hold" else
                "HOLD_OTHER_INTEGRITY_FAILURE"
            )
            print(json.dumps({
                "mode": "windows_cloud_no_send",
                "status": status,
                "eligible": len(candidates), "verified": 0,
                "email_sent": False, "private_state_used": False,
            }), flush=True)
            if status == "HOLD_OTHER_INTEGRITY_FAILURE":
                raise SystemExit(2) from None
            return
        if (len(proof) != 1 or
                proof[0]["status"] != "verified" or
                not word.is_file() or word.stat().st_size < 3000):
            raise SystemExit("RASD_HOLD_PROOF_INTEGRITY")
        print(json.dumps({
            "mode": "windows_cloud_no_send",
            "status": "ONE_ORIGINAL_PUBLISHER_WORD_VERIFIED",
            "eligible": len(candidates), "verified": 1,
            "word_bytes": word.stat().st_size,
            "email_sent": False, "private_state_used": False,
        }), flush=True)


if __name__ == "__main__":
    main()
