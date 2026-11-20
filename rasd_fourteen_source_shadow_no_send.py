"""Original 14-profile newsroom shadow audit; zero SMTP or private state.

Run the exact production strict RSS/date/title matcher, but only read public
publisher origins. Never automatically activate or deliver a candidate.
A real publisher screenshot is attempted only on a bounded Al Nahar match.
"""
from __future__ import annotations
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cloud_proof_report import proof_capture
from scheduled_rasd import discover_interval_news


def main():
    now = datetime.now(timezone.utc)
    config = json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    if len(config["feeds"]) != 14 or len(config["keywords"]) != 29:
        raise RuntimeError("staged_newsroom_inventory_not_fourteen_hold")
    source_rows = []
    stories = discover_interval_news(
        config, now, allow_degraded=True, source_records=source_rows)
    matched_by_name = {}
    for item in stories:
        matched_by_name[item["source"]] = matched_by_name.get(item["source"], 0) + 1
    active_by_id = {x["id"]: x for x in config["feeds"]}
    print("RASD_SHADOW_SOURCES_CONFIGURED=14")
    print("RASD_SHADOW_STRICT_RSS_HEALTHY=" +
          str(sum(x["status"]=="ok" for x in source_rows)))
    print("RASD_SHADOW_STRICT_RSS_MATCHES_LAST_72H=" + str(len(stories)))
    for status in source_rows:
        count = matched_by_name.get(
            active_by_id[status["feed_id"]]["name"], 0)
        print("RASD_SHADOW_SOURCE_ID=" + status["feed_id"] +
              " STATUS=" + status["status"] +
              " MATCHES_72H=" + str(count) +
              (" HOLD_REASON=" + status.get("failure_code", "other")
               if status["status"] == "failed" else ""))
    extra = active_by_id["alnaharegypt"]
    matches = [item for item in stories if item["source"] == extra["name"]][:2]
    results=[]
    with tempfile.TemporaryDirectory(prefix="rasd-14-shadow-") as temp:
        for i, story in enumerate(matches):
            img = Path(temp) / ("extra-original-"+str(i)+".jpg")
            proof = proof_capture(story, config["feeds"], img)
            results.append(proof.get("status") == "verified")
    print("RASD_SHADOW_NEW_SOURCE_ALNAHAR_PHOTOS_ATTEMPTED=" + str(len(matches)))
    print("RASD_SHADOW_NEW_SOURCE_ALNAHAR_PHOTOS_VERIFIED=" + str(sum(results)))
    print("RASD_SHADOW_SEND=0 PRIVATE_LEDGER=0 SOURCE_ACTIVATION=0")


if __name__=="__main__":
    main()
