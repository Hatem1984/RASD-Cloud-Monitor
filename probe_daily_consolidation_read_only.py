"""Production-identical, owner-only, READ-ONLY assembly of this day's daily Word.

No SMTP operation, no private CAS writes, no public files or personal metadata.
"""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from daily_report import CAIRO
from daily_sent_consolidator import consolidate_sent_words
from scheduled_rasd import protected_credentials, news_for_rollup


def main():
    sender, recipient, password, ledger = protected_credentials()
    state, _ = ledger.read()
    target_day = datetime.now(timezone.utc).astimezone(CAIRO).date().isoformat()
    config = json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    stories = news_for_rollup(state, target_day, config)
    if not stories:
        print("RASD_DAILY_LIVE_READONLY=HOLD_NO_ACCEPTED_STORIES EMAIL_SENT=0")
        raise SystemExit(2)
    with TemporaryDirectory(prefix="rasd-one-daily-preview-") as dirpath:
        word, receipts = consolidate_sent_words(
            stories, state, Path(dirpath), sender=sender, recipient=recipient,
            app_password=password,
            title="رصد | مراجعة دمج التقارير المرسلة — بدون إرسال",
            start="22:00 القاهرة يوم أمس",
            end=target_day + " 22:00 القاهرة",
            config=config)
        from docx import Document
        inside = Document(word)
        if (len(inside.inline_shapes) != len(stories)
                or len(receipts) != len(stories)):
            raise SystemExit("RASD_DAILY_LIVE_READONLY=HOLD_IMAGE_COUNT")
        print("RASD_DAILY_LIVE_READONLY=VERIFIED"
              f" UNIQUE_ACCEPTED_NEWS={len(stories)}"
              f" ORIGINAL_PHOTOS_IN_ONE_WORD={len(inside.inline_shapes)}"
              f" WORD_BYTES={word.stat().st_size}"
              " EMAIL_SENT=0 LEDGER_WRITES=0",
              flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("RASD_DAILY_LIVE_READONLY=HOLD"
              f" TYPE={type(exc).__name__}"
              " EMAIL_SENT=0 LEDGER_WRITES=0", flush=True)
        raise SystemExit(2) from None
