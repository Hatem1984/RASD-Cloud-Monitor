"""Separate manual web RSS PREVIEW; no email, private state or photo proof."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from daily_report import gather, render_docx


def run_manual_web(output_dir: Path, *, gather_fn=gather,
                   config_file: Path | None = None,
                   now: datetime | None = None) -> dict:
    config_path = config_file or Path(__file__).with_name(
        "sources_newsroom_active.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    report = gather_fn(config, now=now)
    report["title"] = "رصد | مسودة بحث الويب — دون صور ناشر موثقة"
    report["preview_only"] = True
    report["manual_web_mode"] = True
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S-%f")
    output = output_dir / ("RASD-Web-Preview-" + stamp + ".docx")
    render_docx(report, output)
    return {"status": "MANUAL_WEB_PREVIEW_ONLY", "word": str(output),
            "items": len(report["articles"]),
            "sources_checked": len(report["sources"]),
            "sources_failed": sum(s["status"] != "ok" for s in report["sources"]),
            "email_sent": False, "private_ledger_used": False}


if __name__ == "__main__":
    try:
        print(json.dumps(run_manual_web(Path("report-output/web")),
                         ensure_ascii=False))
    except Exception:
        print(json.dumps({"status": "MANUAL_WEB_PREVIEW_HOLD",
                          "email_sent": False}))
        raise SystemExit(1) from None
