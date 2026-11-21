"""Inspect LIVE approved original publisher images without sending or storing.

Takes at most four distinct current ministry-relevant article candidates from
the reviewed RSS inventory, then captures only the untouched original URL
through the production image-identity code. Does not print article URLs or
sensitive HTML; no files escape the ephemeral runner.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime,timezone
from pathlib import Path

from capture_public import capture_publisher
from gate11_runner import eligible_candidates,SAFE_CAPTURE_FAILURE_CODES
from monitor import inspect

MAX_ATTEMPTS=4


def main():
    cfg=json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    inspected=inspect(cfg,now=datetime.now(timezone.utc),article_limit=200,
                      require_complete_items=True)
    candidates=eligible_candidates(inspected,cfg,
                                   datetime.now(timezone.utc),limit=80)
    sample=[]
    seen=set()
    for item in candidates:
        name=item["source"]
        if name not in seen:
            sample.append(item)
            seen.add(name)
        if len(sample)==MAX_ATTEMPTS:
            break
    with tempfile.TemporaryDirectory(prefix="rasd-real-original-qa-") as d:
        for index,item in enumerate(sample):
            source=next(x["id"] for x in cfg["feeds"]
                        if x["name"]==item["source"])
            output=Path(d)/f"sample-{index}.jpg"
            result=capture_publisher(item["url"],item["publisher"],output)
            reason=result.get("reason")
            code=reason if reason in SAFE_CAPTURE_FAILURE_CODES else (
                "ok" if result.get("ok") else "other")
            # Reject URL mismatch even when browser returned a lovely image.
            from monitor import canonical_url
            if result.get("ok") and (
                canonical_url(result.get("actual_url","")) !=
                    canonical_url(item["url"])):
                code="url_mismatch"
            verified=(result.get("ok") and code=="ok")
            print("RASD_REAL_ORIGINAL_PHOTO="+json.dumps({
                "source_id":source,
                "status":"verified" if verified else "HOLD",
                "safe_reason":code,
                "bytes":output.stat().st_size if verified else 0
            },ensure_ascii=True),flush=True)
    print("RASD_REAL_ORIGINAL_SOURCE_CANDIDATES="+str(len(candidates)))
    print("RASD_REAL_ORIGINAL_CAPTURE_ATTEMPTS="+str(len(sample)))
    print("RASD_REAL_ORIGINAL_CAPTURE_NO_MAIL_NO_ARTIFACT_UPLOAD=1")


if __name__=="__main__":
    main()
